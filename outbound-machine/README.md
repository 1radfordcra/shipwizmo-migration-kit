# Broad Reach Outbound Machine (v10)

Automated B2B outbound sales system running a 9-step daily cycle: Apollo enrichment → HubSpot sync → Expandi LinkedIn campaigns → Email warmup tracking → Slack/Notion reporting.

## Quick Start

### Option 1: Open in Replit
[**Import on Replit →**](https://replit.com/github.com/shipwizmo/outbound-machine)

Click **Run** — installs dependencies and runs the full daily cycle.
Use Replit Shell to run individual steps or set up Scheduled Jobs.

### Option 2: Docker (not applicable — this is a script runner, not a web server)
```bash
cp .env.example .env
# Edit .env with all API credentials
pip install -r requirements.txt
python run_daily_cycle.py
```

### Option 3: Deploy to Azure Functions
[![Deploy to Azure](https://aka.ms/deploytoazurebutton)](https://portal.azure.com/#create/Microsoft.Template/uri/https%3A%2F%2Fraw.githubusercontent.com%2Fshipwizmo%2Foutbound-machine%2Fmain%2Fazuredeploy.json)

The ARM template creates an Azure Function App with Timer Triggers for:
- Daily outbound cycle (6 AM ET)
- Hot lead monitor (every hour)
- Weekly performance report (Monday 9 AM ET)

## Architecture
- **Runner:** `run_daily_cycle.py` orchestrates the 9-step sequence
- **Crons:** Individual scripts in `crons/` for modular execution
- **Integrations:** HubSpot, Apollo.io, Expandi, Slack, Notion, Zapier

## Environment Variables
See `.env.example` — this app has the most env vars (20+). Key integrations:
- `HUBSPOT_PAT` — CRM operations
- `APOLLO_API_KEY` — Contact enrichment
- `SLACK_BOT_TOKEN` — Notifications
- `EXPANDI_*` — LinkedIn automation webhooks

---
*Part of the [Broad Reach Migration Kit](https://github.com/shipwizmo) — built with [Perplexity Computer](https://www.perplexity.ai/computer)*
