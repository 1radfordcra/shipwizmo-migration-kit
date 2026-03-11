#!/usr/bin/env python3
"""
Broad Reach Command Center — Fast KPI Refresh
==============================================
Lightweight cache updater that refreshes only the numeric KPIs:
contacts, companies, deals totals + deal stages & tiers.

Skips:
  - Activity feed rebuild
  - Domain DNS health checks
  - Blocked contacts list
  - Warmup / Expandi status

This makes it ~5 seconds vs ~30 seconds for the full refresh.

Typical use:
  - Intra-day top-of-hour refresh (e.g. every 2 hours via cron)
  - Post-import validation (run immediately after bulk HubSpot import)
  - Quick sanity check without burning API rate limits

Merge strategy:
  Read existing dashboard_cache.json → update contacts/companies/deals
  blocks → write back. All other blocks (health, activity_feed,
  blocked_contacts) are preserved unchanged.

Environment variables:
  HUBSPOT_PAT   (required) HubSpot Private App token
  CACHE_PATH    (optional) Path to dashboard_cache.json
                (default: ./dashboard_cache.json)

Usage:
  export HUBSPOT_PAT=your-hubspot-pat-here  # Get from .env.example
  python update_cache_fast.py
"""

import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

# Optional: load .env file if python-dotenv is installed
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

HUBSPOT_PAT = os.environ.get("HUBSPOT_PAT", "")
HS_BASE = "https://api.hubapi.com"
PIPELINE_ID = "877291099"           # "Broad Reach Shipping Savings"
CACHE_PATH = Path(os.environ.get("CACHE_PATH", Path(__file__).parent / "dashboard_cache.json"))

# Deal tier thresholds (USD) — must match update_dashboard_cache.py
ENTERPRISE_THRESHOLD = 250_000
MIDMARKET_THRESHOLD = 25_000

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("cache_fast")


# ---------------------------------------------------------------------------
# HubSpot helpers (minimal — only what this script needs)
# ---------------------------------------------------------------------------

def _headers() -> dict:
    return {"Authorization": f"Bearer {HUBSPOT_PAT}"}


def hs_post(path: str, body: dict) -> dict:
    """POST to a HubSpot search endpoint."""
    resp = requests.post(
        f"{HS_BASE}{path}",
        headers={**_headers(), "Content-Type": "application/json"},
        json=body,
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json()


def hs_get(path: str, params: dict = None) -> dict:
    """GET a HubSpot endpoint."""
    resp = requests.get(f"{HS_BASE}{path}", headers=_headers(), params=params, timeout=20)
    resp.raise_for_status()
    return resp.json()


def _paginate_search(object_type: str, properties: list, filters: list = None) -> list:
    """
    Paginate HubSpot CRM search for an object type.
    Returns flat list of all result objects.
    Kept intentionally minimal — only fetches the properties listed.
    """
    path = f"/crm/v3/objects/{object_type}/search"
    results = []
    after = None

    while True:
        body: dict = {
            "filterGroups": [{"filters": filters}] if filters else [],
            "properties": properties,
            "limit": 100,
        }
        if after:
            body["after"] = after

        data = hs_post(path, body)
        results.extend(data.get("results", []))

        after = data.get("paging", {}).get("next", {}).get("after")
        if not after:
            break

    return results


# ---------------------------------------------------------------------------
# Fast KPI fetches
# ---------------------------------------------------------------------------

def fast_contacts() -> dict:
    """
    Fetch contact counts only — no activity or detail properties.

    Computes: total, cold_dtc, expansion, with_linkedin, no_linkedin,
              pushed_campaign_a, pushed_campaign_b, not_pushed,
              leads, hot_leads, linkedin_coverage_pct.

    Only fetches the 4 properties needed for segmentation.
    """
    log.info("Contacts...")
    contacts = _paginate_search(
        "contacts",
        ["br_source", "br_expandi_status", "hs_linkedin_url",
         "lifecyclestage", "br_icp_score"],
    )
    total = len(contacts)

    cold_dtc = expansion = 0
    with_linkedin = no_linkedin = 0
    pushed_a = pushed_b = not_pushed = 0
    leads = hot_leads = 0

    for c in contacts:
        p = c.get("properties", {})

        source = (p.get("br_source") or "").lower().strip()
        if source == "expansion":
            expansion += 1
        else:
            cold_dtc += 1

        if (p.get("hs_linkedin_url") or "").strip():
            with_linkedin += 1
        else:
            no_linkedin += 1

        expandi = (p.get("br_expandi_status") or "").lower().strip()
        if expandi == "pushed_campaign_a":
            pushed_a += 1
        elif expandi == "pushed_campaign_b":
            pushed_b += 1
        else:
            not_pushed += 1

        stage = (p.get("lifecyclestage") or "").lower().strip()
        if stage in ("lead", ""):
            leads += 1

        try:
            if float(p.get("br_icp_score") or 0) >= 70:
                hot_leads += 1
        except (ValueError, TypeError):
            pass

    coverage = round(with_linkedin / total * 100, 1) if total else 0.0
    log.info("  contacts: %d (DTC %d | Exp %d | LinkedIn %d%%)", total, cold_dtc, expansion, coverage)

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


def fast_companies() -> dict:
    """
    Fetch company count and vertical distribution.
    Only fetches br_icp_vertical — minimal payload.
    """
    log.info("Companies...")
    companies = _paginate_search("companies", ["br_icp_vertical"])
    total = len(companies)

    verticals: dict = {
        "health_supplements": 0,
        "beauty_cosmetics": 0,
        "fashion_apparel": 0,
        "3pl_fulfillment": 0,
        "home_garden": 0,
        "food_beverage": 0,
        "consumer_electronics": 0,
        "other": 0,
    }

    for co in companies:
        v = (co.get("properties", {}).get("br_icp_vertical") or "other").lower().strip()
        if v in verticals:
            verticals[v] += 1
        else:
            verticals["other"] += 1

    log.info("  companies: %d", total)
    return {"total": total, "verticals": verticals}


def fast_deals() -> dict:
    """
    Fetch deal totals, stage counts, and tier breakdown.
    Fetches pipeline stages for human-readable stage labels.
    """
    log.info("Deals...")

    # Get stage labels
    stage_names: dict = {}
    try:
        data = hs_get(f"/crm/v3/pipelines/deals/{PIPELINE_ID}/stages")
        stage_names = {s["id"]: s["label"] for s in data.get("results", [])}
    except Exception as e:
        log.warning("  Could not fetch stage names: %s — using raw IDs", e)

    deals = _paginate_search(
        "deals",
        ["amount", "dealstage"],
        filters=[{"propertyName": "pipeline", "operator": "EQ", "value": PIPELINE_ID}],
    )

    total_value = 0.0
    stages: dict = {}
    tiers = {
        "enterprise": {"count": 0, "value": 0.0},
        "midmarket": {"count": 0, "value": 0.0},
        "smb": {"count": 0, "value": 0.0},
    }

    for deal in deals:
        p = deal.get("properties", {})
        try:
            amount = float(p.get("amount") or 0)
        except (ValueError, TypeError):
            amount = 0.0
        total_value += amount

        stage_id = p.get("dealstage", "")
        label = stage_names.get(stage_id, stage_id)
        stages[label] = stages.get(label, 0) + 1

        if amount > ENTERPRISE_THRESHOLD:
            tiers["enterprise"]["count"] += 1
            tiers["enterprise"]["value"] += amount
        elif amount >= MIDMARKET_THRESHOLD:
            tiers["midmarket"]["count"] += 1
            tiers["midmarket"]["value"] += amount
        else:
            tiers["smb"]["count"] += 1
            tiers["smb"]["value"] += amount

    log.info("  deals: %d (${:,.0f})".format(total_value), len(deals))
    return {
        "total": len(deals),
        "total_value": round(total_value, 2),
        "stages": stages,
        "tiers": tiers,
    }


# ---------------------------------------------------------------------------
# Cache merge
# ---------------------------------------------------------------------------

def load_cache() -> dict:
    """Load and parse the existing dashboard_cache.json."""
    if not CACHE_PATH.exists():
        log.warning("No existing cache at %s — will create fresh file", CACHE_PATH)
        return {}
    try:
        with open(CACHE_PATH) as f:
            return json.load(f)
    except Exception as e:
        log.warning("Could not read existing cache (%s) — will create fresh file", e)
        return {}


def merge_and_write(contacts: dict, companies: dict, deals: dict) -> dict:
    """
    Read existing cache, update the three KPI blocks, refresh timestamp,
    and write the result back to CACHE_PATH.

    Preserves:
    - health (domain, warmup, expandi, exclusion_count, outreach_pieces, systems)
    - activity_feed
    - blocked_contacts

    Args:
        contacts: new contacts block
        companies: new companies block
        deals: new deals block

    Returns:
        Updated cache dict (also written to disk)
    """
    cache = load_cache()

    # Update only KPI blocks
    cache["contacts"] = contacts
    cache["companies"] = companies
    cache["deals"] = deals
    cache["timestamp"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")

    with open(CACHE_PATH, "w") as f:
        json.dump(cache, f, indent=2, default=str)

    log.info("Cache updated: %s (%d bytes)", CACHE_PATH, CACHE_PATH.stat().st_size)
    return cache


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if not HUBSPOT_PAT:
        log.error("HUBSPOT_PAT environment variable is not set. Cannot proceed.")
        sys.exit(1)

    t0 = time.time()
    log.info("=== Fast KPI refresh starting ===")

    contacts = fast_contacts()
    companies = fast_companies()
    deals = fast_deals()

    cache = merge_and_write(contacts, companies, deals)

    elapsed = time.time() - t0
    log.info("=== Fast refresh complete in %.1fs ===", elapsed)

    print(f"\nKPI Snapshot:")
    print(f"  Contacts : {cache['contacts']['total']:,}  "
          f"(DTC {cache['contacts']['cold_dtc']} | Expansion {cache['contacts']['expansion']})")
    print(f"  Companies: {cache['companies']['total']:,}")
    print(f"  Deals    : {cache['deals']['total']:,}  "
          f"(${cache['deals']['total_value']:,.0f})")
    print(f"  Stages   : {dict(sorted(cache['deals']['stages'].items()))}")
    print(f"  Elapsed  : {elapsed:.1f}s")
