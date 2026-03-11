# Broad Reach Outbound Machine — Cron Scripts

This directory contains the four Python scripts that power the Broad Reach B2B outbound prospecting system. They were originally run as scheduled tasks on Perplexity Computer and have been reconstructed here as standalone Python scripts for migration to Azure Functions or any other scheduler (cron, Render, Railway, GitHub Actions, etc.).

---

## Scripts at a glance

| Script | What it does | Schedule |
|---|---|---|
| `daily_cron_v10.py` | Full daily outbound prospecting cycle | 7:00 AM EST daily |
| `hot_lead_monitor.py` | Detects genuine prospect replies in HubSpot | Hourly, Mon–Fri 8 AM–6 PM EST |
| `weekly_report_cron.py` | Weekly performance report → Slack + Notion | Mondays 9:00 AM EDT |
| `hubspot_sequence_enroll.py` | Helper utility for sequence enrollment | Manual / on-demand |

---

## Script details

### 1. `daily_cron_v10.py` — Daily Outbound Cycle

**What it does**

Runs the full B2B prospecting pipeline every morning. Pulls contacts from HubSpot that were sourced via Apollo (`br_source=apollo`), applies qualification filters, enforces anti-pollution cooldowns, sends outbound emails via HubSpot's Engagements API (direct send, not sequences — see the connected inbox bug note below), and pushes LinkedIn-eligible contacts to Expandi.

**Pipeline steps**

| Step | What happens |
|---|---|
| 0.5 | Safety guard: aborts if `active_clients_exclusion_list.txt` has fewer than 100 entries |
| 1 | Syncs active client exclusion list from Notion |
| 2 | Queries HubSpot for uncontacted Apollo contacts |
| 2.5 | ICP scoring filter: requires `br_icp_score >= 60` and senior title |
| 2.7 | Anti-pollution cooldown: opt-out/bounce exclusions, max 3 sequences/contact, max 3 contacts/company/90 days, 14-day same-company cooldown |
| 3 | USA/Canada HQ filter: hard-disqualifies non-US/CA companies |
| 4 | Reads `warmup_tracker.json` to enforce daily send limit (5→10→20→25/day) |
| 5 | Sends emails via HubSpot Engagements API (direct send workaround) |
| 6 | Pushes LinkedIn contacts to Expandi (Campaign A: cold_dtc_savings / Campaign B: expansion_signal) |
| 7 | Updates Notion dashboard |

**Cron expression**
```
0 0 12 * * *     # Azure Functions (12:00 UTC = 7:00 AM EST)
0 7 * * *        # Linux cron (7:00 AM server-local time)
```

**State files read/written**
- `active_clients_exclusion_list.txt` — active client domains (never contact)
- `warmup_tracker.json` — email warmup status and daily limit
- `physical_address.txt` — CAN-SPAM footer address
- `daily_cron_run_log.json` — run history (last 90 days)

---

### 2. `hot_lead_monitor.py` — Hot Lead Monitor

**What it does**

Polls HubSpot every hour during business hours looking for prospect replies. When a genuine response is detected (not automation noise), sends an immediate alert email to Craig so he can follow up while the prospect is warm.

**Original cron ID:** `ce4786ef`

**Signal detection**
- `hs_email_last_reply_date` updated in the last 75 minutes → email reply signal
- `notes_last_updated` in the last 75 minutes → inspects the note body for system-generated prefixes to filter automation noise

**False-positive prevention**
- Contacts with `br_last_sequence_outcome` of `opted_out`, `bounced`, `blocked_manual`, or `removed_manual` are excluded (their records may be updated by automation workflows)
- Notes starting with `[EXPANDI]`, `[AUTO]`, `[SEQ]`, etc. are filtered out
- Seen-contact state (`hot_lead_seen_contacts.json`) prevents duplicate alerts

**Cron expression**
```
0 0 13-23 * * 1-5     # Azure Functions (13:00–23:00 UTC Mon–Fri = 8 AM–6 PM EST)
0 8-18 * * 1-5        # Linux cron (hourly, Mon–Fri business hours)
```

**State files read/written**
- `hot_lead_seen_contacts.json` — contacts already alerted (expires after 48h)
- `hot_lead_monitor_log.json` — run history (last 500 runs)

---

### 3. `weekly_report_cron.py` — Weekly Performance Report

**What it does**

Every Monday morning, pulls a week's worth of outbound metrics from HubSpot, cross-references the daily cron run log, formats a Slack-friendly markdown digest, and posts it to the team Slack channel. Also updates the Notion dashboard.

**Report covers**
- Email: contacts enrolled, emails sent (from run log), replies received, reply rate
- LinkedIn: Campaign A vs B push counts, LinkedIn URL coverage, no-URL gap
- Hot leads: list of contacts who replied this week with names and companies
- Pipeline health: total BR contacts, pending outreach queue, opt-outs, bounces
- Cron health: number of successful/failed daily runs this week
- ICP vertical breakdown

**Cron expression**
```
0 0 13 * * 1          # Azure Functions (13:00 UTC Monday = 8:00 AM EST / 9:00 AM EDT)
0 9 * * 1             # Linux cron (9:00 AM Monday, server-local time)
```

**Slack delivery**

Supports two methods:
1. `SLACK_WEBHOOK_URL` — incoming webhook (simplest, preferred)
2. `SLACK_BOT_TOKEN` + `SLACK_CHANNEL` — Slack bot (more flexible)

Set whichever one you have. If both are set, the webhook takes priority.

**State files read/written**
- `daily_cron_run_log.json` — read for email/LinkedIn sent counts
- `weekly_report_log.json` — written with report summary (last 52 weeks)

---

### 4. `hubspot_sequence_enroll.py` — Sequence Enrollment Utility

**What it does**

A helper utility for enrolling contacts into HubSpot sequences programmatically. Used ad-hoc by the sales team or called from the daily cron. Handles the connected inbox bug workaround and includes full CLI support.

**The connected inbox bug**

HubSpot Sequences require a connected Gmail/Outlook inbox to send emails. In production, sequences enrolled via the UI caused emails to occasionally send from an unexpected sender identity. The workaround:

1. Sequence enrollment is made via `/automation/v4/sequences/enrollments` so the contact appears "in sequence" in HubSpot's CRM pipeline view
2. Actual email sending bypasses the sequence step — emails are sent via `/crm/v3/objects/emails` (HubSpot Engagements API), which respects the authenticated sender identity from the domain setup

**CLI usage**

```bash
# Enroll a single contact into cold_dtc_savings sequence
python hubspot_sequence_enroll.py --contact-ids 12345 --sequence cold_dtc_savings

# Enroll multiple contacts
python hubspot_sequence_enroll.py --contact-ids 12345 67890 --sequence expansion_signal

# Enroll from a file (one ID per line)
python hubspot_sequence_enroll.py --contact-file prospects.txt --sequence cold_dtc_savings

# Dry run — validate without enrolling
python hubspot_sequence_enroll.py --contact-ids 12345 --sequence cold_dtc_savings --dry-run

# Enroll without direct send (sequence step sends the email)
python hubspot_sequence_enroll.py --contact-ids 12345 --sequence cold_dtc_savings --no-direct-send

# Save full results to file
python hubspot_sequence_enroll.py --contact-file batch.txt --sequence cold_dtc_savings --output results.json
```

**Import API**

```python
from hubspot_sequence_enroll import enroll_single, batch_enroll

# Enroll one contact
result = enroll_single("12345", "cold_dtc_savings")

# Enroll a batch
results = batch_enroll(
    contact_ids=["12345", "67890"],
    sequence_name="expansion_signal",
    direct_send=True,  # Use workaround
    dry_run=False,
)
```

---

## Required environment variables

Copy `.env.example` (in the repo root) to `.env` and fill in the values. All scripts read these from the environment.

| Variable | Used by | Description |
|---|---|---|
| `HUBSPOT_PAT` | All scripts | HubSpot Private App token (account 6282372) |
| `EXPANDI_CAMPAIGN_A_WEBHOOK` | `daily_cron_v10.py` | Expandi reversed webhook for Campaign 770808 (cold_dtc_savings) |
| `EXPANDI_CAMPAIGN_B_WEBHOOK` | `daily_cron_v10.py` | Expandi reversed webhook for Campaign 770814 (expansion_signal) |
| `EXPANDI_API_KEY` | `daily_cron_v10.py` | Expandi API key (included in webhook URL params) |
| `EXPANDI_API_SECRET` | `daily_cron_v10.py` | Expandi API secret (included in webhook URL params) |
| `SLACK_WEBHOOK_URL` | `weekly_report_cron.py` | Slack incoming webhook URL |
| `SLACK_BOT_TOKEN` | `weekly_report_cron.py` | Slack bot token (alternative to webhook) |
| `SLACK_CHANNEL` | `weekly_report_cron.py` | Slack channel name (e.g. `#outbound-machine`) |
| `NOTION_TOKEN` | `daily_cron_v10.py`, `weekly_report_cron.py` | Notion integration token |
| `NOTION_CLIENTS_DATABASE_ID` | `daily_cron_v10.py` | Notion database ID for active clients |
| `NOTION_DASHBOARD_PAGE_ID` | `daily_cron_v10.py`, `weekly_report_cron.py` | Notion page ID for dashboard updates |
| `GMAIL_SENDER` | All scripts | Outbound sender address (`craig@brdrch.com`) |
| `HUBSPOT_SENDER_USER_ID` | `hubspot_sequence_enroll.py` | Craig's HubSpot user ID for sequence enrollment |
| `SMTP_HOST` | `daily_cron_v10.py`, `hot_lead_monitor.py` | SMTP server (default: `smtp.gmail.com`) |
| `SMTP_PORT` | `daily_cron_v10.py`, `hot_lead_monitor.py` | SMTP port (default: `587`) |
| `SMTP_USER` | `daily_cron_v10.py`, `hot_lead_monitor.py` | SMTP username |
| `SMTP_PASSWORD` | `daily_cron_v10.py`, `hot_lead_monitor.py` | SMTP password / app password |
| `ALERT_TO_EMAIL` | `daily_cron_v10.py`, `hot_lead_monitor.py` | Email address for alerts (default: `craig@brdrch.com`) |
| `PHYSICAL_ADDRESS` | `daily_cron_v10.py`, `hubspot_sequence_enroll.py` | CAN-SPAM footer address (fallback if file missing) |
| `WORKSPACE_DIR` | All scripts | Base path for state files (default: `/home/user/workspace`) |

---

## How to run locally

### Prerequisites

```bash
pip install requests python-dotenv
```

Or install from the repo requirements file:

```bash
pip install -r ../requirements.txt
```

### Setup

```bash
# 1. Copy and fill in credentials
cp ../.env.example .env
nano .env   # Fill in HUBSPOT_PAT and other values

# 2. Make sure state files exist (or let scripts create them on first run)
touch ~/workspace/active_clients_exclusion_list.txt
echo "Broad Reach Digital, [Your Address]" > ~/workspace/physical_address.txt
```

### Run each script

```bash
# Daily cycle (runs live — sends emails and pushes to Expandi)
python daily_cron_v10.py

# Hot lead monitor (checks last 75 minutes of HubSpot activity)
python hot_lead_monitor.py

# Weekly report (prints report and posts to Slack if configured)
python weekly_report_cron.py

# Sequence enrollment (dry run first to validate)
python hubspot_sequence_enroll.py --contact-ids 12345 --sequence cold_dtc_savings --dry-run
```

---

## How to deploy to Azure Functions

The Azure Functions stubs live in `../azure-functions/`. Each Function has a `function.json` (timer trigger schedule) and an `__init__.py` (stub with TODO comments).

### Step 1: Fill in the Azure Function stubs

For each function, import the script's main function and call it:

**`../azure-functions/DailyOutboundCycle/__init__.py`**
```python
import sys
sys.path.insert(0, '/path/to/crons')
from daily_cron_v10 import run_daily_cycle
import azure.functions as func
import logging

def main(timer: func.TimerRequest) -> None:
    if timer.past_due:
        logging.warning("Timer is past due — running anyway")
    run_daily_cycle()
```

**`../azure-functions/HotLeadMonitor/__init__.py`**
```python
from hot_lead_monitor import check_for_hot_leads
import azure.functions as func

def main(timer: func.TimerRequest) -> None:
    check_for_hot_leads()
```

**`../azure-functions/WeeklyPerformanceReport/__init__.py`**
```python
from weekly_report_cron import generate_weekly_report
import azure.functions as func

def main(timer: func.TimerRequest) -> None:
    generate_weekly_report()
```

### Step 2: Set environment variables in Azure

In the Azure Portal → Function App → Configuration → Application Settings, add each variable from the `.env.example` file.

**Important:** Set `WEBSITE_TIME_ZONE` to `Eastern Standard Time` if you want the logs to display in EST. The cron schedules are already expressed in UTC (no timezone conversion needed for the timer trigger itself).

### Step 3: Handle state files

The scripts use local disk for state (e.g., `warmup_tracker.json`, `active_clients_exclusion_list.txt`). Azure Functions have ephemeral local storage that resets on restarts.

**Options:**
- **Azure Blob Storage** (recommended): Replace `Path(...).read_text()` / `.write_text()` calls with `azure-storage-blob` reads/writes. The `azure-storage-blob` dependency is already commented in `../azure-functions/requirements.txt`.
- **Azure File Share**: Mount a persistent file share and set `WORKSPACE_DIR` to the mount path.
- **Environment variables**: For small configs (physical address, warmup schedule), store the values directly as App Settings.

### Step 4: Verify cron schedules

The `function.json` files use Azure's NCRONTAB format (6 fields: second minute hour day month weekday):

| Function | Schedule | UTC expression |
|---|---|---|
| DailyOutboundCycle | 7:00 AM EST | `0 0 12 * * *` |
| HotLeadMonitor | Hourly Mon–Fri 8 AM–6 PM EST | `0 0 13-23 * * 1-5` |
| WeeklyPerformanceReport | Monday 8:00 AM EST | `0 0 13 * * 1` |

---

## HubSpot custom properties referenced

These custom contact properties are read and written by the scripts. They must exist in your HubSpot account. Create them under Settings → Properties → Contact properties.

| Property | Type | Description |
|---|---|---|
| `br_source` | Single-line text | Set to `apollo` for contacts sourced via Apollo |
| `br_sequence_assigned` | Single-line text | Sequence name: `cold_dtc_savings` or `expansion_signal` |
| `br_icp_score` | Number | ICP score 0–100 (set by Apollo enrichment job) |
| `br_shipping_pain_score` | Number | Shipping cost pain signal score |
| `br_icp_vertical` | Single-line text | Industry vertical (e.g., `Beauty`, `Apparel`) |
| `br_expandi_status` | Single-line text | `pushed_campaign_a`, `pushed_campaign_b`, or `not_pushed` |
| `br_last_sequence_outcome` | Single-line text | `opted_out`, `bounced`, `blocked_manual`, `removed_manual` |
| `br_total_sequences_enrolled` | Number | Total number of sequences enrolled (anti-spam counter) |
| `br_last_outreach_date` | Date | Date of most recent outreach email send |
| `br_contact_cooldown_until` | Date | Manual cooldown end date |
| `br_deal_tier` | Single-line text | `enterprise`, `mid-market`, or `smb` |

---

## Expandi campaign reference

| Campaign | ID | Sequence | Webhook env var |
|---|---|---|---|
| Campaign A | 770808 | `cold_dtc_savings` | `EXPANDI_CAMPAIGN_A_WEBHOOK` |
| Campaign B | 770814 | `expansion_signal` | `EXPANDI_CAMPAIGN_B_WEBHOOK` |

The Expandi API domain is `api.liaufa.com` (not `api.expandi.io`) — this is specific to the reversed webhook feature.

---

## File structure

```
outbound-machine/
├── .env.example                    ← Copy to .env with real credentials
├── requirements.txt                ← pip install -r requirements.txt
├── crons/
│   ├── README.md                   ← This file
│   ├── daily_cron_v10.py           ← Daily prospecting cycle
│   ├── hot_lead_monitor.py         ← Hourly hot lead checker
│   ├── weekly_report_cron.py       ← Monday performance report
│   └── hubspot_sequence_enroll.py  ← Sequence enrollment utility
└── azure-functions/
    ├── DailyOutboundCycle/
    ├── HotLeadMonitor/
    ├── WeeklyPerformanceReport/
    ├── host.json
    └── requirements.txt
```

---

## Questions / contacts

- **Craig Radford** — system designer, `craig@brdrch.com`
- **HubSpot Account ID:** 6282372
- **Sender domain:** `brdrch.com` (SPF/DKIM/DMARC configured)
