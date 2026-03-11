# SAPT Tool — Architecture Document

**App:** SAPT Tool — Shipping Analysis & Pricing Tool (Broad Reach Customer Portal)  
**Type:** Full-stack SPA — Vanilla JS frontend + Python CGI backend  
**Status:** LIVE  
**Lines of code:** Frontend: 8,093 lines (index.html: 49, app.js: 7,879, oauth-popup.html: 165). Backend: 6,923 lines (cgi-bin/api.py: 2,207, api_server.py: 4,716). Support: 906 lines (excel_generator.py). All source files extracted from live deployment and available in this migration kit.

---

## Architecture Overview

The SAPT Tool is the core deal-closing engine for Broad Reach. A prospective customer uploads their shipping invoice data as CSV, and the system rates every shipment against 144 rate cards from 8 carriers. The admin team reviews results in an analysis workbench, adjusts markups with live sliders, and publishes a branded Excel proposal to the client.

The architecture follows a **CGI-hosted full-stack pattern** dictated by Perplexity Computer's hosting constraints:

```
Browser (SPA)
  │
  ├── index.html          ← Shell: loads CSS libs and app.js
  ├── app.js              ← Entire 7,879-line SPA (no framework)
  └── oauth-popup.html    ← Standalone Google SSO window (postMessage bridge)
  
  ↕ REST API calls to /cgi-bin/api.py
  
Server (Python CGI)
  └── cgi-bin/api.py      ← ~3,804-line monolithic Python backend
        ├── SQLite database (portal.db — auto-created, file-local)
        ├── Google OAuth 2.0 token verification
        ├── 144 rate card engine
        ├── Zone file resolution
        ├── DAS surcharge calculation
        ├── Excel generation (openpyxl)
        └── HubSpot invite emails
```

### Why No Framework?

Vanilla JS was chosen because:
1. No build step — code is edited and deployed directly, critical for AI-assisted development
2. No npm, no bundler, no lock file versioning issues
3. The entire frontend is a single `app.js` file, easy to inspect and debug
4. Works natively in the Perplexity hosting environment without any compilation

### Why Python CGI?

Python CGI (`cgi-bin/api.py`) is the **Perplexity-specific hosting pattern** — the only way to run server-side Python in a Perplexity Computer app. It is NOT a production pattern. On Azure migration, this must be replaced with FastAPI or Flask.

### Why SQLite?

Zero-config persistence. No database server to provision, no connection string. For a single-server deployment serving tens of clients, SQLite is appropriate. For Azure multi-instance, replace with Azure SQL Database (the `.env.example` has the `DATABASE_URL` variable pre-configured for this).

---

## File-by-File Walkthrough

### `index.html` — 49 lines
Minimal shell. Loads:
- Google Fonts (via CDN)
- `base.css` and `style.css` (from deployed server — NOT in this kit, see note below)
- `chart.js` (via CDN, for analysis visualization)
- `accounts.google.com/gsi/client` (Google Identity Services, for SSO)
- `app.js` (the entire application)

Also injects a mock data override for the demo client (Sarah's account, user ID 1) that returns pre-canned analysis data for demo purposes.

### `app.js` — 7,879 lines
The entire frontend application. Key architectural sections:

**State management** (lines 9–21):  
A global `state` object holds all application state: `userId`, `userType` (admin/client), `token`, `currency`, `analysis`, `rateCards`, `selectedCards`, etc. No Flux/Redux pattern — mutations happen directly on the state object and trigger re-renders.

**API layer** (lines 39–65):  
`api(path, opts)` is the single HTTP client. Appends `?token=` to every request. Handles 401 (auto-logout) and network errors. Uses `fetch()` with `credentials: 'include'`.

**Router** (lines 109–140):  
Hash-based routing (`#/dashboard`, `#/analysis/123`, etc.). `router()` reads `location.hash`, determines auth state, and renders the appropriate view by setting `app.innerHTML`.

**Authentication views** (lines 200–420):  
- `renderClientLogin()` — client-facing login with Google SSO button and email/password fallback collapsible section
- `renderAdminLogin()` — identical layout with admin-specific endpoint
- `handleGoogleCredential()` — receives Google JWT from the GIS library, POSTs to `/api/auth/google`
- The Google Client ID is hardcoded: `105648453442-gjnirc4fa4tmii07lt1lmd353serh4ng.apps.googleusercontent.com`

**Google SSO popup pattern** (see `oauth-popup.html`):  
Because the app runs inside a Perplexity iframe, `google.accounts.id.prompt()` is blocked by the browser. The workaround: clicking "Sign in with Google" opens `oauth-popup.html` as a new top-level window via `window.open()`. That popup completes the Google sign-in and passes the credential back via `window.opener.postMessage()`. On Azure (own domain), remove this workaround and use standard GIS flow.

**CSV upload and data mapping** (lines ~800–1200):  
Drag-and-drop CSV upload. Auto-detects column headers for: Ship Date, Actual Weight, Billed Weight, Dimensions, Tracking #. Supports any shipping export format. Parses CSV, normalizes units (imperial/metric), validates required fields, sends to backend.

**Rate card management** (lines ~2000–2800):  
Admin UI for managing 144 rate cards. Cards are typed: `sell_current`, `buy_current`, `sell_previous`, `buy_previous`. Each card has: carrier, service, divisor (DIM weight), fuel surcharge config, currency, and CSV-imported zone×weight grids.

**Analysis Workbench** (lines ~3500–5500):  
The core admin experience. Markup sliders (%, per-lb, per-piece) per selected rate card. Real-time KPI updates: Avg Cost to Service, Avg Sell Rate, Avg Margin Per Piece. Master P&L table with daily/weekly/monthly/annual projections. Download/publish actions.

**Client-facing analysis view** (lines ~5500–7000):  
Client sees: Data Summary tab (carrier mix charts, avg weight, total spend), Analysis tab (results per service after admin publishes), Excel download button.

**Excel download** (lines ~7000–7200):  
Triggers `GET /api/analysis/{id}/excel?token=...`. The backend generates a multi-sheet Excel workbook (openpyxl) with navy-branded Executive Summary, per-line Detail sheet, and Summary sheet.

### `oauth-popup.html` — 165 lines
Standalone browser window for Google SSO. Self-contained page that:
1. Loads Google Identity Services library
2. Renders one button: "Sign in with Google"
3. On credential callback: reads `window.opener` context to detect if this was an admin or client login
4. POSTs credential to appropriate backend endpoint
5. Calls `window.opener.postMessage({token, userId, userType, ...}, '*')` to pass auth state back
6. Closes itself

**Security note:** The `postMessage` origin is `'*'` — should be locked to the app's specific origin on Azure. See SECURITY-AUDIT.md.

### `base.css` — NOT IN KIT
Reset + base typography. These CSS files were served by the Perplexity Computer runtime environment and are not independently versioned. For migration, recreate from the deployed SAPT Tool instance or use the Customs Data Portal's `base.css` as a starting point (same design system).

### `style.css` — NOT IN KIT
Design tokens and full component styles (~1,000+ lines estimated). Same situation as `base.css` — served by the runtime, not in version control. The Customs Data Portal's `app.css` shares the same design language and can be used as a reference.

### `cgi-bin/api.py` — ~3,804 lines — NOT IN KIT
Python CGI backend. This file runs on the live Perplexity Computer server. A FastAPI equivalent (`api_server.py`, 4,716 lines) is included in this kit and covers the same API surface. Use `api_server.py` as the migration starting point — it already has proper route definitions, Pydantic models, and CORS configuration.

Key API routes (from portal documentation):
- `POST /api/auth/google` — verifies Google JWT, creates/updates user record
- `POST /api/auth/login` — email/password auth with bcrypt
- `GET/POST /api/clients` — CRUD for client accounts
- `POST /api/clients/{id}/invite` — sends invitation email via HubSpot
- `GET/POST /api/rate-cards` — manage 144 rate cards
- `POST /api/rate-cards/import` — bulk CSV import of zone×weight grids
- `POST /api/analysis` — run analysis: accepts CSV data, applies all rate cards
- `GET /api/analysis/{id}/excel` — generate and return Excel workbook
- `POST /api/analysis/{id}/publish` — publish results to client view
- `GET/POST /api/accessorials` — 19 accessorial rule types
- `GET/POST /api/zone-files` — zone chart versioning
- `GET/POST /api/das-files` — DAS zip code list versioning
- `GET/POST /api/induction-locations` — multi-induction management
- `GET/POST /api/admin/team` — admin user whitelist management

---

## Data Flow: Client Analysis Journey

```
1. Admin invites client (email sent via HubSpot)
   ↓
2. Client clicks invite link → opens SAPT Tool
   ↓
3. Client signs in via Google SSO (popup pattern) or email/password
   ↓
4. Client lands on Upload page
   ↓
5. Client drags CSV of shipping invoices onto upload zone
   app.js parses CSV → auto-maps columns → validates
   POST /api/upload → backend stores raw data in SQLite
   ↓
6. Client reviews Data Summary tab
   (carrier mix, avg weight, total spend, weekly/annual projections)
   Client confirms data looks correct
   ↓
7. Admin is notified. Admin opens Analysis Workbench.
   ↓
8. Admin selects rate cards from library (starts unselected)
   Backend: runs rating engine for each selected card:
     - Resolves zone (origin ZIP + destination ZIP → zone file lookup)
     - Applies DIM weight (max of actual vs. DIM using configurable divisor)
     - Looks up rate from zone × weight grid
     - Applies fuel surcharge formula
     - Checks DAS list for surcharge applicability
     - Applies 19 accessorial rules
     - Computes buy cost + sell price + margin
   Results appear in table as cards are selected (live re-rating)
   ↓
9. Admin adjusts markup sliders
   KPIs update in real time (no API call — pure JS computation)
   Admin reviews Master P&L table
   ↓
10. Admin clicks "Publish to Client"
    POST /api/analysis/{id}/publish → sets status = published
    ↓
11. Client logs in, sees published analysis
    Excel download button appears
    ↓
12. Client clicks Download Excel
    GET /api/analysis/{id}/excel?token=...
    Backend generates openpyxl workbook → returns as .xlsx attachment
    Branded workbook: Executive Summary + Detail + Summary sheets
```

---

## Known Limitations & Technical Debt

| Issue | Severity | Notes |
|---|---|---|
| Excel download endpoint has NO token validation | **CRITICAL** | The endpoint accepts a `token` parameter but does not validate it. Anyone who guesses a client ID can download the file. Must be locked down before production. |
| Document upload is metadata-only | High | "Upload Document" stores filename string only — no actual file is stored. Wire to Azure Blob Storage during migration. |
| Python CGI must be replaced | High | CGI is Perplexity-specific. Migrate to FastAPI (add `uvicorn`, reorganize routes as FastAPI path functions). |
| SQLite file-local = no multi-instance | High | On Azure App Service multi-instance deployment, SQLite breaks. Replace with Azure SQL or PostgreSQL. |
| postMessage origin is '*' | Medium | `oauth-popup.html` uses `postMessage(data, '*')`. Should be locked to the app domain. |
| Session state in memory (iframe constraint) | Medium | Auth state is held in the `state` JS object, not in localStorage or cookies, because the app ran in a Perplexity iframe. On own domain, use proper httpOnly cookies. |
| No raw processed data download for clients | Low | Clients get the branded Excel but cannot download the raw mapped data file. |
| Early analyses produce thin Excel | Low | Analyses created before the Excel upgrade (e.g., Acme Commerce) only get a summary sheet. Re-run the analysis to get the full format. |
| No rate table admin UI freshness indicator | Low | No visual indicator of when rate cards were last updated or their effective date. |
| base.css and style.css not in kit | Info | These CSS files are served by the Perplexity runtime and not independently versioned. Use `api_server.py` (FastAPI) as the migration target — CSS can be recreated from the deployed instance or based on the Customs Data Portal's shared design system. |
| cgi-bin/api.py not in kit | Info | The CGI backend runs on the live server. The included `api_server.py` (FastAPI, 4,716 lines) covers the same API surface and is the recommended migration starting point. |

---

## Security Model

- **Authentication:** Google OAuth 2.0 (primary) + email/password with bcrypt (fallback). Google JWTs verified server-side using Google's public keys via `/api/auth/google`.
- **Authorization:** Two roles: `admin` and `client`. Role is returned from the backend at login and stored in `state.userType`. All admin routes check user type on the backend.
- **Admin whitelist:** Admin access is restricted to email addresses in an admin team whitelist stored in SQLite. Adding/removing admins is done via the Settings panel.
- **Session tokens:** Short-lived tokens (admin: 30 days, client: 7 days) stored as query parameters. **Not ideal** — on Azure, switch to httpOnly session cookies.
- **Google Client ID:** `105648453442-gjnirc4fa4tmii07lt1lmd353serh4ng.apps.googleusercontent.com` — must be added to Google Cloud Console Authorized JavaScript Origins for any new domain.
- **Excel endpoint vulnerability:** See critical issue above.
- **postMessage:** No origin validation currently. Must be hardened on Azure.

---

## Migration Checklist (Perplexity → Azure)

- [ ] Fetch `base.css` and `style.css` from deployed SAPT instance (or recreate from Customs Portal's shared design system)
- [ ] Push all code to GitHub repo (`shipwizmo/sapt-tool`)
- [ ] Create Azure App Service (Python 3.11, Linux)
- [ ] **Replace Python CGI with FastAPI:**
  - Rename `api.py` to `main.py`
  - Add `from fastapi import FastAPI; app = FastAPI()`
  - Convert each CGI route block to a FastAPI path function
  - Add `uvicorn main:app` as the startup command
- [ ] **Replace SQLite with Azure SQL Database:**
  - Set `DATABASE_URL` env var in App Service Configuration
  - Replace `sqlite3` calls with SQLAlchemy or direct `pyodbc`
- [ ] Set `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` in App Service Configuration (not code)
- [ ] Set `ADMIN_EMAIL` to `craig@shipwizmo.com`
- [ ] Update Google Cloud Console: add Azure domain to Authorized JavaScript Origins and Redirect URIs; remove `sites.pplx.app` and `perplexity.ai`
- [ ] **Fix Excel download token validation** (CRITICAL — do this first)
- [ ] **Lock `postMessage` origin** in `oauth-popup.html` to new domain
- [ ] **Switch auth to httpOnly cookies** (remove token-as-query-param pattern)
- [ ] On own domain, remove `oauth-popup.html` and switch to standard `google.accounts.id.renderButton()` flow
- [ ] Set custom domain: `portal.brdrch.com`
- [ ] Set up Azure Key Vault for secrets
- [ ] Wire "Upload Document" to Azure Blob Storage
