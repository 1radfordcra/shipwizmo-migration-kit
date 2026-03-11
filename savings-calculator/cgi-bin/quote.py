#!/usr/bin/env python3
"""
Quote form → HubSpot lead creation endpoint.
Creates a contact in HubSpot tagged as a hot inbound lead from the shipping calculator.
"""
import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone

HUBSPOT_TOKEN = os.environ.get("HUBSPOT_PAT", "")  # SECURITY: Never hardcode tokens. Set via environment variable.
HUBSPOT_BASE = "https://api.hubapi.com"

method = os.environ.get("REQUEST_METHOD", "GET")

def respond(status, body):
    print(f"Status: {status}")
    print("Content-Type: application/json")
    print()
    print(json.dumps(body))
    sys.exit(0)

def hubspot_request(endpoint, method="POST", data=None):
    """Make a request to HubSpot API."""
    url = f"{HUBSPOT_BASE}{endpoint}"
    headers = {
        "Authorization": f"Bearer {HUBSPOT_TOKEN}",
        "Content-Type": "application/json",
    }
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())

if method != "POST":
    respond(405, {"error": "Method not allowed"})

# Read request body
try:
    content_length = int(os.environ.get("CONTENT_LENGTH", 0))
    raw = sys.stdin.read(content_length) if content_length > 0 else sys.stdin.read()
    payload = json.loads(raw)
except Exception:
    respond(400, {"error": "Invalid JSON payload"})

# Validate required fields
name = payload.get("name", "").strip()
email = payload.get("email", "").strip()
company = payload.get("company", "").strip()
phone = payload.get("phone", "").strip()

# Calculator context (passed from frontend)
carrier = payload.get("carrier", "")
volume = payload.get("volume", "")
weight = payload.get("weight", "")
destinations = payload.get("destinations", "")
current_cost = payload.get("current_cost", "")
annual_savings = payload.get("annual_savings", "")
savings_pct = payload.get("savings_pct", "")

if not name or not email or not company:
    respond(400, {"error": "Name, email, and company are required"})

# Split name into first/last
name_parts = name.split(" ", 1)
first_name = name_parts[0]
last_name = name_parts[1] if len(name_parts) > 1 else ""

today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

# Build notes with calculator context
notes_lines = [
    f"INBOUND HOT LEAD — Shipping Calculator Quote Request",
    f"Submitted: {today}",
    f"",
    f"Calculator Inputs:",
    f"  Current Carrier: {carrier}",
    f"  Monthly Volume: {volume} packages",
    f"  Avg Weight: {weight}",
    f"  Destinations: {destinations}",
    f"  Current Cost/Pkg: ${current_cost}",
    f"",
    f"Estimated Savings:",
    f"  Annual Savings: {annual_savings}",
    f"  Savings Percentage: {savings_pct}",
]
notes = "\n".join(notes_lines)

# Step 1: Create the contact in HubSpot
contact_props = {
    "email": email,
    "firstname": first_name,
    "lastname": last_name,
    "company": company,
    "lifecyclestage": "lead",
    "hs_lead_status": "NEW",
    "br_source": "inbound",
    "br_icp_score": "90",
    "br_shipping_pain_score": "85",
    "br_sequence_assigned": "",
    "br_expandi_status": "not_pushed",
    "br_nurture_status": "not_started",
}

if phone:
    contact_props["phone"] = phone

status, result = hubspot_request(
    "/crm/v3/objects/contacts",
    data={"properties": contact_props}
)

contact_id = None

if status == 201:
    contact_id = result.get("id")
elif status == 409:
    # Contact already exists — extract ID and update
    existing_id = None
    try:
        msg = result.get("message", "")
        if "Existing ID:" in msg:
            existing_id = msg.split("Existing ID:")[1].strip().split()[0]
        elif result.get("category") == "CONFLICT":
            # Try to find via email
            search_status, search_result = hubspot_request(
                "/crm/v3/objects/contacts/search",
                data={
                    "filterGroups": [{
                        "filters": [{
                            "propertyName": "email",
                            "operator": "EQ",
                            "value": email
                        }]
                    }]
                }
            )
            if search_status == 200 and search_result.get("total", 0) > 0:
                existing_id = search_result["results"][0]["id"]
    except Exception:
        pass

    if existing_id:
        contact_id = existing_id
        # Update existing contact with hot lead info
        hubspot_request(
            f"/crm/v3/objects/contacts/{contact_id}",
            method="PATCH",
            data={"properties": {
                "hs_lead_status": "NEW",
                "br_source": "inbound",
                "br_icp_score": "90",
                "br_shipping_pain_score": "85",
            }}
        )
else:
    respond(422, {"error": "Failed to create contact in CRM", "details": result})

# Step 2: Create a Note/Engagement with the calculator details
if contact_id:
    note_data = {
        "properties": {
            "hs_timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "hs_note_body": notes,
        },
        "associations": [{
            "to": {"id": contact_id},
            "types": [{
                "associationCategory": "HUBSPOT_DEFINED",
                "associationTypeId": 202
            }]
        }]
    }
    hubspot_request("/crm/v3/objects/notes", data=note_data)

# Step 3: Create a Deal for this hot inbound lead
if contact_id:
    # Clean the amount — remove $, commas, and any non-numeric chars
    clean_amount = ""
    if annual_savings:
        clean_amount = annual_savings.replace("$", "").replace(",", "").strip()
        try:
            float(clean_amount)
        except ValueError:
            clean_amount = ""

    deal_props = {
        "dealname": f"{company} — Calculator Inbound",
        "pipeline": "default",
        "dealstage": "appointmentscheduled",
        "description": f"INBOUND HOT LEAD from shipping calculator. Currently on {carrier}, ~{volume} pkgs/mo, {savings_pct} potential savings. Estimated annual savings: {annual_savings}.",
    }
    if clean_amount:
        deal_props["amount"] = clean_amount

    deal_status, deal_result = hubspot_request(
        "/crm/v3/objects/deals",
        data={"properties": deal_props}
    )

    if deal_status == 201:
        deal_id = deal_result.get("id")
        # Associate deal with contact
        hubspot_request(
            f"/crm/v4/objects/contacts/{contact_id}/associations/deals/{deal_id}",
            method="PUT",
            data=[{
                "associationCategory": "HUBSPOT_DEFINED",
                "associationTypeId": 4
            }]
        )

respond(200, {
    "success": True,
    "contact_id": contact_id,
    "message": "Lead created successfully"
})
