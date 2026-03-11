#!/usr/bin/env python3
"""
daily_cron_v10.py — Broad Reach B2B Outbound Machine
Daily Prospecting Cycle (Version 10)

Schedule: Every day at 7:00 AM EST (12:00 UTC)
Azure Function: DailyOutboundCycle (cron: "0 0 12 * * *")

Purpose:
    Runs the full outbound prospecting pipeline. Pulls qualified prospects
    from HubSpot (sourced via Apollo), applies ICP scoring, enforces anti-
    pollution cooldowns, sends outbound emails via HubSpot API (direct send
    — NOT sequences, which have a connected inbox bug), and pushes contacts
    to Expandi for LinkedIn outreach.

    This is the core revenue-generation engine for Broad Reach's B2B
    outbound motion targeting DTC ecommerce brands in the USA/Canada.

Author: Craig Radford <craig@brdrch.com>
Original platform: Perplexity Computer scheduled task
Migration target: Azure Functions / standalone cron
"""

import os
import sys
import json
import logging
import smtplib
import time
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
    pass  # python-dotenv not required in production (env vars set externally)

# ─── Logging ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("daily_cron_v10")

# ─── Configuration (from environment variables) ──────────────────────────────
# See .env.example at the root of this repo for all required variables.
HUBSPOT_PAT = os.environ.get("HUBSPOT_PAT", "")
EXPANDI_CAMPAIGN_A_WEBHOOK = os.environ.get("EXPANDI_CAMPAIGN_A_WEBHOOK", "")  # cold_dtc_savings → campaign 770808
EXPANDI_CAMPAIGN_B_WEBHOOK = os.environ.get("EXPANDI_CAMPAIGN_B_WEBHOOK", "")  # expansion_signal → campaign 770814
NOTION_TOKEN = os.environ.get("NOTION_TOKEN", "")
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN", "")
GMAIL_SENDER = os.environ.get("GMAIL_SENDER", "craig@brdrch.com")

# HubSpot API base
HS_BASE = "https://api.hubapi.com"

# State files (local disk; swap for Azure Blob Storage in production)
# See: azure-functions/ stubs — these paths become blob container paths
WORKSPACE = Path(os.environ.get("WORKSPACE_DIR", "/home/user/workspace"))
WARMUP_TRACKER_PATH = WORKSPACE / "warmup_tracker.json"
EXCLUSION_LIST_PATH = WORKSPACE / "active_clients_exclusion_list.txt"
PHYSICAL_ADDRESS_PATH = WORKSPACE / "physical_address.txt"
RUN_LOG_PATH = WORKSPACE / "daily_cron_run_log.json"

# Safety thresholds
EXCLUSION_LIST_MIN_ENTRIES = 100    # Alert if exclusion list drops below this
MAX_SEQUENCES_PER_CONTACT = 3       # Hard cap: never contact more than 3x total
MAX_CONTACTS_PER_COMPANY_90D = 3    # Anti-pollution: max 3 per company per 90-day window
MIN_DAYS_BETWEEN_SAME_COMPANY = 14  # Anti-pollution: 2-week cooldown within same company

# Warmup ramp schedule (emails per day by week number)
# Week 4+ is the steady-state ceiling.
WARMUP_RAMP = {1: 5, 2: 10, 3: 20, 4: 25}

# ICP score threshold — contacts below this are not enrolled
ICP_SCORE_MIN = 60

# Sender identity (CAN-SPAM: must match authenticated sending domain)
SENDER_NAME = "Craig Radford"
SENDER_EMAIL = "craig@brdrch.com"


# ═════════════════════════════════════════════════════════════════════════════
# HubSpot API helpers
# ═════════════════════════════════════════════════════════════════════════════

def hs_headers() -> dict:
    """Return authorization headers for HubSpot API calls."""
    return {
        "Authorization": f"Bearer {HUBSPOT_PAT}",
        "Content-Type": "application/json",
    }


def hs_get(path: str, params: dict = None) -> dict:
    """GET request to HubSpot API with basic error handling."""
    url = f"{HS_BASE}{path}"
    resp = requests.get(url, headers=hs_headers(), params=params, timeout=20)
    resp.raise_for_status()
    return resp.json()


def hs_post(path: str, body: dict) -> dict:
    """POST request to HubSpot API with basic error handling."""
    url = f"{HS_BASE}{path}"
    resp = requests.post(url, headers=hs_headers(), json=body, timeout=20)
    resp.raise_for_status()
    return resp.json()


def hs_patch(path: str, body: dict) -> dict:
    """PATCH request to HubSpot API (update a contact/company property)."""
    url = f"{HS_BASE}{path}"
    resp = requests.patch(url, headers=hs_headers(), json=body, timeout=20)
    resp.raise_for_status()
    return resp.json()


def search_contacts(filter_groups: list, properties: list, limit: int = 100) -> list:
    """
    Search HubSpot contacts with pagination.
    Returns all results across pages (up to 10 pages / 1000 contacts).

    HubSpot Search API: POST /crm/v3/objects/contacts/search
    """
    all_results = []
    after = None
    for page in range(10):  # Safety: max 10 pages
        body = {
            "filterGroups": filter_groups,
            "properties": properties,
            "limit": limit,
        }
        if after:
            body["after"] = after
        data = hs_post("/crm/v3/objects/contacts/search", body)
        results = data.get("results", [])
        all_results.extend(results)
        after = data.get("paging", {}).get("next", {}).get("after")
        if not after:
            break
        time.sleep(0.1)  # Gentle rate limiting
    return all_results


def update_contact(contact_id: str, properties: dict) -> dict:
    """Update a HubSpot contact's properties via PATCH."""
    return hs_patch(f"/crm/v3/objects/contacts/{contact_id}", {"properties": properties})


def send_hubspot_email(contact_id: str, subject: str, body_html: str) -> dict:
    """
    Send a single outbound email via HubSpot Transactional Email API.

    WHY direct send (not sequences):
        HubSpot Sequences require a connected inbox (OAuth). When sequences
        were configured with Craig's connected inbox, emails sporadically
        sent from the wrong sender address. Switching to direct transactional
        send (using a HubSpot email template or raw HTML) resolved the sender
        identity bug and gave us full control over the from/reply-to address.

    HubSpot API: POST /crm/v3/objects/emails
    This creates an email engagement on the contact record AND sends it
    via HubSpot's sending infrastructure (respects domain authentication).

    NOTE: You must have a HubSpot Marketing or Sales Hub subscription that
    allows transactional email sends. Confirm with your HubSpot admin.
    """
    payload = {
        "properties": {
            "hs_timestamp": str(int(datetime.now(timezone.utc).timestamp() * 1000)),
            "hubspot_owner_id": "",  # Set to Craig's HubSpot user ID if needed
            "hs_email_direction": "EMAIL",
            "hs_email_status": "SENT",
            "hs_email_subject": subject,
            "hs_email_html": body_html,
            "hs_email_text": body_html,  # Plain-text fallback
        },
        "associations": [
            {
                "to": {"id": contact_id},
                "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 198}],
            }
        ],
    }
    return hs_post("/crm/v3/objects/emails", payload)


# ═════════════════════════════════════════════════════════════════════════════
# Exclusion / active client list helpers
# ═════════════════════════════════════════════════════════════════════════════

def load_exclusion_list() -> set:
    """
    Load the active clients exclusion list from disk.
    This file contains company domain names and/or HubSpot company IDs
    that must NEVER receive outbound prospecting (current clients, warm
    intros, etc.).

    The list is maintained manually and synced from Notion.
    Format: one domain or identifier per line, e.g.:
        acmecorp.com
        bigretailer.io
    """
    if not EXCLUSION_LIST_PATH.exists():
        log.warning("active_clients_exclusion_list.txt not found at %s", EXCLUSION_LIST_PATH)
        return set()
    lines = EXCLUSION_LIST_PATH.read_text().strip().splitlines()
    return {line.strip().lower() for line in lines if line.strip()}


def sync_exclusion_list_from_notion() -> None:
    """
    Step 1: Sync the active client exclusion list from Notion.

    Notion is the source of truth for active clients (updated by the sales
    team as deals close). This step pulls the latest list and overwrites
    the local file before we run any outreach logic.

    NOTE: This requires NOTION_TOKEN to be set and a Notion database with
    client domain names. Adapt the database_id below to match your workspace.

    Notion API docs: https://developers.notion.com/reference/post-database-query
    """
    if not NOTION_TOKEN:
        log.warning("Step 1: NOTION_TOKEN not set — skipping Notion sync, using cached exclusion list")
        return

    NOTION_DATABASE_ID = os.environ.get("NOTION_CLIENTS_DATABASE_ID", "")
    if not NOTION_DATABASE_ID:
        log.warning("Step 1: NOTION_CLIENTS_DATABASE_ID not set — skipping Notion sync")
        return

    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28",
    }

    domains = []
    start_cursor = None
    while True:
        body = {"page_size": 100}
        if start_cursor:
            body["start_cursor"] = start_cursor
        resp = requests.post(
            f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}/query",
            headers=headers,
            json=body,
            timeout=15,
        )
        if resp.status_code != 200:
            log.error("Step 1: Notion API error %s — %s", resp.status_code, resp.text[:300])
            return

        data = resp.json()
        for page in data.get("results", []):
            props = page.get("properties", {})
            # Adapt the property name "Domain" to match your Notion database schema
            domain_prop = props.get("Domain", {})
            domain_val = ""
            if domain_prop.get("type") == "rich_text":
                rich = domain_prop.get("rich_text", [])
                domain_val = rich[0].get("plain_text", "") if rich else ""
            elif domain_prop.get("type") == "title":
                title = domain_prop.get("title", [])
                domain_val = title[0].get("plain_text", "") if title else ""
            if domain_val:
                domains.append(domain_val.strip().lower())

        if not data.get("has_more"):
            break
        start_cursor = data.get("next_cursor")

    if domains:
        EXCLUSION_LIST_PATH.write_text("\n".join(sorted(set(domains))) + "\n")
        log.info("Step 1: Synced %d client domains to exclusion list", len(domains))
    else:
        log.warning("Step 1: Notion returned 0 client domains — not overwriting existing list")


# ═════════════════════════════════════════════════════════════════════════════
# Warmup tracker
# ═════════════════════════════════════════════════════════════════════════════

def get_daily_email_limit() -> int:
    """
    Step 4 (gate): Read warmup_tracker.json to determine today's email
    send limit based on which week of warmup we're in.

    Warmup schedule (emails/day):
        Week 1: 5
        Week 2: 10
        Week 3: 20
        Week 4+: 25 (steady-state ceiling)

    The warmup tracker is maintained by the email warmup tool (e.g.,
    Instantly, Warmup Inbox) and written to workspace by a separate
    background job. If the file is missing, default to week 4+ (25/day)
    — this assumes warmup is complete.
    """
    if not WARMUP_TRACKER_PATH.exists():
        log.warning("warmup_tracker.json not found — defaulting to 25 emails/day (post-warmup)")
        return 25

    tracker = json.loads(WARMUP_TRACKER_PATH.read_text())
    warmup_start = tracker.get("warmup_start_date", "")
    if not warmup_start:
        return WARMUP_RAMP[4]

    try:
        start_date = datetime.strptime(warmup_start, "%Y-%m-%d")
        days_elapsed = (datetime.now() - start_date).days
        week = min((days_elapsed // 7) + 1, 4)
        limit = WARMUP_RAMP.get(week, WARMUP_RAMP[4])
        log.info("Warmup week %d — daily email limit: %d", week, limit)
        return limit
    except Exception as e:
        log.warning("Could not parse warmup_start_date: %s — defaulting to 25", e)
        return WARMUP_RAMP[4]


# ═════════════════════════════════════════════════════════════════════════════
# CAN-SPAM compliance
# ═════════════════════════════════════════════════════════════════════════════

def get_physical_address() -> str:
    """
    CAN-SPAM requires a physical postal address in every commercial email.
    Read from physical_address.txt (or fall back to env var).
    """
    if PHYSICAL_ADDRESS_PATH.exists():
        return PHYSICAL_ADDRESS_PATH.read_text().strip()
    return os.environ.get("PHYSICAL_ADDRESS", "Broad Reach Digital, [Address on file]")


def build_email_footer(unsubscribe_url: str = "") -> str:
    """Build CAN-SPAM compliant email footer."""
    address = get_physical_address()
    unsub_line = f'<br><a href="{unsubscribe_url}">Unsubscribe</a>' if unsubscribe_url else ""
    return f"""
<p style="color:#888;font-size:11px;margin-top:32px;">
{address}{unsub_line}
</p>
"""


# ═════════════════════════════════════════════════════════════════════════════
# ICP scoring and qualification
# ═════════════════════════════════════════════════════════════════════════════

def passes_icp_filter(contact: dict) -> bool:
    """
    Step 2.5: Apply ICP (Ideal Customer Profile) scoring and qualification.

    Qualification criteria for Broad Reach outbound:
    - br_icp_score >= 60 (set by Apollo enrichment + scoring job)
    - Contact has a job title indicating decision-making authority
      (e.g., VP, Director, Head of, C-suite, Founder, Owner)
    - Company is not in the exclusion list

    Returns True if contact passes ICP filter and should proceed.
    """
    props = contact.get("properties", {})

    # ICP score check
    try:
        icp_score = int(props.get("br_icp_score", 0) or 0)
    except (ValueError, TypeError):
        icp_score = 0

    if icp_score < ICP_SCORE_MIN:
        log.debug("Contact %s ICP score %d below threshold — skip", contact.get("id"), icp_score)
        return False

    # Job title / seniority check
    title = (props.get("jobtitle") or "").lower()
    senior_keywords = [
        "vp", "vice president", "director", "head of", "chief", "ceo", "coo",
        "cfo", "cmo", "cto", "founder", "owner", "president", "partner",
        "gm", "general manager", "managing director",
    ]
    if not any(kw in title for kw in senior_keywords):
        log.debug("Contact %s title '%s' not senior enough — skip", contact.get("id"), title)
        return False

    return True


def passes_hq_filter(contact: dict) -> bool:
    """
    Step 3: USA/Canada HQ filter.

    Broad Reach's ICP is DTC ecommerce brands headquartered in the USA or
    Canada. Hard-disqualify any company with HQ outside these countries.
    This prevents wasted outreach and protects domain reputation.

    HubSpot stores company country on the associated company record.
    This function checks the contact-level country field as a proxy.
    For full accuracy, look up the associated company object.
    """
    props = contact.get("properties", {})
    country = (props.get("country") or props.get("hs_country") or "").strip().upper()

    # Empty country = unclear, let it through (don't hard block on missing data)
    if not country:
        return True

    allowed_countries = {"US", "USA", "UNITED STATES", "CA", "CANADA"}
    if country not in allowed_countries:
        log.debug(
            "Contact %s country '%s' not USA/Canada — hard disqualify",
            contact.get("id"),
            country,
        )
        return False

    return True


# ═════════════════════════════════════════════════════════════════════════════
# Anti-pollution cooldown checks
# ═════════════════════════════════════════════════════════════════════════════

def passes_anti_pollution_check(contact: dict, company_touch_log: dict) -> tuple[bool, str]:
    """
    Step 2.7: Anti-pollution cooldown system.

    This system protects domain reputation and prevents over-contacting.
    Four enforcement rules:

    1. PERMANENT EXCLUSION: Any contact with br_last_sequence_outcome of
       'opted_out' or 'bounced' is excluded forever. No exceptions.

    2. MAX SEQUENCES (contact-level): A contact may never be enrolled in
       more than MAX_SEQUENCES_PER_CONTACT (3) sequences total. This
       prevents persistent harassment of a single individual.

    3. MAX CONTACTS PER COMPANY (90-day window): No more than
       MAX_CONTACTS_PER_COMPANY_90D (3) different contacts at the same
       company may be touched in any rolling 90-day window. This prevents
       BR from carpet-bombing a single company with outreach.

    4. SAME-COMPANY COOLDOWN: At least MIN_DAYS_BETWEEN_SAME_COMPANY (14)
       days must elapse between contacting two different people at the same
       company. This keeps outreach from feeling coordinated/spammy.

    Args:
        contact: HubSpot contact dict (with 'properties' and 'id')
        company_touch_log: dict of {company_domain: [touch_timestamps]}
            tracking contacts sent today's run (updated in-place)

    Returns:
        (passes: bool, reason: str)
    """
    props = contact.get("properties", {})
    contact_id = contact.get("id", "unknown")

    # Rule 1: Permanent exclusion on opt-out or bounce
    outcome = (props.get("br_last_sequence_outcome") or "").lower()
    if outcome in ("opted_out", "bounced", "opted_out_unsubscribed"):
        return False, f"permanent_exclusion:{outcome}"

    # Rule 2: Max sequences per contact
    try:
        sequences_enrolled = int(props.get("br_total_sequences_enrolled", 0) or 0)
    except (ValueError, TypeError):
        sequences_enrolled = 0
    if sequences_enrolled >= MAX_SEQUENCES_PER_CONTACT:
        return False, f"max_sequences_reached:{sequences_enrolled}"

    # Rules 3 & 4: Company-level checks
    company_domain = (props.get("associatedcompanydomain") or props.get("company") or "").lower().strip()
    if company_domain:
        now = datetime.now(timezone.utc)
        cutoff_90d = now - timedelta(days=90)
        cutoff_14d = now - timedelta(days=MIN_DAYS_BETWEEN_SAME_COMPANY)

        recent_touches = [
            ts for ts in company_touch_log.get(company_domain, [])
            if ts > cutoff_90d
        ]

        # Rule 3: Max 3 contacts at same company in 90 days
        if len(recent_touches) >= MAX_CONTACTS_PER_COMPANY_90D:
            return False, f"company_90d_limit:{company_domain}"

        # Rule 4: Min 14 days since last touch at this company
        if recent_touches and max(recent_touches) > cutoff_14d:
            days_since = (now - max(recent_touches)).days
            return False, f"company_14d_cooldown:{company_domain}:{days_since}d_ago"

    return True, "ok"


# ═════════════════════════════════════════════════════════════════════════════
# Expandi LinkedIn push
# ═════════════════════════════════════════════════════════════════════════════

def push_to_expandi(contact: dict, campaign: str) -> bool:
    """
    Step 6: Push contact to Expandi for LinkedIn outreach.

    Expandi uses "reversed webhook URLs" — you POST a contact payload to
    a campaign-specific URL, and Expandi automatically adds the person to
    the LinkedIn campaign queue.

    Campaign routing:
        cold_dtc_savings  → Campaign A (770808): Cold outreach to DTC brands
                            with high shipping cost pain signal
        expansion_signal  → Campaign B (770814): Expansion outreach to brands
                            showing growth signals (Shopify Plus upgrade, etc.)

    API domain: api.liaufa.com (NOT api.expandi.io — this is the correct domain
    for the reversed webhook feature as of the time of original build)

    The webhook URL is stored in .env as:
        EXPANDI_CAMPAIGN_A_WEBHOOK (for cold_dtc_savings)
        EXPANDI_CAMPAIGN_B_WEBHOOK (for expansion_signal)

    Returns True on success, False on failure.
    """
    props = contact.get("properties", {})
    linkedin_url = (props.get("hs_linkedin_url") or "").strip()

    if not linkedin_url:
        log.debug("Contact %s has no LinkedIn URL — skipping Expandi push", contact.get("id"))
        return False

    if campaign == "cold_dtc_savings":
        webhook_url = EXPANDI_CAMPAIGN_A_WEBHOOK
    elif campaign == "expansion_signal":
        webhook_url = EXPANDI_CAMPAIGN_B_WEBHOOK
    else:
        log.warning("Unknown Expandi campaign: %s — skipping", campaign)
        return False

    if not webhook_url:
        log.warning("Expandi webhook URL not configured for campaign %s — skipping", campaign)
        return False

    payload = {
        "linkedin_url": linkedin_url,
        "first_name": props.get("firstname", ""),
        "last_name": props.get("lastname", ""),
        "email": props.get("email", ""),
        "company": props.get("company", ""),
        "title": props.get("jobtitle", ""),
    }

    try:
        resp = requests.post(webhook_url, json=payload, timeout=10)
        if resp.status_code in (200, 201, 204):
            log.info("Pushed contact %s to Expandi campaign %s", contact.get("id"), campaign)
            return True
        else:
            log.warning(
                "Expandi push failed for contact %s: HTTP %s — %s",
                contact.get("id"),
                resp.status_code,
                resp.text[:200],
            )
            return False
    except Exception as e:
        log.error("Expandi push exception for contact %s: %s", contact.get("id"), e)
        return False


# ═════════════════════════════════════════════════════════════════════════════
# Notion dashboard update
# ═════════════════════════════════════════════════════════════════════════════

def update_notion_dashboard(stats: dict) -> None:
    """
    Step 7: Push today's run stats to the Notion outbound dashboard.

    The Notion dashboard gives Craig and the team a human-readable view of
    daily outbound activity without needing to log into HubSpot.

    Adapt NOTION_DASHBOARD_PAGE_ID to your workspace. The page should have
    a database with columns matching the stats dict keys below.

    Notion API: https://developers.notion.com/reference/patch-page
    """
    if not NOTION_TOKEN:
        log.info("Step 7: NOTION_TOKEN not set — skipping dashboard update")
        return

    NOTION_DASHBOARD_PAGE_ID = os.environ.get("NOTION_DASHBOARD_PAGE_ID", "")
    if not NOTION_DASHBOARD_PAGE_ID:
        log.info("Step 7: NOTION_DASHBOARD_PAGE_ID not set — skipping dashboard update")
        return

    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28",
    }

    # Build the properties payload (adapt to your actual Notion schema)
    properties = {
        "Last Run": {"date": {"start": datetime.now().isoformat()}},
        "Emails Sent": {"number": stats.get("emails_sent", 0)},
        "LinkedIn Pushed": {"number": stats.get("linkedin_pushed", 0)},
        "Contacts Processed": {"number": stats.get("contacts_processed", 0)},
        "Contacts Qualified": {"number": stats.get("contacts_qualified", 0)},
        "Contacts Skipped": {"number": stats.get("contacts_skipped", 0)},
        "Run Status": {
            "select": {"name": "Success" if not stats.get("error") else "Error"}
        },
    }

    resp = requests.patch(
        f"https://api.notion.com/v1/pages/{NOTION_DASHBOARD_PAGE_ID}",
        headers=headers,
        json={"properties": properties},
        timeout=15,
    )
    if resp.status_code == 200:
        log.info("Step 7: Notion dashboard updated")
    else:
        log.warning("Step 7: Notion update failed: %s — %s", resp.status_code, resp.text[:200])


# ═════════════════════════════════════════════════════════════════════════════
# Alert helper
# ═════════════════════════════════════════════════════════════════════════════

def send_alert_email(subject: str, body: str) -> None:
    """
    Send an alert email to Craig when a safety guard trips.
    Uses SMTP (Gmail SMTP or equivalent). Configure via environment variables.

    Required env vars: SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, ALERT_TO_EMAIL
    """
    smtp_host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = os.environ.get("SMTP_USER", GMAIL_SENDER)
    smtp_pass = os.environ.get("SMTP_PASSWORD", "")
    alert_to = os.environ.get("ALERT_TO_EMAIL", "craig@brdrch.com")

    if not smtp_pass:
        log.warning("SMTP_PASSWORD not set — cannot send alert email")
        log.warning("ALERT: %s — %s", subject, body)
        return

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"[BR Outbound Alert] {subject}"
        msg["From"] = f"{SENDER_NAME} <{GMAIL_SENDER}>"
        msg["To"] = alert_to
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.ehlo()
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(GMAIL_SENDER, [alert_to], msg.as_string())
        log.info("Alert email sent: %s", subject)
    except Exception as e:
        log.error("Failed to send alert email: %s", e)


# ═════════════════════════════════════════════════════════════════════════════
# Main cycle
# ═════════════════════════════════════════════════════════════════════════════

def run_daily_cycle() -> dict:
    """
    Execute the full daily outbound prospecting cycle.

    Returns a stats dict summarizing the run (used for Notion dashboard
    update and run log).
    """
    run_start = datetime.now(timezone.utc)
    stats = {
        "run_date": run_start.isoformat(),
        "contacts_processed": 0,
        "contacts_qualified": 0,
        "contacts_skipped": 0,
        "emails_sent": 0,
        "linkedin_pushed": 0,
        "error": None,
    }

    log.info("═" * 60)
    log.info("Broad Reach Daily Outbound Cycle — %s", run_start.strftime("%Y-%m-%d %H:%M UTC"))
    log.info("═" * 60)

    # ──────────────────────────────────────────────────────────────────────
    # STEP 0.5: Safety guard — exclusion list integrity check
    # WHY: If the active_clients_exclusion_list.txt were to be accidentally
    # deleted or truncated, we could send outreach to current paying clients.
    # That would be catastrophic for relationships and churn. This hard stop
    # prevents any outreach from running if the list looks wrong.
    # ──────────────────────────────────────────────────────────────────────
    log.info("Step 0.5: Safety guard — checking exclusion list integrity")
    exclusion_set = load_exclusion_list()
    if len(exclusion_set) < EXCLUSION_LIST_MIN_ENTRIES:
        msg = (
            f"SAFETY STOP: active_clients_exclusion_list.txt has only "
            f"{len(exclusion_set)} entries (minimum: {EXCLUSION_LIST_MIN_ENTRIES}). "
            f"Daily outbound cycle ABORTED to prevent contacting active clients."
        )
        log.critical(msg)
        send_alert_email("SAFETY STOP — Exclusion List Too Short", msg)
        stats["error"] = "safety_stop:exclusion_list_too_short"
        return stats

    log.info("Step 0.5: Exclusion list OK — %d entries", len(exclusion_set))

    # ──────────────────────────────────────────────────────────────────────
    # STEP 1: Sync exclusion list from Notion (refresh active clients)
    # ──────────────────────────────────────────────────────────────────────
    log.info("Step 1: Syncing active client exclusion list from Notion")
    sync_exclusion_list_from_notion()
    exclusion_set = load_exclusion_list()  # Reload after sync
    log.info("Step 1: Exclusion list updated — %d entries", len(exclusion_set))

    # ──────────────────────────────────────────────────────────────────────
    # STEP 2: Query HubSpot for BR contacts needing outreach
    # Pull contacts sourced via Apollo (br_source=apollo) that have not
    # yet been enrolled in a sequence (br_sequence_assigned is empty).
    # ──────────────────────────────────────────────────────────────────────
    log.info("Step 2: Querying HubSpot for uncontacted BR contacts")
    contact_properties = [
        "firstname", "lastname", "email", "company", "jobtitle",
        "country", "hs_linkedin_url", "associatedcompanydomain",
        "br_source", "br_icp_score", "br_shipping_pain_score",
        "br_sequence_assigned", "br_last_sequence_outcome",
        "br_total_sequences_enrolled", "br_expandi_status",
        "br_icp_vertical", "br_contact_cooldown_until",
        "notes_last_updated", "hs_email_last_reply_date",
        "lifecyclestage",
    ]

    raw_contacts = search_contacts(
        filter_groups=[
            {
                "filters": [
                    {"propertyName": "br_source", "operator": "EQ", "value": "apollo"},
                    {"propertyName": "br_sequence_assigned", "operator": "NOT_HAS_PROPERTY"},
                ]
            }
        ],
        properties=contact_properties,
        limit=100,
    )
    log.info("Step 2: Found %d uncontacted Apollo contacts", len(raw_contacts))

    # ──────────────────────────────────────────────────────────────────────
    # STEP 4 (gate): Check today's email limit from warmup tracker
    # Read this BEFORE qualification loop so we can short-circuit early
    # once we hit the daily ceiling.
    # ──────────────────────────────────────────────────────────────────────
    daily_email_limit = get_daily_email_limit()
    log.info("Step 4: Daily email limit today: %d", daily_email_limit)

    # company_touch_log tracks touches made during THIS run (in-memory).
    # For full accuracy, pre-populate from HubSpot activity in the last 90
    # days (omitted here for brevity — add a search by hs_email_last_sent_date
    # grouped by company if needed).
    company_touch_log: dict = {}  # {company_domain: [datetime, ...]}

    qualified = []
    skip_reasons = {}

    # ──────────────────────────────────────────────────────────────────────
    # STEP 2.5 + 2.7 + 3: Qualification pipeline
    # Each contact runs through the full filter stack.
    # ──────────────────────────────────────────────────────────────────────
    for contact in raw_contacts:
        stats["contacts_processed"] += 1
        props = contact.get("properties", {})
        cid = contact.get("id")

        # Step 2.5: ICP scoring filter
        if not passes_icp_filter(contact):
            reason = "icp_filter"
            skip_reasons[reason] = skip_reasons.get(reason, 0) + 1
            stats["contacts_skipped"] += 1
            continue

        # Step 2.7: Anti-pollution cooldown check
        passes, reason = passes_anti_pollution_check(contact, company_touch_log)
        if not passes:
            log.debug("Contact %s failed anti-pollution: %s", cid, reason)
            top_reason = reason.split(":")[0]
            skip_reasons[top_reason] = skip_reasons.get(top_reason, 0) + 1
            stats["contacts_skipped"] += 1
            continue

        # Step 3: USA/Canada HQ filter
        if not passes_hq_filter(contact):
            reason = "hq_filter"
            skip_reasons[reason] = skip_reasons.get(reason, 0) + 1
            stats["contacts_skipped"] += 1
            continue

        # Exclusion list check: skip if company domain is in active clients list
        company_domain = (
            props.get("associatedcompanydomain") or props.get("company") or ""
        ).lower().strip()
        if company_domain and company_domain in exclusion_set:
            log.debug("Contact %s company '%s' on exclusion list — skip", cid, company_domain)
            skip_reasons["exclusion_list"] = skip_reasons.get("exclusion_list", 0) + 1
            stats["contacts_skipped"] += 1
            continue

        qualified.append(contact)
        # Record this company as touched (for anti-pollution within this run)
        if company_domain:
            company_touch_log.setdefault(company_domain, []).append(datetime.now(timezone.utc))

    log.info(
        "Qualification complete: %d qualified, %d skipped | Skip reasons: %s",
        len(qualified),
        stats["contacts_skipped"],
        skip_reasons,
    )
    stats["contacts_qualified"] = len(qualified)

    # ──────────────────────────────────────────────────────────────────────
    # STEP 5: Send outbound emails via HubSpot API (direct send)
    # Apply daily email limit from warmup_tracker.json.
    # ──────────────────────────────────────────────────────────────────────
    log.info("Step 5: Sending outbound emails (limit: %d)", daily_email_limit)
    contacts_to_email = qualified[:daily_email_limit]

    for contact in contacts_to_email:
        props = contact.get("properties", {})
        cid = contact.get("id")
        first_name = props.get("firstname") or "there"
        company = props.get("company") or "your company"
        email_addr = props.get("email") or ""
        sequence = props.get("br_sequence_assigned") or "cold_dtc_savings"

        if not email_addr:
            log.debug("Contact %s has no email — skipping email send", cid)
            continue

        # Build subject and body based on sequence type.
        # In production: pull the actual email copy from the outreach_*.md files
        # or a HubSpot email template. These are simplified placeholders.
        if sequence == "cold_dtc_savings":
            subject = f"Quick question about {company}'s shipping costs"
            body_html = f"""
<p>Hi {first_name},</p>
<p>I came across {company} and noticed you're likely spending a significant
portion of revenue on outbound shipping. I work with DTC brands to renegotiate
carrier rates — we typically find 15–30% savings with no operational changes.</p>
<p>Worth a 15-minute call to see if there's an opportunity?</p>
<p>Best,<br>{SENDER_NAME}</p>
{build_email_footer()}
"""
        else:  # expansion_signal
            subject = f"Congrats on {company}'s growth — quick thought"
            body_html = f"""
<p>Hi {first_name},</p>
<p>Noticed {company} has been scaling fast — congrats. As you grow, shipping
costs tend to become a bigger line item. We help brands at your stage lock in
better carrier terms before volume thresholds reset.</p>
<p>Happy to share what we're seeing in your category if it'd be useful.</p>
<p>Best,<br>{SENDER_NAME}</p>
{build_email_footer()}
"""

        try:
            send_hubspot_email(cid, subject, body_html)
            # Mark as sequence enrolled in HubSpot
            update_contact(cid, {
                "br_sequence_assigned": sequence,
                "br_total_sequences_enrolled": str(
                    int(props.get("br_total_sequences_enrolled", 0) or 0) + 1
                ),
                "br_last_outreach_date": datetime.now().strftime("%Y-%m-%d"),
            })
            stats["emails_sent"] += 1
            log.info("Email sent to contact %s (%s) at %s", cid, email_addr, company)
            time.sleep(0.5)  # Rate limiting: ~2 emails/sec max
        except Exception as e:
            log.error("Failed to send email to contact %s: %s", cid, e)

    log.info("Step 5 complete: %d emails sent", stats["emails_sent"])

    # ──────────────────────────────────────────────────────────────────────
    # STEP 6: Push to Expandi for LinkedIn outreach
    # Only contacts with a LinkedIn URL are eligible. Route to Campaign A
    # (cold_dtc_savings) or Campaign B (expansion_signal) based on the
    # assigned sequence.
    # ──────────────────────────────────────────────────────────────────────
    log.info("Step 6: Pushing qualified contacts to Expandi for LinkedIn outreach")
    for contact in qualified:
        props = contact.get("properties", {})
        cid = contact.get("id")
        sequence = props.get("br_sequence_assigned") or "cold_dtc_savings"

        # Skip if already pushed to Expandi
        expandi_status = props.get("br_expandi_status") or ""
        if expandi_status.startswith("pushed_campaign"):
            continue

        campaign = "cold_dtc_savings" if sequence == "cold_dtc_savings" else "expansion_signal"
        pushed = push_to_expandi(contact, campaign)

        if pushed:
            campaign_tag = "pushed_campaign_a" if campaign == "cold_dtc_savings" else "pushed_campaign_b"
            update_contact(cid, {"br_expandi_status": campaign_tag})
            stats["linkedin_pushed"] += 1
            time.sleep(0.2)  # Rate limiting

    log.info("Step 6 complete: %d contacts pushed to Expandi", stats["linkedin_pushed"])

    # ──────────────────────────────────────────────────────────────────────
    # STEP 7: Update Notion dashboard
    # ──────────────────────────────────────────────────────────────────────
    log.info("Step 7: Updating Notion dashboard")
    update_notion_dashboard(stats)

    # Append to run log
    run_log = []
    if RUN_LOG_PATH.exists():
        try:
            run_log = json.loads(RUN_LOG_PATH.read_text())
        except Exception:
            run_log = []
    run_log.append(stats)
    run_log = run_log[-90:]  # Keep last 90 days
    RUN_LOG_PATH.write_text(json.dumps(run_log, indent=2))

    elapsed = (datetime.now(timezone.utc) - run_start).total_seconds()
    log.info("═" * 60)
    log.info(
        "Daily cycle complete in %.1fs | Emails: %d | LinkedIn: %d | Qualified: %d/%d",
        elapsed,
        stats["emails_sent"],
        stats["linkedin_pushed"],
        stats["contacts_qualified"],
        stats["contacts_processed"],
    )
    log.info("═" * 60)
    return stats


# ═════════════════════════════════════════════════════════════════════════════
# Entrypoint
# ═════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    """
    Standalone execution for local testing.

    Usage:
        python daily_cron_v10.py

    Required environment variables (set in .env or shell):
        HUBSPOT_PAT, EXPANDI_CAMPAIGN_A_WEBHOOK, EXPANDI_CAMPAIGN_B_WEBHOOK,
        NOTION_TOKEN (optional), SLACK_BOT_TOKEN (optional), SMTP_PASSWORD (optional)

    The script will:
    1. Load .env from the current directory (via python-dotenv)
    2. Run the full daily cycle
    3. Print stats to stdout
    4. Write a run log entry to daily_cron_run_log.json
    """
    if not HUBSPOT_PAT:
        print("ERROR: HUBSPOT_PAT environment variable is not set.")
        print("Copy .env.example to .env and fill in your credentials.")
        sys.exit(1)

    result = run_daily_cycle()
    print("\n── Run Summary ──")
    print(json.dumps(result, indent=2))
