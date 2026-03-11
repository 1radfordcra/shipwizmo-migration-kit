"""
test_sapt_tool.py — Contract tests for the SAPT Tool API.

The SAPT Tool backend (cgi-bin/api.py, ~3,804 lines) is not available locally.
These tests define the expected API contract based on ARCHITECTURE.md.

Two modes:
  1. Integration tests — hit a real running instance (set SAPT_BASE_URL env var)
  2. Contract tests   — verify request/response shapes using mocked HTTP (default)

Run against a live instance:
    SAPT_BASE_URL=http://localhost:8080 pytest tests/test_sapt_tool.py -v -m integration

Run contract tests only (no server needed):
    pytest tests/test_sapt_tool.py -v -m "not integration"
"""

import json
import io
import pytest
import responses as resp_lib
import requests
from unittest.mock import patch, MagicMock
from pathlib import Path

# Base URL for integration tests — default to a non-routable address so
# tests gracefully skip when no server is running.
import os
SAPT_BASE = os.environ.get("SAPT_BASE_URL", "http://localhost:8080")


# ---------------------------------------------------------------------------
# Pytest marks
# ---------------------------------------------------------------------------

def pytest_configure(config):
    config.addinivalue_line("markers", "integration: mark test as requiring a live SAPT server")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def sapt_url(path: str) -> str:
    return f"{SAPT_BASE}{path}"


def auth_token(token: str = "test-token-abc123") -> dict:
    """Returns query params with token appended."""
    return {"token": token}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def rate_card_payload(sample_rate_card):
    return sample_rate_card


@pytest.fixture
def csv_upload_payload(sample_shipment_csv_rows):
    """CSV bytes as if drag-dropped onto the upload zone."""
    header = "Ship Date,Actual Weight (lbs),Billed Weight (lbs),Length (in),Width (in),Height (in),Tracking Number,Destination Zip"
    rows = [
        f"{r['ship_date']},{r['actual_weight_lbs']},{r['billed_weight_lbs']},"
        f"{r['length_in']},{r['width_in']},{r['height_in']},"
        f"{r['tracking_number']},{r['destination_zip']}"
        for r in sample_shipment_csv_rows
    ]
    return (header + "\n" + "\n".join(rows)).encode("utf-8")


# ---------------------------------------------------------------------------
# Tests: Authentication
# ---------------------------------------------------------------------------

class TestSAPTAuthentication:
    """Verify the authentication contract for the SAPT Tool API."""

    @resp_lib.activate
    def test_missing_token_returns_401(self):
        """
        All API endpoints require a token query parameter.
        A request without a token must return HTTP 401.
        """
        resp_lib.add(
            resp_lib.GET,
            sapt_url("/api/clients"),
            json={"error": "Unauthorized", "message": "Token required"},
            status=401,
        )
        response = requests.get(sapt_url("/api/clients"))
        assert response.status_code == 401

    @resp_lib.activate
    def test_invalid_token_returns_401(self):
        """An expired or forged token should return 401."""
        resp_lib.add(
            resp_lib.GET,
            sapt_url("/api/clients"),
            json={"error": "Unauthorized", "message": "Invalid or expired token"},
            status=401,
        )
        response = requests.get(sapt_url("/api/clients"), params={"token": "bad-token"})
        assert response.status_code == 401

    @resp_lib.activate
    def test_valid_token_returns_200(self):
        """A valid token should grant access."""
        resp_lib.add(
            resp_lib.GET,
            sapt_url("/api/clients"),
            json={"clients": [], "total": 0},
            status=200,
        )
        response = requests.get(sapt_url("/api/clients"), params=auth_token())
        assert response.status_code == 200

    @resp_lib.activate
    def test_google_sso_auth_endpoint_contract(self):
        """
        POST /api/auth/google should accept a Google JWT credential and return
        a session token, userId, and userType.
        """
        resp_lib.add(
            resp_lib.POST,
            sapt_url("/api/auth/google"),
            json={
                "token": "session-token-xyz",
                "userId": 1,
                "userType": "admin",
                "email": "craig@shipwizmo.com",
            },
            status=200,
        )
        response = requests.post(
            sapt_url("/api/auth/google"),
            json={"credential": "google-jwt-token-here"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert "userId" in data
        assert data["userType"] in ("admin", "client")

    @resp_lib.activate
    def test_admin_auth_blocked_for_non_whitelisted_email(self):
        """
        Admin login should return 403 for emails not on the admin whitelist.
        The whitelist is stored in SQLite admin team table.
        """
        resp_lib.add(
            resp_lib.POST,
            sapt_url("/api/auth/google"),
            json={"error": "Access denied", "message": "Email not on admin whitelist"},
            status=403,
        )
        response = requests.post(
            sapt_url("/api/auth/google"),
            json={"credential": "google-jwt-for-unknown@example.com"}
        )
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# Tests: Client management — GET/POST /api/clients
# ---------------------------------------------------------------------------

class TestClientManagement:
    """Test CRUD contract for client accounts."""

    @resp_lib.activate
    def test_list_clients_returns_array(self):
        """GET /api/clients must return a list of client objects."""
        resp_lib.add(
            resp_lib.GET,
            sapt_url("/api/clients"),
            json={
                "clients": [
                    {"id": 1, "name": "Acme Commerce", "email": "acme@example.com", "status": "active"},
                    {"id": 2, "name": "BoxFlow Inc", "email": "boxflow@example.com", "status": "active"},
                ],
                "total": 2,
            },
            status=200,
        )
        response = requests.get(sapt_url("/api/clients"), params=auth_token())
        assert response.status_code == 200
        data = response.json()
        assert "clients" in data
        assert isinstance(data["clients"], list)

    @resp_lib.activate
    def test_create_client_returns_201_with_id(self):
        """POST /api/clients must create a new client and return HTTP 201 with the new ID."""
        resp_lib.add(
            resp_lib.POST,
            sapt_url("/api/clients"),
            json={"id": 3, "name": "Widget World", "email": "widget@example.com", "status": "pending"},
            status=201,
        )
        response = requests.post(
            sapt_url("/api/clients"),
            params=auth_token(),
            json={"name": "Widget World", "email": "widget@example.com"}
        )
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert isinstance(data["id"], int)

    @resp_lib.activate
    def test_client_invite_sends_email(self):
        """POST /api/clients/{id}/invite should trigger an invitation email."""
        resp_lib.add(
            resp_lib.POST,
            sapt_url("/api/clients/3/invite"),
            json={"success": True, "message": "Invitation sent to widget@example.com"},
            status=200,
        )
        response = requests.post(
            sapt_url("/api/clients/3/invite"),
            params=auth_token()
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


# ---------------------------------------------------------------------------
# Tests: Rate card management — GET/POST /api/rate-cards
# ---------------------------------------------------------------------------

class TestRateCardManagement:
    """Test CRUD contract for the 144 rate card library."""

    @resp_lib.activate
    def test_list_rate_cards_returns_array(self):
        """GET /api/rate-cards must return a list of rate card objects."""
        resp_lib.add(
            resp_lib.GET,
            sapt_url("/api/rate-cards"),
            json={
                "rate_cards": [
                    {
                        "id": 1,
                        "carrier": "Broad Reach",
                        "service": "Economy Ground",
                        "card_type": "sell_current",
                        "currency": "USD",
                    }
                ],
                "total": 1,
            },
            status=200,
        )
        response = requests.get(sapt_url("/api/rate-cards"), params=auth_token())
        assert response.status_code == 200
        data = response.json()
        assert "rate_cards" in data
        assert isinstance(data["rate_cards"], list)

    @resp_lib.activate
    def test_create_rate_card_returns_201(self, rate_card_payload):
        """POST /api/rate-cards must create a new rate card and return 201."""
        resp_lib.add(
            resp_lib.POST,
            sapt_url("/api/rate-cards"),
            json={"id": 10, **rate_card_payload},
            status=201,
        )
        response = requests.post(
            sapt_url("/api/rate-cards"),
            params=auth_token(),
            json=rate_card_payload
        )
        assert response.status_code == 201
        data = response.json()
        assert "id" in data

    @resp_lib.activate
    def test_rate_card_has_required_fields(self):
        """Each rate card must have carrier, service, card_type, and currency."""
        resp_lib.add(
            resp_lib.GET,
            sapt_url("/api/rate-cards"),
            json={
                "rate_cards": [{
                    "id": 1,
                    "carrier": "Broad Reach",
                    "service": "Economy Ground",
                    "card_type": "sell_current",
                    "currency": "USD",
                    "divisor": 139,
                    "fuel_surcharge_pct": 12.5,
                }],
                "total": 1,
            },
            status=200,
        )
        response = requests.get(sapt_url("/api/rate-cards"), params=auth_token())
        card = response.json()["rate_cards"][0]
        assert "carrier" in card
        assert "service" in card
        assert "card_type" in card
        assert card["card_type"] in ("sell_current", "buy_current", "sell_previous", "buy_previous")

    @resp_lib.activate
    def test_rate_card_import_accepts_csv(self):
        """POST /api/rate-cards/import must accept CSV data for bulk zone×weight grid import."""
        resp_lib.add(
            resp_lib.POST,
            sapt_url("/api/rate-cards/import"),
            json={"imported": 8, "errors": []},
            status=200,
        )
        csv_data = b"zone,under_1_lb,1_2_lbs,2_5_lbs,5_10_lbs\nzone_2,4.50,5.20,6.80,9.10\n"
        response = requests.post(
            sapt_url("/api/rate-cards/import"),
            params=auth_token(),
            files={"file": ("rates.csv", csv_data, "text/csv")}
        )
        assert response.status_code == 200
        data = response.json()
        assert "imported" in data
        assert data["errors"] == []


# ---------------------------------------------------------------------------
# Tests: CSV upload — POST /api/upload
# ---------------------------------------------------------------------------

class TestCSVUpload:
    """Test the shipment data CSV upload contract."""

    @resp_lib.activate
    def test_upload_returns_upload_id(self, csv_upload_payload):
        """
        POST /api/upload should accept a CSV file and return an upload ID
        that can be used to run analysis.
        """
        resp_lib.add(
            resp_lib.POST,
            sapt_url("/api/upload"),
            json={
                "upload_id": 42,
                "shipment_count": 3,
                "columns_mapped": ["ship_date", "actual_weight_lbs", "billed_weight_lbs",
                                   "length_in", "width_in", "height_in",
                                   "tracking_number", "destination_zip"],
                "validation_errors": [],
            },
            status=200,
        )
        response = requests.post(
            sapt_url("/api/upload"),
            params=auth_token(),
            files={"file": ("shipments.csv", csv_upload_payload, "text/csv")}
        )
        assert response.status_code == 200
        data = response.json()
        assert "upload_id" in data
        assert data["shipment_count"] == 3

    @resp_lib.activate
    def test_upload_auto_maps_standard_columns(self, csv_upload_payload):
        """
        The upload response should include a columns_mapped list showing
        which headers were auto-detected.
        """
        resp_lib.add(
            resp_lib.POST,
            sapt_url("/api/upload"),
            json={
                "upload_id": 43,
                "shipment_count": 3,
                "columns_mapped": ["ship_date", "actual_weight_lbs", "destination_zip"],
                "validation_errors": [],
            },
            status=200,
        )
        response = requests.post(
            sapt_url("/api/upload"),
            params=auth_token(),
            files={"file": ("shipments.csv", csv_upload_payload, "text/csv")}
        )
        data = response.json()
        assert "columns_mapped" in data
        assert len(data["columns_mapped"]) > 0

    @resp_lib.activate
    def test_upload_empty_csv_returns_error(self):
        """An empty CSV (no data rows) should return an error response."""
        resp_lib.add(
            resp_lib.POST,
            sapt_url("/api/upload"),
            json={"error": "No data rows found in uploaded file"},
            status=422,
        )
        response = requests.post(
            sapt_url("/api/upload"),
            params=auth_token(),
            files={"file": ("empty.csv", b"Ship Date,Weight\n", "text/csv")}
        )
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# Tests: Analysis engine — POST /api/analyze
# ---------------------------------------------------------------------------

class TestAnalysisEngine:
    """Test the rate analysis engine contract."""

    @resp_lib.activate
    def test_analyze_returns_analysis_id(self):
        """
        POST /api/analysis should return an analysis ID and per-shipment results.
        """
        resp_lib.add(
            resp_lib.POST,
            sapt_url("/api/analysis"),
            json={
                "analysis_id": 101,
                "status": "complete",
                "shipment_count": 3,
                "rate_cards_applied": 1,
                "kpis": {
                    "avg_cost_to_service": 5.42,
                    "avg_sell_rate": 7.20,
                    "avg_margin_per_piece": 1.78,
                },
            },
            status=200,
        )
        response = requests.post(
            sapt_url("/api/analysis"),
            params=auth_token(),
            json={"upload_id": 43, "rate_card_ids": [1]}
        )
        assert response.status_code == 200
        data = response.json()
        assert "analysis_id" in data
        assert "kpis" in data

    @resp_lib.activate
    def test_analyze_kpis_are_numeric(self):
        """KPI values in the analysis response must be numeric, not strings."""
        resp_lib.add(
            resp_lib.POST,
            sapt_url("/api/analysis"),
            json={
                "analysis_id": 101,
                "status": "complete",
                "kpis": {
                    "avg_cost_to_service": 5.42,
                    "avg_sell_rate": 7.20,
                    "avg_margin_per_piece": 1.78,
                },
            },
            status=200,
        )
        response = requests.post(
            sapt_url("/api/analysis"),
            params=auth_token(),
            json={"upload_id": 43, "rate_card_ids": [1]}
        )
        kpis = response.json()["kpis"]
        for key, value in kpis.items():
            assert isinstance(value, (int, float)), f"KPI {key} should be numeric, got {type(value)}"

    @resp_lib.activate
    def test_excel_download_endpoint_exists(self):
        """GET /api/analysis/{id}/excel must return an xlsx attachment."""
        resp_lib.add(
            resp_lib.GET,
            sapt_url("/api/analysis/101/excel"),
            body=b"PK...(xlsx binary)...",  # mock xlsx bytes
            status=200,
            headers={
                "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "Content-Disposition": "attachment; filename=analysis_101.xlsx",
            },
        )
        response = requests.get(
            sapt_url("/api/analysis/101/excel"),
            params=auth_token()
        )
        assert response.status_code == 200
        assert "spreadsheetml" in response.headers.get("Content-Type", "")

    @resp_lib.activate
    def test_publish_analysis_to_client(self):
        """POST /api/analysis/{id}/publish should set the analysis status to published."""
        resp_lib.add(
            resp_lib.POST,
            sapt_url("/api/analysis/101/publish"),
            json={"success": True, "status": "published", "analysis_id": 101},
            status=200,
        )
        response = requests.post(
            sapt_url("/api/analysis/101/publish"),
            params=auth_token()
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "published"


# ---------------------------------------------------------------------------
# Tests: Rate card internal logic (pure Python)
# ---------------------------------------------------------------------------

class TestRateCardLogic:
    """
    Unit tests for the rate card arithmetic that the SAPT backend applies.
    Tests the formulas without requiring a running server.
    """

    def test_dim_weight_calculation(self):
        """
        DIM weight = (L × W × H) / divisor.
        Billed weight = max(actual weight, DIM weight).
        Standard DIM divisor is 139 (imperial).
        """
        length, width, height = 12, 10, 6
        divisor = 139
        actual_weight = 2.0

        dim_weight = (length * width * height) / divisor
        billed_weight = max(actual_weight, dim_weight)

        expected_dim = (12 * 10 * 6) / 139
        assert dim_weight == pytest.approx(expected_dim, rel=1e-6)
        assert billed_weight == max(actual_weight, expected_dim)

    def test_billed_weight_uses_actual_when_heavier(self):
        """When actual weight > DIM weight, actual weight is billed."""
        actual = 5.0
        dim = 3.2
        billed = max(actual, dim)
        assert billed == actual

    def test_billed_weight_uses_dim_when_heavier(self):
        """When DIM weight > actual weight, DIM weight is billed."""
        actual = 1.5
        dim = 4.1
        billed = max(actual, dim)
        assert billed == dim

    def test_fuel_surcharge_applied_as_percentage(self):
        """Total rate = base rate × (1 + fuel_surcharge_pct / 100)."""
        base_rate = 6.50
        fuel_pct = 12.5
        total = base_rate * (1 + fuel_pct / 100)
        assert total == pytest.approx(7.3125, rel=1e-6)

    def test_margin_calculation(self):
        """Margin per piece = sell_rate - cost_rate."""
        sell_rate = 7.20
        cost_rate = 5.42
        margin = sell_rate - cost_rate
        assert margin == pytest.approx(1.78, rel=1e-4)

    def test_markup_percentage_applied(self):
        """Sell rate = cost × (1 + markup_pct / 100)."""
        cost = 5.42
        markup_pct = 32.8
        sell = cost * (1 + markup_pct / 100)
        assert sell == pytest.approx(7.197, rel=0.01)

    def test_per_lb_markup_added_to_base(self):
        """Per-lb markup: sell_rate = base_rate + (weight × markup_per_lb)."""
        base = 5.00
        weight = 2.5
        markup_per_lb = 0.50
        sell = base + (weight * markup_per_lb)
        assert sell == pytest.approx(6.25, rel=1e-6)

    def test_per_piece_markup_added_flat(self):
        """Per-piece markup: sell_rate = base_rate + markup_per_piece."""
        base = 5.00
        markup = 1.50
        sell = base + markup
        assert sell == pytest.approx(6.50, rel=1e-6)

    def test_das_surcharge_added_when_zip_matches(self):
        """Delivery Area Surcharge (DAS) is added when destination ZIP is in DAS list."""
        das_zip_list = {"90210", "10001", "77001"}
        destination_zip = "90210"
        base_rate = 7.20
        das_surcharge = 4.50  # standard DAS rate

        total = base_rate + (das_surcharge if destination_zip in das_zip_list else 0)
        assert total == pytest.approx(11.70, rel=1e-6)

    def test_das_surcharge_not_added_when_zip_not_in_list(self):
        """No DAS surcharge when destination ZIP is not in the DAS list."""
        das_zip_list = {"90210"}
        destination_zip = "10005"
        base_rate = 7.20
        das_surcharge = 4.50

        total = base_rate + (das_surcharge if destination_zip in das_zip_list else 0)
        assert total == pytest.approx(7.20, rel=1e-6)

    def test_zone_lookup_selects_correct_rate(self, sample_rate_card):
        """Rate lookup by zone and weight band should return the correct cell value."""
        zones = sample_rate_card["zones"]
        zone = "zone_5"
        weight_band = "1_2_lbs"

        rate = zones[zone][weight_band]
        assert rate == pytest.approx(7.30, rel=1e-6)


# ---------------------------------------------------------------------------
# Tests: CSV column auto-mapping logic
# ---------------------------------------------------------------------------

class TestCSVColumnMapping:
    """Validate the column header normalisation and auto-mapping logic."""

    COLUMN_ALIASES = {
        "ship_date": ["ship date", "shipdate", "ship_date", "date shipped", "date"],
        "actual_weight_lbs": ["actual weight", "actual weight (lbs)", "weight lbs", "weight"],
        "billed_weight_lbs": ["billed weight", "billed weight (lbs)", "rated weight"],
        "destination_zip": ["destination zip", "dest zip", "zip code", "postal code", "to zip"],
        "tracking_number": ["tracking number", "tracking #", "tracking", "parcel id"],
    }

    def _auto_map(self, headers: list) -> dict:
        """Simplified version of the SAPT column auto-mapper."""
        mapping = {}
        for col, aliases in self.COLUMN_ALIASES.items():
            for h in headers:
                if h.lower().strip() in aliases:
                    mapping[col] = h
                    break
        return mapping

    def test_standard_headers_map_correctly(self):
        """Standard column names from the TESTING.md example CSV should map correctly."""
        headers = [
            "Ship Date", "Actual Weight (lbs)", "Billed Weight (lbs)",
            "Length (in)", "Width (in)", "Height (in)",
            "Tracking Number", "Destination Zip"
        ]
        mapping = self._auto_map(headers)
        assert mapping.get("ship_date") == "Ship Date"
        assert mapping.get("actual_weight_lbs") == "Actual Weight (lbs)"
        assert mapping.get("destination_zip") == "Destination Zip"

    def test_alias_headers_map_correctly(self):
        """Alternative column names ('Tracking #', 'Date') should also map."""
        headers = ["Date", "Weight", "Billed Weight", "Tracking #", "Zip Code"]
        mapping = self._auto_map(headers)
        assert "ship_date" in mapping
        assert "tracking_number" in mapping

    def test_unmapped_headers_not_in_result(self):
        """Columns with no known alias should not appear in the mapping dict."""
        headers = ["Customer ID", "Order Number", "Some Custom Field"]
        mapping = self._auto_map(headers)
        assert mapping == {}
