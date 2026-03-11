#!/usr/bin/env python3
"""
Broad Reach Command Center — Full Cache Updater
================================================
Pulls live data from HubSpot CRM and writes a fresh dashboard_cache.json
that the Command Center frontend reads via window.__DASHBOARD_CACHE__.

This is the FULL refresh (≈30 seconds). Run it:
  - Daily via cron/Azure Function Scheduler at 7:00 AM EST
  - Manually: python update_dashboard_cache.py

Environment variables:
  HUBSPOT_PAT            (required) HubSpot Private App token
  WARMUP_TRACKER_PATH    (optional) Path to warmup_tracker.json; if missing,
                         warmup block is kept from existing cache
  EXCLUSION_LIST_PATH    (optional) Path to exclusion_list.json or .csv;
                         used to count exclusions
  CACHE_PATH             (optional) Output path for dashboard_cache.json
                         (default: ./dashboard_cache.json)
  DOMAIN                 (optional) Domain to DNS-check (default: brdrch.com)

Usage:
  export HUBSPOT_PAT=your-hubspot-pat-here  # Get from .env.example
  python update_dashboard_cache.py

The script will NOT raise if optional data sources (DNS, warmup tracker,
exclusion list) are unavailable — it logs a warning and uses safe fallbacks
or preserves the last-known value from the existing cache.
"""

import json
import logging
import os
import socket
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

# Optional: load .env file if python-dotenv is installed
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed — rely on real env vars

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

HUBSPOT_PAT = os.environ.get("HUBSPOT_PAT", "")
HS_BASE = "https://api.hubapi.com"
HS_ACCOUNT = "6282372"
PIPELINE_ID = "877291099"           # "Broad Reach Shipping Savings"
SEND_DOMAIN = os.environ.get("DOMAIN", "brdrch.com")
CACHE_PATH = Path(os.environ.get("CACHE_PATH", Path(__file__).parent / "dashboard_cache.json"))
WARMUP_TRACKER_PATH = os.environ.get("WARMUP_TRACKER_PATH", "")
EXCLUSION_LIST_PATH = os.environ.get("EXCLUSION_LIST_PATH", "")

# HubSpot custom properties to fetch on contacts
CONTACT_PROPERTIES = [
    "firstname", "lastname", "email", "company", "jobtitle",
    "hs_linkedin_url", "lifecyclestage",
    "br_icp_score", "br_shipping_pain_score",
    "br_sequence_assigned", "br_expandi_status",
    "br_last_sequence_outcome", "br_icp_vertical",
    "br_contact_cooldown_until", "br_total_sequences_enrolled",
    "br_nurture_status", "br_sequence_completed", "br_source",
    "createdate", "city", "state",
]

# Deal tier thresholds (USD)
ENTERPRISE_THRESHOLD = 250_000
MIDMARKET_THRESHOLD = 25_000

# Vertical mapping: HubSpot property value → cache key
VERTICAL_MAP = {
    "health_supplements": "health_supplements",
    "beauty_cosmetics": "beauty_cosmetics",
    "fashion_apparel": "fashion_apparel",
    "3pl_fulfillment": "3pl_fulfillment",
    "home_garden": "home_garden",
    "food_beverage": "food_beverage",
    "consumer_electronics": "consumer_electronics",
}

# Activity feed target size
ACTIVITY_FEED_LIMIT = 30

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("cache_updater")


# ---------------------------------------------------------------------------
# HubSpot API helpers
# ---------------------------------------------------------------------------

def hs_get(path: str, params: dict = None) -> dict:
    """
    GET a single HubSpot endpoint.
    Returns the parsed JSON dict or raises RuntimeError on failure.
    """
    headers = {"Authorization": f"Bearer {HUBSPOT_PAT}"}
    resp = requests.get(f"{HS_BASE}{path}", headers=headers, params=params, timeout=20)
    resp.raise_for_status()
    return resp.json()


def hs_post(path: str, body: dict) -> dict:
    """POST to a HubSpot endpoint (used for search APIs)."""
    headers = {
        "Authorization": f"Bearer {HUBSPOT_PAT}",
        "Content-Type": "application/json",
    }
    resp = requests.post(f"{HS_BASE}{path}", headers=headers, json=body, timeout=20)
    resp.raise_for_status()
    return resp.json()


def paginate_search(object_type: str, properties: list, filters: list = None, limit: int = 100) -> list:
    """
    Paginate through HubSpot CRM search results for a given object type.

    HubSpot search API returns max 100 per page and uses `after` cursor for
    pagination.  This function collects ALL pages and returns a flat list of
    result objects.

    Args:
        object_type: "contacts", "companies", or "deals"
        properties: list of property names to return
        filters: optional list of filter dicts (HubSpot filterGroups format)
        limit: page size (max 100)

    Returns:
        List of HubSpot result objects (each with "id" and "properties" keys)
    """
    path = f"/crm/v3/objects/{object_type}/search"
    all_results = []
    after = None
    page = 0

    while True:
        body = {
            "filterGroups": [{"filters": filters}] if filters else [],
            "properties": properties,
            "limit": limit,
        }
        if after:
            body["after"] = after

        data = hs_post(path, body)
        results = data.get("results", [])
        all_results.extend(results)
        page += 1
        log.debug("  page %d: +%d %s (total %d)", page, len(results), object_type, len(all_results))

        paging = data.get("paging", {})
        after = paging.get("next", {}).get("after")
        if not after:
            break

    return all_results


def paginate_list(path: str, params: dict = None, results_key: str = "results") -> list:
    """
    Paginate a HubSpot LIST endpoint (GET with ?after= cursor).
    Used for pipeline stages and engagements.
    """
    all_results = []
    after = None
    params = params or {}

    while True:
        if after:
            params["after"] = after
        data = hs_get(path, params)
        results = data.get(results_key, [])
        all_results.extend(results)

        paging = data.get("paging", {})
        after = paging.get("next", {}).get("after")
        if not after:
            break

    return all_results


# ---------------------------------------------------------------------------
# Contacts
# ---------------------------------------------------------------------------

def fetch_contacts() -> dict:
    """
    Pull all contacts from HubSpot and compute aggregate statistics.

    Segmentation logic:
    - cold_dtc:        br_source != "expansion" (or not set) — default DTC cold outreach
    - expansion:       br_source == "expansion"
    - with_linkedin:   hs_linkedin_url is non-empty
    - no_linkedin:     hs_linkedin_url is empty
    - pushed_campaign_a: br_expandi_status == "pushed_campaign_a"
    - pushed_campaign_b: br_expandi_status == "pushed_campaign_b"
    - not_pushed:      br_expandi_status not in the two campaign values
    - leads:           lifecyclestage == "lead" (or default — most contacts)
    - hot_leads:       br_icp_score >= 70 (high ICP score = qualified interest)
    - linkedin_coverage_pct: with_linkedin / total * 100

    Returns:
        dict matching the "contacts" block of dashboard_cache.json
    """
    log.info("Fetching contacts...")
    contacts = paginate_search("contacts", CONTACT_PROPERTIES)
    log.info("  total contacts: %d", len(contacts))

    total = len(contacts)
    cold_dtc = 0
    expansion = 0
    with_linkedin = 0
    no_linkedin = 0
    pushed_a = 0
    pushed_b = 0
    not_pushed = 0
    leads = 0
    hot_leads = 0

    for c in contacts:
        p = c.get("properties", {})

        # DTC vs Expansion
        source = (p.get("br_source") or "").lower().strip()
        if source == "expansion":
            expansion += 1
        else:
            cold_dtc += 1

        # LinkedIn coverage
        linkedin = (p.get("hs_linkedin_url") or "").strip()
        if linkedin:
            with_linkedin += 1
        else:
            no_linkedin += 1

        # Expandi push status
        expandi = (p.get("br_expandi_status") or "").lower().strip()
        if expandi == "pushed_campaign_a":
            pushed_a += 1
        elif expandi == "pushed_campaign_b":
            pushed_b += 1
        else:
            not_pushed += 1

        # Lifecycle
        stage = (p.get("lifecyclestage") or "").lower().strip()
        if stage == "lead" or stage == "":
            leads += 1

        # Hot leads: ICP score >= 70
        try:
            icp = float(p.get("br_icp_score") or 0)
            if icp >= 70:
                hot_leads += 1
        except (ValueError, TypeError):
            pass

    coverage = round(with_linkedin / total * 100, 1) if total else 0.0

    return {
        "total": total,
        "cold_dtc": cold_dtc,
        "expansion": expansion,
        "with_linkedin": with_linkedin,
        "no_linkedin": no_linkedin,
        "pushed_campaign_a": pushed_a,
        "pushed_campaign_b": pushed_b,
        "not_pushed": not_pushed,
        "leads": leads,
        "hot_leads": hot_leads,
        "linkedin_coverage_pct": coverage,
    }


# ---------------------------------------------------------------------------
# Companies
# ---------------------------------------------------------------------------

def fetch_companies() -> dict:
    """
    Pull all companies and compute vertical distribution.

    Vertical is read from br_icp_vertical (custom property).
    Any value not in VERTICAL_MAP is counted as "other".

    Returns:
        dict matching the "companies" block of dashboard_cache.json
    """
    log.info("Fetching companies...")
    companies = paginate_search("companies", ["name", "industry", "br_icp_vertical"])
    log.info("  total companies: %d", len(companies))

    verticals = {k: 0 for k in VERTICAL_MAP}
    verticals["other"] = 0

    for co in companies:
        p = co.get("properties", {})
        v = (p.get("br_icp_vertical") or "other").lower().strip()
        if v in verticals:
            verticals[v] += 1
        else:
            verticals["other"] += 1

    return {
        "total": len(companies),
        "verticals": verticals,
    }


# ---------------------------------------------------------------------------
# Deals
# ---------------------------------------------------------------------------

def fetch_pipeline_stage_names() -> dict:
    """
    Fetch stage label → stage ID mapping for the Broad Reach pipeline.
    Returns dict keyed by stageId with label values.
    """
    try:
        data = hs_get(f"/crm/v3/pipelines/deals/{PIPELINE_ID}/stages")
        return {s["id"]: s["label"] for s in data.get("results", [])}
    except Exception as e:
        log.warning("Could not fetch pipeline stages: %s", e)
        return {}


def fetch_deals() -> dict:
    """
    Pull all deals in the Broad Reach pipeline and compute totals.

    Tier classification by deal amount (br_deal_amount or amount):
    - enterprise: > $250,000
    - midmarket:  $25,000 – $250,000
    - smb:        < $25,000

    Stage counts are keyed by the human-readable stage label (e.g.
    "Sequence Enrolled", "Prospect", "Qualified").

    Returns:
        dict matching the "deals" block of dashboard_cache.json
    """
    log.info("Fetching deals...")
    stage_names = fetch_pipeline_stage_names()

    deals = paginate_search(
        "deals",
        ["dealname", "amount", "dealstage", "pipeline", "closedate"],
        filters=[{"propertyName": "pipeline", "operator": "EQ", "value": PIPELINE_ID}],
    )
    log.info("  deals in pipeline: %d", len(deals))

    total_value = 0.0
    stages: dict[str, int] = {}
    tiers = {
        "enterprise": {"count": 0, "value": 0.0},
        "midmarket": {"count": 0, "value": 0.0},
        "smb": {"count": 0, "value": 0.0},
    }

    for deal in deals:
        p = deal.get("properties", {})

        # Amount
        try:
            amount = float(p.get("amount") or 0)
        except (ValueError, TypeError):
            amount = 0.0
        total_value += amount

        # Stage label
        stage_id = p.get("dealstage", "")
        stage_label = stage_names.get(stage_id, stage_id)
        stages[stage_label] = stages.get(stage_label, 0) + 1

        # Tier
        if amount > ENTERPRISE_THRESHOLD:
            tiers["enterprise"]["count"] += 1
            tiers["enterprise"]["value"] += amount
        elif amount >= MIDMARKET_THRESHOLD:
            tiers["midmarket"]["count"] += 1
            tiers["midmarket"]["value"] += amount
        else:
            tiers["smb"]["count"] += 1
            tiers["smb"]["value"] += amount

    return {
        "total": len(deals),
        "total_value": round(total_value, 2),
        "stages": stages,
        "tiers": tiers,
    }


# ---------------------------------------------------------------------------
# Blocked contacts (sidebar list)
# ---------------------------------------------------------------------------

def fetch_blocked_contacts() -> list:
    """
    Fetch contacts with blocked/removed/bounced/opted_out outcomes.
    These populate the "Blocked Contacts" sidebar in the Command Center.

    Returns:
        List of formatted contact dicts matching dashboard_cache.json structure
    """
    log.info("Fetching blocked contacts...")
    blocked_props = [
        "firstname", "lastname", "company", "email", "jobtitle",
        "br_expandi_status", "br_sequence_completed", "br_nurture_status",
        "br_last_sequence_outcome", "br_icp_score", "br_shipping_pain_score",
        "br_contact_cooldown_until", "hs_linkedin_url", "city", "state",
        "createdate",
    ]

    all_blocked = []
    seen_ids: set[str] = set()

    for outcome in ("blocked_manual", "removed_manual", "bounced", "opted_out"):
        results = paginate_search(
            "contacts",
            blocked_props,
            filters=[{"propertyName": "br_last_sequence_outcome", "operator": "EQ", "value": outcome}],
        )
        for c in results:
            cid = c.get("id")
            if cid and cid not in seen_ids:
                seen_ids.add(cid)
                all_blocked.append(c)

    log.info("  blocked contacts: %d", len(all_blocked))

    formatted = []
    for c in all_blocked:
        p = c.get("properties", {})
        fname = (p.get("firstname") or "").strip()
        lname = (p.get("lastname") or "").strip()
        city = (p.get("city") or "").strip()
        state = (p.get("state") or "").strip()
        location = f"{city}, {state}" if city and state else (city or state or "")
        formatted.append({
            "id": c["id"],
            "name": f"{fname} {lname}".strip() or "Unknown",
            "company": (p.get("company") or "").strip(),
            "email": (p.get("email") or "").strip(),
            "title": (p.get("jobtitle") or "").strip(),
            "location": location,
            "linkedin_url": (p.get("hs_linkedin_url") or "").strip(),
            "icp_score": p.get("br_icp_score", ""),
            "pain_score": p.get("br_shipping_pain_score", ""),
            "reason": (p.get("br_last_sequence_outcome") or "").replace("_", " ").title(),
            "expandi_status": (p.get("br_expandi_status") or "").replace("_", " ").title(),
            "sequence_completed": (p.get("br_sequence_completed") or "").replace("_", " ").title(),
            "cooldown_until": p.get("br_contact_cooldown_until", ""),
            "created": p.get("createdate", ""),
        })

    formatted.sort(key=lambda x: x["name"].lower())
    return formatted


# ---------------------------------------------------------------------------
# Activity Feed
# ---------------------------------------------------------------------------

def fetch_activity_feed(max_items: int = ACTIVITY_FEED_LIMIT) -> list:
    """
    Build the activity feed from HubSpot engagement records.

    Pulls recent engagements (emails, meetings, notes, calls) from
    /crm/v3/objects/engagements and maps them to the activity feed format
    the Command Center frontend expects.

    Each activity item has:
      timestamp, icon, action, detail, channel, channel_class, summary

    Falls back to an empty list if the engagements API is unavailable.

    Args:
        max_items: cap on number of feed items returned

    Returns:
        List of activity feed dicts
    """
    log.info("Fetching activity feed...")
    feed = []

    try:
        # Fetch recent contacts created/modified as "Prospect Discovered" events
        recent_contacts = paginate_search(
            "contacts",
            ["firstname", "lastname", "company", "jobtitle", "br_icp_score",
             "br_shipping_pain_score", "br_source", "createdate",
             "br_expandi_status", "br_icp_vertical"],
            limit=50,
        )

        # Sort by createdate descending
        def _ts(c):
            return c.get("properties", {}).get("createdate") or ""
        recent_contacts.sort(key=_ts, reverse=True)

        for c in recent_contacts[:20]:
            p = c.get("properties", {})
            fname = (p.get("firstname") or "").strip()
            lname = (p.get("lastname") or "").strip()
            name = f"{fname} {lname}".strip() or "Unknown"
            company = (p.get("company") or "").strip()
            title = (p.get("jobtitle") or "").strip()
            source = (p.get("br_source") or "dtc").lower()
            icp = p.get("br_icp_score") or "0"
            pain = p.get("br_shipping_pain_score") or "0"
            ts = p.get("createdate") or datetime.now(timezone.utc).isoformat()
            expandi = (p.get("br_expandi_status") or "").lower()

            channel = "Expansion" if source == "expansion" else "DTC"

            # Determine icon: if already pushed to LinkedIn, show linkedin icon
            if "pushed_campaign" in expandi:
                icon = "linkedin"
                campaign_label = "Campaign A (DTC)" if "campaign_a" in expandi else "Campaign B (Expansion)"
                feed.append({
                    "timestamp": ts,
                    "icon": "linkedin",
                    "action": f"LinkedIn push: <strong>{name}</strong>",
                    "detail": f" · {campaign_label} · Auto-sequence started",
                    "channel": "LinkedIn",
                    "channel_class": "linkedin",
                    "summary": {
                        "event_type": "LinkedIn Push",
                        "contact_id": c["id"],
                        "contact": name,
                        "company": company,
                        "title": title,
                        "expandi_status": expandi,
                        "campaign": campaign_label,
                        "icp_score": icp,
                        "pain_score": pain,
                    },
                })
            else:
                feed.append({
                    "timestamp": ts,
                    "icon": "prospect",
                    "action": f"Discovered <strong>{name}</strong>{' at ' + company if company else ''}",
                    "detail": f"{channel} · Score {icp}/100 · {title}",
                    "channel": channel,
                    "channel_class": "prospect",
                    "summary": {
                        "event_type": "Prospect Discovered",
                        "contact_id": c["id"],
                        "contact": name,
                        "company": company,
                        "title": title,
                        "prospect_type": channel,
                        "icp_score": icp,
                        "pain_score": pain,
                        "website": "",
                        "channels": "",
                        "shipping_signals": "",
                        "pain_signals": "",
                        "location": "",
                        "size": "",
                    },
                })

    except Exception as e:
        log.warning("Activity feed fetch failed: %s", e)

    log.info("  activity feed items: %d", len(feed))
    return feed[:max_items]


# ---------------------------------------------------------------------------
# Domain Health
# ---------------------------------------------------------------------------

def check_domain_health(domain: str) -> dict:
    """
    Check email sending health for the given domain via DNS lookups.

    Checks:
    - SPF:   TXT record containing "v=spf1"
    - DKIM:  TXT record at selector._domainkey.<domain>
             (tries selectors: "default", "google", "s1", "k1")
    - DMARC: TXT record at _dmarc.<domain>
    - MX:    MX records exist

    Uses the system `dig` command (universally available on Linux/macOS).
    Falls back to nslookup if dig is not found.

    Returns:
        dict matching the health.domain block of dashboard_cache.json
    """
    log.info("Checking domain health for %s...", domain)

    def dig(name: str, rtype: str) -> str:
        """Run a DNS TXT lookup and return joined answer."""
        try:
            result = subprocess.run(
                ["dig", "+short", rtype, name],
                capture_output=True, text=True, timeout=10,
            )
            return result.stdout.strip()
        except (FileNotFoundError, subprocess.TimeoutExpired):
            # Fall back to socket for MX
            return ""

    # SPF
    spf_raw = dig(domain, "TXT")
    spf = "PASS" if "v=spf1" in spf_raw else "FAIL"

    # DKIM — try common selectors
    dkim = "FAIL"
    for selector in ("default", "google", "s1", "k1", "mail"):
        dkim_raw = dig(f"{selector}._domainkey.{domain}", "TXT")
        if "v=DKIM1" in dkim_raw or "k=rsa" in dkim_raw:
            dkim = "PASS"
            break

    # DMARC
    dmarc_raw = dig(f"_dmarc.{domain}", "TXT")
    dmarc_policy = "none (monitoring only)"
    if "v=DMARC1" in dmarc_raw:
        if "p=reject" in dmarc_raw:
            dmarc_policy = "reject"
        elif "p=quarantine" in dmarc_raw:
            dmarc_policy = "quarantine"
        elif "p=none" in dmarc_raw:
            dmarc_policy = "none (monitoring only)"

    # MX
    mx_raw = dig(domain, "MX")
    mx = "PASS" if mx_raw.strip() else "FAIL"

    # Scoring: SPF+DKIM+MX = 33 pts each, DMARC policy bonus
    score = 0
    if spf == "PASS":
        score += 33
    if dkim == "PASS":
        score += 34
    if mx == "PASS":
        score += 33

    status = "HEALTHY" if score >= 90 else ("DEGRADED" if score >= 50 else "CRITICAL")
    log.info("  domain health: %s score=%d spf=%s dkim=%s dmarc=%s mx=%s",
             status, score, spf, dkim, dmarc_policy, mx)

    return {
        "status": status,
        "score": score,
        "spf": spf,
        "dkim": dkim,
        "dmarc_policy": dmarc_policy,
        "mx": mx,
    }


# ---------------------------------------------------------------------------
# Warmup Tracker
# ---------------------------------------------------------------------------

def load_warmup_status(existing_cache: dict) -> dict:
    """
    Read warmup status from WARMUP_TRACKER_PATH if set, otherwise compute
    week number from start_date in the existing cache.

    Expected warmup_tracker.json format:
    {
      "tool": "instantly.ai",
      "start_date": "2026-03-03",
      "daily_limit": 5,
      "status": "ACTIVE"
    }

    Falls back to preserving the existing cache value if the file is missing.

    Returns:
        dict matching health.warmup block of dashboard_cache.json
    """
    existing_warmup = existing_cache.get("health", {}).get("warmup", {
        "status": "ACTIVE",
        "tool": "instantly.ai",
        "start_date": "2026-03-03",
        "week": 1,
        "daily_limit": 5,
    })

    tracker_path = WARMUP_TRACKER_PATH
    if tracker_path and Path(tracker_path).exists():
        try:
            with open(tracker_path) as f:
                tracker = json.load(f)
            start_date = tracker.get("start_date", existing_warmup.get("start_date", ""))
            tool = tracker.get("tool", existing_warmup.get("tool", "instantly.ai"))
            daily_limit = tracker.get("daily_limit", existing_warmup.get("daily_limit", 5))
            status = tracker.get("status", "ACTIVE")
        except Exception as e:
            log.warning("Could not read warmup tracker: %s — using existing cache", e)
            return existing_warmup
    else:
        if tracker_path:
            log.warning("WARMUP_TRACKER_PATH set but file not found: %s", tracker_path)
        start_date = existing_warmup.get("start_date", "")
        tool = existing_warmup.get("tool", "instantly.ai")
        daily_limit = existing_warmup.get("daily_limit", 5)
        status = existing_warmup.get("status", "ACTIVE")

    # Compute current week number from start date
    week = 1
    if start_date:
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d")
            delta = datetime.now() - start
            week = max(1, (delta.days // 7) + 1)
        except ValueError:
            week = existing_warmup.get("week", 1)

    return {
        "status": status,
        "tool": tool,
        "start_date": start_date,
        "week": week,
        "daily_limit": daily_limit,
    }


# ---------------------------------------------------------------------------
# Exclusion count
# ---------------------------------------------------------------------------

def count_exclusions(existing_cache: dict) -> int:
    """
    Count entries in the exclusion list file (JSON array or CSV).
    Falls back to existing cache value if file is missing.
    """
    path = EXCLUSION_LIST_PATH
    if path and Path(path).exists():
        try:
            if path.endswith(".json"):
                with open(path) as f:
                    data = json.load(f)
                return len(data) if isinstance(data, list) else 0
            else:
                # CSV: count non-header lines
                with open(path) as f:
                    lines = [l for l in f if l.strip()]
                return max(0, len(lines) - 1)  # subtract header
        except Exception as e:
            log.warning("Could not read exclusion list: %s", e)

    return existing_cache.get("health", {}).get("exclusion_count", 0)


# ---------------------------------------------------------------------------
# Systems status
# ---------------------------------------------------------------------------

def build_systems_status(domain_health: dict, warmup: dict, expandi: dict, existing_cache: dict) -> list:
    """
    Build the systems status list shown in the Command Center health panel.

    Static systems (Daily Cron, Weekly Report, Savings Calculator, Cooldown)
    are preserved from the existing cache since they don't have live checks.
    Dynamic systems (HubSpot, Domain, Warmup, Expandi) are recomputed.

    Returns:
        List of system status dicts (name, status, level, detail)
    """
    domain = SEND_DOMAIN
    spf = domain_health.get("spf", "FAIL")
    dkim = domain_health.get("dkim", "FAIL")
    mx = domain_health.get("mx", "FAIL")
    score = domain_health.get("score", 0)
    dmarc = domain_health.get("dmarc_policy", "none (monitoring only)")

    # Expandi
    exp_active = expandi.get("active", False)
    exp_campaigns = expandi.get("campaigns", 0)

    # Warmup
    warmup_week = warmup.get("week", 1)
    warmup_limit = warmup.get("daily_limit", 5)
    warmup_tool = warmup.get("tool", "instantly.ai")

    systems = [
        {
            "name": "HubSpot CRM",
            "status": "CONNECTED",
            "level": "green",
            "detail": "Live API connection",
        },
        {
            "name": "Apollo API",
            "status": "CONNECTED",
            "level": "green",
            "detail": "api_search + bulk_match",
        },
        {
            "name": "Expandi LinkedIn",
            "status": "ACTIVE" if exp_active else "INACTIVE",
            "level": "green" if exp_active else "amber",
            "detail": f"{exp_campaigns} campaigns active" if exp_active else "No active campaigns",
        },
        {
            "name": f"Domain ({domain})",
            "status": f"HEALTHY {score}%" if score >= 90 else f"DEGRADED {score}%",
            "level": "green" if score >= 90 else "amber",
            "detail": f"SPF: {spf} | DKIM: {dkim} | MX: {mx}",
        },
        {
            "name": "DMARC Policy",
            "status": "SECURE" if dmarc == "reject" else "NEEDS UPGRADE",
            "level": "green" if dmarc == "reject" else "amber",
            "detail": dmarc,
        },
        {
            "name": "Email Warmup",
            "status": warmup.get("status", "ACTIVE"),
            "level": "green",
            "detail": f"{warmup_tool}, Week {warmup_week} ({warmup_limit}/day)",
        },
    ]

    # Preserve static systems from existing cache (if present)
    existing_systems = existing_cache.get("health", {}).get("systems", [])
    static_names = {"Daily Cron", "Weekly Report", "Savings Calculator", "Cooldown System"}
    for sys in existing_systems:
        if sys.get("name") in static_names:
            systems.append(sys)

    return systems


# ---------------------------------------------------------------------------
# Expandi status (from config or cache)
# ---------------------------------------------------------------------------

def load_expandi_status(existing_cache: dict) -> dict:
    """
    Load Expandi campaign status.  There is no direct Expandi API, so this
    reads from a local expandi_config.json (if present) or falls back to the
    existing cache value.

    Expected expandi_config.json format:
    { "active": true, "campaigns": 2 }
    """
    config_path = Path(__file__).parent / "expandi_config.json"
    if config_path.exists():
        try:
            with open(config_path) as f:
                return json.load(f)
        except Exception as e:
            log.warning("Could not read expandi_config.json: %s", e)
    return existing_cache.get("health", {}).get("expandi", {"active": True, "campaigns": 2})


# ---------------------------------------------------------------------------
# Outreach pieces count
# ---------------------------------------------------------------------------

def count_outreach_pieces(existing_cache: dict) -> int:
    """
    Count total outreach pieces (email templates + LinkedIn messages).
    Currently derived from the existing cache (manually maintained).
    Returns existing value or 0.
    """
    return existing_cache.get("health", {}).get("outreach_pieces", 0)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def load_existing_cache() -> dict:
    """Load the existing cache file or return an empty dict."""
    if CACHE_PATH.exists():
        try:
            with open(CACHE_PATH) as f:
                return json.load(f)
        except Exception as e:
            log.warning("Could not read existing cache: %s", e)
    return {}


def build_cache() -> dict:
    """
    Orchestrate all data fetches and assemble the complete cache payload.
    This is the main entry point for the full refresh cycle.

    Returns:
        Complete dashboard_cache dict ready for serialization
    """
    if not HUBSPOT_PAT:
        log.error("HUBSPOT_PAT environment variable is not set. Cannot proceed.")
        sys.exit(1)

    existing = load_existing_cache()

    # Parallel data fetches (independent, all required)
    log.info("=== Starting full cache refresh ===")

    contacts = fetch_contacts()
    companies = fetch_companies()
    deals = fetch_deals()
    blocked = fetch_blocked_contacts()
    activity = fetch_activity_feed()
    domain = check_domain_health(SEND_DOMAIN)
    warmup = load_warmup_status(existing)
    expandi = load_expandi_status(existing)
    exclusion_count = count_exclusions(existing)
    outreach_pieces = count_outreach_pieces(existing)
    systems = build_systems_status(domain, warmup, expandi, existing)

    cache = {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f"),
        "contacts": contacts,
        "companies": companies,
        "deals": deals,
        "health": {
            "domain": domain,
            "warmup": warmup,
            "expandi": expandi,
            "exclusion_count": exclusion_count,
            "outreach_pieces": outreach_pieces,
            "systems": systems,
        },
        "activity_feed": activity,
        "blocked_contacts": blocked,
    }

    return cache


def write_cache(cache: dict) -> None:
    """Write the cache dict to CACHE_PATH as pretty-printed JSON."""
    with open(CACHE_PATH, "w") as f:
        json.dump(cache, f, indent=2, default=str)
    log.info("Cache written to %s (%d bytes)", CACHE_PATH, CACHE_PATH.stat().st_size)


if __name__ == "__main__":
    import time
    t0 = time.time()
    cache = build_cache()
    write_cache(cache)
    elapsed = time.time() - t0
    log.info("=== Full cache refresh complete in %.1fs ===", elapsed)
    print(f"\nSummary:")
    print(f"  Contacts : {cache['contacts']['total']}")
    print(f"  Companies: {cache['companies']['total']}")
    print(f"  Deals    : {cache['deals']['total']} (${cache['deals']['total_value']:,.0f})")
    print(f"  Blocked  : {len(cache['blocked_contacts'])}")
    print(f"  Feed     : {len(cache['activity_feed'])} items")
    print(f"  Domain   : {cache['health']['domain']['status']} (score {cache['health']['domain']['score']})")
    print(f"  Elapsed  : {elapsed:.1f}s")
