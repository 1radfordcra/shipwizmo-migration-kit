# Broad Reach Savings Calculator

Prospect-facing shipping savings calculator. Visitors enter their volume and current costs, and instantly see what they'd save with Broad Reach.

## Quick Start

### Option 1: Open in Replit
[**Import on Replit →**](https://replit.com/github.com/shipwizmo/savings-calculator)

Click **Run** — the `.replit` config handles everything.

### Option 2: Docker
```bash
docker compose up
# Access: http://localhost:8000
```

### Option 3: Deploy to Azure
[![Deploy to Azure](https://aka.ms/deploytoazurebutton)](https://portal.azure.com/#create/Microsoft.Template/uri/https%3A%2F%2Fraw.githubusercontent.com%2Fshipwizmo%2Fsavings-calculator%2Fmain%2Fazuredeploy.json)

## Architecture
Static HTML/CSS/JS single-page app with optional Python CGI backend for quote form submissions.

## Environment Variables
See `.env.example` — only `HUBSPOT_PAT` needed if wiring up lead capture to HubSpot.

## Files
| File | Purpose |
|------|---------|
| `index.html` | Main calculator page |
| `app.js` | Calculator logic |
| `base.css` / `style.css` / `page.css` | Styles |
| `cgi-bin/quote.py` | Lead capture backend (optional) |

---
*Part of the [Broad Reach Migration Kit](https://github.com/shipwizmo) — built with [Perplexity Computer](https://www.perplexity.ai/computer)*
