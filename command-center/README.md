# Broad Reach Command Center

Bloomberg-style real-time dashboard pulling from HubSpot CRM. Shows pipeline value, deal stages, contact activity, and enables direct feed actions (block/remove/unblock contacts).

## Quick Start

### Option 1: Open in Replit
[**Import on Replit →**](https://replit.com/github.com/shipwizmo/command-center)

Click **Run** — serves the static dashboard on port 8000.

### Option 2: Docker
```bash
cp .env.example .env
# Edit .env with HubSpot PAT
docker compose up
# Access: http://localhost:8000
```

### Option 3: Deploy to Azure
[![Deploy to Azure](https://aka.ms/deploytoazurebutton)](https://portal.azure.com/#create/Microsoft.Template/uri/https%3A%2F%2Fraw.githubusercontent.com%2Fshipwizmo%2Fcommand-center%2Fmain%2Fazuredeploy.json)

## Architecture
- **Dashboard:** Static HTML/JS — can deploy to Azure Static Web Apps
- **API Proxy:** FastAPI server (`api_server.py`) for HubSpot API calls
- **Cache:** `dashboard_cache.json` updated by cron scripts

## Environment Variables
See `.env.example`. Key ones:
- `HUBSPOT_PAT` — HubSpot Private App Token (Account: 6282372)
- `GOOGLE_CLIENT_ID` — For OAuth-gated access
- `CORS_ORIGINS` — Allowed frontend origins

---
*Part of the [Broad Reach Migration Kit](https://github.com/shipwizmo) — built with [Perplexity Computer](https://www.perplexity.ai/computer)*
