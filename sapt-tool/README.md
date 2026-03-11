# SAPT Tool (Shipping Analysis & Pricing Tool)

Full-featured customer portal with 144 rate cards across 8 carriers, real-time zone lookups, accessorial calculations, Excel report generation, and multi-user role management.

## Quick Start

### Option 1: Open in Replit
[**Import on Replit →**](https://replit.com/github.com/shipwizmo/sapt-tool)

Click **Run** — installs dependencies and starts the FastAPI server automatically.

### Option 2: Docker
```bash
cp .env.example .env
# Edit .env with your Google OAuth credentials
docker compose up
# Access: http://localhost:8000
```

### Option 3: Deploy to Azure
[![Deploy to Azure](https://aka.ms/deploytoazurebutton)](https://portal.azure.com/#create/Microsoft.Template/uri/https%3A%2F%2Fraw.githubusercontent.com%2Fshipwizmo%2Fsapt-tool%2Fmain%2Fazuredeploy.json)

## Architecture
- **Frontend:** 7,047-line JS app with tabbed interface (Dashboard, Clients, Rate Engine, Reports)
- **Backend:** FastAPI (Python 3.11) with SQLite, 18 database tables
- **Auth:** Google OAuth 2.0 with role-based access (admin/user)

## Environment Variables
See `.env.example` for all required variables. Key ones:
- `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` — OAuth credentials
- `ADMIN_EMAIL` — Initial admin account
- `CORS_ORIGINS` — Allowed origins for API calls

---
*Part of the [Broad Reach Migration Kit](https://github.com/shipwizmo) — built with [Perplexity Computer](https://www.perplexity.ai/computer)*
