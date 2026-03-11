#!/usr/bin/env python3
"""
weekly_report_cron.py — Broad Reach B2B Outbound Machine
Weekly Performance Report

Schedule: Every Monday at 9:00 AM EDT / 8:00 AM EST
Cron expression: 0 0 13 * * 1   (UTC; 13:00 UTC = 8 AM EST / 9 AM EDT)
Azure Function: WeeklyPerformanceReport (cron: "0 0 13 * * 1")

Purpose:
    Generates a weekly outbound performance report covering the 7-day period
    ending at midnight Sunday (i.e., Mon–Sun). Pulls metrics from HubSpot,
    cross-references Expandi LinkedIn activity, and posts a formatted
    Slack-friendly markdown digest to the team Slack channel. Also updates
    the Notion dashboard with the weekly summary.

    Report covers:
    - Email channel: contacts reached, emails sent, replies received
    - LinkedIn channel: contacts pushed to Expandi (Campaign A vs B),
      contacts with vs without LinkedIn URLs (coverage gap)
    - Pipeline health: queue status, contacts pending outreach
    - Daily cron run log summary (from daily_cron_run_log.json)
    - No-LinkedIn-URL count (these contacts can't use the LinkedIn channel)

    The report is designed to be actionable: Craig should be able to read it
    in 2 minutes and know exactly what happened last week and what needs
    attention this week.

Author: Craig Radford <craig@brdrch.com>
Original platform: Perplexity Computer scheduled task
Migration target: Azure Functions / standalone cron
"""

import os
import sys
import json
import time
import logging
import requests
from datetime import datetime, timedelta, timezone
from pathlib import Path
from collections import defaultdict

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
log = logging.getLogger("weekly_report_cron")

# ─── Configuration ────────────────────────────────────────────────────────────
HUBSPOT_PAT = os.environ.get("HUBSPOT_PAT", "")
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN", "")
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")  # Incoming webhook (alternative to bot token)
SLACK_CHANNEL = os.environ.get("SLACK_CHANNEL", "#outbound-machine")
NOTION_TOKEN = os.environ.get("NOTION_TOKEN", "")
NOTION_DASHBOARD_PAGE_ID = os.environ.get("NOTION_DASHBOARD_PAGE_ID", "")

HS_BASE = "https://api.hubapi.com"

WORKSPACE = Path(os.environ.get("WORKSPACE_DIR", "/home/user/workspace"))
DAILY_RUN_LOG_PATH = WORKSPACE / "daily_cron_run_log.json"
WEEKLY_REPORT_LOG_PATH = WORKSPACE / "weekly_report_log.json"


# ═════════════════════════════════════════════════════════════════════════════
# HubSpot API helpers
# ═════════════════════════════════════════════════════════════════════════════

def hs_headers() -> dict:
    return {
        "Authorization": f"Bearer {HUBSPOT_PAT}",
        "Content-Type": "application/json",
    }


def hs_post(path: str, body: dict) -> dict:
    url = f"{HS_BASE}{path}"
    resp = requests.post(url, headers=hs_headers(), json=body, timeout=20)
    resp.raise_for_status()
    return resp.json()


def search_contacts_paginated(filter_groups: list, properties: list, max_pages: int = 10) -> list:
    """Paginate through HubSpot contact search results."""
    all_results = []
    after = None
    for _ in range(max_pages):
        body = {"filterGroups": filter_groups, "properties": properties, "limit": 100}
        if after:
            body["after"] = after
        data = hs_post("/crm/v3/objects/contacts/search", body)
        all_results.extend(data.get("results", []))
        after = data.get("paging", {}).get("next", {}).get("after")
        if not after:
            break
        time.sleep(0.1)
    return all_results


def ms_to_dt(ms_str: str) -> datetime | None:
    """Convert HubSpot millisecond timestamp string to UTC datetime."""
    if not ms_str:
        return None
    try:
        return datetime.fromtimestamp(int(ms_str) / 1000, tz=timezone.utc)
    except (ValueError, TypeError):
        return None


# ═════════════════════════════════════════════════════════════════════════════
# Data gathering
# ═════════════════════════════════════════════════════════════════════════════

def get_week_window() -> tuple[datetime, datetime]:
    """
    Return the reporting window: Mon 00:00 UTC through Sun 23:59 UTC for the
    most recent completed week (i.e., the 7 days ending last Sunday).
    """
    now = datetime.now(timezone.utc)
    # Go back to last Monday
    days_since_monday = now.weekday()  # Monday=0, Sunday=6
    last_monday = (now - timedelta(days=days_since_monday + 7)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    last_sunday = last_monday + timedelta(days=6, hours=23, minutes=59, seconds=59)
    return last_monday, last_sunday


def pull_hubspot_metrics(week_start: datetime, week_end: datetime) -> dict:
    """
    Pull HubSpot metrics for the reporting week.

    Queries used:
    1. All BR contacts (br_source=apollo) — total pipeline snapshot
    2. Contacts with br_sequence_assigned set (i.e., were enrolled during or before this week)
    3. Contacts with hs_email_last_reply_date in the week window (replies received)

    Note: HubSpot's Search API does not support "created this week" filters on
    engagement timestamps directly. We use contact properties (hs_email_last_reply_date,
    br_last_outreach_date) as proxies. For more granular engagement data, use the
    Engagements API (v3/objects/emails, v3/objects/notes).
    """
    week_start_ms = str(int(week_start.timestamp() * 1000))
    week_end_ms = str(int(week_end.timestamp() * 1000))

    contact_properties = [
        "firstname", "lastname", "email", "company",
        "br_source", "br_sequence_assigned", "br_expandi_status",
        "br_icp_score", "br_last_sequence_outcome",
        "br_last_outreach_date", "hs_email_last_reply_date",
        "hs_linkedin_url", "lifecyclestage", "br_total_sequences_enrolled",
        "br_icp_vertical",
    ]

    metrics = {
        "total_br_contacts": 0,
        "contacts_enrolled_this_week": 0,
        "contacts_replied_this_week": 0,
        "total_emails_sent_this_week": 0,  # Proxied from run log
        "with_linkedin_url": 0,
        "no_linkedin_url": 0,
        "pushed_campaign_a": 0,
        "pushed_campaign_b": 0,
        "not_pushed_to_expandi": 0,
        "sequence_cold_dtc": 0,
        "sequence_expansion": 0,
        "pending_outreach": 0,
        "opted_out_total": 0,
        "bounced_total": 0,
        "icp_verticals": defaultdict(int),
        "lifecycle_stages": defaultdict(int),
        "weekly_hot_leads": [],
    }

    # ── Query 1: Full BR contact snapshot ──────────────────────────────────
    log.info("Fetching full BR contact snapshot from HubSpot...")
    all_br = search_contacts_paginated(
        filter_groups=[{
            "filters": [
                {"propertyName": "br_source", "operator": "EQ", "value": "apollo"}
            ]
        }],
        properties=contact_properties,
    )
    metrics["total_br_contacts"] = len(all_br)

    for c in all_br:
        p = c.get("properties", {})

        # LinkedIn coverage
        if (p.get("hs_linkedin_url") or "").strip():
            metrics["with_linkedin_url"] += 1
        else:
            metrics["no_linkedin_url"] += 1

        # Expandi push status
        expandi = p.get("br_expandi_status") or ""
        if expandi == "pushed_campaign_a":
            metrics["pushed_campaign_a"] += 1
        elif expandi == "pushed_campaign_b":
            metrics["pushed_campaign_b"] += 1
        else:
            metrics["not_pushed_to_expandi"] += 1

        # Sequence distribution
        seq = p.get("br_sequence_assigned") or ""
        if seq == "cold_dtc_savings":
            metrics["sequence_cold_dtc"] += 1
        elif seq == "expansion_signal":
            metrics["sequence_expansion"] += 1
        elif not seq:
            metrics["pending_outreach"] += 1

        # Outcomes
        outcome = (p.get("br_last_sequence_outcome") or "").lower()
        if outcome == "opted_out":
            metrics["opted_out_total"] += 1
        elif outcome == "bounced":
            metrics["bounced_total"] += 1

        # ICP vertical breakdown
        vertical = p.get("br_icp_vertical") or "Unknown"
        metrics["icp_verticals"][vertical] += 1

        # Lifecycle stage
        stage = p.get("lifecyclestage") or "unknown"
        metrics["lifecycle_stages"][stage] += 1

    # ── Query 2: Contacts enrolled THIS week ────────────────────────────────
    # Proxy: contacts where br_last_outreach_date falls within the window
    log.info("Fetching contacts enrolled this week...")
    try:
        enrolled_this_week = search_contacts_paginated(
            filter_groups=[{
                "filters": [
                    {"propertyName": "br_source", "operator": "EQ", "value": "apollo"},
                    {"propertyName": "br_last_outreach_date", "operator": "GTE", "value": week_start_ms},
                    {"propertyName": "br_last_outreach_date", "operator": "LTE", "value": week_end_ms},
                ]
            }],
            properties=["firstname", "company", "br_sequence_assigned"],
            max_pages=5,
        )
        metrics["contacts_enrolled_this_week"] = len(enrolled_this_week)
    except Exception as e:
        log.warning("Could not fetch enrolled-this-week count: %s", e)

    # ── Query 3: Contacts that replied this week ─────────────────────────────
    log.info("Fetching contacts that replied this week...")
    try:
        replied_this_week = search_contacts_paginated(
            filter_groups=[{
                "filters": [
                    {"propertyName": "br_source", "operator": "EQ", "value": "apollo"},
                    {"propertyName": "hs_email_last_reply_date", "operator": "GTE", "value": week_start_ms},
                    {"propertyName": "hs_email_last_reply_date", "operator": "LTE", "value": week_end_ms},
                ]
            }],
            properties=[
                "firstname", "lastname", "company", "email", "jobtitle",
                "hs_email_last_reply_date", "br_icp_score",
            ],
            max_pages=3,
        )
        metrics["contacts_replied_this_week"] = len(replied_this_week)
        for c in replied_this_week:
            p = c.get("properties", {})
            metrics["weekly_hot_leads"].append({
                "name": f"{p.get('firstname', '')} {p.get('lastname', '')}".strip(),
                "company": p.get("company", ""),
                "email": p.get("email", ""),
                "title": p.get("jobtitle", ""),
                "replied": ms_to_dt(p.get("hs_email_last_reply_date")),
                "icp_score": p.get("br_icp_score", ""),
            })
    except Exception as e:
        log.warning("Could not fetch replied-this-week count: %s", e)

    # Convert defaultdicts to regular dicts for JSON serialization
    metrics["icp_verticals"] = dict(metrics["icp_verticals"])
    metrics["lifecycle_stages"] = dict(metrics["lifecycle_stages"])

    return metrics


def pull_daily_run_log_stats(week_start: datetime, week_end: datetime) -> dict:
    """
    Read daily_cron_run_log.json to get actual email send counts for the week.

    The daily cron writes a log entry after each run. This gives us ground-
    truth numbers for emails sent and LinkedIn contacts pushed per day,
    supplementing the HubSpot contact-count approximations.
    """
    if not DAILY_RUN_LOG_PATH.exists():
        log.info("No daily run log found at %s", DAILY_RUN_LOG_PATH)
        return {"runs": 0, "emails_sent": 0, "linkedin_pushed": 0, "errors": 0}

    try:
        log_entries = json.loads(DAILY_RUN_LOG_PATH.read_text())
    except Exception as e:
        log.warning("Could not parse daily run log: %s", e)
        return {"runs": 0, "emails_sent": 0, "linkedin_pushed": 0, "errors": 0}

    stats = {"runs": 0, "emails_sent": 0, "linkedin_pushed": 0, "errors": 0}
    for entry in log_entries:
        try:
            run_dt = datetime.fromisoformat(entry.get("run_date", ""))
            if week_start <= run_dt <= week_end:
                stats["runs"] += 1
                stats["emails_sent"] += entry.get("emails_sent", 0)
                stats["linkedin_pushed"] += entry.get("linkedin_pushed", 0)
                if entry.get("error"):
                    stats["errors"] += 1
        except Exception:
            continue

    return stats


# ═════════════════════════════════════════════════════════════════════════════
# Report formatting
# ═════════════════════════════════════════════════════════════════════════════

def format_slack_report(
    week_start: datetime,
    week_end: datetime,
    hs: dict,
    run_log: dict,
) -> str:
    """
    Format the weekly report as Slack-friendly markdown.

    Slack's mrkdwn format uses *bold*, _italic_, and > blockquotes.
    Avoid markdown headers (#) — Slack doesn't render them.

    The report is intentionally concise. Craig should be able to read it
    in < 2 minutes on his phone Monday morning.
    """
    week_label = f"{week_start.strftime('%b %d')} – {week_end.strftime('%b %d, %Y')}"

    # Reply rate calculation
    emails_sent = run_log.get("emails_sent", 0) or hs.get("contacts_enrolled_this_week", 0)
    replies = hs.get("contacts_replied_this_week", 0)
    reply_rate_str = (
        f"{round(replies / emails_sent * 100, 1)}%" if emails_sent > 0 else "N/A"
    )

    # LinkedIn coverage
    total_br = hs.get("total_br_contacts", 0)
    with_li = hs.get("with_linkedin_url", 0)
    no_li = hs.get("no_linkedin_url", 0)
    li_coverage_pct = round(with_li / total_br * 100, 1) if total_br > 0 else 0

    # Expandi stats
    cam_a = hs.get("pushed_campaign_a", 0)
    cam_b = hs.get("pushed_campaign_b", 0)
    not_pushed = hs.get("not_pushed_to_expandi", 0)

    # Queue
    pending = hs.get("pending_outreach", 0)

    # Top verticals
    verticals = sorted(
        hs.get("icp_verticals", {}).items(), key=lambda x: x[1], reverse=True
    )[:5]
    vertical_lines = " | ".join(f"{v}: {n}" for v, n in verticals)

    # Daily runs health
    runs = run_log.get("runs", 0)
    run_errors = run_log.get("errors", 0)
    run_health = "✅ All runs OK" if run_errors == 0 else f"⚠️ {run_errors} error(s)"

    # Hot leads section
    hot_lead_lines = ""
    weekly_hot = hs.get("weekly_hot_leads", [])
    if weekly_hot:
        for lead in weekly_hot[:5]:  # Max 5 in Slack to keep it readable
            replied_str = lead["replied"].strftime("%a %b %d") if lead.get("replied") else "?"
            hot_lead_lines += (
                f"\n> • *{lead['name']}* — {lead['company']}"
                f" ({lead.get('title', 'N/A')}) — replied {replied_str}"
            )
    else:
        hot_lead_lines = "\n> _No replies recorded this week_"

    report = f"""
*Broad Reach Outbound — Weekly Report*
*Week of {week_label}*
━━━━━━━━━━━━━━━━━━━━━━━━

*📧 Email Channel*
• Emails sent this week: *{emails_sent}*
• Contacts enrolled: *{hs.get('contacts_enrolled_this_week', 0)}*
• Replies received: *{replies}*
• Reply rate: *{reply_rate_str}*
• Cold DTC Savings sequence: {hs.get('sequence_cold_dtc', 0)}
• Expansion Signal sequence: {hs.get('sequence_expansion', 0)}

*💼 LinkedIn Channel (Expandi)*
• Campaign A (cold_dtc_savings / 770808): *{cam_a}* pushed
• Campaign B (expansion_signal / 770814): *{cam_b}* pushed
• Contacts with LinkedIn URL: {with_li} ({li_coverage_pct}% coverage)
• No LinkedIn URL (email-only): *{no_li}*

*🔥 Hot Leads This Week ({replies} replies)*{hot_lead_lines}

*📊 Pipeline Health*
• Total BR contacts in HubSpot: {total_br}
• Pending outreach (not yet enrolled): *{pending}*
• Opted out (all-time): {hs.get('opted_out_total', 0)}
• Bounced (all-time): {hs.get('bounced_total', 0)}

*⚙️ Cron Health ({runs}/7 runs expected)*
• Status: {run_health}
• Emails sent via cron: {run_log.get('emails_sent', 0)}
• LinkedIn pushed via cron: {run_log.get('linkedin_pushed', 0)}

*🏷️ Top ICP Verticals*
{vertical_lines or '_No verticals recorded_'}

_Report generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}_
""".strip()

    return report


# ═════════════════════════════════════════════════════════════════════════════
# Delivery: Slack
# ═════════════════════════════════════════════════════════════════════════════

def post_to_slack(message: str) -> bool:
    """
    Post the weekly report to Slack.

    Supports two methods:
    1. Incoming Webhook URL (SLACK_WEBHOOK_URL) — simplest, no OAuth needed
    2. Bot token + channel (SLACK_BOT_TOKEN + SLACK_CHANNEL) — more flexible

    Prefer the webhook method for this use case.

    Slack Incoming Webhooks: https://api.slack.com/messaging/webhooks
    Slack chat.postMessage API: https://api.slack.com/methods/chat.postMessage
    """
    if SLACK_WEBHOOK_URL:
        try:
            resp = requests.post(
                SLACK_WEBHOOK_URL,
                json={"text": message, "mrkdwn": True},
                timeout=10,
            )
            if resp.status_code == 200 and resp.text == "ok":
                log.info("Report posted to Slack via webhook")
                return True
            else:
                log.warning("Slack webhook returned %s: %s", resp.status_code, resp.text[:200])
        except Exception as e:
            log.error("Slack webhook failed: %s", e)

    if SLACK_BOT_TOKEN:
        try:
            resp = requests.post(
                "https://slack.com/api/chat.postMessage",
                headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}", "Content-Type": "application/json"},
                json={"channel": SLACK_CHANNEL, "text": message, "mrkdwn": True},
                timeout=10,
            )
            data = resp.json()
            if data.get("ok"):
                log.info("Report posted to Slack via bot token to %s", SLACK_CHANNEL)
                return True
            else:
                log.warning("Slack bot post failed: %s", data.get("error", "unknown"))
        except Exception as e:
            log.error("Slack bot post exception: %s", e)

    log.warning("No Slack credentials configured — report not sent to Slack")
    return False


# ═════════════════════════════════════════════════════════════════════════════
# Delivery: Notion dashboard update
# ═════════════════════════════════════════════════════════════════════════════

def update_notion_weekly(
    week_label: str,
    hs: dict,
    run_log: dict,
) -> None:
    """
    Update the Notion dashboard with this week's performance metrics.

    Adapt the property names to match your actual Notion database schema.
    Notion API: https://developers.notion.com/reference/patch-page
    """
    if not NOTION_TOKEN or not NOTION_DASHBOARD_PAGE_ID:
        log.info("Notion credentials not configured — skipping dashboard update")
        return

    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28",
    }

    properties = {
        "Week": {"rich_text": [{"type": "text", "text": {"content": week_label}}]},
        "Emails Sent": {"number": run_log.get("emails_sent", 0)},
        "Replies": {"number": hs.get("contacts_replied_this_week", 0)},
        "LinkedIn Pushed": {"number": hs.get("pushed_campaign_a", 0) + hs.get("pushed_campaign_b", 0)},
        "Total BR Contacts": {"number": hs.get("total_br_contacts", 0)},
        "Pending Outreach": {"number": hs.get("pending_outreach", 0)},
        "No LinkedIn URL": {"number": hs.get("no_linkedin_url", 0)},
        "Last Updated": {"date": {"start": datetime.now(timezone.utc).isoformat()}},
    }

    resp = requests.patch(
        f"https://api.notion.com/v1/pages/{NOTION_DASHBOARD_PAGE_ID}",
        headers=headers,
        json={"properties": properties},
        timeout=15,
    )
    if resp.status_code == 200:
        log.info("Notion dashboard updated for week %s", week_label)
    else:
        log.warning("Notion update failed: %s — %s", resp.status_code, resp.text[:200])


# ═════════════════════════════════════════════════════════════════════════════
# Main entry
# ═════════════════════════════════════════════════════════════════════════════

def generate_weekly_report() -> dict:
    """
    Generate and deliver the weekly outbound performance report.

    Returns a summary dict for logging.
    """
    run_start = datetime.now(timezone.utc)
    log.info("═" * 60)
    log.info("Broad Reach Weekly Performance Report — %s", run_start.strftime("%Y-%m-%d %H:%M UTC"))
    log.info("═" * 60)

    week_start, week_end = get_week_window()
    week_label = f"{week_start.strftime('%b %d')} – {week_end.strftime('%b %d, %Y')}"
    log.info("Reporting window: %s to %s", week_start.isoformat(), week_end.isoformat())

    # Gather data
    log.info("Pulling HubSpot metrics...")
    hs_metrics = pull_hubspot_metrics(week_start, week_end)
    log.info("Reading daily run log...")
    run_log_stats = pull_daily_run_log_stats(week_start, week_end)

    # Format report
    log.info("Formatting report...")
    slack_report = format_slack_report(week_start, week_end, hs_metrics, run_log_stats)

    # Always print to stdout (useful for debugging and Azure Functions logs)
    print("\n" + "=" * 60)
    print(slack_report)
    print("=" * 60 + "\n")

    # Deliver
    slack_ok = post_to_slack(slack_report)
    update_notion_weekly(week_label, hs_metrics, run_log_stats)

    summary = {
        "report_date": run_start.isoformat(),
        "week": week_label,
        "slack_delivered": slack_ok,
        "emails_sent_this_week": run_log_stats.get("emails_sent", 0),
        "replies_this_week": hs_metrics.get("contacts_replied_this_week", 0),
        "linkedin_pushed_cumulative": (
            hs_metrics.get("pushed_campaign_a", 0) + hs_metrics.get("pushed_campaign_b", 0)
        ),
        "total_br_contacts": hs_metrics.get("total_br_contacts", 0),
        "pending_outreach": hs_metrics.get("pending_outreach", 0),
    }

    # Write to weekly report log (keep last 52 weeks)
    report_log = []
    if WEEKLY_REPORT_LOG_PATH.exists():
        try:
            report_log = json.loads(WEEKLY_REPORT_LOG_PATH.read_text())
        except Exception:
            report_log = []
    report_log.append(summary)
    report_log = report_log[-52:]
    WEEKLY_REPORT_LOG_PATH.write_text(json.dumps(report_log, indent=2))

    elapsed = (datetime.now(timezone.utc) - run_start).total_seconds()
    log.info("Weekly report complete in %.1fs | Slack: %s", elapsed, "OK" if slack_ok else "FAILED")
    return summary


# ═════════════════════════════════════════════════════════════════════════════
# Entrypoint
# ═════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    """
    Standalone execution for local testing.

    Usage:
        python weekly_report_cron.py

    The report will be printed to stdout. If SLACK_WEBHOOK_URL or
    SLACK_BOT_TOKEN is set, it will also be posted to Slack.

    Required environment variables:
        HUBSPOT_PAT           — HubSpot private app token
        SLACK_WEBHOOK_URL     — Slack incoming webhook URL (preferred)
        SLACK_BOT_TOKEN       — Slack bot token (alternative)
        SLACK_CHANNEL         — Slack channel (e.g. #outbound-machine)
        NOTION_TOKEN          — Notion integration token (optional)
        NOTION_DASHBOARD_PAGE_ID — Notion page to update (optional)

    To test without Slack: leave SLACK_WEBHOOK_URL and SLACK_BOT_TOKEN unset.
    The report will only print to stdout.
    """
    if not HUBSPOT_PAT:
        print("ERROR: HUBSPOT_PAT environment variable is not set.")
        sys.exit(1)

    result = generate_weekly_report()
    print("\n── Run Summary ──")
    print(json.dumps(result, indent=2, default=str))
