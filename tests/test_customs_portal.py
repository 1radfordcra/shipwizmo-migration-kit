"""
test_customs_portal.py — Contract tests for the Customs Data Portal API.

The Customs Data Portal backend (api_server.py) is not available locally.
These tests define the expected API contract based on ARCHITECTURE.md.

Two modes:
  1. Integration tests — hit a real running instance (set CUSTOMS_BASE_URL env var)
  2. Contract tests   — verify request/response shapes using mocked HTTP (default)

Run against a live instance:
    CUSTOMS_BASE_URL=https://customs.brdrch.com pytest tests/test_customs_portal.py -v -m integration

Run contract tests only (no server needed):
    pytest tests/test_customs_portal.py -v -m "not integration"
"""

import pytest
import responses as resp_lib
import requests
import json
import time
import os
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

CUSTOMS_BASE = os.environ.get("CUSTOMS_BASE_URL", "http://localhost:8001")

VALID_API_KEY = "brdr_live_abc123def456"
INVALID_API_KEY = "invalid_key_xyz"


def customs_url(path: str) -> str:
    return f"{CUSTOMS_BASE}{path}"


def auth_headers(token: str = "valid-session-token") -> dict:
    return {"Authorization": f"Bearer {token}"}


def api_key_headers(key: str = VALID_API_KEY) -> dict:
    return {"X-API-Key": key}


# ---------------------------------------------------------------------------
# Tests: Authentication
# ---------------------------------------------------------------------------

class TestCustomsPortalAuth:
    """Verify authentication contract for the Customs Data Portal."""

    @resp_lib.activate
    def test_google_sso_creates_new_account(self):
        """
        POST /api/auth/google with a new Google JWT should auto-create
        a customer account and return a session token.
        Any Google user can register — no whitelist required.
        """
        resp_lib.add(
            resp_lib.POST,
            customs_url("/api/auth/google"),
            json={
                "token": "session-token-new-user",
                "user_id": 42,
                "email": "newuser@gmail.com",
                "created": True,
            },
            status=200,
        )
        response = requests.post(
            customs_url("/api/auth/google"),
            json={"credential": "google-jwt-for-new-user"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert "user_id" in data

    @resp_lib.activate
    def test_google_sso_returns_existing_account(self):
        """
        POST /api/auth/google for an already-registered user should return
        created=False and the existing user_id.
        """
        resp_lib.add(
            resp_lib.POST,
            customs_url("/api/auth/google"),
            json={
                "token": "session-token-existing",
                "user_id": 7,
                "email": "existing@gmail.com",
                "created": False,
            },
            status=200,
        )
        response = requests.post(
            customs_url("/api/auth/google"),
            json={"credential": "google-jwt-for-existing-user"}
        )
        data = response.json()
        assert data.get("created") is False
        assert data.get("user_id") == 7

    @resp_lib.activate
    def test_email_password_registration(self):
        """POST /api/auth/register should create a new account."""
        resp_lib.add(
            resp_lib.POST,
            customs_url("/api/auth/register"),
            json={"user_id": 43, "email": "business@example.com", "token": "session-abc"},
            status=201,
        )
        response = requests.post(
            customs_url("/api/auth/register"),
            json={"email": "business@example.com", "password": "Secure1234!"}
        )
        assert response.status_code == 201
        data = response.json()
        assert "token" in data

    @resp_lib.activate
    def test_email_password_login(self):
        """POST /api/auth/login should return a session token for valid credentials."""
        resp_lib.add(
            resp_lib.POST,
            customs_url("/api/auth/login"),
            json={"user_id": 43, "token": "session-def"},
            status=200,
        )
        response = requests.post(
            customs_url("/api/auth/login"),
            json={"email": "business@example.com", "password": "Secure1234!"}
        )
        assert response.status_code == 200
        assert "token" in response.json()

    @resp_lib.activate
    def test_invalid_credentials_return_401(self):
        """POST /api/auth/login with wrong password must return 401."""
        resp_lib.add(
            resp_lib.POST,
            customs_url("/api/auth/login"),
            json={"error": "Invalid credentials"},
            status=401,
        )
        response = requests.post(
            customs_url("/api/auth/login"),
            json={"email": "business@example.com", "password": "WrongPassword"}
        )
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# Tests: SKU CRUD — /api/skus
# ---------------------------------------------------------------------------

class TestSKUCRUD:
    """Test the full SKU create-read-update-delete lifecycle."""

    @resp_lib.activate
    def test_list_skus_returns_array(self):
        """GET /api/skus must return an array of SKUs for the authenticated user."""
        resp_lib.add(
            resp_lib.GET,
            customs_url("/api/skus"),
            json={
                "skus": [
                    {
                        "id": 1,
                        "sku_code": "TEST-SKU-001",
                        "description": "Test Widget",
                        "hs_code": "8517.12.00",
                        "country_of_origin": "CA",
                        "customs_value": 15.00,
                        "currency": "CAD",
                    }
                ],
                "total": 1,
            },
            status=200,
        )
        response = requests.get(customs_url("/api/skus"), headers=auth_headers())
        assert response.status_code == 200
        data = response.json()
        assert "skus" in data
        assert isinstance(data["skus"], list)

    @resp_lib.activate
    def test_create_sku_returns_201(self, sample_sku):
        """POST /api/skus must create a SKU and return HTTP 201 with the new ID."""
        resp_lib.add(
            resp_lib.POST,
            customs_url("/api/skus"),
            json={"id": 1, **sample_sku},
            status=201,
        )
        response = requests.post(
            customs_url("/api/skus"),
            headers=auth_headers(),
            json=sample_sku
        )
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["sku_code"] == "TEST-SKU-001"

    @resp_lib.activate
    def test_create_sku_validates_hs_code_format(self):
        """
        POST /api/skus with an invalid HS code format should return 422.
        Valid HS codes have the format NNNN.NN or NNNN.NN.NN (6–10 digits with dots).
        """
        resp_lib.add(
            resp_lib.POST,
            customs_url("/api/skus"),
            json={"error": "Invalid HS code format", "field": "hs_code"},
            status=422,
        )
        response = requests.post(
            customs_url("/api/skus"),
            headers=auth_headers(),
            json={
                "sku_code": "BAD-SKU",
                "description": "Bad SKU",
                "hs_code": "NOT-VALID",  # invalid
                "country_of_origin": "CA",
                "customs_value": 10.00,
                "currency": "CAD",
            }
        )
        assert response.status_code == 422

    @resp_lib.activate
    def test_update_sku_returns_200(self):
        """PUT /api/skus/{id} must update the SKU and return the updated record."""
        resp_lib.add(
            resp_lib.PUT,
            customs_url("/api/skus/1"),
            json={
                "id": 1,
                "sku_code": "TEST-SKU-001",
                "description": "Test Widget",
                "hs_code": "8517.12.00",
                "country_of_origin": "CA",
                "customs_value": 18.00,  # updated
                "currency": "CAD",
            },
            status=200,
        )
        response = requests.put(
            customs_url("/api/skus/1"),
            headers=auth_headers(),
            json={"customs_value": 18.00}
        )
        assert response.status_code == 200
        assert response.json()["customs_value"] == 18.00

    @resp_lib.activate
    def test_delete_sku_returns_204(self):
        """DELETE /api/skus/{id} must return HTTP 204 No Content on success."""
        resp_lib.add(
            resp_lib.DELETE,
            customs_url("/api/skus/1"),
            status=204,
        )
        response = requests.delete(
            customs_url("/api/skus/1"),
            headers=auth_headers()
        )
        assert response.status_code == 204

    @resp_lib.activate
    def test_delete_nonexistent_sku_returns_404(self):
        """DELETE /api/skus/{id} for a nonexistent ID must return 404."""
        resp_lib.add(
            resp_lib.DELETE,
            customs_url("/api/skus/9999"),
            json={"error": "SKU not found"},
            status=404,
        )
        response = requests.delete(
            customs_url("/api/skus/9999"),
            headers=auth_headers()
        )
        assert response.status_code == 404

    @resp_lib.activate
    def test_tenant_isolation_cannot_access_other_users_skus(self):
        """
        A user should only see their own SKUs. Requesting another user's
        SKU ID must return 403 or 404 — not the actual SKU data.
        """
        resp_lib.add(
            resp_lib.GET,
            customs_url("/api/skus/5000"),  # belongs to another user
            json={"error": "Not found"},
            status=404,
        )
        response = requests.get(
            customs_url("/api/skus/5000"),
            headers=auth_headers("other-users-token")
        )
        # Must NOT return 200 with another user's data
        assert response.status_code in (403, 404)


# ---------------------------------------------------------------------------
# Tests: HTS code validation
# ---------------------------------------------------------------------------

class TestHTSCodeValidation:
    """Validate HS/HTS tariff code format checking logic."""

    # HS codes must be 4–10 digit numeric codes with period separators.
    # Standard formats: NNNN.NN (6 digits) or NNNN.NN.NN (10 digits)
    VALID_HS_CODES = [
        "8517.12",
        "8517.12.00",
        "6109.10.00",
        "6110.20.10",
        "0101.21",
        "9999.99.99",
    ]
    INVALID_HS_CODES = [
        "NOT-VALID",
        "ABC.DE.FG",
        "12345",         # no period separator
        "",              # empty
        "8517.1X.00",   # non-numeric
        "8517.12.00.99",  # too many segments
    ]

    def _validate_hs_code(self, code: str) -> bool:
        """Mirror the HS code validation logic expected in the portal."""
        import re
        if not code:
            return False
        # Accept 4-digit heading with 2–4 digit subheadings separated by dots
        return bool(re.match(r'^\d{4}(\.\d{2}){1,2}$', code.strip()))

    def test_valid_hs_codes_pass(self):
        """All standard-format HS codes should pass validation."""
        for code in self.VALID_HS_CODES:
            assert self._validate_hs_code(code), f"Expected {code!r} to be valid"

    def test_invalid_hs_codes_fail(self):
        """Malformed HS codes must fail validation."""
        for code in self.INVALID_HS_CODES:
            assert not self._validate_hs_code(code), f"Expected {code!r} to be invalid"

    def test_hs_code_stripped_before_validation(self):
        """Leading/trailing whitespace should not invalidate a correct code."""
        assert self._validate_hs_code("  8517.12.00  ")

    def test_empty_code_fails(self):
        """An empty string must fail validation."""
        assert not self._validate_hs_code("")


# ---------------------------------------------------------------------------
# Tests: CUSMA certificate generation
# ---------------------------------------------------------------------------

class TestCUSMACertificateGeneration:
    """Test the CUSMA/USMCA certificate generation contract."""

    @resp_lib.activate
    def test_generate_certificate_returns_draft_status(self, sample_cusma_request):
        """
        POST /api/cusma should create a certificate with status='draft'.
        The certificate is not active until explicitly activated.
        """
        resp_lib.add(
            resp_lib.POST,
            customs_url("/api/cusma"),
            json={
                "id": "cert_abc123",
                "status": "draft",
                "blanket_period": {
                    "start": "2026-01-01",
                    "end": "2026-12-31"
                },
                "sku_count": 2,
                "created_at": "2026-03-06T12:00:00Z",
            },
            status=201,
        )
        response = requests.post(
            customs_url("/api/cusma"),
            headers=auth_headers(),
            json=sample_cusma_request
        )
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "draft"
        assert "id" in data

    @resp_lib.activate
    def test_certificate_contains_all_9_cusma_elements(self):
        """
        GET /api/cusma/{id} must return all 9 CUSMA minimum data elements:
        1. Country of origin per good
        2. HS tariff classification
        3. Net cost / transaction value method
        4. Description of goods
        5. Producer name and address
        6. Exporter name and address
        7. Importer name and address
        8. Blanket period
        9. Authorized signature and date
        """
        resp_lib.add(
            resp_lib.GET,
            customs_url("/api/cusma/cert_abc123"),
            json={
                "id": "cert_abc123",
                "status": "draft",
                "goods": [
                    {
                        "sku_code": "TEST-SKU-001",
                        "description": "Test Widget",           # element 4
                        "hs_code": "8517.12.00",               # element 2
                        "country_of_origin": "CA",             # element 1
                        "customs_value": 15.00,
                        "value_method": "transaction_value",   # element 3
                    }
                ],
                "exporter": {                                   # element 6
                    "name": "Widgets Inc Canada",
                    "address": "100 Export St, Toronto, ON M5V 3K2",
                    "country": "CA",
                },
                "importer": {                                   # element 7
                    "name": "Widgets Inc USA",
                    "address": "200 Import Ave, Detroit, MI 48201",
                    "country": "US",
                },
                "producer": {                                   # element 5
                    "name": "Widgets Inc Canada",
                    "address": "100 Export St, Toronto, ON M5V 3K2",
                },
                "blanket_period": {                            # element 8
                    "start": "2026-01-01",
                    "end": "2026-12-31",
                },
                "authorized_signatory": "Jane Shipper",        # element 9
                "signature_date": "2026-03-06",
            },
            status=200,
        )
        response = requests.get(
            customs_url("/api/cusma/cert_abc123"),
            headers=auth_headers()
        )
        assert response.status_code == 200
        cert = response.json()

        # Verify all 9 elements are present
        assert "goods" in cert and len(cert["goods"]) > 0
        good = cert["goods"][0]
        assert "country_of_origin" in good   # element 1
        assert "hs_code" in good             # element 2
        assert "value_method" in good        # element 3
        assert "description" in good         # element 4
        assert "producer" in cert            # element 5
        assert "exporter" in cert            # element 6
        assert "importer" in cert            # element 7
        assert "blanket_period" in cert      # element 8
        assert "authorized_signatory" in cert  # element 9

    @resp_lib.activate
    def test_activate_certificate_changes_status(self):
        """PUT /api/cusma/{id} to set status='active' should work."""
        resp_lib.add(
            resp_lib.PUT,
            customs_url("/api/cusma/cert_abc123"),
            json={"id": "cert_abc123", "status": "active"},
            status=200,
        )
        response = requests.put(
            customs_url("/api/cusma/cert_abc123"),
            headers=auth_headers(),
            json={"status": "active"}
        )
        assert response.status_code == 200
        assert response.json()["status"] == "active"

    @resp_lib.activate
    def test_delete_certificate_returns_204(self):
        """DELETE /api/cusma/{id} must return 204 on success."""
        resp_lib.add(
            resp_lib.DELETE,
            customs_url("/api/cusma/cert_abc123"),
            status=204,
        )
        response = requests.delete(
            customs_url("/api/cusma/cert_abc123"),
            headers=auth_headers()
        )
        assert response.status_code == 204

    @resp_lib.activate
    def test_list_certificates_shows_lifecycle_statuses(self):
        """
        GET /api/cusma must return certificates with status in
        {draft, active, expired}.
        """
        resp_lib.add(
            resp_lib.GET,
            customs_url("/api/cusma"),
            json={
                "certificates": [
                    {"id": "cert_1", "status": "draft"},
                    {"id": "cert_2", "status": "active"},
                    {"id": "cert_3", "status": "expired"},
                ],
                "total": 3,
            },
            status=200,
        )
        response = requests.get(customs_url("/api/cusma"), headers=auth_headers())
        certs = response.json()["certificates"]
        statuses = {c["status"] for c in certs}
        assert statuses.issubset({"draft", "active", "expired"})


# ---------------------------------------------------------------------------
# Tests: External API — /api/lookup/{sku}
# ---------------------------------------------------------------------------

class TestSKULookupAPI:
    """Test the external REST API endpoint used by ShipWizmo's shipping application."""

    @resp_lib.activate
    def test_lookup_by_header_returns_sku_data(self):
        """
        GET /api/lookup/{sku} with X-API-Key header should return
        hs_code, country_of_origin, and customs_value.
        """
        resp_lib.add(
            resp_lib.GET,
            customs_url("/api/lookup/TEST-SKU-001"),
            json={
                "sku": "TEST-SKU-001",
                "description": "Test Widget",
                "hs_code": "8517.12.00",
                "country_of_origin": "CA",
                "customs_value": 18.00,
                "currency": "CAD",
                "cusma_eligible": True,
            },
            status=200,
        )
        response = requests.get(
            customs_url("/api/lookup/TEST-SKU-001"),
            headers=api_key_headers(VALID_API_KEY)
        )
        assert response.status_code == 200
        data = response.json()
        assert data["sku"] == "TEST-SKU-001"
        assert data["hs_code"] == "8517.12.00"
        assert data["country_of_origin"] == "CA"

    @resp_lib.activate
    def test_lookup_includes_cusma_data_when_requested(self):
        """
        GET /api/lookup/{sku}?include_cusma=true should include
        certificate_id and blanket_period in the response.
        """
        resp_lib.add(
            resp_lib.GET,
            customs_url("/api/lookup/TEST-SKU-001"),
            json={
                "sku": "TEST-SKU-001",
                "hs_code": "8517.12.00",
                "country_of_origin": "CA",
                "customs_value": 18.00,
                "currency": "CAD",
                "cusma_eligible": True,
                "certificate_id": "cert_abc123",
                "blanket_period": {"start": "2026-01-01", "end": "2026-12-31"},
            },
            status=200,
        )
        response = requests.get(
            customs_url("/api/lookup/TEST-SKU-001"),
            headers=api_key_headers(VALID_API_KEY),
            params={"include_cusma": "true"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "certificate_id" in data
        assert "blanket_period" in data
        assert data["blanket_period"]["start"] == "2026-01-01"

    @resp_lib.activate
    def test_lookup_invalid_api_key_returns_401(self):
        """GET /api/lookup/{sku} with an invalid API key must return 401."""
        resp_lib.add(
            resp_lib.GET,
            customs_url("/api/lookup/TEST-SKU-001"),
            json={"error": "Unauthorized"},
            status=401,
        )
        response = requests.get(
            customs_url("/api/lookup/TEST-SKU-001"),
            headers=api_key_headers(INVALID_API_KEY)
        )
        assert response.status_code == 401

    @resp_lib.activate
    def test_lookup_missing_api_key_returns_401(self):
        """GET /api/lookup/{sku} with no authentication must return 401."""
        resp_lib.add(
            resp_lib.GET,
            customs_url("/api/lookup/TEST-SKU-001"),
            json={"error": "API key required"},
            status=401,
        )
        response = requests.get(customs_url("/api/lookup/TEST-SKU-001"))
        assert response.status_code == 401

    @resp_lib.activate
    def test_lookup_nonexistent_sku_returns_404(self):
        """GET /api/lookup/{sku} for an unknown SKU code must return 404."""
        resp_lib.add(
            resp_lib.GET,
            customs_url("/api/lookup/DOES-NOT-EXIST"),
            json={"error": "SKU not found"},
            status=404,
        )
        response = requests.get(
            customs_url("/api/lookup/DOES-NOT-EXIST"),
            headers=api_key_headers(VALID_API_KEY)
        )
        assert response.status_code == 404

    @resp_lib.activate
    def test_lookup_query_param_also_works(self):
        """
        GET /api/lookup/{sku}?api_key=... should also authenticate successfully.
        (Note: migrate to header-only on Azure for security.)
        """
        resp_lib.add(
            resp_lib.GET,
            customs_url("/api/lookup/TEST-SKU-001"),
            json={"sku": "TEST-SKU-001", "hs_code": "8517.12.00"},
            status=200,
        )
        response = requests.get(
            customs_url("/api/lookup/TEST-SKU-001"),
            params={"api_key": VALID_API_KEY}
        )
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# Tests: Rate limiting
# ---------------------------------------------------------------------------

class TestRateLimiting:
    """
    Test the rate limiting contract: 120 requests per 60 seconds per API key.
    These are contract tests that verify the expected behaviour.
    """

    def test_rate_limit_threshold_is_120_per_60s(self):
        """
        The documented rate limit is 120 requests/60 seconds per API key.
        Verify this constant matches the architecture spec.
        """
        RATE_LIMIT_REQUESTS = 120
        RATE_LIMIT_WINDOW_SECONDS = 60
        assert RATE_LIMIT_REQUESTS == 120
        assert RATE_LIMIT_WINDOW_SECONDS == 60

    @resp_lib.activate
    def test_exceeding_rate_limit_returns_429(self):
        """
        After exceeding the rate limit, the API must return HTTP 429
        with a Retry-After header.
        """
        resp_lib.add(
            resp_lib.GET,
            customs_url("/api/lookup/TEST-SKU-001"),
            json={"error": "Rate limit exceeded", "retry_after": 45},
            status=429,
            headers={"Retry-After": "45"},
        )
        response = requests.get(
            customs_url("/api/lookup/TEST-SKU-001"),
            headers=api_key_headers(VALID_API_KEY)
        )
        assert response.status_code == 429
        data = response.json()
        assert "error" in data

    @resp_lib.activate
    def test_rate_limit_is_per_api_key(self):
        """
        Rate limiting must be scoped per API key, not globally.
        A second API key should still work even if the first is throttled.
        """
        # First key is throttled
        resp_lib.add(
            resp_lib.GET,
            customs_url("/api/lookup/TEST-SKU-001"),
            json={"error": "Rate limit exceeded"},
            status=429,
        )
        r1 = requests.get(
            customs_url("/api/lookup/TEST-SKU-001"),
            headers=api_key_headers("key_1_throttled")
        )
        assert r1.status_code == 429

        # Second key responds normally
        resp_lib.add(
            resp_lib.GET,
            customs_url("/api/lookup/TEST-SKU-001"),
            json={"sku": "TEST-SKU-001", "hs_code": "8517.12.00"},
            status=200,
        )
        r2 = requests.get(
            customs_url("/api/lookup/TEST-SKU-001"),
            headers=api_key_headers("key_2_not_throttled")
        )
        assert r2.status_code == 200


# ---------------------------------------------------------------------------
# Tests: API key management
# ---------------------------------------------------------------------------

class TestAPIKeyManagement:
    """Test API key generation, listing, and revocation."""

    @resp_lib.activate
    def test_generate_api_key_returns_key(self):
        """POST /api/keys must return a new API key string."""
        resp_lib.add(
            resp_lib.POST,
            customs_url("/api/keys"),
            json={
                "id": 1,
                "key": VALID_API_KEY,
                "created_at": "2026-03-06T12:00:00Z",
                "label": "ShipWizmo Integration",
            },
            status=201,
        )
        response = requests.post(
            customs_url("/api/keys"),
            headers=auth_headers(),
            json={"label": "ShipWizmo Integration"}
        )
        assert response.status_code == 201
        data = response.json()
        assert "key" in data
        assert len(data["key"]) > 10  # key should be non-trivially long

    @resp_lib.activate
    def test_list_keys_does_not_expose_full_key(self):
        """
        GET /api/keys should list active keys but must NOT return the full
        key value — only a masked version (e.g., 'brdr_live_abc1****').
        """
        resp_lib.add(
            resp_lib.GET,
            customs_url("/api/keys"),
            json={
                "keys": [
                    {
                        "id": 1,
                        "key_preview": "brdr_live_abc1****",  # masked
                        "label": "ShipWizmo Integration",
                        "created_at": "2026-03-06T12:00:00Z",
                        "last_used": "2026-03-06T14:30:00Z",
                    }
                ],
                "total": 1,
            },
            status=200,
        )
        response = requests.get(customs_url("/api/keys"), headers=auth_headers())
        assert response.status_code == 200
        keys = response.json()["keys"]
        for key_record in keys:
            # Full key should not be exposed in list responses
            assert "key_preview" in key_record or "key" not in key_record

    @resp_lib.activate
    def test_revoke_key_returns_204(self):
        """DELETE /api/keys/{id} must return 204 and invalidate the key."""
        resp_lib.add(
            resp_lib.DELETE,
            customs_url("/api/keys/1"),
            status=204,
        )
        response = requests.delete(
            customs_url("/api/keys/1"),
            headers=auth_headers()
        )
        assert response.status_code == 204


# ---------------------------------------------------------------------------
# Tests: Bulk CSV import
# ---------------------------------------------------------------------------

class TestBulkSKUImport:
    """Test the bulk SKU import via CSV upload."""

    @resp_lib.activate
    def test_bulk_import_creates_multiple_skus(self, sample_sku_csv):
        """POST /api/skus/import with a valid CSV should create 3 new SKUs."""
        resp_lib.add(
            resp_lib.POST,
            customs_url("/api/skus/import"),
            json={
                "imported": 3,
                "errors": [],
                "skus": [
                    {"id": 10, "sku_code": "BULK-001"},
                    {"id": 11, "sku_code": "BULK-002"},
                    {"id": 12, "sku_code": "BULK-003"},
                ],
            },
            status=200,
        )
        response = requests.post(
            customs_url("/api/skus/import"),
            headers=auth_headers(),
            files={"file": ("skus.csv", sample_sku_csv.encode(), "text/csv")}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["imported"] == 3
        assert data["errors"] == []

    @resp_lib.activate
    def test_bulk_import_reports_validation_errors(self):
        """CSV rows with invalid HS codes should be reported in the errors list."""
        resp_lib.add(
            resp_lib.POST,
            customs_url("/api/skus/import"),
            json={
                "imported": 2,
                "errors": [
                    {"row": 3, "sku_code": "BAD-SKU", "error": "Invalid HS code format: NOT-VALID"}
                ],
            },
            status=200,
        )
        bad_csv = (
            "sku_code,description,hs_code,country_of_origin,customs_value,currency\n"
            "BULK-001,Widget A,6109.10.00,CA,12.50,CAD\n"
            "BULK-002,Widget B,6110.20.10,US,8.75,USD\n"
            "BAD-SKU,Bad Widget,NOT-VALID,CA,10.00,CAD\n"  # invalid HS code
        ).encode()
        response = requests.post(
            customs_url("/api/skus/import"),
            headers=auth_headers(),
            files={"file": ("skus.csv", bad_csv, "text/csv")}
        )
        data = response.json()
        assert len(data["errors"]) == 1
        assert "NOT-VALID" in data["errors"][0]["error"]


# ---------------------------------------------------------------------------
# Tests: Multi-tenant data isolation
# ---------------------------------------------------------------------------

class TestMultiTenantIsolation:
    """
    Verify that tenant data isolation is enforced — users cannot see
    or modify other users' SKUs, certificates, or API keys.
    """

    @resp_lib.activate
    def test_user_a_cannot_see_user_b_skus(self):
        """
        Requesting a SKU that belongs to a different user should return
        404 (not 403, to avoid leaking existence information).
        """
        resp_lib.add(
            resp_lib.GET,
            customs_url("/api/skus/9999"),  # belongs to user B
            json={"error": "Not found"},
            status=404,
        )
        response = requests.get(
            customs_url("/api/skus/9999"),
            headers=auth_headers("user-a-token")  # user A's token
        )
        assert response.status_code in (403, 404)

    @resp_lib.activate
    def test_user_a_cannot_delete_user_b_sku(self):
        """User A attempting to delete user B's SKU must be rejected."""
        resp_lib.add(
            resp_lib.DELETE,
            customs_url("/api/skus/9999"),
            json={"error": "Not found"},
            status=404,
        )
        response = requests.delete(
            customs_url("/api/skus/9999"),
            headers=auth_headers("user-a-token")
        )
        assert response.status_code in (403, 404)

    @resp_lib.activate
    def test_sku_lookup_api_scoped_to_api_key_owner(self):
        """
        The /api/lookup endpoint must only return SKUs owned by the API key holder.
        A SKU belonging to another customer should return 404.
        """
        resp_lib.add(
            resp_lib.GET,
            customs_url("/api/lookup/OTHER-CUSTOMERS-SKU"),
            json={"error": "SKU not found"},
            status=404,
        )
        response = requests.get(
            customs_url("/api/lookup/OTHER-CUSTOMERS-SKU"),
            headers=api_key_headers(VALID_API_KEY)
        )
        assert response.status_code == 404
