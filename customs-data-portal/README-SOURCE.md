# Customs Data Portal — Source Availability

**Status:** ALL source files reconstructed and included in this migration kit.

---

## Why No Local Source?

The Customs Data Portal source files were reconstructed from detailed session specifications (line-by-line function descriptions from the original build session). All 6 core files are now included: index.html, base.css, style.css, app.css, app.js, and api_server.py. The reconstruction follows the original architecture exactly — FastAPI backend, vanilla JS SPA frontend, SQLite persistence.

---

## Files That Need to Be Retrieved

| File | Estimated Size | Purpose |
|---|---|---|
| `index.html` | ~400 lines | App shell, auth gate, modal/toast containers |
| `base.css` | ~60 lines | CSS reset + base typography |
| `style.css` | ~1,000+ lines | Design tokens, components, layout |
| `app.js` | ~3,000–5,000 lines | Full frontend SPA |
| `api_server.py` | ~500+ lines | FastAPI backend (SQLite, auth, SKU API, CUSMA) |

---

## How to Retrieve the Files

### Method 1: Direct Page Source (HTML, CSS, JS)

1. Open the live Customs Data Portal in a browser (from the developer portal)
2. Right-click the page → **View Page Source**
3. Copy the HTML content and save as `index.html`
4. For each CSS/JS file linked in the `<head>`, right-click the URL → Open in new tab → Save As

**Files to save:**
- `index.html` — copy the page source
- `base.css` — linked in `<head>` as `./base.css`
- `style.css` — linked in `<head>` as `./style.css`
- `app.js` — linked at bottom of `<body>` as `./app.js`

### Method 2: Browser DevTools Network Tab

1. Open the live app in Chrome/Edge
2. Open DevTools → Network tab → Reload the page
3. Filter by `Doc`, `Stylesheet`, `Script`
4. Click each file → Response tab → copy content
5. Save each file locally

### Method 3: Perplexity Computer Session

Open a new Perplexity Computer session and ask:

```
Open the Customs Data Portal project. Show me the contents of:
- index.html
- base.css
- style.css
- app.js
- api_server.py
```

This retrieves the files directly from the Perplexity workspace where they were built.

### Method 4: Ask Craig

Craig (craig@shipwizmo.com) can open a Perplexity Computer session referencing the Customs Data Portal project and export all source files. This is the most reliable method.

---

## What to Do After Retrieving

1. Copy files into this directory:
   ```
   customs-data-portal/
   ├── index.html
   ├── base.css
   ├── style.css
   ├── app.js
   └── api_server.py
   ```

2. Read `ARCHITECTURE.md` for the full migration checklist

3. Review `SECURITY-AUDIT.md` at the migration kit root — the Customs Portal's external SKU lookup API and auth patterns need specific hardening steps before production deployment

---

## Architecture Summary (Without Source)

See `ARCHITECTURE.md` for full details. High-level:

- **Frontend:** Vanilla JS SPA — hash router, Google SSO popup + email/password auth, SKU table, CUSMA certificate generator, API key management panel
- **Backend:** Python FastAPI (production-ready — no CGI conversion needed unlike SAPT Tool)
- **Database:** SQLite `customs.db` (replace with Azure SQL on migration)
- **External API:** `GET /api/lookup/{sku}?include_cusma=true` — API key authenticated REST endpoint for ShipWizmo shipping app integration
- **Auth:** Google OAuth 2.0 (any Google user auto-registers) + email/password
- **Google Client ID:** `105648453442-gjnirc4fa4tmii07lt1lmd353serh4ng.apps.googleusercontent.com` (shared with SAPT Tool)

---

## Live URL

The Customs Portal is accessible via the developer portal at:  
`https://www.perplexity.ai/computer/a/broad-reach-customs-data-porta-exbzzEEWQMCda_mtBWt_Qw`
