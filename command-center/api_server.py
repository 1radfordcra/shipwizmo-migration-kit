#!/usr/bin/env python3
"""
Broad Reach Command Center — API Proxy Server
Proxies HubSpot API calls from the dashboard frontend to avoid CORS issues.
Runs on port 8000.
"""
import json
import os
import urllib.request
import urllib.error
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional

HS_TOKEN = os.environ.get("HUBSPOT_PAT", "")  # SECURITY: Set via environment variable
HS_BASE = "https://api.hubapi.com"

app = FastAPI()
# SECURITY: Restrict CORS to known origins in production.
# For local dev, override with CORS_ORIGINS=* environment variable.
_cors_origins = os.environ.get("CORS_ORIGINS", "https://www.perplexity.ai,https://sites.pplx.app").split(",")
app.add_middleware(CORSMiddleware, allow_origins=_cors_origins, allow_methods=["*"], allow_headers=["*"])


def hs_request(method, path, body=None):
    """Make a request to the HubSpot API."""
    url = f"{HS_BASE}{path}"
    headers = {
        "Authorization": f"Bearer {HS_TOKEN}",
        "Content-Type": "application/json"
    }
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status == 204:
                return {"ok": True}
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()[:500]
        raise HTTPException(status_code=e.code, detail=f"HubSpot API error: {error_body}")
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))


class ActionRequest(BaseModel):
    contact_id: str
    action: str  # "remove" or "block"

class UnblockRequest(BaseModel):
    contact_id: str


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "br-command-center-api"}


@app.get("/api/contact/{contact_id}")
def get_contact(contact_id: str):
    """Get contact properties from HubSpot."""
    props = ",".join([
        "firstname", "lastname", "company", "email", "jobtitle",
        "hs_sequences_is_enrolled", "br_sequence_assigned",
        "br_expandi_status", "br_sequence_completed",
        "br_nurture_status", "br_last_sequence_outcome",
        "br_contact_cooldown_until"
    ])
    return hs_request("GET", f"/crm/v3/objects/contacts/{contact_id}?properties={props}")


@app.get("/api/blocked-contacts")
def get_blocked_contacts():
    """Fetch all contacts that have been blocked/removed from outreach."""
    props = ",".join([
        "firstname", "lastname", "company", "email", "jobtitle",
        "br_expandi_status", "br_sequence_completed", "br_nurture_status",
        "br_last_sequence_outcome", "br_icp_score", "br_shipping_pain_score",
        "br_contact_cooldown_until", "hs_linkedin_url", "city", "state",
        "notes_last_updated", "createdate"
    ])
    # Search for contacts with blocked/removed outcomes
    all_blocked = []
    for outcome_val in ["blocked_manual", "removed_manual", "bounced", "opted_out"]:
        r = hs_request("POST", "/crm/v3/objects/contacts/search", {
            "filterGroups": [{"filters": [
                {"propertyName": "br_last_sequence_outcome", "operator": "EQ", "value": outcome_val}
            ]}],
            "properties": props.split(","),
            "limit": 100
        })
        for c in r.get("results", []):
            all_blocked.append(c)

    # Deduplicate by contact ID
    seen = set()
    unique = []
    for c in all_blocked:
        cid = c.get("id")
        if cid and cid not in seen:
            seen.add(cid)
            unique.append(c)

    # Format for frontend
    contacts = []
    for c in unique:
        p = c.get("properties", {})
        fname = (p.get("firstname") or "").strip()
        lname = (p.get("lastname") or "").strip()
        city = (p.get("city") or "").strip()
        state = (p.get("state") or "").strip()
        location = f"{city}, {state}" if city and state else (city or state or "")
        contacts.append({
            "id": c["id"],
            "name": f"{fname} {lname}".strip() or "Unknown",
            "first_name": fname,
            "last_name": lname,
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
            "created": p.get("createdate", "")
        })

    # Sort by name
    contacts.sort(key=lambda x: x["name"].lower())
    return {"total": len(contacts), "contacts": contacts}


@app.post("/api/unblock")
def unblock_contact(req: UnblockRequest):
    """Unblock a contact — resets all blocked properties to allow future outreach."""
    contact_id = req.contact_id

    # Get current contact info
    props = ",".join(["firstname", "lastname", "company"])
    contact = hs_request("GET", f"/crm/v3/objects/contacts/{contact_id}?properties={props}")
    cp = contact.get("properties", {})

    # Reset all blocked properties
    update_props = {
        "br_expandi_status": "not_pushed",
        "br_sequence_completed": "none",
        "br_nurture_status": "not_started",
        "br_last_sequence_outcome": "",
        "br_contact_cooldown_until": ""
    }

    hs_request("PATCH", f"/crm/v3/objects/contacts/{contact_id}", {"properties": update_props})

    contact_name = f"{cp.get('firstname', '')} {cp.get('lastname', '')}".strip()
    company_name = cp.get("company", "")

    return {
        "success": True,
        "contact_id": contact_id,
        "contact_name": contact_name,
        "company": company_name,
        "message": f"Unblocked {contact_name} at {company_name} — eligible for future outreach"
    }


@app.post("/api/action")
def execute_action(req: ActionRequest):
    """Execute a remove or block action on a contact."""
    contact_id = req.contact_id
    action = req.action

    if action not in ("remove", "block"):
        raise HTTPException(status_code=400, detail="Invalid action. Use 'remove' or 'block'.")

    # Step 1: Get current contact info
    props = ",".join([
        "firstname", "lastname", "company",
        "hs_sequences_is_enrolled", "br_expandi_status",
        "br_sequence_completed", "br_nurture_status"
    ])
    contact = hs_request("GET", f"/crm/v3/objects/contacts/{contact_id}?properties={props}")
    cp = contact.get("properties", {})

    # Step 2: Update HubSpot properties
    update_props = {
        "br_expandi_status": "blocked",
        "br_sequence_completed": "blocked" if action == "block" else "removed",
        "br_nurture_status": "blocked",
        "br_last_sequence_outcome": "blocked_manual" if action == "block" else "removed_manual",
        "br_contact_cooldown_until": "2099-12-31"
    }

    hs_request("PATCH", f"/crm/v3/objects/contacts/{contact_id}", {"properties": update_props})

    contact_name = f"{cp.get('firstname', '')} {cp.get('lastname', '')}".strip()
    company_name = cp.get("company", "")

    return {
        "success": True,
        "action": action,
        "contact_id": contact_id,
        "contact_name": contact_name,
        "company": company_name,
        "message": f"{'Blocked' if action == 'block' else 'Removed'} {contact_name} at {company_name}"
    }


# ---------------------------------------------------------------------------
# Static file serving — dashboard HTML/JS/CSS
# Mount AFTER API routes so /api/* takes priority
# ---------------------------------------------------------------------------
_static_dir = Path(__file__).parent

@app.get("/")
def serve_index():
    """Serve the dashboard index.html."""
    return FileResponse(_static_dir / "index.html")

# Serve static assets (JS, CSS, JSON cache)
app.mount("/", StaticFiles(directory=str(_static_dir), html=False), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
