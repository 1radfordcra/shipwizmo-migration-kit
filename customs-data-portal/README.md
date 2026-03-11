# Broad Reach Customs Data Portal

Internal tool for managing customs declarations, DAS (Delivered At Surface) shipments, and generating CUSMA certificates of origin for cross-border shipments.

## Quick Start

### Option 1: Open in Replit
[**Import on Replit →**](https://replit.com/github.com/shipwizmo/customs-data-portal)

Click **Run** — installs dependencies and starts the FastAPI server.

### Option 2: Docker
```bash
cp .env.example .env
# Edit .env with Google OAuth credentials
docker compose up
# Access: http://localhost:8000
```

### Option 3: Deploy to Azure
[![Deploy to Azure](https://aka.ms/deploytoazurebutton)](https://portal.azure.com/#create/Microsoft.Template/uri/https%3A%2F%2Fraw.githubusercontent.com%2Fshipwizmo%2Fcustoms-data-portal%2Fmain%2Fazuredeploy.json)

## Architecture
- **Frontend:** HTML/CSS/JS with tabbed interface (Shipments, Declarations, CUSMA Certs)
- **Backend:** FastAPI (Python 3.11) with SQLite
- **Auth:** Google OAuth 2.0

## Environment Variables
See `.env.example`. Key ones:
- `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` — OAuth credentials
- `DATABASE_PATH` — SQLite DB path (default: `./customs.db`)
- `ANTHROPIC_API_KEY` — Optional, for AI-powered CUSMA certificate generation

---
*Part of the [Broad Reach Migration Kit](https://github.com/shipwizmo) — built with [Perplexity Computer](https://www.perplexity.ai/computer)*
