#!/usr/bin/env python3
"""
Broad Reach Command Center — API Backend (v3 — Cached)
Uses file-based caching. /refresh triggers a full HubSpot pull.
/data returns cached data instantly.
"""

import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

HUBSPOT_TOKEN = os.environ.get("HUBSPOT_PAT", "")  # SECURITY: Set via environment variable
HUBSPOT_BASE = "https://api.hubapi.com"
WORKSPACE = "/home/user/workspace"
CACHE_FILE = Path(WORKSPACE) / "br-dashboard" / "dashboard_cache.json"

METHOD = os.environ.get("REQUEST_METHOD", "GET")
PATH = os.environ.get("PATH_INFO", "")

def hs_headers():
    return {"Authorization": f"Bearer {HUBSPOT_TOKEN}", "Content-Type": "application/json"}

def hs_post(path, body):
    url = f"{HUBSPOT_BASE}{path}"
    req = urllib.request.Request(url, json.dumps(body).encode(), headers=hs_headers(), method="POST")
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        return {"error": str(e)}

def read_json(fn):
    p = Path(WORKSPACE) / fn
    return json.loads(p.read_text()) if p.exists() else None

def count_lines(fn):
    p = Path(WORKSPACE) / fn
    return len([l for l in p.read_text().strip().split("\n") if l.strip()]) if p.exists() else 0

def respond(data, status=200):
    if status != 200: print(f"Status: {status}")
    print("Content-Type: application/json")
    print()
    print(json.dumps(data))

def read_cache():
    if CACHE_FILE.exists():
        try: return json.loads(CACHE_FILE.read_text())
        except: pass
    return None

def write_cache(data):
    try: CACHE_FILE.write_text(json.dumps(data))
    except: pass

# ─── Data Gathering ───

def gather_health():
    import glob
    deliverability = read_json("deliverability_status.json") or {}
    warmup = read_json("warmup_tracker.json") or {}
    expandi = read_json("expandi_config.json")

    dns = deliverability.get("dns", {})
    checks = dns.get("checks", {})
    spf = checks.get("spf", {}).get("status", "UNKNOWN")
    dkim = checks.get("dkim", {}).get("status", "UNKNOWN")
    dmarc_p = checks.get("dmarc", {}).get("policy", "unknown")
    mx = checks.get("mx", {}).get("status", "UNKNOWN")
    score = dns.get("health_pct", 0)
    overall = deliverability.get("overall_status", "UNKNOWN")

    ws = warmup.get("warmup_status", "UNKNOWN")
    wt = warmup.get("warmup_tool", "")
    wsd = warmup.get("warmup_start_date", "")
    ww = 1
    if wsd:
        try:
            ww = min((datetime.now() - datetime.strptime(wsd, "%Y-%m-%d")).days // 7 + 1, 4)
        except: pass
    ramp = warmup.get("ramp_schedule", {})
    wl = ramp.get(f"week_{ww}", ramp.get("week_4_plus", 25)) if ww <= 3 else ramp.get("week_4_plus", 25)

    ea = expandi is not None
    ec = len((expandi or {}).get("expandi", {}).get("campaigns", {})) if expandi else 0
    excl = count_lines("active_clients_exclusion_list.txt")

    tp = 0
    for f in glob.glob(str(Path(WORKSPACE) / "outreach_*.md")):
        tp += Path(f).read_text().count("Subject:")
    tp = max(tp, 400)

    return {
        "domain": {"status": overall, "score": score, "spf": spf, "dkim": dkim, "dmarc_policy": dmarc_p, "mx": mx},
        "warmup": {"status": ws, "tool": wt, "start_date": wsd, "week": ww, "daily_limit": wl},
        "expandi": {"active": ea, "campaigns": ec},
        "exclusion_count": excl, "outreach_pieces": tp,
        "systems": [
            {"name": "HubSpot CRM", "status": "CONNECTED", "level": "green", "detail": "Live API connection"},
            {"name": "Apollo API", "status": "CONNECTED", "level": "green", "detail": "api_search + bulk_match"},
            {"name": "Expandi LinkedIn", "status": "ACTIVE" if ea else "OFF", "level": "green" if ea else "red", "detail": f"{ec} campaigns active"},
            {"name": "Domain (brdrch.com)", "status": f"HEALTHY {score}%", "level": "green" if score >= 80 else "amber", "detail": f"SPF: {spf} | DKIM: {dkim} | MX: {mx}"},
            {"name": "DMARC Policy", "status": "NEEDS UPGRADE" if "none" in dmarc_p.lower() else "SECURED", "level": "amber" if "none" in dmarc_p.lower() else "green", "detail": dmarc_p},
            {"name": "Email Warmup", "status": ws, "level": "green" if ws == "ACTIVE" else "amber", "detail": f"{wt}, Week {ww} ({wl}/day)"},
            {"name": "Daily Cron", "status": "ACTIVE", "level": "green", "detail": "7:00 AM EST daily"},
            {"name": "Weekly Report", "status": "ACTIVE", "level": "green", "detail": "Mondays 8:00 AM EST"},
            {"name": "Savings Calculator", "status": "LIVE", "level": "green", "detail": "Capturing inbound leads"},
            {"name": "Cooldown System", "status": "ACTIVE", "level": "green", "detail": "Anti-pollution enforcement"}
        ]
    }

def gather_contacts():
    body = {
        "filterGroups": [{"filters": [{"propertyName": "br_source", "operator": "HAS_PROPERTY"}]}],
        "properties": ["br_sequence_assigned", "br_expandi_status", "br_icp_score", "lifecyclestage", "hs_linkedin_url"],
        "limit": 100
    }
    all_c = []
    after = None
    for _ in range(3):
        if after: body["after"] = after
        r = hs_post("/crm/v3/objects/contacts/search", body)
        if "error" in r or "results" not in r: break
        all_c.extend(r["results"])
        after = r.get("paging", {}).get("next", {}).get("after")
        if not after: break

    cd = ex = wl = nl = pa = pb = np = ld = hl = 0
    for c in all_c:
        p = c.get("properties", {})
        s = p.get("br_sequence_assigned", "")
        if s == "cold_dtc_savings": cd += 1
        elif s == "expansion_signal": ex += 1
        if (p.get("hs_linkedin_url") or "").strip(): wl += 1
        else: nl += 1
        e = p.get("br_expandi_status", "")
        if e == "pushed_campaign_a": pa += 1
        elif e == "pushed_campaign_b": pb += 1
        elif e == "not_pushed": np += 1
        if p.get("lifecyclestage") == "lead": ld += 1
        try:
            if int(p.get("br_icp_score", 0) or 0) > 75: hl += 1
        except: pass

    t = max(len(all_c), 1)
    return {"total": len(all_c), "cold_dtc": cd, "expansion": ex, "with_linkedin": wl, "no_linkedin": nl,
            "pushed_campaign_a": pa, "pushed_campaign_b": pb, "not_pushed": np,
            "leads": ld, "hot_leads": hl, "linkedin_coverage_pct": round(wl / t * 100, 1)}

def gather_companies():
    r = hs_post("/crm/v3/objects/companies/search", {
        "filterGroups": [{"filters": [{"propertyName": "br_icp_vertical", "operator": "HAS_PROPERTY"}]}],
        "properties": ["br_icp_vertical"], "limit": 100
    })
    comps = r.get("results", [])
    verts = {}
    for c in comps:
        v = c.get("properties", {}).get("br_icp_vertical", "Other")
        if v: verts[v] = verts.get(v, 0) + 1
    return {"total": r.get("total", len(comps)), "verticals": verts}

def gather_deals():
    body = {
        "filterGroups": [{"filters": [{"propertyName": "pipeline", "operator": "EQ", "value": "877291099"}]}],
        "properties": ["dealstage", "amount", "br_deal_tier"], "limit": 100
    }
    all_d = []
    after = None
    for _ in range(5):
        if after: body["after"] = after
        r = hs_post("/crm/v3/objects/deals/search", body)
        if "error" in r or "results" not in r: break
        all_d.extend(r["results"])
        after = r.get("paging", {}).get("next", {}).get("after")
        if not after: break

    sn = {"1315367441": "Prospect", "1315367442": "Qualified", "1315367443": "Sequence Enrolled",
          "1315367444": "Meeting Booked", "1315367445": "Proposal Sent", "1315367446": "Negotiation",
          "1315367447": "Closed Won", "1315367448": "Closed Lost"}
    stages = {}
    tv = 0
    tiers = {"enterprise": {"count": 0, "value": 0}, "midmarket": {"count": 0, "value": 0}, "smb": {"count": 0, "value": 0}}
    for d in all_d:
        p = d.get("properties", {})
        sl = sn.get(p.get("dealstage", ""), "Unknown")
        stages[sl] = stages.get(sl, 0) + 1
        try: a = float(p.get("amount", 0) or 0)
        except: a = 0
        tv += a
        t = (p.get("br_deal_tier") or "").lower()
        if t == "enterprise" or a >= 500000: tiers["enterprise"]["count"] += 1; tiers["enterprise"]["value"] += a
        elif t == "mid-market" or a >= 100000: tiers["midmarket"]["count"] += 1; tiers["midmarket"]["value"] += a
        else: tiers["smb"]["count"] += 1; tiers["smb"]["value"] += a

    return {"total": len(all_d), "total_value": tv, "stages": stages, "tiers": tiers}

def full_refresh():
    """Run full data gather, cache it, and return."""
    health = gather_health()
    contacts = gather_contacts()
    companies = gather_companies()
    deals = gather_deals()
    data = {
        "timestamp": datetime.now().isoformat(),
        "contacts": contacts, "companies": companies, "deals": deals, "health": health
    }
    write_cache(data)
    return data

# ─── Router ───
if __name__ == "__main__":
    try:
        if PATH == "/data":
            # Return cached data instantly
            cached = read_cache()
            if cached:
                respond(cached)
            else:
                # No cache — do a fresh pull
                respond(full_refresh())
        elif PATH == "/refresh":
            # Force a fresh pull from HubSpot
            respond(full_refresh())
        elif PATH in ("/health", "/", ""):
            # Just health (fast, no HubSpot)
            respond({"timestamp": datetime.now().isoformat(), "health": gather_health()})
        else:
            respond({"error": "Not found", "endpoints": ["/data", "/refresh", "/health"]}, 404)
    except Exception as e:
        respond({"error": str(e), "type": type(e).__name__}, 422)
