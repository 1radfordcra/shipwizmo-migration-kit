# Savings Calculator — Architecture Document

**App:** Broad Reach Shipping Savings Calculator  
**Type:** Pure static site (no server, no build step)  
**Status:** LIVE  
**Lines of code:** ~1,049 (HTML: 323, JS: 352, CSS base: 58, CSS style: 94, CSS page: 952, Python CGI: 222)

---

## Architecture Overview

The Savings Calculator is a prospect-facing lead generation tool. A visitor enters their shipping volume, weight profile, current carrier, and destination mix. The calculator instantly computes their estimated annual savings from switching to Broad Reach — using hardcoded carrier rate tables compared against Broad Reach's volume-tiered rates.

It is a **single-page static application** with no framework, no build pipeline, and no mandatory backend. All calculation logic runs entirely in the browser. The optional Python CGI backend (`cgi-bin/quote.py`) handles lead capture by forwarding form submissions to HubSpot as hot inbound leads.

### Data Flow Diagram

```
Browser
  │
  ├── index.html         ← Page structure, form markup
  │     loads base.css, style.css, page.css, app.js
  │
  ├── app.js (client-side)
  │     ├── User fills form (volume, weight, carrier, destinations)
  │     ├── calculateResults() → looks up carrier rate tables
  │     ├── Computes savings: (currentRate - broadReachRate) × annualVolume
  │     ├── Renders animated results panel (savings %, dollar amount, ROI)
  │     └── Lead capture form submitted
  │           │
  │           └── POST cgi-bin/quote.py  (optional — only on Python hosting)
  │                 └── Calls HubSpot Contacts API
  │                       → Creates contact tagged "hot_inbound_lead"
  │                       → Sets 19 custom properties (volume, savings, carrier, etc.)
  │
  └── No state persistence — all in memory, cleared on page refresh
```

---

## Decision Rationale

| Technology | Why It Was Chosen |
|---|---|
| Vanilla HTML/CSS/JS | No build step needed. Deploys as static files to any CDN (Azure Static Web Apps, Netlify, S3). Zero runtime dependencies. |
| Hardcoded rate tables | Carrier rate negotiations are stable for 12-month periods. Hardcoding avoids a database and keeps the app fully offline-capable. |
| Python CGI backend | Matches the Perplexity hosting pattern (CGI scripts served by Apache). On Azure migration, replace with a minimal Azure Function or direct HubSpot embed form. |
| No framework (React/Vue) | Adds bundle complexity with zero benefit for a single-page calculator. |
| IntersectionObserver animations | Smooth scroll-triggered reveals without any animation library dependency. |

---

## File-by-File Walkthrough

### `index.html` — 323 lines
Entry point. Contains the full page structure:
- Header with Broad Reach / Asendia branding (inline SVG logo)
- Hero section with savings headline
- Calculator form (`#calcForm`) — volume selector, weight profile, carrier checkboxes, destination mix sliders
- Results panel (hidden until calculation) — animated savings figure, carrier comparison breakdown
- Lead capture form (name, email, company, phone)
- Social proof section and footer
- Loads all CSS and `app.js` at bottom of `<body>`

### `app.js` — 352 lines
All calculator logic. Key sections:
- **Rate tables** (lines 12–78): Five carrier rate objects (`uspsRates`, `upsRates`, `fedexRates`, `dhlRates`, `otherRates`) and Broad Reach rates. Each has domestic/Canada/international tiers × four weight bands (under 1 lb, 1–2 lbs, 2–5 lbs, 5–10 lbs). Rates reflect 2026 commercial pricing with ~25% volume discounts.
- **`calculateResults()`** (central function): Reads form state, applies volume mid-point, looks up current carrier rates by weight tier, blends by destination %, computes annual savings = `(currentRate - broadReachRate) × annualVolume`.
- **Results rendering**: Animates the savings figure (counter animation), populates per-carrier comparison rows, shows savings percentage.
- **Lead form handler**: Collects contact info + calculator context, POSTs to `cgi-bin/quote.py`. Falls back gracefully if CGI is unavailable (shows in-page confirmation only).
- **IntersectionObserver**: Triggers `.reveal` class animations as sections scroll into view.
- **Shake animation**: Injected CSS keyframe for form validation feedback.

### `base.css` — 58 lines
CSS reset + base typography. Sets `box-sizing: border-box`, removes default margins, establishes font stack (system-ui with fallbacks), sets base `line-height` and `font-size`. No design tokens — bare reset layer.

### `style.css` — 94 lines
Design tokens and component styles. CSS custom properties for colors (`--color-primary`, `--color-text`, `--color-bg`, etc.), spacing scale, border radius. Header, hero, and main layout components.

### `page.css` — 952 lines
Full page-level styles. The bulk of visual design:
- Calculator card, form groups, selectors, sliders
- Results panel with animated savings display
- Carrier comparison table
- Lead capture form
- Social proof tiles
- Mobile-responsive breakpoints
- Loading states and transitions

### `cgi-bin/quote.py` — 222 lines
Python CGI script for lead capture. Triggered when a prospect submits the contact form.

Key functions:
- `respond(status, body)` — writes CGI-formatted HTTP response to stdout
- `hubspot_request(endpoint, method, data)` — makes authenticated calls to HubSpot REST API using `urllib` (no third-party dependencies)

Flow:
1. Reads POST body from `stdin` (CGI pattern — `CONTENT_LENGTH` env var)
2. Validates required fields (name, email, company)
3. Checks if contact already exists in HubSpot (`GET /crm/v3/objects/contacts?email=...`)
4. If exists: updates the contact with new calculator context
5. If new: creates contact with all 19 custom properties (carrier, volume, weight, destinations, current_cost, annual_savings, savings_pct, br_sequence_assigned = "hot_inbound_lead", etc.)
6. Returns `{"success": true}` or error JSON

**Security note:** The HubSpot PAT token was previously hardcoded — this has been fixed. The code now reads from the `HUBSPOT_PAT` environment variable. Set this in your deployment environment (Azure Key Vault recommended). The old token has been rotated. See SECURITY-AUDIT.md.

---

## Data Flow: Main User Journey

```
1. Prospect lands on page
   ↓
2. Selects monthly volume (dropdown: 200–10,000+)
   ↓
3. Selects weight profile (slider: % under 1 lb / 1–2 lbs / 2–5 lbs / 5–10 lbs)
   ↓
4. Checks current carriers (USPS, UPS, FedEx, DHL, Other)
   ↓
5. Selects destination mix (domestic %, Canada %, international %)
   ↓
6. Clicks "Calculate My Savings"
   ↓
7. app.js runs calculateResults():
   - Multiplies volume by 12 for annual figure
   - Looks up carrier rates for each weight band
   - Blends rates by weight profile %
   - Blends by destination mix %
   - Computes delta vs. Broad Reach rates
   ↓
8. Results panel animates into view:
   - Annual savings ($)
   - Savings percentage (%)
   - Per-package savings
   - Breakdown by carrier
   ↓
9. (Optional) Prospect fills lead form
   ↓
10. POST to cgi-bin/quote.py → HubSpot contact created
    → Contact tagged as hot_inbound_lead
    → Enters HubSpot sales sequence
```

---

## Known Limitations & Technical Debt

| Issue | Severity | Notes |
|---|---|---|
| HubSpot PAT hardcoded in quote.py | **CRITICAL** | Must be moved to env var before any public deployment. Token is live and functional. |
| Lead capture has no backend validation | High | The JS form sends data to CGI but doesn't re-validate server-side beyond required fields. Malformed data could enter HubSpot. |
| Carrier rates are hardcoded for 2026 | Medium | Rate tables will need manual updates each year. No admin UI. |
| No confirmation email to prospect | Medium | When a lead is captured, HubSpot creates the contact but no automatic email is sent to the prospect confirming receipt. |
| Form data lost on page refresh | Low | If a prospect calculates savings but doesn't submit the form, their data is gone. No localStorage persistence. |
| No rate-card versioning | Low | No audit trail of when rates were last updated. |
| No analytics tracking | Low | No Google Analytics or similar. Zero visibility into calculator usage. |
| CGI not available on Azure Static Web Apps | Info | `cgi-bin/quote.py` cannot run on a static host. Replace with an Azure Function trigger or embed a HubSpot native form. |

---

## Security Model

- **No authentication** — this is a public prospect-facing tool. No login required.
- **No session state** — purely stateless. Each page load is independent.
- **API token exposure** — the HubSpot PAT in `quote.py` is the only secret. It is currently hardcoded (see critical issue above).
- **No CORS configuration needed** — CGI is same-origin when served from the same server.
- **Input validation** — minimal client-side only. Name, email, company are required. No length limits, no sanitization.
- **No XSS vectors** — the app doesn't render user-provided input back to the DOM except through `innerHTML` in a controlled context.

---

## Migration Checklist (Perplexity → Azure)

- [ ] Create Azure Static Web App in Azure Portal
- [ ] Connect to GitHub repo (`shipwizmo/savings-calculator`)
- [ ] Copy all files: `index.html`, `app.js`, `base.css`, `style.css`, `page.css` into repo root
- [ ] **Replace CGI lead capture** with one of:
  - Option A: Azure Function (HTTP trigger) that calls HubSpot API — move `quote.py` logic there, set `HUBSPOT_PAT` in App Settings
  - Option B: Embed a native HubSpot form (`POST /crm/v3/objects/contacts`) directly from JS using the public Forms API (no server needed)
- [ ] Move `HUBSPOT_PAT` out of `quote.py` into Azure Key Vault / App Settings
- [ ] Set custom domain: `savings.brdrch.com` → Azure Static Web App
- [ ] No build step needed — deploy as-is
- [ ] Test: load page, run a calculation, verify results panel, submit lead form, verify contact appears in HubSpot
