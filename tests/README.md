# ShipWizmo Migration Kit — Automated Tests

Tests for all four apps in the migration kit. Written with pytest. Run these after any migration step to confirm nothing has broken.

---

## Quick Start

From the `migration-kit` directory:

```bash
# 1. Install dependencies
pip install -r tests/requirements.txt

# 2. Run all tests
pytest tests/ -v

# 3. Run with coverage report
pytest tests/ --cov=. --cov-report=term-missing
```

---

## What Each Test File Covers

### `test_savings_calculator.py` — 40+ tests
Pure unit tests for `savings-calculator/cgi-bin/quote.py`. No external services needed. All HubSpot calls are mocked.

| Test class | What it checks |
|---|---|
| `TestNameSplitting` | First/last name split logic (single name, compound last names, whitespace) |
| `TestRequiredFieldValidation` | Missing name/email/company returns correct error |
| `TestContactPropsBuilder` | HubSpot contact properties are built correctly (ICP scores, phone conditional) |
| `TestAmountCleaning` | `$45,000` → `45000`, non-numeric values become empty string |
| `TestDealPropsBuilder` | Deal name format, stage, amount, description |
| `TestNotesBuilder` | Carrier/volume/savings all appear in the HubSpot note |
| `TestHubSpotIntegration` | 201 new contact, 409 duplicate handling, deal association endpoint format |
| `TestCGIEnvironment` | `CONTENT_LENGTH` reading, invalid JSON, wrong HTTP method |
| `TestRateCalculationLogic` | Annual savings formula, blended rate by destination mix and weight band |

---

### `test_command_center.py` — 50+ tests
Tests for `command-center/api_server.py` (FastAPI proxy) and `command-center/cgi-bin/api.py` (cache updater).

| Test class | What it checks |
|---|---|
| `TestApiHealth` | `/api/health` returns 200 with `status: ok` |
| `TestGetContact` | HubSpot contact proxy, correct endpoint, correct properties requested |
| `TestGetBlockedContacts` | Blocked contacts aggregated, deduplicated, sorted, reason formatted as title case |
| `TestUnblockContact` | All five blocked properties reset, eligibility message |
| `TestExecuteAction` | Block sets cooldown=2099, remove sets completed=removed, invalid action = 400 |
| `TestCacheIO` | Write→read roundtrip, missing file, corrupt JSON |
| `TestGatherContactsAggregation` | cold_dtc/expansion counts, LinkedIn coverage %, hot_leads threshold |
| `TestGatherDealsBucketing` | Enterprise/midmarket/SMB tiers by amount and tag, total value, stage mapping |
| `TestGatherCompaniesVerticals` | Vertical distribution, missing vertical defaults to "Other" |
| `TestWarmupWeekCalculation` | Days-since-start → week number, capped at 4, invalid date defaults to 1 |
| `TestFullRefreshStructure` | Cache contains all required top-level keys, write_cache called once |
| `TestPydanticModels` | `ActionRequest` and `UnblockRequest` validation |

---

### `test_sapt_tool.py` — 35+ tests
Contract tests for the SAPT Tool API. The backend is not available locally, so these tests verify the expected API shape using mocked HTTP responses. They also include pure logic tests that run without any server.

| Test class | What it checks |
|---|---|
| `TestSAPTAuthentication` | Missing token → 401, invalid token → 401, Google SSO contract, admin whitelist |
| `TestClientManagement` | List clients, create client, invite email |
| `TestRateCardManagement` | List rate cards, create rate card, card_type enum values, CSV import |
| `TestCSVUpload` | Upload returns upload_id + shipment_count, column auto-mapping, empty CSV → 422 |
| `TestAnalysisEngine` | Analysis returns KPIs, KPIs are numeric, Excel endpoint returns xlsx, publish to client |
| `TestRateCardLogic` | DIM weight calc, billed weight (max of actual vs DIM), fuel surcharge %, margin, markup types, DAS surcharge |
| `TestCSVColumnMapping` | Standard headers auto-map, alias headers map, unknown headers excluded |

---

### `test_customs_portal.py` — 50+ tests
Contract tests for the Customs Data Portal. The backend is not available locally.

| Test class | What it checks |
|---|---|
| `TestCustomsPortalAuth` | Google SSO auto-creates account, returns existing account, email/password registration and login |
| `TestSKUCRUD` | Full create/read/update/delete lifecycle, HS code format validation, tenant isolation |
| `TestHTSCodeValidation` | Valid/invalid HS code patterns (pure Python regex logic) |
| `TestCUSMACertificateGeneration` | Certificate created as draft, all 9 CUSMA elements present, lifecycle transitions |
| `TestSKULookupAPI` | X-API-Key header auth, include_cusma param, invalid key → 401, missing key → 401, nonexistent SKU → 404, query param also works |
| `TestRateLimiting` | 120 req/60s limit constant, rate limit returns 429 with Retry-After, per-key scoping |
| `TestAPIKeyManagement` | Generate key, list doesn't expose full key, revoke key |
| `TestBulkSKUImport` | 3 SKUs imported, validation errors reported per-row |
| `TestMultiTenantIsolation` | User A cannot read/delete user B's SKUs, API key lookup scoped to owner |

---

### `test_outbound_machine.py` — 55+ tests
Pure unit tests for the outbound cron system logic. No external services needed.

| Test class | What it checks |
|---|---|
| `TestICPScoring` | Strong ICP profile scores above 60, existing client disqualified (-100), pure B2B penalised, hot_lead threshold, individual criterion weights |
| `TestCooldownSystem` | Active/expired/exact-day cooldown, permanent sentinel, cooldown duration by reason (sequence=180d, bounce=365d, optout=permanent) |
| `TestContactQueuingLogic` | Clean contact can be queued, permanently blocked cannot, active cooldown blocks, already-in-Expandi blocks, expired cooldown allows |
| `TestWarmupScheduleCalculation` | Week 1=10, Week 2=20, Week 3=35, Week 4+=50 (capped), invalid date defaults to week 1, schedule is monotonically increasing |
| `TestExpandiPayloadFormatting` | Required fields, correct campaign_id, LinkedIn URL as profile_url, ICP score tag, validation for empty campaign/URL |
| `TestAntiPollutionRules` | Below-ICP contacts not pushed, 180-day cooldown enforced after sequence, 365-day after bounce, opt-out permanent, batch filtering removes ineligible contacts, daily volume capped at warmup limit |

---

## Running Specific Tests

```bash
# One file
pytest tests/test_savings_calculator.py -v

# One test class
pytest tests/test_command_center.py::TestExecuteAction -v

# One test
pytest tests/test_outbound_machine.py::TestCooldownSystem::test_optout_is_permanent_and_never_expires -v

# All tests matching a pattern
pytest tests/ -k "cooldown" -v

# Skip integration tests (those requiring a live server)
pytest tests/ -m "not integration" -v

# Integration tests only (requires SAPT_BASE_URL or CUSTOMS_BASE_URL env var)
SAPT_BASE_URL=http://localhost:8080 pytest tests/test_sapt_tool.py -m integration -v
CUSTOMS_BASE_URL=http://localhost:8001 pytest tests/test_customs_portal.py -m integration -v
```

---

## Coverage Report

```bash
pytest tests/ --cov=. --cov-report=term-missing --cov-report=html
# Opens htmlcov/index.html for a visual coverage map
```

---

## Running Integration Tests Against a Live Server

For `test_sapt_tool.py` and `test_customs_portal.py`, integration tests hit a real server. Set the base URL environment variable before running:

```bash
# SAPT Tool
export SAPT_BASE_URL=https://portal.brdrch.com
pytest tests/test_sapt_tool.py -m integration -v

# Customs Portal
export CUSTOMS_BASE_URL=https://customs.brdrch.com
pytest tests/test_customs_portal.py -m integration -v
```

Contract tests (the default) run without any server using mocked HTTP — they verify that request/response shapes are correct.

---

## Test Architecture Decisions

**Why are SAPT Tool and Customs Portal tests contract-style?**
The backend source files for both apps are only on the deployed Perplexity server (not in this kit). Contract tests let Rozano verify that migrated instances respond with the expected shapes even before having access to the source.

**Why does test_command_center.py import the real modules?**
`api_server.py` and `cgi-bin/api.py` are available in the kit, so we can import and test them directly with mocked HubSpot calls.

**Why are outbound machine tests pure Python?**
The outbound machine logic is spread across multiple cron scripts. The business rules (ICP scoring, cooldown calculation, warmup schedule) are extracted into plain functions that can be validated without touching HubSpot or Expandi.

---

## Adding New Tests

1. Add a new test class to the relevant file, or create a new file `tests/test_your_feature.py`
2. Import fixtures from `conftest.py` — see that file for available fixtures
3. Mock external services using `@responses.activate` (for HTTP) or `@patch` (for function calls)
4. Add a docstring to every test explaining what it validates
5. Run `pytest tests/ -v` to confirm all tests pass

---

## Known Limitations

| Limitation | Notes |
|---|---|
| No browser tests for JS calculator logic | The `app.js` rate table logic runs in the browser. These tests mirror the formulas in Python. For full coverage, add Playwright or Cypress tests. |
| SAPT/Customs integration tests require a live server | Set `SAPT_BASE_URL` / `CUSTOMS_BASE_URL` env vars to run them. |
| HubSpot API calls are all mocked | Tests verify logic and payload structure — not that HubSpot actually accepts the data. Run Test SC-3 from TESTING.md to verify the live HubSpot connection. |
| Expandi payload tests are contract-only | Verify actual Expandi campaign behavior manually using TESTING.md procedures. |
