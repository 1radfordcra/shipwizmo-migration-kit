"""
conftest.py — Shared pytest fixtures and configuration for ShipWizmo migration kit tests.

Run all tests from the migration-kit directory:
    pytest tests/

Run a specific test file:
    pytest tests/test_savings_calculator.py -v

Run with coverage:
    pytest tests/ --cov=. --cov-report=term-missing
"""

import json
import os
import sys
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Path helpers — make imports work regardless of how pytest is invoked
# ---------------------------------------------------------------------------

MIGRATION_KIT = Path(__file__).parent.parent
SAVINGS_CALC_DIR = MIGRATION_KIT / "savings-calculator" / "cgi-bin"
COMMAND_CENTER_DIR = MIGRATION_KIT / "command-center"


# ---------------------------------------------------------------------------
# HubSpot mock response factories
# ---------------------------------------------------------------------------

def make_hubspot_contact(contact_id="1001", email="test@example.com", **props):
    """Return a minimal HubSpot contact object."""
    base_props = {
        "email": email,
        "firstname": "Test",
        "lastname": "User",
        "company": "Test Co",
        "lifecyclestage": "lead",
        "hs_lead_status": "NEW",
        "br_source": "inbound",
        "br_icp_score": "90",
        "br_shipping_pain_score": "85",
    }
    base_props.update(props)
    return {"id": contact_id, "properties": base_props}


def make_hubspot_deal(deal_id="2001", dealname="Test Co — Calculator Inbound", **props):
    """Return a minimal HubSpot deal object."""
    base_props = {
        "dealname": dealname,
        "pipeline": "default",
        "dealstage": "appointmentscheduled",
        "amount": "50000",
    }
    base_props.update(props)
    return {"id": deal_id, "properties": base_props}


def make_hubspot_search_response(results=None, total=None):
    """Return a HubSpot search response envelope."""
    results = results or []
    return {
        "total": total if total is not None else len(results),
        "results": results,
        "paging": {}
    }


# ---------------------------------------------------------------------------
# Fixtures: HubSpot API stubs
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_hubspot_create_contact():
    """
    Returns HTTP 201 with a new contact ID.
    Use this when the contact does not exist yet.
    """
    return (201, make_hubspot_contact())


@pytest.fixture
def mock_hubspot_duplicate_contact():
    """
    Returns HTTP 409 simulating a duplicate contact.
    The message includes 'Existing ID: 1001' so the code extracts the ID.
    """
    return (409, {
        "status": "error",
        "message": "Contact already exists. Existing ID: 1001",
        "category": "CONFLICT"
    })


@pytest.fixture
def mock_hubspot_create_deal_ok():
    """Returns HTTP 201 with a new deal object."""
    return (201, make_hubspot_deal())


# ---------------------------------------------------------------------------
# Fixtures: Reusable form payloads
# ---------------------------------------------------------------------------

@pytest.fixture
def valid_lead_payload():
    """A fully populated savings calculator lead capture payload."""
    return {
        "name": "Jane Shipper",
        "email": "jane@example.com",
        "company": "Widgets Inc",
        "phone": "416-555-0100",
        "carrier": "USPS",
        "volume": "1000",
        "weight": "Under 1 lb",
        "destinations": "80% domestic, 20% Canada",
        "current_cost": "8.50",
        "annual_savings": "$45,000",
        "savings_pct": "55%",
    }


@pytest.fixture
def minimal_lead_payload():
    """Only the three required fields — no calculator context."""
    return {
        "name": "John Doe",
        "email": "john@example.com",
        "company": "Acme Corp",
    }


# ---------------------------------------------------------------------------
# Fixtures: Dashboard cache
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_dashboard_cache():
    """A representative dashboard_cache.json structure."""
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "contacts": {
            "total": 250,
            "cold_dtc": 180,
            "expansion": 70,
            "with_linkedin": 210,
            "no_linkedin": 40,
            "pushed_campaign_a": 120,
            "pushed_campaign_b": 50,
            "not_pushed": 80,
            "leads": 60,
            "hot_leads": 35,
            "linkedin_coverage_pct": 84.0,
        },
        "companies": {
            "total": 180,
            "verticals": {
                "DTC E-commerce": 90,
                "3PL / Fulfillment": 45,
                "Subscription Box": 30,
                "Health & Wellness": 15,
            },
        },
        "deals": {
            "total": 42,
            "total_value": 26250000.0,
            "stages": {
                "Prospect": 12,
                "Qualified": 8,
                "Sequence Enrolled": 10,
                "Meeting Booked": 5,
                "Proposal Sent": 4,
                "Negotiation": 2,
                "Closed Won": 1,
            },
            "tiers": {
                "enterprise": {"count": 5, "value": 15000000},
                "midmarket": {"count": 15, "value": 9000000},
                "smb": {"count": 22, "value": 2250000},
            },
        },
        "health": {
            "domain": {
                "status": "HEALTHY",
                "score": 95,
                "spf": "PASS",
                "dkim": "PASS",
                "dmarc_policy": "quarantine",
                "mx": "PASS",
            },
            "warmup": {
                "status": "ACTIVE",
                "tool": "Mailreach",
                "start_date": "2026-01-01",
                "week": 3,
                "daily_limit": 50,
            },
            "expandi": {"active": True, "campaigns": 3},
            "exclusion_count": 12,
            "outreach_pieces": 400,
            "systems": [
                {"name": "HubSpot CRM", "status": "CONNECTED", "level": "green"},
                {"name": "Apollo API", "status": "CONNECTED", "level": "green"},
            ],
        },
        "activity_feed": [
            {
                "type": "linkedin_push",
                "contact": "Sarah Mills",
                "company": "BoxFlow Inc",
                "timestamp": "2026-03-06T10:00:00Z",
                "summary": {"icp_score": 88, "message": "Hi Sarah..."},
            },
        ],
        "blocked_contacts": [
            {
                "id": "9001",
                "name": "Mark Block",
                "company": "NoShip Co",
                "reason": "Blocked Manual",
                "cooldown_until": "2099-12-31",
            }
        ],
    }


# ---------------------------------------------------------------------------
# Fixtures: SAPT Tool test data
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_rate_card():
    """A representative rate card payload for SAPT Tool API tests."""
    return {
        "carrier": "Broad Reach",
        "service": "Economy Ground",
        "card_type": "sell_current",
        "currency": "USD",
        "divisor": 139,
        "fuel_surcharge_pct": 12.5,
        "zones": {
            "zone_2": {"under_1_lb": 4.50, "1_2_lbs": 5.20, "2_5_lbs": 6.80, "5_10_lbs": 9.10},
            "zone_5": {"under_1_lb": 6.10, "1_2_lbs": 7.30, "2_5_lbs": 9.50, "5_10_lbs": 13.20},
            "zone_8": {"under_1_lb": 9.80, "1_2_lbs": 11.20, "2_5_lbs": 14.60, "5_10_lbs": 19.40},
        },
    }


@pytest.fixture
def sample_shipment_csv_rows():
    """Three sample shipment rows matching the SAPT Tool CSV format."""
    return [
        {
            "ship_date": "2026-01-15",
            "actual_weight_lbs": 0.5,
            "billed_weight_lbs": 0.5,
            "length_in": 8,
            "width_in": 6,
            "height_in": 2,
            "tracking_number": "1Z999AA10123456784",
            "destination_zip": "90210",
        },
        {
            "ship_date": "2026-01-16",
            "actual_weight_lbs": 1.2,
            "billed_weight_lbs": 1.5,
            "length_in": 10,
            "width_in": 8,
            "height_in": 4,
            "tracking_number": "1Z999AA10123456785",
            "destination_zip": "10001",
        },
        {
            "ship_date": "2026-01-17",
            "actual_weight_lbs": 3.0,
            "billed_weight_lbs": 3.0,
            "length_in": 12,
            "width_in": 10,
            "height_in": 6,
            "tracking_number": "1Z999AA10123456786",
            "destination_zip": "77001",
        },
    ]


# ---------------------------------------------------------------------------
# Fixtures: Customs Portal test data
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_sku():
    """A complete SKU record for Customs Portal tests."""
    return {
        "sku_code": "TEST-SKU-001",
        "description": "Test Widget",
        "hs_code": "8517.12.00",
        "country_of_origin": "CA",
        "customs_value": 15.00,
        "currency": "CAD",
    }


@pytest.fixture
def sample_sku_csv():
    """CSV content for bulk SKU import tests."""
    return (
        "sku_code,description,hs_code,country_of_origin,customs_value,currency\n"
        "BULK-001,Widget A,6109.10.00,CA,12.50,CAD\n"
        "BULK-002,Widget B,6110.20.10,US,8.75,USD\n"
        "BULK-003,Widget C,8517.12.00,CA,45.00,CAD\n"
    )


@pytest.fixture
def sample_cusma_request():
    """A CUSMA certificate generation request payload."""
    return {
        "sku_ids": [1, 2],
        "blanket_period_start": "2026-01-01",
        "blanket_period_end": "2026-12-31",
        "exporter": {
            "name": "Widgets Inc Canada",
            "address": "100 Export St, Toronto, ON M5V 3K2",
            "country": "CA",
        },
        "importer": {
            "name": "Widgets Inc USA",
            "address": "200 Import Ave, Detroit, MI 48201",
            "country": "US",
        },
        "producer": "SAME_AS_EXPORTER",
        "authorized_signatory": "Jane Shipper",
    }


# ---------------------------------------------------------------------------
# Fixtures: Outbound machine / cron data
# ---------------------------------------------------------------------------

@pytest.fixture
def warmup_tracker():
    """A warmup_tracker.json fixture with a known start date."""
    return {
        "warmup_status": "ACTIVE",
        "warmup_tool": "Mailreach",
        "warmup_start_date": "2026-01-01",
        "ramp_schedule": {
            "week_1": 10,
            "week_2": 20,
            "week_3": 35,
            "week_4_plus": 50,
        },
    }


@pytest.fixture
def expandi_config():
    """An expandi_config.json fixture with two active campaigns."""
    return {
        "expandi": {
            "campaigns": {
                "campaign_a": {
                    "name": "DTC Cold Outreach A",
                    "status": "active",
                    "daily_connection_limit": 20,
                },
                "campaign_b": {
                    "name": "DTC Cold Outreach B",
                    "status": "active",
                    "daily_connection_limit": 20,
                },
            }
        }
    }


@pytest.fixture
def sample_icp_prospect():
    """A prospect object as it would appear after Apollo enrichment."""
    return {
        "id": "apollo_001",
        "first_name": "Sarah",
        "last_name": "Mills",
        "title": "VP of Operations",
        "company": "BoxFlow Inc",
        "linkedin_url": "https://linkedin.com/in/sarah-mills",
        "email": "sarah@boxflow.com",
        "icp_signals": {
            "dtc_ecommerce": True,
            "ships_canada": True,
            "ships_usa": True,
            "shopify_store": True,
            "estimated_monthly_volume": 5000,
        },
        "pain_signals": [
            "uses_usps_priority",
            "no_volume_discount",
        ],
        "raw_icp_score": 88,
    }
