# Command Center — Architecture Document

**App:** Broad Reach Command Center (CEO Dashboard)  
**Type:** Static dashboard (data baked inline) + Python API proxy backend  
**Status:** LIVE  
**Lines of code:** index.html: 386, app.js: 1,188, style.css: 1,880, oauth-popup.html: 104, api_server.py: 211, cgi-bin/api.py: 234

---

## Architecture Overview

The Command Center is a Bloomberg Terminal-inspired CEO dashboard showing the live state of the B2B outbound sales system. It displays pipeline health, activity feed, contact metrics, and system status — all drawn from HubSpot CRM data.

### Data Architecture: Pre-Loaded Cache Pattern

The Command Center uses an unusual architecture forced by the Perplexity hosting environment:

```
Daily Cron (7 AM EST)
  └── cgi-bin/api.py runs full_refresh()
        ├── Calls HubSpot REST API (contacts, companies, deals, health)
        ├── Reads workspace batch JSON files (activity feed, blocked contacts)
        └── Writes dashboard_cache.json

dashboard_cache.json
  └── Read by api_server.py
        └── Served via GET /api/dashboard (FastAPI endpoint)

index.html
  └── window.__DASHBOARD_CACHE__ = { ...inlined JSON at build time... }
        └── app.js reads this object directly (no API call needed on load)
              └── Falls back to GET /api/dashboard if cache is stale
```

The critical detail: **the HubSpot data is inlined directly into `index.html`** as a JavaScript object (`window.__DASHBOARD_CACHE__`). This means the dashboard loads instantly with zero API calls on page open. The cache is refreshed daily by the cron job, and the inline data is the most recent snapshot.

### Why This Pattern?

- The Perplexity sandbox has network constraints — direct browser-to-HubSpot API calls are blocked by CORS
- Inlining the cache in the HTML guarantees the dashboard always has data, even if the API proxy is down
- Bloomberg-style dashboards are read-only — no need for real-time WebSocket connections
- On Azure migration: serve `index.html` as a static file, run the cache updater as an Azure Timer Trigger Function, and update the inline cache on each deploy

---

## File-by-File Walkthrough

### `index.html` — 386 lines
Full dashboard shell. Key features:
- **Inline cache blob**: `window.__DASHBOARD_CACHE__` contains the full HubSpot snapshot (contacts, companies, deals, health status, activity feed, blocked contacts). This is ~50KB of JSON embedded directly in the HTML.
- **Auth gate**: Google SSO popup button rendered before the dashboard div. Same postMessage pattern as SAPT Tool.
- **Loading overlay**: Hidden immediately when inline cache exists (via `#loading-overlay { display: none !important }` injected style).
- **Dashboard layout**: Fixed sidebar + main content area. Sidebar has clock, nav links, system status dot.
- **`window.confirm` override**: Hardcoded `return true` for Remove & Block Contact action during testing. Remove in production.
- Loads: Google Fonts (Inter), Chart.js (CDN), `style.css`, app.js loads inline

### `app.js` — 1,188 lines
Dashboard logic and rendering engine.

Key constants and state:
- `GOOGLE_CLIENT_ID` (line 13): `105648453442-gjnirc4fa4tmii07lt1lmd353serh4ng.apps.googleusercontent.com`
- `AUTH_MAX_AGE_MS` (line 14): 8 hours — auth state auto-expires
- `_authState`: In-memory auth state (not localStorage — iframe constraint)
- `API_BASE`: `port/8000` — FastAPI proxy port

Key functions:
- `updateClock()`: Updates sidebar clock every second
- `setSyncTime(ts)`: Shows "Last synced" timestamp from cache
- `renderKPIs(contacts, companies, deals, health)`: Animates KPI cards with counter animation (`animateTo()`)
- `renderPipeline(deals)`: Renders 8-stage pipeline funnel with deal counts and values
- `renderActivityFeed(items)`: Filterable activity log (Email, LinkedIn, Prospects). Expandable rows show full message content (email copy, LinkedIn message text).
- `renderSystems(systems)`: 7-system health grid with green/amber/red status indicators
- `renderVerticals(companies)`: Bar chart of ICP verticals (Chart.js)
- `renderBlockedContacts(contacts)`: Table of blocked/suppressed contacts with reason and cooldown date
- `_openGooglePopup()`: Opens `oauth-popup.html` as popup window for SSO
- `_receiveGoogleAuth(event)`: postMessage listener — receives auth token from popup, sets `_authState`
- `refreshDashboard()`: Calls `/api/dashboard` for fresh data (used for manual refresh)
- `initDashboard()`: Entry point — reads `window.__DASHBOARD_CACHE__`, calls all render functions

### `style.css` — 1,880 lines
Full design system. Bloomberg Terminal dark aesthetic:
- Dark background (`#0a0e17`), blue accent (`#0EA5E9`)
- Sidebar: fixed-width dark panel with nav items
- KPI cards: bordered boxes with animated number counters
- Activity feed: dense row layout with expand/collapse
- System health grid: colored status badges
- Pipeline funnel: horizontal bar visualization
- Auth gate: centered modal over blurred background
- Responsive: adapts to narrower viewports

### `oauth-popup.html` — 104 lines
Google SSO popup (same pattern as SAPT Tool, but simpler — admin-only, no client/admin split). Opens as standalone window, completes Google sign-in, passes credential back via `postMessage`, closes itself.

### `api_server.py` — 211 lines
FastAPI proxy server. Runs locally on port 8000. Provides:
- `GET /api/health` — returns `{"status": "ok"}`
- `GET /api/contact/{contact_id}` — proxies to HubSpot Contacts API, returns contact properties
- `GET /api/blocked-contacts` — reads `blocked_contacts` from HubSpot using custom property `br_contact_blocked = true`
- `POST /api/unblock` — updates HubSpot contact to clear blocked status
- `POST /api/action` — executes CRM actions: block, unblock, remove from sequence, mark as hot lead

Key pattern: This is a **pass-through proxy** — the browser can't call HubSpot directly (CORS), so `app.js` calls `localhost:8000/api/...` which calls HubSpot with the server-side PAT token.

Uses Pydantic models for request validation (`ActionRequest`, `UnblockRequest`).

### `cgi-bin/api.py` — 234 lines
CGI-based cache updater. Run by the daily cron to refresh `dashboard_cache.json`. Key functions:
- `hs_headers()` / `hs_post()`: HubSpot API calls with authentication
- `read_json(fn)` / `write_cache(data)`: File I/O for cache
- `gather_health()`: Checks domain DNS health (SPF, DKIM, DMARC), Expandi status, exclusion list count
- `gather_contacts()`: Fetches all HubSpot contacts with custom properties; computes DTC/3PL split, LinkedIn coverage
- `gather_companies()`: Fetches companies, aggregates ICP vertical distribution
- `gather_deals()`: Fetches all deals, aggregates by stage and tier, computes total pipeline value
- `full_refresh()`: Orchestrates all gather functions, writes `dashboard_cache.json`

### `dashboard_cache.json`
The live data cache. Updated daily by `cgi-bin/api.py`. Contains:
- `timestamp`: ISO timestamp of last refresh
- `contacts`: total counts, DTC/3PL split, LinkedIn coverage stats
- `companies`: total count, vertical distribution breakdown
- `deals`: total count, total value ($26.25M), stage breakdown, tier breakdown
- `health`: domain DNS results, warmup status, Expandi campaign status, system health array
- `activity_feed`: array of recent prospect discoveries, LinkedIn pushes, email events (each with expandable `summary` object)
- `blocked_contacts`: array of suppressed/blocked contacts

---

## Data Flow: Dashboard Refresh

```
Daily Cron (7 AM EST)
  └── cgi-bin/api.py :: full_refresh()
        ├── HubSpot API: GET contacts (all, paginated)
        ├── HubSpot API: GET companies (all, paginated)
        ├── HubSpot API: GET deals (all, paginated)
        ├── DNS check: brdrch.com SPF/DKIM/DMARC
        └── Writes dashboard_cache.json
              ↓
index.html regenerated
  └── dashboard_cache.json inlined as window.__DASHBOARD_CACHE__

Browser loads index.html
  └── app.js reads window.__DASHBOARD_CACHE__
        └── Calls all render functions
              ├── renderKPIs() — counter animation
              ├── renderPipeline() — funnel chart
              ├── renderActivityFeed() — filterable log
              ├── renderSystems() — health grid
              └── renderVerticals() — Chart.js bar chart
```

---

## Known Limitations & Technical Debt

| Issue | Severity | Notes |
|---|---|---|
| `window.confirm` always returns true | High | `index.html` overrides `confirm()` for testing. Any "are you sure?" dialog will auto-accept in production. Remove before deploying. |
| Auth state in memory only (iframe constraint) | Medium | `_authState` is a JS variable. Page refresh = logged out. On own domain, use `localStorage` or httpOnly cookies. |
| postMessage origin is '*' | Medium | `oauth-popup.html` sends to `'*'`. Should be locked to the app domain on Azure. |
| Cache can be stale (up to 24 hours) | Low | The dashboard shows data as of last cron run. No real-time updates. Add a "Refresh" button that calls `/api/dashboard` for fresh data. |
| api_server.py HubSpot token hardcoded | Medium | `HUBSPOT_TOKEN` may be hardcoded in `api_server.py`. Move to `HUBSPOT_PAT` env var on Azure. |
| No pagination in activity feed | Low | Activity feed shows the most recent N events from the cache. Historical data is not paginated. |
| Chart.js loaded from CDN | Low | No local fallback if CDN is unavailable. Vertical distribution chart would be blank. |

---

## Security Model

- **Authentication:** Google OAuth 2.0 via popup pattern. Access is for authorized Broad Reach team only (no public access).
- **No role-based access:** The Command Center is single-user (admin). No multi-user authorization logic.
- **API proxy auth:** `api_server.py` uses `HUBSPOT_TOKEN` env var for HubSpot calls. The browser never sees the PAT.
- **Blocked contacts:** Contact blocking/unblocking goes through the API proxy (`POST /api/action`) — this ensures HubSpot auth is server-side only.
- **Data sensitivity:** The dashboard cache contains real prospect names, emails, ICP scores, and message content. The cache JSON file should not be publicly accessible.

---

## Migration Checklist (Perplexity → Azure)

- [ ] Push all files to GitHub repo (`shipwizmo/command-center`)
- [ ] Deploy `index.html`, `app.js`, `style.css`, `oauth-popup.html` as Azure Static Web App
- [ ] **Convert `cgi-bin/api.py` to Azure Timer Trigger Function:**
  - Create `CommandCenterCacheUpdate` function (already stubbed in `azure-functions/`)
  - Move `full_refresh()` logic there
  - Schedule: `0 30 12 * * *` (12:30 UTC = 7:30 AM EST, after daily cron at 12:00 UTC)
- [ ] **Convert `api_server.py` to Azure Function (HTTP trigger):**
  - Expose `/api/contact/{id}`, `/api/action`, `/api/blocked-contacts` as HTTP functions
  - Or: migrate to Azure API Management layer
- [ ] Store `HUBSPOT_PAT` in Azure Key Vault
- [ ] Replace workspace file reads in cache updater with Azure Blob Storage
- [ ] Update `dashboard_cache.json` publishing: cache updater writes to Blob Storage, CI/CD inlines it into `index.html` on each deploy
- [ ] **Remove `window.confirm = function() { return true; }`** from `index.html`
- [ ] **Lock `postMessage` origin** in `oauth-popup.html` to `https://command.brdrch.com`
- [ ] On own domain, remove popup pattern and use standard Google GIS flow
- [ ] Set custom domain: `command.brdrch.com`
- [ ] Set up Application Insights for uptime monitoring
