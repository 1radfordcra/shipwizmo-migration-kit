#!/usr/bin/env python3
"""
hubspot_sequence_enroll.py — Broad Reach B2B Outbound Machine
HubSpot Sequence Enrollment Helper Utility

This is a standalone utility script, NOT a scheduled cron.
Run manually or call from daily_cron_v10.py when needed.

Purpose:
    Provides programmatic enrollment of contacts into HubSpot sequences,
    with full handling for the connected inbox bug that affected the original
    Broad Reach outbound system.

    CRITICAL BACKGROUND — The Connected Inbox Bug:
    ───────────────────────────────────────────────
    HubSpot Sequences require a "connected inbox" (Gmail/Outlook OAuth) to
    send emails. When Craig's inbox was connected to HubSpot Sequences, emails
    sporadically sent from an unexpected sender identity — sometimes appearing
    to come from HubSpot's shared sending infrastructure rather than
    craig@brdrch.com. This created deliverability issues and made the sender
    identity unpredictable.

    The workaround implemented in production:
    1. We still USE HubSpot sequences for tracking/pipeline visibility (the
       sequence enrollment is made via the Sequences API so the contact shows
       as "in sequence" in HubSpot's UI)
    2. But we DO NOT rely on sequence steps to actually send the emails
    3. Instead, email sending is handled by daily_cron_v10.py via the
       HubSpot Engagements API (POST /crm/v3/objects/emails) — direct send
       using Craig's authenticated credentials

    This utility handles step 1 (enrollment) separately so the sales team
    can also use it ad-hoc to enroll contacts found outside the daily cron
    (e.g., manually prospected contacts, warm intros, etc.).

    Batch processing:
    - Accepts a list of HubSpot contact IDs
    - Respects HubSpot API rate limits (100 req/10s burst, 110 req/10s sustained)
    - Retries on transient errors with exponential backoff
    - Writes a detailed enrollment log to hubspot_enrollment_log.json

Author: Craig Radford <craig@brdrch.com>
Original platform: Perplexity Computer (inline utility)
Migration target: Standalone script / Azure Function trigger
"""

import os
import sys
import json
import time
import logging
import argparse
import requests
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

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
log = logging.getLogger("hubspot_sequence_enroll")

# ─── Configuration ────────────────────────────────────────────────────────────
HUBSPOT_PAT = os.environ.get("HUBSPOT_PAT", "")
HS_BASE = "https://api.hubapi.com"

WORKSPACE = Path(os.environ.get("WORKSPACE_DIR", "/home/user/workspace"))
ENROLLMENT_LOG_PATH = WORKSPACE / "hubspot_enrollment_log.json"

# HubSpot API rate limits
# Reference: https://developers.hubspot.com/docs/api/usage-details
# Free/Starter: 100 calls per 10 seconds
# Pro/Enterprise: 150 calls per 10 seconds
# We use conservative 8 requests/second to stay well within limits.
REQUESTS_PER_SECOND = 8
MIN_DELAY_BETWEEN_REQUESTS = 1.0 / REQUESTS_PER_SECOND  # ~125ms

# Retry configuration for transient errors (429 rate limit, 5xx server errors)
MAX_RETRIES = 3
RETRY_BASE_DELAY = 2.0  # seconds; doubles each retry attempt

# HubSpot Sequence IDs used in Broad Reach outbound.
# These IDs are from Craig's HubSpot account (6282372).
# If you recreate sequences in a new account, update these.
SEQUENCE_IDS = {
    "cold_dtc_savings": "",     # Replace with actual sequence ID from HubSpot
    "expansion_signal": "",     # Replace with actual sequence ID from HubSpot
}

# Sender identity used for sequence enrollment.
# This MUST match a connected inbox OR a user with sending permissions.
# NOTE: Due to the connected inbox bug, we use this for record-keeping only;
# actual email sending is done via daily_cron_v10.py's direct send.
SENDER_EMAIL = os.environ.get("GMAIL_SENDER", "craig@brdrch.com")
HUBSPOT_SENDER_USER_ID = os.environ.get("HUBSPOT_SENDER_USER_ID", "")  # Craig's HubSpot user ID


# ═════════════════════════════════════════════════════════════════════════════
# HubSpot API helpers with retry logic
# ═════════════════════════════════════════════════════════════════════════════

def hs_headers() -> dict:
    """Return authorization headers for HubSpot API calls."""
    return {
        "Authorization": f"Bearer {HUBSPOT_PAT}",
        "Content-Type": "application/json",
    }


def hs_request(
    method: str,
    path: str,
    body: dict = None,
    params: dict = None,
    retries: int = MAX_RETRIES,
) -> tuple[dict, int]:
    """
    Make an HTTP request to HubSpot API with retry logic.

    Handles:
    - 429 Too Many Requests: backs off using Retry-After header if present
    - 5xx Server Errors: exponential backoff
    - 4xx Client Errors: raises immediately (no retry — likely a bad request)

    Returns (response_dict, status_code).
    Raises requests.HTTPError on unrecoverable errors.
    """
    url = f"{HS_BASE}{path}"
    attempt = 0

    while attempt <= retries:
        try:
            resp = requests.request(
                method=method.upper(),
                url=url,
                headers=hs_headers(),
                json=body,
                params=params,
                timeout=20,
            )

            if resp.status_code == 204:
                return {}, 204

            if resp.status_code == 429:
                # Rate limited. Honor the Retry-After header if present.
                retry_after = int(resp.headers.get("Retry-After", RETRY_BASE_DELAY * (2 ** attempt)))
                log.warning("Rate limited (429). Retrying after %ss (attempt %d/%d)", retry_after, attempt + 1, retries)
                time.sleep(retry_after)
                attempt += 1
                continue

            if resp.status_code >= 500:
                delay = RETRY_BASE_DELAY * (2 ** attempt)
                log.warning("Server error %s. Retrying in %ss (attempt %d/%d)", resp.status_code, delay, attempt + 1, retries)
                time.sleep(delay)
                attempt += 1
                continue

            resp.raise_for_status()

            try:
                return resp.json(), resp.status_code
            except ValueError:
                return {"raw": resp.text}, resp.status_code

        except requests.exceptions.Timeout:
            delay = RETRY_BASE_DELAY * (2 ** attempt)
            log.warning("Request timeout. Retrying in %ss (attempt %d/%d)", delay, attempt + 1, retries)
            time.sleep(delay)
            attempt += 1
            continue

        except requests.exceptions.ConnectionError as e:
            delay = RETRY_BASE_DELAY * (2 ** attempt)
            log.warning("Connection error: %s. Retrying in %ss", e, delay)
            time.sleep(delay)
            attempt += 1
            continue

    raise Exception(f"HubSpot API call failed after {retries} retries: {method} {path}")


def get_contact(contact_id: str) -> Optional[dict]:
    """
    Fetch a single contact from HubSpot with key outbound properties.
    Returns None if the contact is not found.
    """
    props = ",".join([
        "firstname", "lastname", "email", "company", "jobtitle",
        "br_source", "br_sequence_assigned", "br_last_sequence_outcome",
        "br_total_sequences_enrolled", "br_icp_score",
        "hs_sequences_is_enrolled", "lifecyclestage",
    ])
    try:
        data, status = hs_request("GET", f"/crm/v3/objects/contacts/{contact_id}", params={"properties": props})
        return data
    except requests.HTTPError as e:
        if e.response.status_code == 404:
            log.warning("Contact %s not found in HubSpot", contact_id)
            return None
        raise


def update_contact_properties(contact_id: str, properties: dict) -> bool:
    """
    Update a contact's custom properties in HubSpot.
    Used to mark enrollment status, sequence name, outreach date, etc.
    Returns True on success.
    """
    try:
        hs_request("PATCH", f"/crm/v3/objects/contacts/{contact_id}", body={"properties": properties})
        return True
    except Exception as e:
        log.error("Failed to update contact %s: %s", contact_id, e)
        return False


# ═════════════════════════════════════════════════════════════════════════════
# Sequence enrollment
# ═════════════════════════════════════════════════════════════════════════════

def enroll_contact_in_sequence(
    contact_id: str,
    sequence_id: str,
    sender_email: str = SENDER_EMAIL,
    sender_user_id: str = HUBSPOT_SENDER_USER_ID,
) -> dict:
    """
    Enroll a single contact into a HubSpot sequence.

    HubSpot Sequences Enrollment API:
    POST /automation/v4/sequences/enrollments

    Required fields:
    - sequenceId: The HubSpot sequence ID (numeric string)
    - contactId: The HubSpot contact object ID
    - senderEmail: Must match a connected inbox or validated sender

    IMPORTANT — Connected Inbox Bug Notes:
    Due to the connected inbox bug discovered in production, HubSpot sequence
    steps are NOT relied upon to send emails. After enrolling:
    1. The enrollment is recorded here for CRM visibility
    2. The actual email send happens via daily_cron_v10.py's direct send
    3. If you want sequences to send emails again in the future, fix the
       connected inbox auth under Settings → Inbox → Reconnect

    Returns a dict with enrollment status and any error details.
    """
    if not sequence_id:
        return {
            "contact_id": contact_id,
            "status": "error",
            "error": "sequence_id is empty — check SEQUENCE_IDS in config",
        }

    payload = {
        "sequenceId": sequence_id,
        "contactId": contact_id,
        "senderEmail": sender_email,
    }
    if sender_user_id:
        payload["senderId"] = sender_user_id

    try:
        data, status = hs_request(
            "POST",
            "/automation/v4/sequences/enrollments",
            body=payload,
        )
        if status in (200, 201):
            log.info("Enrolled contact %s in sequence %s", contact_id, sequence_id)
            return {
                "contact_id": contact_id,
                "sequence_id": sequence_id,
                "status": "enrolled",
                "enrollment_id": data.get("id", ""),
                "error": None,
            }
        else:
            log.warning("Unexpected status %s for contact %s: %s", status, contact_id, data)
            return {
                "contact_id": contact_id,
                "sequence_id": sequence_id,
                "status": "unexpected_status",
                "error": f"HTTP {status}: {data}",
            }

    except requests.HTTPError as e:
        error_body = ""
        try:
            error_body = e.response.json().get("message", e.response.text[:200])
        except Exception:
            error_body = str(e)

        if e.response.status_code == 409:
            # 409 Conflict = already enrolled. This is not a fatal error.
            log.info("Contact %s is already enrolled in sequence %s", contact_id, sequence_id)
            return {
                "contact_id": contact_id,
                "sequence_id": sequence_id,
                "status": "already_enrolled",
                "error": None,
            }

        if e.response.status_code == 400:
            # 400 often means: contact has no email, connected inbox not valid, etc.
            log.warning("Bad request enrolling contact %s: %s", contact_id, error_body)
            return {
                "contact_id": contact_id,
                "sequence_id": sequence_id,
                "status": "error",
                "error": f"400 Bad Request: {error_body}",
            }

        log.error("HTTP error enrolling contact %s: %s", contact_id, error_body)
        return {
            "contact_id": contact_id,
            "sequence_id": sequence_id,
            "status": "error",
            "error": error_body,
        }

    except Exception as e:
        log.error("Unexpected error enrolling contact %s: %s", contact_id, e)
        return {
            "contact_id": contact_id,
            "sequence_id": sequence_id,
            "status": "error",
            "error": str(e),
        }


def direct_send_workaround(
    contact_id: str,
    sequence_name: str,
    first_name: str,
    company: str,
    email_address: str,
) -> dict:
    """
    The connected inbox bug workaround: send the first outreach email via
    HubSpot's Engagements API instead of relying on the sequence step.

    This creates an email engagement on the contact record (so it appears
    in HubSpot's activity timeline) and sends the email via HubSpot's
    infrastructure using Craig's authenticated identity.

    Call this AFTER enroll_contact_in_sequence() for contacts where you want
    the first email sent immediately rather than waiting for the sequence step.

    In the daily cron, this is handled inside the Step 5 email loop.
    This function is provided here for ad-hoc use.

    API: POST /crm/v3/objects/emails
    """
    physical_address_path = WORKSPACE / "physical_address.txt"
    physical_address = (
        physical_address_path.read_text().strip()
        if physical_address_path.exists()
        else os.environ.get("PHYSICAL_ADDRESS", "Broad Reach Digital, [Address]")
    )

    first_name_display = first_name or "there"
    company_display = company or "your company"

    if sequence_name == "cold_dtc_savings":
        subject = f"Quick question about {company_display}'s shipping costs"
        body_html = f"""
<p>Hi {first_name_display},</p>
<p>I came across {company_display} and noticed you're likely spending a
significant portion of revenue on outbound shipping. We help DTC brands
renegotiate carrier rates — typically finding 15–30% savings with no
operational changes required.</p>
<p>Worth a quick 15-minute call to see if there's an opportunity?</p>
<p>Best,<br>Craig Radford<br>Broad Reach Digital</p>
<p style="color:#888;font-size:11px;margin-top:24px;">{physical_address}</p>
"""
    else:  # expansion_signal
        subject = f"Congrats on {company_display}'s growth — quick thought"
        body_html = f"""
<p>Hi {first_name_display},</p>
<p>Noticed {company_display} has been scaling — congrats. As you grow,
shipping costs become a larger line item. We help brands at your stage
lock in better carrier terms before volume thresholds reset.</p>
<p>Happy to share what we're seeing in your category.</p>
<p>Best,<br>Craig Radford<br>Broad Reach Digital</p>
<p style="color:#888;font-size:11px;margin-top:24px;">{physical_address}</p>
"""

    payload = {
        "properties": {
            "hs_timestamp": str(int(datetime.now(timezone.utc).timestamp() * 1000)),
            "hs_email_direction": "EMAIL",
            "hs_email_status": "SENT",
            "hs_email_subject": subject,
            "hs_email_html": body_html,
            "hs_email_text": body_html,
        },
        "associations": [
            {
                "to": {"id": contact_id},
                "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 198}],
            }
        ],
    }

    try:
        data, status = hs_request("POST", "/crm/v3/objects/emails", body=payload)
        if status in (200, 201):
            log.info("Direct send email created for contact %s (sequence: %s)", contact_id, sequence_name)
            return {"status": "sent", "engagement_id": data.get("id", ""), "subject": subject}
        else:
            return {"status": "error", "error": f"HTTP {status}: {data}"}
    except Exception as e:
        log.error("Direct send failed for contact %s: %s", contact_id, e)
        return {"status": "error", "error": str(e)}


# ═════════════════════════════════════════════════════════════════════════════
# Batch enrollment
# ═════════════════════════════════════════════════════════════════════════════

def batch_enroll(
    contact_ids: list[str],
    sequence_name: str,
    direct_send: bool = True,
    dry_run: bool = False,
) -> dict:
    """
    Enroll a batch of contacts into a HubSpot sequence with rate limiting.

    Args:
        contact_ids:   List of HubSpot contact IDs (strings)
        sequence_name: "cold_dtc_savings" or "expansion_signal"
        direct_send:   If True, also sends the first email via the direct-send
                       workaround (bypassing the sequence step's sender bug)
        dry_run:       If True, validates contacts but does NOT enroll or send

    Returns a summary dict with per-contact results.
    """
    sequence_id = SEQUENCE_IDS.get(sequence_name, "")
    if not sequence_id and not dry_run:
        log.warning(
            "No sequence ID configured for '%s'. "
            "Set it in SEQUENCE_IDS at the top of this file. "
            "Continuing with contact property updates only.",
            sequence_name,
        )

    results = {
        "sequence_name": sequence_name,
        "total": len(contact_ids),
        "enrolled": 0,
        "already_enrolled": 0,
        "direct_sends": 0,
        "errors": 0,
        "skipped": 0,
        "dry_run": dry_run,
        "details": [],
    }

    log.info(
        "Batch enrollment: %d contacts → sequence '%s'%s",
        len(contact_ids),
        sequence_name,
        " [DRY RUN]" if dry_run else "",
    )

    for i, contact_id in enumerate(contact_ids):
        contact_id = str(contact_id).strip()
        log.info("[%d/%d] Processing contact %s", i + 1, len(contact_ids), contact_id)

        # Fetch contact to validate eligibility
        contact = get_contact(contact_id)
        if not contact:
            result = {"contact_id": contact_id, "status": "not_found"}
            results["details"].append(result)
            results["errors"] += 1
            continue

        props = contact.get("properties", {})

        # Skip if already enrolled in a sequence
        existing_seq = props.get("br_sequence_assigned")
        if existing_seq:
            log.info("Contact %s already enrolled in '%s' — skip", contact_id, existing_seq)
            result = {"contact_id": contact_id, "status": "already_has_sequence", "existing": existing_seq}
            results["details"].append(result)
            results["skipped"] += 1
            continue

        # Skip opted-out or bounced contacts
        outcome = (props.get("br_last_sequence_outcome") or "").lower()
        if outcome in ("opted_out", "bounced", "opted_out_unsubscribed"):
            log.info("Contact %s has outcome '%s' — skip", contact_id, outcome)
            result = {"contact_id": contact_id, "status": "excluded", "reason": outcome}
            results["details"].append(result)
            results["skipped"] += 1
            continue

        if dry_run:
            log.info("[DRY RUN] Would enroll contact %s in sequence '%s'", contact_id, sequence_name)
            result = {
                "contact_id": contact_id,
                "status": "dry_run",
                "name": f"{props.get('firstname', '')} {props.get('lastname', '')}".strip(),
                "company": props.get("company", ""),
                "email": props.get("email", ""),
            }
            results["details"].append(result)
            continue

        # Enroll in HubSpot sequence (for CRM visibility)
        enroll_result = enroll_contact_in_sequence(
            contact_id=contact_id,
            sequence_id=sequence_id,
        )
        result = enroll_result.copy()
        result["name"] = f"{props.get('firstname', '')} {props.get('lastname', '')}".strip()
        result["company"] = props.get("company", "")

        if enroll_result["status"] == "enrolled":
            results["enrolled"] += 1
        elif enroll_result["status"] == "already_enrolled":
            results["already_enrolled"] += 1
        elif enroll_result["status"] == "error":
            results["errors"] += 1

        # Update HubSpot contact properties to track enrollment
        if enroll_result["status"] in ("enrolled", "already_enrolled"):
            update_contact_properties(contact_id, {
                "br_sequence_assigned": sequence_name,
                "br_last_outreach_date": datetime.now().strftime("%Y-%m-%d"),
                "br_total_sequences_enrolled": str(
                    int(props.get("br_total_sequences_enrolled", 0) or 0) + 1
                ),
            })

            # Direct send workaround (bypasses connected inbox bug)
            if direct_send and props.get("email"):
                send_result = direct_send_workaround(
                    contact_id=contact_id,
                    sequence_name=sequence_name,
                    first_name=props.get("firstname", ""),
                    company=props.get("company", ""),
                    email_address=props.get("email", ""),
                )
                result["direct_send"] = send_result
                if send_result.get("status") == "sent":
                    results["direct_sends"] += 1

        results["details"].append(result)

        # Rate limiting: pause between requests
        if i < len(contact_ids) - 1:
            time.sleep(MIN_DELAY_BETWEEN_REQUESTS)

    # Write to enrollment log
    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "summary": {k: v for k, v in results.items() if k != "details"},
    }
    enrollment_log = []
    if ENROLLMENT_LOG_PATH.exists():
        try:
            enrollment_log = json.loads(ENROLLMENT_LOG_PATH.read_text())
        except Exception:
            enrollment_log = []
    enrollment_log.append(log_entry)
    enrollment_log = enrollment_log[-200:]
    ENROLLMENT_LOG_PATH.write_text(json.dumps(enrollment_log, indent=2))

    log.info(
        "Batch complete | Enrolled: %d | Already enrolled: %d | "
        "Direct sends: %d | Errors: %d | Skipped: %d",
        results["enrolled"],
        results["already_enrolled"],
        results["direct_sends"],
        results["errors"],
        results["skipped"],
    )

    return results


# ═════════════════════════════════════════════════════════════════════════════
# CLI interface
# ═════════════════════════════════════════════════════════════════════════════

def main():
    """
    CLI interface for ad-hoc sequence enrollment.

    Usage examples:

    # Enroll a single contact:
    python hubspot_sequence_enroll.py --contact-ids 12345 --sequence cold_dtc_savings

    # Enroll multiple contacts:
    python hubspot_sequence_enroll.py --contact-ids 12345 67890 11111 --sequence expansion_signal

    # Enroll from a file (one contact ID per line):
    python hubspot_sequence_enroll.py --contact-file contacts_to_enroll.txt --sequence cold_dtc_savings

    # Dry run (validate only, no actual enrollment):
    python hubspot_sequence_enroll.py --contact-ids 12345 --sequence cold_dtc_savings --dry-run

    # Enroll without direct email send (sequence email only):
    python hubspot_sequence_enroll.py --contact-ids 12345 --sequence cold_dtc_savings --no-direct-send
    """
    parser = argparse.ArgumentParser(
        description="Enroll HubSpot contacts into Broad Reach outbound sequences",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--contact-ids",
        nargs="+",
        metavar="ID",
        help="One or more HubSpot contact IDs to enroll",
    )
    parser.add_argument(
        "--contact-file",
        metavar="FILE",
        help="Path to a file with one contact ID per line",
    )
    parser.add_argument(
        "--sequence",
        choices=["cold_dtc_savings", "expansion_signal"],
        required=True,
        help="Which sequence to enroll contacts into",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate contacts but do not enroll or send emails",
    )
    parser.add_argument(
        "--no-direct-send",
        action="store_true",
        help="Skip the direct email send workaround (use sequence step only)",
    )
    parser.add_argument(
        "--output",
        metavar="FILE",
        help="Write full results to this JSON file",
    )

    args = parser.parse_args()

    if not HUBSPOT_PAT:
        print("ERROR: HUBSPOT_PAT environment variable is not set.")
        sys.exit(1)

    # Collect contact IDs
    contact_ids = []
    if args.contact_ids:
        contact_ids.extend(args.contact_ids)
    if args.contact_file:
        fpath = Path(args.contact_file)
        if not fpath.exists():
            print(f"ERROR: Contact file not found: {args.contact_file}")
            sys.exit(1)
        file_ids = [line.strip() for line in fpath.read_text().splitlines() if line.strip()]
        contact_ids.extend(file_ids)
        log.info("Loaded %d contact IDs from %s", len(file_ids), args.contact_file)

    if not contact_ids:
        print("ERROR: Provide at least one contact ID via --contact-ids or --contact-file")
        sys.exit(1)

    # Deduplicate
    contact_ids = list(dict.fromkeys(contact_ids))
    log.info("Total unique contacts to process: %d", len(contact_ids))

    results = batch_enroll(
        contact_ids=contact_ids,
        sequence_name=args.sequence,
        direct_send=not args.no_direct_send,
        dry_run=args.dry_run,
    )

    # Write output file if requested
    if args.output:
        Path(args.output).write_text(json.dumps(results, indent=2))
        log.info("Full results written to %s", args.output)

    # Print summary
    print("\n── Enrollment Summary ──")
    print(f"Sequence:       {results['sequence_name']}")
    print(f"Total:          {results['total']}")
    print(f"Enrolled:       {results['enrolled']}")
    print(f"Already in seq: {results['already_enrolled']}")
    print(f"Direct sends:   {results['direct_sends']}")
    print(f"Errors:         {results['errors']}")
    print(f"Skipped:        {results['skipped']}")
    if args.dry_run:
        print("\n[DRY RUN — no changes were made]")


# ═════════════════════════════════════════════════════════════════════════════
# Importable API (for use from daily_cron_v10.py)
# ═════════════════════════════════════════════════════════════════════════════

def enroll_single(
    contact_id: str,
    sequence_name: str,
    direct_send: bool = True,
) -> dict:
    """
    Convenience function for enrolling a single contact.
    Suitable for import in daily_cron_v10.py:

        from hubspot_sequence_enroll import enroll_single
        result = enroll_single("12345", "cold_dtc_savings")
    """
    results = batch_enroll(
        contact_ids=[contact_id],
        sequence_name=sequence_name,
        direct_send=direct_send,
        dry_run=False,
    )
    return results["details"][0] if results["details"] else {"status": "no_result"}


if __name__ == "__main__":
    main()
