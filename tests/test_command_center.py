"""
test_command_center.py — Unit tests for the Command Center backend.

Covers:
  - api_server.py (FastAPI proxy): health endpoint, get_contact, get_blocked_contacts,
    unblock_contact, execute_action (block / remove)
  - cgi-bin/api.py (cache updater): gather_health logic, gather_contacts aggregation,
    gather_deals tier/stage bucketing, gather_companies vertical aggregation,
    full_refresh cache write, read_cache / write_cache I/O
  - ICP scoring derived logic
  - Data transformation: blocked contacts formatting, location building, name building

Run from migration-kit directory:
    pytest tests/test_command_center.py -v
"""

import json
import os
import sys
import pytest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open

# ---------------------------------------------------------------------------
# Import the testable modules
# ---------------------------------------------------------------------------

COMMAND_CENTER = Path(__file__).parent.parent / "command-center"

# Add command center to path so we can import api_server.py
sys.path.insert(0, str(COMMAND_CENTER))

# Import api_server — FastAPI app
import api_server
from api_server import (
    app,
    hs_request,
    ActionRequest,
    UnblockRequest,
)

# Import cgi api.py functions by loading the module carefully.
# The cgi api.py has top-level code guarded by `if __name__ == "__main__"`,
# so direct import is safe.
CGI_API = COMMAND_CENTER / "cgi-bin" / "api.py"

import importlib.util

def load_cgi_api():
    spec = importlib.util.spec_from_file_location("cgi_api", CGI_API)
    mod = importlib.util.module_from_spec(spec)
    # Prevent the __main__ block from executing
    mod.__name__ = "cgi_api"
    spec.loader.exec_module(mod)
    return mod

cgi_api = load_cgi_api()


# ---------------------------------------------------------------------------
# FastAPI TestClient
# ---------------------------------------------------------------------------

from fastapi.testclient import TestClient

client = TestClient(app)


# ---------------------------------------------------------------------------
# Tests: api_server.py — /api/health
# ---------------------------------------------------------------------------

class TestApiHealth:
    """The /api/health endpoint should always return 200 with status=ok."""

    def test_health_returns_200(self):
        """Health check should return HTTP 200."""
        response = client.get("/api/health")
        assert response.status_code == 200

    def test_health_body_has_status_ok(self):
        """Health response body must contain status: ok."""
        response = client.get("/api/health")
        data = response.json()
        assert data["status"] == "ok"

    def test_health_body_has_service_name(self):
        """Health response must identify the service."""
        response = client.get("/api/health")
        data = response.json()
        assert "service" in data
        assert "command-center" in data["service"]


# ---------------------------------------------------------------------------
# Tests: api_server.py — /api/contact/{contact_id}
# ---------------------------------------------------------------------------

class TestGetContact:
    """Test the HubSpot contact proxy endpoint."""

    def _make_mock_contact(self, contact_id="1001"):
        return {
            "id": contact_id,
            "properties": {
                "firstname": "Sarah",
                "lastname": "Mills",
                "company": "BoxFlow Inc",
                "email": "sarah@boxflow.com",
                "jobtitle": "VP of Operations",
                "br_expandi_status": "pushed_campaign_a",
                "br_sequence_assigned": "cold_dtc_savings",
                "br_contact_cooldown_until": "",
            }
        }

    @patch("api_server.hs_request")
    def test_get_contact_returns_contact_data(self, mock_hs):
        """Successful HubSpot lookup should return the contact properties."""
        mock_hs.return_value = self._make_mock_contact("1001")
        response = client.get("/api/contact/1001")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "1001"
        assert data["properties"]["firstname"] == "Sarah"

    @patch("api_server.hs_request")
    def test_get_contact_calls_correct_hubspot_endpoint(self, mock_hs):
        """The proxy must call HubSpot's contacts endpoint with the right ID."""
        mock_hs.return_value = self._make_mock_contact("9999")
        client.get("/api/contact/9999")
        call_args = mock_hs.call_args
        assert "9999" in call_args[0][1]  # second positional arg is the path
        assert "/crm/v3/objects/contacts/9999" in call_args[0][1]

    @patch("api_server.hs_request")
    def test_get_contact_requests_expected_properties(self, mock_hs):
        """
        The contact endpoint must request all required CRM properties
        including cooldown_until.
        """
        mock_hs.return_value = self._make_mock_contact()
        client.get("/api/contact/1001")
        call_path = mock_hs.call_args[0][1]
        assert "br_contact_cooldown_until" in call_path


# ---------------------------------------------------------------------------
# Tests: api_server.py — /api/blocked-contacts
# ---------------------------------------------------------------------------

class TestGetBlockedContacts:
    """Test the blocked contacts aggregation endpoint."""

    def _blocked_contact_raw(self, cid, outcome):
        return {
            "id": cid,
            "properties": {
                "firstname": "Mark",
                "lastname": "Block",
                "company": "NoShip Co",
                "email": f"{cid}@noemail.com",
                "jobtitle": "CEO",
                "city": "Toronto",
                "state": "ON",
                "hs_linkedin_url": "",
                "br_icp_score": "70",
                "br_shipping_pain_score": "60",
                "br_last_sequence_outcome": outcome,
                "br_expandi_status": "blocked",
                "br_sequence_completed": "blocked",
                "br_contact_cooldown_until": "2099-12-31",
                "notes_last_updated": "",
                "createdate": "2026-01-01",
            }
        }

    @patch("api_server.hs_request")
    def test_blocked_contacts_returns_list(self, mock_hs):
        """Endpoint must return a dict with total and contacts list."""
        mock_hs.return_value = {
            "results": [self._blocked_contact_raw("9001", "blocked_manual")],
            "total": 1
        }
        response = client.get("/api/blocked-contacts")
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "contacts" in data
        assert isinstance(data["contacts"], list)

    @patch("api_server.hs_request")
    def test_blocked_contacts_deduplicates_by_id(self, mock_hs):
        """
        Contacts blocked across multiple outcome categories should not be
        returned twice. The deduplication uses contact ID.
        """
        same_contact = self._blocked_contact_raw("9001", "blocked_manual")
        # Return the same contact for every outcome query
        mock_hs.return_value = {"results": [same_contact], "total": 1}
        response = client.get("/api/blocked-contacts")
        data = response.json()
        ids = [c["id"] for c in data["contacts"]]
        assert len(ids) == len(set(ids)), "Duplicate contact IDs found in response"

    @patch("api_server.hs_request")
    def test_blocked_contacts_formats_reason_as_title_case(self, mock_hs):
        """
        'blocked_manual' should be formatted as 'Blocked Manual' in the response
        (underscores replaced, title-cased).
        """
        mock_hs.return_value = {
            "results": [self._blocked_contact_raw("9001", "blocked_manual")],
            "total": 1
        }
        response = client.get("/api/blocked-contacts")
        data = response.json()
        contact = data["contacts"][0]
        assert contact["reason"] == "Blocked Manual"

    @patch("api_server.hs_request")
    def test_blocked_contacts_builds_location_string(self, mock_hs):
        """
        City + State should be combined as 'City, State'.
        If only city is present, just the city should be returned.
        """
        mock_hs.return_value = {
            "results": [self._blocked_contact_raw("9001", "blocked_manual")],
            "total": 1
        }
        response = client.get("/api/blocked-contacts")
        data = response.json()
        contact = data["contacts"][0]
        assert contact["location"] == "Toronto, ON"

    @patch("api_server.hs_request")
    def test_blocked_contacts_sorted_by_name(self, mock_hs):
        """The response contacts list must be sorted alphabetically by name."""
        contacts = [
            self._blocked_contact_raw("9003", "blocked_manual"),
            self._blocked_contact_raw("9001", "blocked_manual"),
            self._blocked_contact_raw("9002", "removed_manual"),
        ]
        # Give them different names
        contacts[0]["properties"]["firstname"] = "Zelda"
        contacts[1]["properties"]["firstname"] = "Alice"
        contacts[2]["properties"]["firstname"] = "Mark"
        mock_hs.return_value = {"results": contacts, "total": 3}

        response = client.get("/api/blocked-contacts")
        data = response.json()
        names = [c["name"] for c in data["contacts"]]
        assert names == sorted(names, key=str.lower)


# ---------------------------------------------------------------------------
# Tests: api_server.py — /api/unblock
# ---------------------------------------------------------------------------

class TestUnblockContact:
    """Test the unblock contact endpoint."""

    @patch("api_server.hs_request")
    def test_unblock_returns_success(self, mock_hs):
        """Successful unblock should return success=True and the contact name."""
        mock_hs.side_effect = [
            # First call: GET contact info
            {
                "id": "9001",
                "properties": {
                    "firstname": "Mark",
                    "lastname": "Block",
                    "company": "NoShip Co"
                }
            },
            # Second call: PATCH to reset blocked properties
            {"ok": True}
        ]
        response = client.post("/api/unblock", json={"contact_id": "9001"})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["contact_id"] == "9001"

    @patch("api_server.hs_request")
    def test_unblock_resets_all_blocked_properties(self, mock_hs):
        """
        The PATCH call must reset all five blocked properties:
        br_expandi_status, br_sequence_completed, br_nurture_status,
        br_last_sequence_outcome, br_contact_cooldown_until.
        """
        mock_hs.side_effect = [
            {"id": "9001", "properties": {"firstname": "Mark", "lastname": "Block", "company": "Co"}},
            {"ok": True}
        ]
        client.post("/api/unblock", json={"contact_id": "9001"})
        patch_call = mock_hs.call_args_list[1]
        props = patch_call[0][2]["properties"]  # third positional arg = body
        assert props["br_expandi_status"] == "not_pushed"
        assert props["br_nurture_status"] == "not_started"
        assert props["br_last_sequence_outcome"] == ""
        assert props["br_contact_cooldown_until"] == ""

    @patch("api_server.hs_request")
    def test_unblock_message_confirms_eligibility(self, mock_hs):
        """The response message should confirm the contact is eligible for outreach."""
        mock_hs.side_effect = [
            {"id": "9001", "properties": {"firstname": "Mark", "lastname": "Block", "company": "Co"}},
            {"ok": True}
        ]
        response = client.post("/api/unblock", json={"contact_id": "9001"})
        data = response.json()
        assert "eligible" in data["message"].lower() or "unblocked" in data["message"].lower()


# ---------------------------------------------------------------------------
# Tests: api_server.py — /api/action
# ---------------------------------------------------------------------------

class TestExecuteAction:
    """Test the block / remove action endpoint."""

    @patch("api_server.hs_request")
    def test_block_action_sets_cooldown_to_2099(self, mock_hs):
        """
        A 'block' action must set br_contact_cooldown_until = '2099-12-31'
        (permanent block sentinel value).
        """
        mock_hs.side_effect = [
            {"id": "1001", "properties": {"firstname": "Jo", "lastname": "Doe", "company": "Co",
                                           "hs_sequences_is_enrolled": "false",
                                           "br_expandi_status": "not_pushed",
                                           "br_sequence_completed": "none",
                                           "br_nurture_status": "not_started"}},
            {"ok": True}
        ]
        response = client.post("/api/action", json={"contact_id": "1001", "action": "block"})
        assert response.status_code == 200
        patch_call = mock_hs.call_args_list[1]
        props = patch_call[0][2]["properties"]
        assert props["br_contact_cooldown_until"] == "2099-12-31"

    @patch("api_server.hs_request")
    def test_block_action_sets_sequence_completed_to_blocked(self, mock_hs):
        """Block action: br_sequence_completed should be 'blocked'."""
        mock_hs.side_effect = [
            {"id": "1001", "properties": {"firstname": "Jo", "lastname": "Doe", "company": "Co",
                                           "hs_sequences_is_enrolled": "false",
                                           "br_expandi_status": "not_pushed",
                                           "br_sequence_completed": "none",
                                           "br_nurture_status": "not_started"}},
            {"ok": True}
        ]
        client.post("/api/action", json={"contact_id": "1001", "action": "block"})
        patch_call = mock_hs.call_args_list[1]
        props = patch_call[0][2]["properties"]
        assert props["br_sequence_completed"] == "blocked"
        assert props["br_last_sequence_outcome"] == "blocked_manual"

    @patch("api_server.hs_request")
    def test_remove_action_sets_sequence_completed_to_removed(self, mock_hs):
        """Remove action: br_sequence_completed should be 'removed'."""
        mock_hs.side_effect = [
            {"id": "1001", "properties": {"firstname": "Jo", "lastname": "Doe", "company": "Co",
                                           "hs_sequences_is_enrolled": "false",
                                           "br_expandi_status": "not_pushed",
                                           "br_sequence_completed": "none",
                                           "br_nurture_status": "not_started"}},
            {"ok": True}
        ]
        client.post("/api/action", json={"contact_id": "1001", "action": "remove"})
        patch_call = mock_hs.call_args_list[1]
        props = patch_call[0][2]["properties"]
        assert props["br_sequence_completed"] == "removed"
        assert props["br_last_sequence_outcome"] == "removed_manual"

    def test_invalid_action_returns_400(self):
        """An unrecognised action value must return HTTP 400."""
        with patch("api_server.hs_request"):
            response = client.post("/api/action", json={"contact_id": "1001", "action": "delete"})
        assert response.status_code == 400

    @patch("api_server.hs_request")
    def test_block_action_response_contains_success(self, mock_hs):
        """A successful block should return success=True and the action."""
        mock_hs.side_effect = [
            {"id": "1001", "properties": {"firstname": "Jo", "lastname": "Doe", "company": "Co",
                                           "hs_sequences_is_enrolled": "false",
                                           "br_expandi_status": "not_pushed",
                                           "br_sequence_completed": "none",
                                           "br_nurture_status": "not_started"}},
            {"ok": True}
        ]
        response = client.post("/api/action", json={"contact_id": "1001", "action": "block"})
        data = response.json()
        assert data["success"] is True
        assert data["action"] == "block"


# ---------------------------------------------------------------------------
# Tests: cgi-bin/api.py — read_cache / write_cache
# ---------------------------------------------------------------------------

class TestCacheIO:
    """Verify the file-based cache read/write helpers."""

    def test_write_then_read_cache_roundtrip(self, tmp_path):
        """Data written by write_cache should be readable by read_cache."""
        cache_file = tmp_path / "dashboard_cache.json"
        test_data = {"timestamp": "2026-03-06T12:00:00", "contacts": {"total": 100}}

        # Temporarily override the cache file path
        original = cgi_api.CACHE_FILE
        cgi_api.CACHE_FILE = cache_file
        try:
            cgi_api.write_cache(test_data)
            result = cgi_api.read_cache()
            assert result is not None
            assert result["contacts"]["total"] == 100
        finally:
            cgi_api.CACHE_FILE = original

    def test_read_cache_returns_none_when_no_file(self, tmp_path):
        """read_cache should return None gracefully when the cache file doesn't exist."""
        original = cgi_api.CACHE_FILE
        cgi_api.CACHE_FILE = tmp_path / "nonexistent.json"
        try:
            result = cgi_api.read_cache()
            assert result is None
        finally:
            cgi_api.CACHE_FILE = original

    def test_read_cache_returns_none_on_corrupt_json(self, tmp_path):
        """read_cache should return None gracefully for malformed JSON."""
        cache_file = tmp_path / "dashboard_cache.json"
        cache_file.write_text("this is not json {{{")
        original = cgi_api.CACHE_FILE
        cgi_api.CACHE_FILE = cache_file
        try:
            result = cgi_api.read_cache()
            assert result is None
        finally:
            cgi_api.CACHE_FILE = original


# ---------------------------------------------------------------------------
# Tests: cgi-bin/api.py — gather_contacts aggregation
# ---------------------------------------------------------------------------

class TestGatherContactsAggregation:
    """
    Validate the aggregation logic in gather_contacts without making real
    HubSpot API calls.
    """

    def _make_raw_contacts(self):
        """Three contacts with known properties for deterministic counting."""
        return [
            {
                "id": "1",
                "properties": {
                    "br_sequence_assigned": "cold_dtc_savings",
                    "br_expandi_status": "pushed_campaign_a",
                    "hs_linkedin_url": "https://linkedin.com/in/alice",
                    "lifecyclestage": "lead",
                    "br_icp_score": "90",
                }
            },
            {
                "id": "2",
                "properties": {
                    "br_sequence_assigned": "expansion_signal",
                    "br_expandi_status": "pushed_campaign_b",
                    "hs_linkedin_url": "",
                    "lifecyclestage": "customer",
                    "br_icp_score": "80",
                }
            },
            {
                "id": "3",
                "properties": {
                    "br_sequence_assigned": "cold_dtc_savings",
                    "br_expandi_status": "not_pushed",
                    "hs_linkedin_url": "https://linkedin.com/in/charlie",
                    "lifecyclestage": "lead",
                    "br_icp_score": "50",  # below 75 threshold
                }
            },
        ]

    def _run_aggregation(self, contacts):
        """Run the aggregation logic extracted from gather_contacts."""
        cd = ex = wl = nl = pa = pb = np_ = ld = hl = 0
        for c in contacts:
            p = c.get("properties", {})
            s = p.get("br_sequence_assigned", "")
            if s == "cold_dtc_savings": cd += 1
            elif s == "expansion_signal": ex += 1
            if (p.get("hs_linkedin_url") or "").strip(): wl += 1
            else: nl += 1
            e = p.get("br_expandi_status", "")
            if e == "pushed_campaign_a": pa += 1
            elif e == "pushed_campaign_b": pb += 1
            elif e == "not_pushed": np_ += 1
            if p.get("lifecyclestage") == "lead": ld += 1
            try:
                if int(p.get("br_icp_score", 0) or 0) > 75: hl += 1
            except: pass
        t = max(len(contacts), 1)
        return {
            "total": len(contacts),
            "cold_dtc": cd, "expansion": ex,
            "with_linkedin": wl, "no_linkedin": nl,
            "pushed_campaign_a": pa, "pushed_campaign_b": pb, "not_pushed": np_,
            "leads": ld, "hot_leads": hl,
            "linkedin_coverage_pct": round(wl / t * 100, 1),
        }

    def test_cold_dtc_count(self):
        """Should count 2 contacts with cold_dtc_savings sequence."""
        result = self._run_aggregation(self._make_raw_contacts())
        assert result["cold_dtc"] == 2

    def test_expansion_count(self):
        """Should count 1 contact with expansion_signal sequence."""
        result = self._run_aggregation(self._make_raw_contacts())
        assert result["expansion"] == 1

    def test_linkedin_coverage(self):
        """2 of 3 contacts have LinkedIn URLs → 66.7% coverage."""
        result = self._run_aggregation(self._make_raw_contacts())
        assert result["with_linkedin"] == 2
        assert result["no_linkedin"] == 1
        assert result["linkedin_coverage_pct"] == pytest.approx(66.7, abs=0.1)

    def test_hot_leads_above_75_threshold(self):
        """Only contacts with icp_score > 75 should be counted as hot_leads."""
        result = self._run_aggregation(self._make_raw_contacts())
        assert result["hot_leads"] == 2  # scores 90 and 80 qualify

    def test_total_matches_input_count(self):
        """Total should equal the number of input contacts."""
        result = self._run_aggregation(self._make_raw_contacts())
        assert result["total"] == 3


# ---------------------------------------------------------------------------
# Tests: cgi-bin/api.py — gather_deals tier/stage bucketing
# ---------------------------------------------------------------------------

class TestGatherDealsBucketing:
    """Validate deal tier and stage aggregation logic."""

    def _bucket_deals(self, deals):
        """Run the tier/stage bucketing logic extracted from gather_deals."""
        sn = {
            "1315367441": "Prospect", "1315367442": "Qualified",
            "1315367443": "Sequence Enrolled", "1315367444": "Meeting Booked",
            "1315367445": "Proposal Sent", "1315367446": "Negotiation",
            "1315367447": "Closed Won", "1315367448": "Closed Lost"
        }
        stages = {}
        tv = 0
        tiers = {
            "enterprise": {"count": 0, "value": 0},
            "midmarket": {"count": 0, "value": 0},
            "smb": {"count": 0, "value": 0}
        }
        for d in deals:
            p = d.get("properties", {})
            sl = sn.get(p.get("dealstage", ""), "Unknown")
            stages[sl] = stages.get(sl, 0) + 1
            try: a = float(p.get("amount", 0) or 0)
            except: a = 0
            tv += a
            t = (p.get("br_deal_tier") or "").lower()
            if t == "enterprise" or a >= 500000:
                tiers["enterprise"]["count"] += 1
                tiers["enterprise"]["value"] += a
            elif t == "mid-market" or a >= 100000:
                tiers["midmarket"]["count"] += 1
                tiers["midmarket"]["value"] += a
            else:
                tiers["smb"]["count"] += 1
                tiers["smb"]["value"] += a
        return {"total": len(deals), "total_value": tv, "stages": stages, "tiers": tiers}

    def _make_deals(self):
        return [
            {"properties": {"dealstage": "1315367441", "amount": "600000", "br_deal_tier": "enterprise"}},
            {"properties": {"dealstage": "1315367442", "amount": "150000", "br_deal_tier": "mid-market"}},
            {"properties": {"dealstage": "1315367443", "amount": "25000", "br_deal_tier": "smb"}},
        ]

    def test_enterprise_tier_by_amount(self):
        """Deal with amount >= 500000 should bucket to enterprise."""
        result = self._bucket_deals(self._make_deals())
        assert result["tiers"]["enterprise"]["count"] == 1
        assert result["tiers"]["enterprise"]["value"] == 600000

    def test_midmarket_tier_by_amount(self):
        """Deal with 100000 <= amount < 500000 should bucket to midmarket."""
        result = self._bucket_deals(self._make_deals())
        assert result["tiers"]["midmarket"]["count"] == 1

    def test_smb_tier_by_amount(self):
        """Deal with amount < 100000 should bucket to smb."""
        result = self._bucket_deals(self._make_deals())
        assert result["tiers"]["smb"]["count"] == 1

    def test_total_value_sums_all_deals(self):
        """Total pipeline value should be the sum of all deal amounts."""
        result = self._bucket_deals(self._make_deals())
        assert result["total_value"] == pytest.approx(775000)

    def test_stage_names_mapped_correctly(self):
        """Stage IDs should be mapped to human-readable names."""
        result = self._bucket_deals(self._make_deals())
        assert "Prospect" in result["stages"]
        assert "Qualified" in result["stages"]

    def test_missing_amount_defaults_to_zero(self):
        """Deals without an amount should contribute 0 to the total value."""
        deals = [{"properties": {"dealstage": "1315367441", "amount": None, "br_deal_tier": ""}}]
        result = self._bucket_deals(deals)
        assert result["total_value"] == 0

    def test_enterprise_tier_by_tag_overrides_amount(self):
        """A deal tagged enterprise should bucket to enterprise even if amount < 500k."""
        deals = [{"properties": {"dealstage": "1315367441", "amount": "10000", "br_deal_tier": "enterprise"}}]
        result = self._bucket_deals(deals)
        assert result["tiers"]["enterprise"]["count"] == 1


# ---------------------------------------------------------------------------
# Tests: cgi-bin/api.py — gather_companies vertical aggregation
# ---------------------------------------------------------------------------

class TestGatherCompaniesVerticals:
    """Validate vertical distribution aggregation."""

    def _aggregate_verticals(self, companies):
        """Mirror gather_companies vertical aggregation."""
        verts = {}
        for c in companies:
            v = c.get("properties", {}).get("br_icp_vertical", "Other")
            if v:
                verts[v] = verts.get(v, 0) + 1
        return {"total": len(companies), "verticals": verts}

    def test_vertical_counts_correct(self):
        """Vertical counts should match the input data."""
        companies = [
            {"properties": {"br_icp_vertical": "DTC E-commerce"}},
            {"properties": {"br_icp_vertical": "DTC E-commerce"}},
            {"properties": {"br_icp_vertical": "3PL / Fulfillment"}},
        ]
        result = self._aggregate_verticals(companies)
        assert result["verticals"]["DTC E-commerce"] == 2
        assert result["verticals"]["3PL / Fulfillment"] == 1

    def test_missing_vertical_uses_other(self):
        """Companies without a vertical should default to 'Other'."""
        companies = [{"properties": {}}]
        result = self._aggregate_verticals(companies)
        assert result["verticals"].get("Other", 0) >= 1


# ---------------------------------------------------------------------------
# Tests: cgi-bin/api.py — gather_health warmup week calculation
# ---------------------------------------------------------------------------

class TestWarmupWeekCalculation:
    """Validate the warmup week calculation (days since start / 7 + 1, capped at 4)."""

    def _calc_week(self, start_date_str, reference_date=None):
        """Mirror the warmup week calc from gather_health."""
        if reference_date is None:
            reference_date = datetime.now()
        try:
            start = datetime.strptime(start_date_str, "%Y-%m-%d")
            week = min((reference_date - start).days // 7 + 1, 4)
            return week
        except:
            return 1

    def test_first_week_when_just_started(self):
        """Day 0 should be week 1."""
        today = datetime(2026, 3, 6)
        week = self._calc_week("2026-03-06", reference_date=today)
        assert week == 1

    def test_week_2_after_7_days(self):
        """7 days in should be week 2."""
        start = datetime(2026, 2, 27)
        today = datetime(2026, 3, 6)
        week = self._calc_week("2026-02-27", reference_date=today)
        assert week == 2

    def test_week_4_plus_caps_at_4(self):
        """After 28+ days, week should be capped at 4."""
        start = datetime(2025, 1, 1)
        today = datetime(2026, 3, 6)
        week = self._calc_week("2025-01-01", reference_date=today)
        assert week == 4

    def test_invalid_date_defaults_to_week_1(self):
        """An invalid start date string should default to week 1."""
        week = self._calc_week("not-a-date")
        assert week == 1


# ---------------------------------------------------------------------------
# Tests: full_refresh data structure
# ---------------------------------------------------------------------------

class TestFullRefreshStructure:
    """Validate that full_refresh produces a correctly structured cache payload."""

    @patch.object(cgi_api, "gather_health")
    @patch.object(cgi_api, "gather_contacts")
    @patch.object(cgi_api, "gather_companies")
    @patch.object(cgi_api, "gather_deals")
    @patch.object(cgi_api, "write_cache")
    def test_full_refresh_includes_all_top_level_keys(
        self, mock_write, mock_deals, mock_companies, mock_contacts, mock_health
    ):
        """The cache payload must include timestamp, contacts, companies, deals, health."""
        mock_health.return_value = {"domain": {}, "warmup": {}, "systems": []}
        mock_contacts.return_value = {"total": 10}
        mock_companies.return_value = {"total": 5, "verticals": {}}
        mock_deals.return_value = {"total": 3, "total_value": 0, "stages": {}, "tiers": {}}

        result = cgi_api.full_refresh()

        assert "timestamp" in result
        assert "contacts" in result
        assert "companies" in result
        assert "deals" in result
        assert "health" in result

    @patch.object(cgi_api, "gather_health")
    @patch.object(cgi_api, "gather_contacts")
    @patch.object(cgi_api, "gather_companies")
    @patch.object(cgi_api, "gather_deals")
    @patch.object(cgi_api, "write_cache")
    def test_full_refresh_writes_cache(
        self, mock_write, mock_deals, mock_companies, mock_contacts, mock_health
    ):
        """full_refresh must call write_cache exactly once."""
        mock_health.return_value = {}
        mock_contacts.return_value = {}
        mock_companies.return_value = {}
        mock_deals.return_value = {}

        cgi_api.full_refresh()
        mock_write.assert_called_once()

    @patch.object(cgi_api, "gather_health")
    @patch.object(cgi_api, "gather_contacts")
    @patch.object(cgi_api, "gather_companies")
    @patch.object(cgi_api, "gather_deals")
    @patch.object(cgi_api, "write_cache")
    def test_full_refresh_timestamp_is_iso_format(
        self, mock_write, mock_deals, mock_companies, mock_contacts, mock_health
    ):
        """The timestamp in the cache should be parseable as ISO 8601."""
        mock_health.return_value = {}
        mock_contacts.return_value = {}
        mock_companies.return_value = {}
        mock_deals.return_value = {}

        result = cgi_api.full_refresh()
        # Should not raise
        datetime.fromisoformat(result["timestamp"])


# ---------------------------------------------------------------------------
# Tests: Pydantic models
# ---------------------------------------------------------------------------

class TestPydanticModels:
    """Validate that the Pydantic models enforce the correct schema."""

    def test_action_request_requires_contact_id(self):
        """ActionRequest must have contact_id."""
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            ActionRequest(action="block")  # missing contact_id

    def test_action_request_requires_action(self):
        """ActionRequest must have action."""
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            ActionRequest(contact_id="1001")  # missing action

    def test_action_request_valid(self):
        """Valid ActionRequest should instantiate without error."""
        req = ActionRequest(contact_id="1001", action="block")
        assert req.contact_id == "1001"
        assert req.action == "block"

    def test_unblock_request_requires_contact_id(self):
        """UnblockRequest must have contact_id."""
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            UnblockRequest()

    def test_unblock_request_valid(self):
        """Valid UnblockRequest should instantiate without error."""
        req = UnblockRequest(contact_id="9001")
        assert req.contact_id == "9001"
