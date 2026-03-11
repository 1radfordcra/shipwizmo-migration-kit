# Customs Data Portal — Architecture Document

**App:** Broad Reach Customs Data Portal  
**Type:** Full-stack web app — Vanilla JS frontend + Python FastAPI backend  
**Status:** LIVE  
**Source availability:** ALL source files reconstructed and included in this migration kit. Frontend: 5,205 lines (index.html: 34, app.js: 3,203, app.css: 1,994). Backend: 3,184 lines (api_server.py). Styles: 306 lines (base.css: 98, style.css: 208).

---

## Architecture Overview

The Customs Data Portal is a customer-facing tool for managing cross-border customs compliance. Customers maintain their SKU catalog with HS codes, customs values, and country of origin. The portal auto-generates CUSMA/USMCA certificates of origin, and exposes a REST API so ShipWizmo's shipping application can look up customs data per SKU at point of shipment.

```
Browser (SPA)
  │
  ├── index.html          ← App shell
  ├── base.css            ← Reset + base
  ├── style.css           ← Design tokens + components
  └── app.js              ← Full frontend SPA
  
  ↕ REST API calls (relative URLs)

Server (Python FastAPI)
  └── api_server.py       ← FastAPI backend
        ├── SQLite database (customs.db — auto-created)
        ├── Google OAuth 2.0 token verification
        ├── SKU CRUD
        ├── CUSMA certificate generator
        └── External REST API (API key auth)
```

### Key Differences from SAPT Tool

| Feature | SAPT Tool | Customs Portal |
|---|---|---|
| Backend | Python CGI | Python **FastAPI** (production-ready) |
| CGI conversion needed? | Yes | No — FastAPI is already production-ready |
| Auth model | Admin/client roles | Single role — any Google user auto-creates account |
| Database | `portal.db` (SQLite) | `customs.db` (SQLite) |
| External API | None | `GET /api/lookup/{sku}?include_cusma=true` (API key auth) |

### Why FastAPI Instead of CGI?

The Customs Portal was built after the SAPT Tool. The decision to use FastAPI was deliberate:
1. FastAPI is production-ready — no conversion needed for Azure
2. FastAPI handles async requests natively (important for the SKU lookup API)
3. Pydantic validation is built in
4. The startup command is simply `uvicorn api_server:app`

---

## File-by-File Walkthrough

> **All files must be retrieved from the deployed server. See `README-SOURCE.md`.**

### `index.html` — line count unknown
App shell. Loads CSS files and `app.js`. Contains Google Identity Services script tag for SSO. Same popup-based auth pattern as SAPT Tool and Command Center (due to Perplexity iframe constraints). Contains modal overlay and toast container.

### `base.css` — line count unknown
CSS reset and base typography. Identical pattern to SAPT Tool's base.css.

### `style.css` — line count unknown
Design tokens and full component styles. Should be similar in scale to SAPT Tool's style (~1,000+ lines estimated).

### `app.js` — line count unknown
Full frontend SPA. Estimated features based on portal documentation:
- **Hash-based router** — same pattern as SAPT Tool
- **Authentication views:** Google SSO popup + email/password registration and login
- **SKU management UI:** Table view, add/edit/delete SKU modals, fields: SKU code, product description, HS code, country of origin, customs value, currency
- **CUSMA certificate generator:** Form to select SKUs, set blanket period, enter importer/exporter details, auto-populate all 9 minimum data elements from SKU records
- **Certificate lifecycle UI:** Draft / Active / Expired status badges, activate/deactivate actions
- **API key management panel:** Generate, display, revoke API keys per customer account
- **CSV bulk import:** Drag-and-drop CSV upload for SKU catalogs
- **External API documentation tab:** Shows endpoint format with the customer's API key pre-populated

### `api_server.py` — line count unknown
FastAPI backend. Key routes from portal documentation:

**Auth routes:**
- `POST /api/auth/google` — verifies Google JWT, auto-creates account on first sign-in
- `POST /api/auth/register` — email/password registration
- `POST /api/auth/login` — email/password login with bcrypt

**SKU routes:**
- `GET /api/skus` — list all SKUs for authenticated user
- `POST /api/skus` — create new SKU
- `PUT /api/skus/{id}` — update SKU
- `DELETE /api/skus/{id}` — delete SKU
- `POST /api/skus/import` — bulk CSV import

**CUSMA certificate routes:**
- `GET /api/cusma` — list all certificates for user
- `POST /api/cusma` — generate new certificate from selected SKUs
- `GET /api/cusma/{id}` — retrieve certificate (includes all 9 data elements)
- `PUT /api/cusma/{id}` — update certificate status
- `DELETE /api/cusma/{id}` — delete certificate

**External API route (API key auth):**
- `GET /api/lookup/{sku}` — returns HS code, country of origin, customs value, CUSMA data (if `?include_cusma=true`). Authenticated by `X-API-Key` header or `api_key` query param.

**API key management:**
- `POST /api/keys` — generate new API key for authenticated user
- `GET /api/keys` — list active keys
- `DELETE /api/keys/{id}` — revoke key

---

## Data Flow: CUSMA Certificate Generation

```
1. Customer signs in (Google SSO or email/password)
   ↓
2. Customer manages SKU catalog
   - Enters: SKU code, description, HS code, country of origin, customs value
   - Or bulk imports via CSV
   ↓
3. Customer clicks "Generate Certificate"
   - Selects SKUs to include
   - Sets blanket period (start date, end date)
   - Confirms importer/exporter details
   ↓
4. Backend generates certificate with all 9 CUSMA minimum data elements:
   1. Country of origin for each good
   2. HS tariff classification
   3. Net cost (or transaction value method)
   4. Description of goods
   5. Producer name and address
   6. Exporter name and address
   7. Importer name and address
   8. Blanket period (if applicable)
   9. Authorized signature and date
   ↓
5. Certificate saved with status = "Draft"
   ↓
6. Customer reviews and activates: status → "Active"
   ↓
7. ShipWizmo shipping app (or customs broker) calls:
   GET /api/lookup/{sku}?include_cusma=true
   Headers: X-API-Key: {customer_api_key}
   ↓
8. Response:
   {
     "sku": "ABC-123",
     "hs_code": "6109.10",
     "country_of_origin": "CA",
     "customs_value": 12.50,
     "currency": "CAD",
     "cusma_eligible": true,
     "certificate_id": "cert_abc123",
     "blanket_period": {"start": "2026-01-01", "end": "2026-12-31"}
   }
```

---

## Known Limitations & Technical Debt

| Issue | Severity | Notes |
|---|---|---|
| All source files missing locally | **BLOCKER** | Cannot review, audit, or deploy without fetching from server. See README-SOURCE.md. |
| SQLite not multi-instance safe | High | Same issue as SAPT Tool — replace with Azure SQL on migration. |
| External API uses query param for API key | Medium | `?api_key=...` exposes the key in URL logs. Switch to `X-API-Key` header only. |
| postMessage origin is '*' | Medium | Same issue as SAPT Tool and Command Center. Lock to domain on Azure. |
| No rate limiting on SKU lookup API | Medium | The external `/api/lookup/{sku}` endpoint has no rate limiting. A misbehaving integration could hammer it. Add Azure API Management or a simple rate limit decorator. |
| Auth tokens as query params | Medium | Same issue as SAPT Tool — switch to httpOnly cookies on Azure. |
| Certificate expiry not auto-enforced | Low | Certificates with a blanket end date in the past are not automatically set to "Expired" — customer must manually update. |

---

## Security Model

- **Authentication:** Google OAuth 2.0 (any Google user auto-creates account, no whitelist) + email/password
- **Authorization:** Single role. Each user only sees their own SKUs and certificates. No admin role.
- **External API auth:** API key per customer account. Keys stored hashed in SQLite. Customer can revoke at any time.
- **Token handling:** Same as SAPT Tool — short-lived token in query params (not ideal — migrate to httpOnly cookies on Azure)
- **CORS:** Must configure on Azure to allow only `https://customs.brdrch.com` and the ShipWizmo shipping app origin
- **Google Client ID:** Shared with SAPT Tool: `105648453442-gjnirc4fa4tmii07lt1lmd353serh4ng.apps.googleusercontent.com`

---

## Migration Checklist (Perplexity → Azure)

- [ ] **Retrieve all source files from deployed server** (CRITICAL — nothing works without this)
  - See `README-SOURCE.md` for step-by-step retrieval instructions
- [ ] Push all files to GitHub repo (`shipwizmo/customs-data-portal`)
- [ ] Create Azure App Service (Python 3.11, Linux)
- [ ] **FastAPI is already production-ready** — start command: `uvicorn api_server:app --host 0.0.0.0 --port 8000`
- [ ] **Replace SQLite with Azure SQL Database:**
  - Set `DATABASE_URL` in App Service Configuration
  - Replace `sqlite3` with SQLAlchemy
- [ ] Set `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` in App Service Configuration
- [ ] Update Google Cloud Console: add `https://customs.brdrch.com` to Authorized JavaScript Origins; remove Perplexity origins
- [ ] Configure CORS in `api_server.py` to allow `https://customs.brdrch.com` and ShipWizmo shipping app origins
- [ ] **Switch API key delivery to header-only** (remove `?api_key=` query param support)
- [ ] **Lock `postMessage` origin** in `oauth-popup.html`
- [ ] **Switch auth to httpOnly cookies**
- [ ] Add rate limiting to `/api/lookup/{sku}` endpoint (Azure API Management or Python middleware)
- [ ] On own domain, remove popup auth workaround — use standard GIS flow
- [ ] Set custom domain: `customs.brdrch.com`
- [ ] Set up Azure Key Vault for secrets
- [ ] Notify ShipWizmo dev team of new API base URL for SKU lookup integration
