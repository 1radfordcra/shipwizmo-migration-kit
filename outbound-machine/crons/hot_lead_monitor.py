#!/usr/bin/env python3
"""
hot_lead_monitor.py — Broad Reach B2B Outbound Machine
Hot Lead Monitor (Hourly)

Schedule: Every hour Mon–Fri, 8 AM–6 PM EST
Cron expression: 0 * 13-23 * * 1-5   (UTC; 13:00–23:00 UTC = 8 AM–6 PM EST)
Original cron ID: ce4786ef (Perplexity Computer scheduler)
Azure Function: HotLeadMonitor

Purpose:
    Monitors HubSpot every hour during business hours for genuine prospect
    replies and engagement signals. When a real response is detected, sends
    an immediate alert email to Craig so he can follow up while the prospect
    is still warm.

    "Hot lead" definition: A BR contact (br_source=apollo) that has either:
    - Replied to an outbound email (hs_email_last_reply_date in last 75 min)
    - Had their notes updated with reply content (notes_last_updated in last 75 min)

    The 75-minute lookback (vs. 60 minutes) provides a generous overlap buffer
    to catch leads that came in during the previous run window even if a run
    runs slightly late.

    False-positive prevention:
    - Contacts flagged as blocked/removed/opted-out are excluded (their records
      may be updated by automation, which would otherwise trigger spurious alerts)
    - System-generated engagement events (e.g., HubSpot sequence touches, Expandi
      LinkedIn activity reflected back) are filtered out

Author: Craig Radford <craig@brdrch.com>
Original platform: Perplexity Computer scheduled task (cron ID: ce4786ef)
Migration target: Azure Functions / standalone cron
"""

import os
import sys
import json
import time
import logging
import smtplib
import requests
from datetime import datetime, timedelta, timezone
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ─── Load .env if running locally ───────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ─── Logging ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("hot_lead_monitor")

# ─── Configuration ────────────────────────────────────────────────────────────
HUBSPOT_PAT = os.environ.get("HUBSPOT_PAT", "")
GMAIL_SENDER = os.environ.get("GMAIL_SENDER", "craig@brdrch.com")
ALERT_TO_EMAIL = os.environ.get("ALERT_TO_EMAIL", "craig@brdrch.com")
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", GMAIL_SENDER)
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")

# HubSpot API base
HS_BASE = "https://api.hubapi.com"

# State files (local disk; swap for Azure Blob Storage in production)
WORKSPACE = Path(os.environ.get("WORKSPACE_DIR", "/home/user/workspace"))
SEEN_CONTACTS_PATH = WORKSPACE / "hot_lead_seen_contacts.json"
HOT_LEAD_LOG_PATH = WORKSPACE / "hot_lead_monitor_log.json"

# Lookback window in minutes. Use 75 to overlap slightly between hourly runs
# and avoid missing leads if a run executes a few minutes late.
LOOKBACK_MINUTES = 75

# Outcome values that indicate a contact is permanently excluded from outreach.
# If a contact has one of these outcomes, their record may be updated by
# automation even after removal — we don't want false alerts.
EXCLUDED_OUTCOMES = {
    "blocked_manual",
    "removed_manual",
    "bounced",
    "opted_out",
    "opted_out_unsubscribed",
}

# System-generated note prefixes that are NOT genuine replies.
# HubSpot automation and Expandi integrations write notes with these prefixes.
SYSTEM_NOTE_PREFIXES = [
    "[EXPANDI]",
    "[AUTO]",
    "[AUTOMATION]",
    "[SEQ]",
    "[SEQUENCE]",
    "Enrolled in sequence",
    "Sequence step",
    "Email opened",
    "Link clicked",
    "[BR-AUTO]",
]


# ═════════════════════════════════════════════════════════════════════════════
# HubSpot API helpers
# ═════════════════════════════════════════════════════════════════════════════

def hs_headers() -> dict:
    """Return authorization headers for HubSpot API requests."""
    return {
        "Authorization": f"Bearer {HUBSPOT_PAT}",
        "Content-Type": "application/json",
    }


def hs_post(path: str, body: dict) -> dict:
    """POST to HubSpot API."""
    url = f"{HS_BASE}{path}"
    resp = requests.post(url, headers=hs_headers(), json=body, timeout=20)
    resp.raise_for_status()
    return resp.json()


def hs_get(path: str, params: dict = None) -> dict:
    """GET from HubSpot API."""
    url = f"{HS_BASE}{path}"
    resp = requests.get(url, headers=hs_headers(), params=params, timeout=20)
    resp.raise_for_status()
    return resp.json()


def ms_timestamp_to_datetime(ms_str: str) -> datetime | None:
    """
    Convert a HubSpot millisecond-epoch timestamp string to a UTC datetime.
    HubSpot stores most datetime properties as milliseconds since epoch.
    Returns None if the value is empty or unparseable.
    """
    if not ms_str:
        return None
    try:
        ms = int(ms_str)
        return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
    except (ValueError, TypeError):
        return None


def get_contact_notes(contact_id: str) -> list[dict]:
    """
    Fetch the most recent notes (engagements of type NOTE) for a contact.

    HubSpot Engagements API: GET /crm/v3/objects/notes
    We filter by associated contact and look at the body text.

    Returns a list of note dicts with 'body' and 'timestamp' keys.
    """
    try:
        resp = hs_get(
            f"/crm/v3/objects/notes",
            params={
                "associations.contact": contact_id,
                "properties": "hs_note_body,hs_timestamp,hs_created_by_user_id",
                "limit": 5,
                "sort": "-hs_timestamp",
            },
        )
        notes = []
        for n in resp.get("results", []):
            props = n.get("properties", {})
            notes.append({
                "body": props.get("hs_note_body", ""),
                "timestamp": ms_timestamp_to_datetime(props.get("hs_timestamp")),
                "created_by": props.get("hs_created_by_user_id", ""),
            })
        return notes
    except Exception as e:
        log.debug("Could not fetch notes for contact %s: %s", contact_id, e)
        return []


# ═════════════════════════════════════════════════════════════════════════════
# Seen-contacts state management
# ═════════════════════════════════════════════════════════════════════════════

def load_seen_contacts() -> set:
    """
    Load the set of contact IDs that have already triggered an alert.

    This prevents duplicate alerts when the same hot lead is detected in
    consecutive hourly runs (before Craig has had a chance to respond and
    update the contact's status in HubSpot).

    State persists in hot_lead_seen_contacts.json (local disk).
    In Azure Functions, replace with an Azure Blob Storage read.
    """
    if not SEEN_CONTACTS_PATH.exists():
        return set()
    try:
        data = json.loads(SEEN_CONTACTS_PATH.read_text())
        # Format: {"contact_id": "ISO_timestamp_when_seen"}
        # Expire entries older than 48 hours so the file doesn't grow unbounded
        cutoff = datetime.now(timezone.utc) - timedelta(hours=48)
        fresh = {
            cid: ts
            for cid, ts in data.items()
            if datetime.fromisoformat(ts) > cutoff
        }
        return set(fresh.keys())
    except Exception:
        return set()


def save_seen_contacts(seen: set) -> None:
    """
    Persist the seen-contacts state. Called after each alert is sent.
    Stores contact_id → ISO timestamp of when the alert was fired.
    """
    # Load existing to merge (preserving timestamps for unexpired entries)
    existing = {}
    if SEEN_CONTACTS_PATH.exists():
        try:
            existing = json.loads(SEEN_CONTACTS_PATH.read_text())
        except Exception:
            pass

    now_iso = datetime.now(timezone.utc).isoformat()
    for cid in seen:
        if cid not in existing:
            existing[cid] = now_iso

    # Expire entries older than 48 hours
    cutoff = datetime.now(timezone.utc) - timedelta(hours=48)
    existing = {
        cid: ts
        for cid, ts in existing.items()
        if datetime.fromisoformat(ts) > cutoff
    }
    SEEN_CONTACTS_PATH.write_text(json.dumps(existing, indent=2))


# ═════════════════════════════════════════════════════════════════════════════
# Signal detection
# ═════════════════════════════════════════════════════════════════════════════

def is_system_generated_note(note_body: str) -> bool:
    """
    Detect whether a note was written by automation rather than by the prospect.

    Automation systems (HubSpot workflows, Expandi integration, BR scripts)
    write structured notes with recognizable prefixes. We don't want to alert
    Craig on these — only on genuine prospect-written responses.
    """
    if not note_body:
        return True  # Empty note = system artifact
    for prefix in SYSTEM_NOTE_PREFIXES:
        if note_body.strip().startswith(prefix):
            return True
    return False


def check_for_hot_leads() -> dict:
    """
    Main logic: query HubSpot for BR contacts with recent reply signals,
    filter out noise, and send alerts for genuine hot leads.

    Returns a run summary dict logged to hot_lead_monitor_log.json.
    """
    run_start = datetime.now(timezone.utc)
    run_summary = {
        "run_time": run_start.isoformat(),
        "contacts_checked": 0,
        "hot_leads_found": 0,
        "alerts_sent": 0,
        "skipped_seen": 0,
        "skipped_excluded": 0,
        "skipped_system_noise": 0,
        "error": None,
    }

    log.info("Hot Lead Monitor — %s", run_start.strftime("%Y-%m-%d %H:%M UTC"))

    # Compute the lookback cutoff as a millisecond epoch timestamp
    # (HubSpot datetime filters use millisecond epoch values)
    cutoff_dt = run_start - timedelta(minutes=LOOKBACK_MINUTES)
    cutoff_ms = str(int(cutoff_dt.timestamp() * 1000))

    # Load seen-contacts state to skip already-alerted leads
    seen_contacts = load_seen_contacts()
    newly_seen = set()

    # ──────────────────────────────────────────────────────────────────────
    # Query 1: Contacts with a recent EMAIL REPLY
    # hs_email_last_reply_date is set by HubSpot when a contact replies to
    # a tracked email sent via HubSpot.
    # ──────────────────────────────────────────────────────────────────────
    reply_contacts = []
    try:
        results = hs_post("/crm/v3/objects/contacts/search", {
            "filterGroups": [
                {
                    "filters": [
                        {"propertyName": "br_source", "operator": "EQ", "value": "apollo"},
                        {"propertyName": "hs_email_last_reply_date", "operator": "GTE", "value": cutoff_ms},
                    ]
                }
            ],
            "properties": [
                "firstname", "lastname", "email", "company", "jobtitle",
                "hs_email_last_reply_date", "notes_last_updated",
                "br_last_sequence_outcome", "br_sequence_assigned",
                "br_icp_score", "hs_linkedin_url", "lifecyclestage",
            ],
            "limit": 50,
        })
        reply_contacts = results.get("results", [])
        log.info("Query 1 (email replies): %d contacts", len(reply_contacts))
    except Exception as e:
        log.error("Query 1 failed: %s", e)
        run_summary["error"] = str(e)

    # ──────────────────────────────────────────────────────────────────────
    # Query 2: Contacts with recent NOTE activity
    # notes_last_updated is set when any note is added to the contact record.
    # This catches replies that came in via other channels (LinkedIn DM
    # synced back, manual note from Craig, Expandi response notification).
    # ──────────────────────────────────────────────────────────────────────
    note_contacts = []
    try:
        results = hs_post("/crm/v3/objects/contacts/search", {
            "filterGroups": [
                {
                    "filters": [
                        {"propertyName": "br_source", "operator": "EQ", "value": "apollo"},
                        {"propertyName": "notes_last_updated", "operator": "GTE", "value": cutoff_ms},
                    ]
                }
            ],
            "properties": [
                "firstname", "lastname", "email", "company", "jobtitle",
                "hs_email_last_reply_date", "notes_last_updated",
                "br_last_sequence_outcome", "br_sequence_assigned",
                "br_icp_score", "hs_linkedin_url", "lifecyclestage",
            ],
            "limit": 50,
        })
        note_contacts = results.get("results", [])
        log.info("Query 2 (notes updated): %d contacts", len(note_contacts))
    except Exception as e:
        log.error("Query 2 failed: %s", e)

    # Merge and deduplicate
    all_contacts = {c["id"]: c for c in reply_contacts + note_contacts}.values()
    run_summary["contacts_checked"] = len(list(all_contacts))

    hot_leads = []

    for contact in all_contacts:
        props = contact.get("properties", {})
        cid = contact.get("id")

        # ── Filter: Already alerted ──
        if cid in seen_contacts:
            run_summary["skipped_seen"] += 1
            continue

        # ── Filter: Excluded/blocked/opted-out ──
        # These contacts may have system-written notes from the exclusion
        # workflow itself. Skip them to prevent false alarms.
        outcome = (props.get("br_last_sequence_outcome") or "").lower()
        if outcome in EXCLUDED_OUTCOMES:
            run_summary["skipped_excluded"] += 1
            log.debug("Contact %s has excluded outcome '%s' — skip", cid, outcome)
            continue

        # ── Validate: Determine WHICH signal triggered ──
        signal_type = None

        # Check email reply signal
        email_reply_ms = props.get("hs_email_last_reply_date")
        if email_reply_ms:
            reply_dt = ms_timestamp_to_datetime(email_reply_ms)
            if reply_dt and reply_dt >= cutoff_dt:
                signal_type = "email_reply"

        # Check notes signal (requires deeper inspection for system noise)
        notes_updated_ms = props.get("notes_last_updated")
        if notes_updated_ms and not signal_type:
            notes_dt = ms_timestamp_to_datetime(notes_updated_ms)
            if notes_dt and notes_dt >= cutoff_dt:
                # Fetch the actual note content to check for system noise
                recent_notes = get_contact_notes(cid)
                genuine_notes = [
                    n for n in recent_notes
                    if n.get("timestamp") and n["timestamp"] >= cutoff_dt
                    and not is_system_generated_note(n.get("body", ""))
                ]
                if genuine_notes:
                    signal_type = "note_reply"
                    contact["_note_preview"] = genuine_notes[0].get("body", "")[:200]
                else:
                    run_summary["skipped_system_noise"] += 1
                    log.debug("Contact %s: notes updated but all are system-generated — skip", cid)
                    continue

        if not signal_type:
            # Signal timestamp was in range but didn't pass validation — skip
            continue

        contact["_signal_type"] = signal_type
        hot_leads.append(contact)
        newly_seen.add(cid)

    run_summary["hot_leads_found"] = len(hot_leads)
    log.info("Hot leads found: %d", len(hot_leads))

    # ──────────────────────────────────────────────────────────────────────
    # Send alerts for each genuine hot lead
    # ──────────────────────────────────────────────────────────────────────
    for lead in hot_leads:
        props = lead.get("properties", {})
        signal = lead.get("_signal_type", "unknown")
        note_preview = lead.get("_note_preview", "")

        first = props.get("firstname") or ""
        last = props.get("lastname") or ""
        name = f"{first} {last}".strip() or "Unknown"
        email = props.get("email") or "N/A"
        company = props.get("company") or "Unknown company"
        title = props.get("jobtitle") or "Unknown title"
        sequence = props.get("br_sequence_assigned") or "N/A"
        icp_score = props.get("br_icp_score") or "N/A"
        linkedin = props.get("hs_linkedin_url") or "N/A"
        hs_url = f"https://app.hubspot.com/contacts/6282372/contact/{lead.get('id')}"

        signal_label = {
            "email_reply": "📧 Replied to outbound email",
            "note_reply": "💬 Note/message activity detected",
        }.get(signal, signal)

        # Format the alert email body (plain text)
        alert_body = f"""HOT LEAD ALERT — {name} at {company}

Signal: {signal_label}
Contact: {name} ({title})
Company: {company}
Email: {email}
LinkedIn: {linkedin}
Sequence: {sequence}
ICP Score: {icp_score}

HubSpot record: {hs_url}
"""
        if note_preview:
            alert_body += f"\nNote preview:\n{note_preview}\n"

        alert_body += f"\nDetected at: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"

        sent = send_hot_lead_alert(
            subject=f"🔥 Hot Lead: {name} at {company}",
            body=alert_body,
            contact_name=name,
        )
        if sent:
            run_summary["alerts_sent"] += 1

    # Persist seen state
    if newly_seen:
        save_seen_contacts(newly_seen)

    # Append to run log (keep last 500 entries)
    run_log = []
    if HOT_LEAD_LOG_PATH.exists():
        try:
            run_log = json.loads(HOT_LEAD_LOG_PATH.read_text())
        except Exception:
            run_log = []
    run_log.append(run_summary)
    run_log = run_log[-500:]
    HOT_LEAD_LOG_PATH.write_text(json.dumps(run_log, indent=2))

    log.info(
        "Run complete | Checked: %d | Hot leads: %d | Alerts sent: %d | "
        "Skipped seen: %d | Skipped excluded: %d | Skipped noise: %d",
        run_summary["contacts_checked"],
        run_summary["hot_leads_found"],
        run_summary["alerts_sent"],
        run_summary["skipped_seen"],
        run_summary["skipped_excluded"],
        run_summary["skipped_system_noise"],
    )

    return run_summary


# ═════════════════════════════════════════════════════════════════════════════
# Alert email
# ═════════════════════════════════════════════════════════════════════════════

def send_hot_lead_alert(subject: str, body: str, contact_name: str = "") -> bool:
    """
    Send a hot lead alert email via SMTP.

    In production, this can be replaced with a Slack webhook POST
    (more immediate than email). See weekly_report_cron.py for the
    Slack integration pattern.

    Returns True on success, False on failure.
    """
    if not SMTP_PASSWORD:
        log.warning("SMTP_PASSWORD not set — printing alert to stdout instead:")
        log.info("ALERT: %s\n%s", subject, body)
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"BR Outbound Monitor <{GMAIL_SENDER}>"
        msg["To"] = ALERT_TO_EMAIL
        msg["X-Priority"] = "1"  # High priority flag
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(GMAIL_SENDER, [ALERT_TO_EMAIL], msg.as_string())

        log.info("Hot lead alert sent for: %s", contact_name)
        return True
    except Exception as e:
        log.error("Failed to send hot lead alert: %s", e)
        return False


# ═════════════════════════════════════════════════════════════════════════════
# Entrypoint
# ═════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    """
    Standalone execution for local testing.

    Usage:
        python hot_lead_monitor.py

    This will check HubSpot for hot leads in the last 75 minutes and
    send alert emails if any are found. Run it manually to verify
    connectivity and alert formatting before deploying.

    Required environment variables:
        HUBSPOT_PAT — HubSpot private app token
        SMTP_PASSWORD — SMTP password for alert email sending
        ALERT_TO_EMAIL — Email address to receive hot lead alerts (default: craig@brdrch.com)

    To test without sending emails: leave SMTP_PASSWORD unset.
    Alerts will be printed to stdout instead.
    """
    if not HUBSPOT_PAT:
        print("ERROR: HUBSPOT_PAT environment variable is not set.")
        sys.exit(1)

    result = check_for_hot_leads()
    print("\n── Run Summary ──")
    print(json.dumps(result, indent=2))
