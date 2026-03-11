# Outbound Machine — Architecture Document

**App:** Outbound Machine — Broad Reach B2B Outbound Prospecting System  
**Type:** Scheduled Python scripts (cron jobs) + JSON config files  
**Status:** LIVE  
**Lines of code:** daily_cron_v10.py: 979, hot_lead_monitor.py: 570, weekly_report_cron.py: 635, hubspot_sequence_enroll.py: 738, config/icp_analysis.md: 593, config/linkedin_outreach_rules.md: 347, expandi_config.json: 32, sequence_ids.json: 33, warmup_tracker.json: 13, .env.example: 34, active_clients_exclusion_list.txt: 22, physical_address.txt: 2

---

## Architecture Overview

The Outbound Machine is the revenue-generation engine for Broad Reach's B2B sales motion. It runs a fully automated daily prospecting pipeline targeting DTC ecommerce brands and 3PL/fulfillment companies in the USA and Canada that are overpaying for parcel shipping.

### What It Does

Every morning at 7:00 AM EST, the main cron pulls a batch of contacts from HubSpot (sourced and enriched via Apollo.io), runs them through a multi-stage qualification funnel, and executes two-channel outreach: outbound email via HubSpot's Engagements API and LinkedIn connection requests via Expandi. The system is fully automated — Craig wakes up to a Notion dashboard update and a Monday Slack digest telling him exactly how the prior week performed.

### How It Fits Into Broad Reach's Sales Motion

```
Apollo.io (sourcing)
  └── Contacts pushed to HubSpot with br_source=apollo
        ↓
Outbound Machine (daily cron, 7 AM EST)
  └── Qualifies, filters, sends → Email + LinkedIn outreach
        ↓
Hot Lead Monitor (hourly, business hours)
  └── Detects replies → Immediate alert email to Craig
        ↓
Craig follows up manually → Deal created in HubSpot
        ↓
SAPT Tool (shipping analysis → Excel proposal → close)
```

The Outbound Machine sits at the very top of the funnel — it is the only system that generates net-new pipeline. Everything downstream (SAPT Tool analysis, deal management, the Command Center dashboard) only exists because this machine surfaces prospects.

### The Daily Cycle

1. **Sync exclusion list** from Notion (active clients must never receive outreach)
2. **Query HubSpot** for Apollo-sourced contacts not yet assigned to a sequence
3. **ICP scoring filter** — requires `br_icp_score >= 60` and a senior job title
4. **Anti-pollution checks** — enforces opt-out suppression, max 3 sequences/contact lifetime, max 3 contacts/company/90 days, 14-day same-company spacing
5. **USA/Canada HQ filter** — hard disqualifies non-USA/CA companies
6. **Warmup gate** — reads `warmup_tracker.json` for today's send limit (5/10/20/25 by week)
7. **Email send** — sends via HubSpot Engagements API (direct send, NOT sequences — see below)
8. **LinkedIn push** — posts contact to Expandi reversed webhook for Campaign A or B
9. **Notion dashboard update** — writes run stats to the outbound dashboard page

### Why Direct Send Instead of HubSpot Sequences

HubSpot Sequences require a connected Gmail/Outlook inbox (OAuth) to send emails. When Craig's inbox was connected, emails sporadically sent from an unexpected sender identity — appearing to come from HubSpot's shared sending infrastructure rather than `craig@brdrch.com`. This is a known HubSpot connected inbox bug with no reliable fix.

The workaround: sequence enrollment is still made via the HubSpot Sequences API (so contacts appear "in sequence" in the CRM pipeline view), but actual email delivery bypasses the sequence step. Emails are sent via `POST /crm/v3/objects/emails` (HubSpot Engagements API), which creates the email engagement on the contact record AND sends it using Craig's authenticated domain identity (`brdrch.com`, with SPF/DKIM/DMARC configured). This gives full control over the `From:` address and resolves the sender identity bug entirely.

---

## File-by-File Walkthrough

### `crons/daily_cron_v10.py` — 979 lines

The core engine. Runs the full daily outbound prospecting cycle. Every function and constant in this file maps to a specific step in the pipeline.

**Configuration (lines 51–86)**

All configuration is read from environment variables (see `.env.example`). Key constants defined at the top:
- `ICP_SCORE_MIN = 60` — minimum ICP score for outreach eligibility
- `EXCLUSION_LIST_MIN_ENTRIES = 100` — safety halt threshold
- `MAX_SEQUENCES_PER_CONTACT = 3` — lifetime contact cap
- `MAX_CONTACTS_PER_COMPANY_90D = 3` — company-level anti-spam
- `MIN_DAYS_BETWEEN_SAME_COMPANY = 14` — company-level cooldown
- `WARMUP_RAMP = {1: 5, 2: 10, 3: 20, 4: 25}` — send volume by week

State files are referenced as `Path` objects pointing to `WORKSPACE_DIR`. In the current Perplexity-hosted deployment, `WORKSPACE_DIR` is `/home/user/workspace`. On Azure, these paths are replaced by Azure Blob Storage reads/writes.

**HubSpot API helpers (lines 89–154)**

- `hs_headers()` — returns Bearer token headers from `HUBSPOT_PAT`
- `hs_get()`, `hs_post()`, `hs_patch()` — thin wrappers with `raise_for_status()` and 20-second timeouts
- `search_contacts()` — paginated contact search (up to 10 pages / 1,000 results); uses HubSpot Search API (`POST /crm/v3/objects/contacts/search`)
- `update_contact()` — PATCH wrapper for updating contact properties
- `send_hubspot_email()` — core email send function; creates an email engagement object (`POST /crm/v3/objects/emails`) with association to the contact record; contains the full explanation of the connected inbox bug and why direct send is used

**Exclusion list helpers (lines 196–285)**

- `load_exclusion_list()` — reads `active_clients_exclusion_list.txt` into a set of lowercase domain strings; returns empty set (with warning) if file is missing
- `sync_exclusion_list_from_notion()` — Step 1 of the daily cycle; queries the Notion clients database via API, extracts the `Domain` property from each page, and overwrites the local file; does not overwrite if Notion returns 0 entries (protects against a failed sync wiping the list)

**Warmup tracker (lines 290–326)**

- `get_daily_email_limit()` — reads `warmup_tracker.json`, parses `warmup_start_date`, computes days elapsed, maps to the appropriate week number, and returns the daily limit from `WARMUP_RAMP`; defaults to 25 if the file is missing (assumes warmup complete)

**CAN-SPAM compliance (lines 330–351)**

- `get_physical_address()` — reads `physical_address.txt` (falls back to `PHYSICAL_ADDRESS` env var)
- `build_email_footer()` — constructs the CAN-SPAM compliant HTML footer with physical address and optional unsubscribe link; injected into every outbound email body

**ICP scoring and qualification (lines 354–424)**

- `passes_icp_filter()` — checks `br_icp_score >= 60` (Step 2.5) and validates that the contact's job title contains at least one senior keyword (VP, Director, Head of, Chief, CEO, COO, CFO, CMO, CTO, Founder, Owner, President, Partner, GM, General Manager, Managing Director)
- `passes_hq_filter()` — checks contact country against `{US, USA, UNITED STATES, CA, CANADA}` (Step 3); passes through contacts with an empty country field to avoid blocking contacts where Apollo didn't populate this field

**Anti-pollution cooldown system (lines 427–499)**

- `passes_anti_pollution_check()` — Step 2.7; enforces four rules in sequence and returns `(passes: bool, reason: str)`:
  1. **Permanent exclusion:** `br_last_sequence_outcome` of `opted_out`, `bounced`, or `opted_out_unsubscribed` → excluded forever
  2. **Max sequences per contact:** `br_total_sequences_enrolled >= 3` → hard block
  3. **Max contacts per company / 90 days:** more than 3 touches at the same company in the rolling 90-day window → block
  4. **14-day company cooldown:** any touch at the same company within the last 14 days → block

**Expandi LinkedIn push (lines 502–572)**

- `push_to_expandi()` — Step 6; POSTs a contact payload (LinkedIn URL, name, email, company, title) to the Expandi reversed webhook URL for the appropriate campaign; routes based on `sequence` parameter:
  - `cold_dtc_savings` → Campaign A (770808) → `EXPANDI_CAMPAIGN_A_WEBHOOK`
  - `expansion_signal` → Campaign B (770814) → `EXPANDI_CAMPAIGN_B_WEBHOOK`
  - API domain is `api.liaufa.com` (not `api.expandi.io` — the reversed webhook feature uses a different domain)

**Notion dashboard update (lines 575–628)**

- `update_notion_dashboard()` — Step 7; PATCHes the Notion dashboard page with the run summary stats (emails sent, LinkedIn pushed, contacts processed, qualified, skipped, run status); requires both `NOTION_TOKEN` and `NOTION_DASHBOARD_PAGE_ID`

**Alert helper (lines 631–667)**

- `send_alert_email()` — sends a plain-text alert via SMTP (Gmail by default) when a safety guard trips; logs to stdout if `SMTP_PASSWORD` is not set

**Main cycle (lines 670–948)**

- `run_daily_cycle()` — orchestrates all steps in order; tracks a `stats` dict throughout; applies the email send cap from the warmup gate by slicing `qualified[:daily_email_limit]` before the email loop; pushes all qualified contacts (not just those emailed) to Expandi; writes a run log entry to `daily_cron_run_log.json` (kept for last 90 days); returns the stats dict for Notion dashboard update and logging

---

### `crons/hot_lead_monitor.py` — 570 lines

Hourly reply detection. Runs every hour during business hours (Monday–Friday, 8 AM–6 PM EST). Polls HubSpot for BR contacts that have shown a genuine reply signal in the last 75 minutes, filters out automation noise, and sends Craig an immediate alert email so he can follow up while the prospect is warm.

**Schedule:** `0 0 13-23 * * 1-5` (Azure NCRONTAB) / `0 8-18 * * 1-5` (Linux cron)  
**Original Perplexity cron ID:** `ce4786ef`

**Signal detection (two queries):**

- **Query 1:** Contacts with `hs_email_last_reply_date >= cutoff_ms` — genuine email reply via HubSpot tracked email. This is a clean signal; no further validation needed beyond the excluded outcomes check.
- **Query 2:** Contacts with `notes_last_updated >= cutoff_ms` — catches replies that came in via other channels (LinkedIn DM synced back, manual note from Craig, Expandi response notification). These require deeper inspection: the script fetches the actual note body via `GET /crm/v3/objects/notes` and checks it against `SYSTEM_NOTE_PREFIXES` to filter out automation-written notes (`[EXPANDI]`, `[AUTO]`, `[SEQ]`, `[SEQUENCE]`, `Enrolled in sequence`, etc.).

**False-positive prevention:**
- Contacts with `br_last_sequence_outcome` in `{blocked_manual, removed_manual, bounced, opted_out, opted_out_unsubscribed}` are skipped — their records may be updated by automation workflows
- System-generated notes are filtered by prefix matching (`is_system_generated_note()`)
- The 75-minute lookback (vs. exactly 60) provides overlap buffer for late-running executions

**State management:** `hot_lead_seen_contacts.json` stores contact IDs already alerted (expires entries older than 48 hours) to prevent duplicate alerts across consecutive hourly runs. `hot_lead_monitor_log.json` keeps the last 500 run summaries.

---

### `crons/weekly_report_cron.py` — 635 lines

Monday morning performance digest. Runs every Monday at 8:00 AM EST. Pulls a week's worth of outbound metrics from HubSpot, cross-references the daily cron run log for ground-truth send counts, formats a Slack-friendly markdown report, posts it to the team Slack channel, and updates the Notion dashboard.

**Schedule:** `0 0 13 * * 1` (Azure NCRONTAB) / `0 9 * * 1` (Linux cron, 9 AM to account for EDT)

**Reporting window:** The most recently completed Mon–Sun week (ending midnight Sunday). Computed by `get_week_window()` which walks back to last Monday using Python's `datetime.weekday()`.

**Data sources:**
- `pull_hubspot_metrics()` — runs 3 HubSpot searches: (1) full BR contact snapshot for cumulative stats, (2) contacts with `br_last_outreach_date` in the reporting window for enrolled-this-week count, (3) contacts with `hs_email_last_reply_date` in the window for reply count and hot leads list
- `pull_daily_run_log_stats()` — reads `daily_cron_run_log.json` for actual send/push counts by day; provides ground-truth numbers that complement the HubSpot contact-count proxies

**Report sections:** Email channel (sends, enrolled, replies, reply rate), LinkedIn channel (Campaign A vs. B push counts, LinkedIn URL coverage), hot leads list (up to 5 replied contacts with name, company, title, reply date), pipeline health (total BR contacts, pending queue, opt-outs, bounces), cron health (successful/failed daily runs this week), top ICP verticals.

**Slack delivery:** Supports two methods — incoming webhook (`SLACK_WEBHOOK_URL`, preferred) or bot token + channel (`SLACK_BOT_TOKEN` + `SLACK_CHANNEL`). If both are set, the webhook takes priority. Report is always printed to stdout regardless of Slack config.

**State written:** `weekly_report_log.json` (last 52 weeks of report summaries).

---

### `crons/hubspot_sequence_enroll.py` — 738 lines

Manual enrollment CLI tool. Not a scheduled cron — run on-demand by Craig or the sales team to enroll contacts that were found outside the daily cron (manually prospected, warm intros, event leads, etc.). Also importable as a Python module for use from `daily_cron_v10.py`.

**CLI usage examples:**
```bash
python hubspot_sequence_enroll.py --contact-ids 12345 --sequence cold_dtc_savings
python hubspot_sequence_enroll.py --contact-file batch.txt --sequence expansion_signal
python hubspot_sequence_enroll.py --contact-ids 12345 --sequence cold_dtc_savings --dry-run
python hubspot_sequence_enroll.py --contact-ids 12345 --sequence cold_dtc_savings --no-direct-send
python hubspot_sequence_enroll.py --contact-file batch.txt --sequence cold_dtc_savings --output results.json
```

**Key functions:**
- `hs_request()` — HTTP wrapper with full retry logic: honors `Retry-After` header on 429, exponential backoff on 5xx, immediate raise on 4xx; max 3 retries, ~8 requests/second rate limiting
- `enroll_contact_in_sequence()` — enrolls via `POST /automation/v4/sequences/enrollments` for CRM visibility; handles 409 Conflict (already enrolled) gracefully
- `direct_send_workaround()` — sends the first email via `POST /crm/v3/objects/emails` immediately after enrollment, bypassing the sequence step's sender bug
- `batch_enroll()` — processes a list of contact IDs; validates each contact, skips already-enrolled and excluded contacts, calls `enroll_contact_in_sequence()` + `direct_send_workaround()`, writes to `hubspot_enrollment_log.json` (last 200 entries)
- `enroll_single()` / `batch_enroll()` — importable API for use from other scripts

---

### `warmup_tracker.json` — 13 lines

Email warmup state file. Managed by Instantly.ai (the warmup tool) and updated by a background job. Read by `daily_cron_v10.py` at Step 4 to determine today's send limit.

```json
{
  "warmup_start_date": "2026-03-03",
  "warmup_tool": "instantly.ai",
  "current_week": 1,
  "daily_limits_by_week": { "1": 5, "2": 10, "3": 20, "4": 25 },
  "notes": "...",
  "last_updated": "2026-03-06T19:00:00Z"
}
```

The cron computes `week = min((days_since_start // 7) + 1, 4)` and uses `daily_limits_by_week[week]` as the cap. Week 4+ is the steady-state ceiling of 25 emails/day. Do not manually edit this file without consulting the deliverability team — overriding limits during the warmup ramp risks domain blacklisting.

---

### `sequence_ids.json` — 33 lines

Sequence definition and targeting config. Defines the two active sequences, their cadence structure, and the 60/40 3PL/DTC targeting split.

```json
{
  "sequences": {
    "cold_dtc_savings": {
      "email_steps": 4, "linkedin_steps": 2, "total_touchpoints": 6,
      "cadence_days": [0, 3, 7, 14, 3, 7]
    },
    "expansion_signal": {
      "email_steps": 3, "linkedin_steps": 2, "total_touchpoints": 5,
      "cadence_days": [0, 4, 10, 4, 7]
    }
  },
  "targeting_split": { "3pl_fulfillment": 0.60, "dtc_brands": 0.40 }
}
```

Note: `hubspot_sequence_id` is `null` for both sequences. This is intentional — because actual email sending is handled via direct send (not the sequence step), the HubSpot sequence IDs are used for CRM pipeline tracking only. The sequence names are the canonical identifiers throughout the system.

---

### `expandi_config.json` — 32 lines

Expandi LinkedIn automation config reference. Contains campaign IDs, API domain, rate limits, and webhook URL variable names. **Not a credentials file** — all sensitive values are in environment variables. The most important field is `api_domain: "api.liaufa.com"` — this is the correct domain for the reversed webhook feature, NOT `api.expandi.io`.

| Campaign | ID | Webhook env var | Description |
|---|---|---|---|
| Cold DTC Savings | 770808 | `EXPANDI_CAMPAIGN_A_WEBHOOK` | Cold outreach to DTC brands |
| 3PL Focused | 770814 | `EXPANDI_CAMPAIGN_B_WEBHOOK` | Outreach to 3PL/fulfillment companies |

Rate limits enforced by Expandi: 25 connection requests/day, 50 messages/day, 60-second minimum delay between actions. These are Expandi dashboard settings — do not modify in this file.

---

### `active_clients_exclusion_list.txt` — 22 lines (current)

One company domain per line. Contains every active Broad Reach client domain that must never receive outbound prospecting. Maintained via Notion sync (Step 1 of the daily cron) — Notion is the source of truth, not this file. Manual edits will be overwritten on the next sync.

The exclusion list currently has 22 entries. This is below the 100-entry safety threshold, which means the cron will trip the safety halt on every run until the exclusion list is populated with real client domains. This is expected behavior during initial setup — populate the Notion clients database and the list will grow on the next sync.

---

### `physical_address.txt` — 2 lines

CAN-SPAM physical address. Read by `get_physical_address()` and injected into every outbound email footer. Contents:

```
Broad Reach Digital (a division of Asendia USA)
701 Ashland Ave, Folcroft, PA 19032
```

---

### `config/icp_analysis.md` — 593 lines

ICP scoring brain. The authoritative definition of how contacts are scored, which verticals qualify, and what signals add or subtract points. This document is the human-readable source of truth; the scoring logic is implemented in `daily_cron_v10.py` (specifically `passes_icp_filter()`).

Key content:
- **Two target segments:** DTC ecommerce brands (40% of volume) and 3PL/fulfillment companies (60% of volume, +15 score bonus)
- **Vertical tiers:** Tier 1 (Beauty, Supplements, Subscription Boxes: 85–100 base), Tier 2 (Fashion, 3PL: 75–90), Tier 3 (Home & Garden, Pet: 60–75), Tier 4 (Food & Bev, Electronics: 50–65)
- **Score formula:** `final = min(100, max(0, base_vertical + positive_signals - negative_penalties + 3pl_bonus))`
- **Minimum for enrollment:** 60
- **Sequence routing:** `expansion_signal` for contacts showing 2+ growth signals (recent funding, Shopify Plus upgrade, logistics hiring); `cold_dtc_savings` for all others
- **Hard disqualifications:** Outside USA/Canada, competitor, active client, government/military, opted out, hard bounce, freight-only
- **Monthly and quarterly review checklists** for scoring calibration

---

### `config/linkedin_outreach_rules.md` — 347 lines

LinkedIn messaging rules and compliance guide. Source of truth for all Expandi campaign messaging.

Key rules:
- **10-word hard limit** on all connection request messages — no exceptions
- No pitch, no stats, no company name, no pricing in connection requests
- 20 approved connection request message templates (DTC founder, 3PL operator, VP/Director, expansion signal variants)
- **Follow-up rules:** max 3 sentences in the first follow-up; second follow-up is the last LinkedIn touchpoint; no call ask in the first follow-up
- **Email rules (cross-channel):** max 20 words in email body; required phrases `"$2 range"` and `"cheaper than postal rates"`; subject lines under 8 words, no question marks
- **CAN-SPAM and CASL compliance matrix** with specific enforcement mechanism for each requirement
- **French variants** for Quebec prospects (postal codes starting with G, H, J)

---

## Data Flow

Full daily cycle pipeline:

```
07:00 AM EST — daily_cron_v10.py starts
│
├── Step 0.5: Safety guard
│   └── Load active_clients_exclusion_list.txt
│       └── HALT + alert email if len < 100
│
├── Step 1: Notion sync
│   └── POST api.notion.com/databases/{id}/query
│       └── Overwrite active_clients_exclusion_list.txt
│
├── Step 2: HubSpot contact query
│   └── POST /crm/v3/objects/contacts/search
│       └── Filter: br_source=apollo AND br_sequence_assigned NOT SET
│           └── Returns up to 1,000 contacts (paginated)
│
├── Step 2.5 + 2.7 + 3: Qualification pipeline (per contact)
│   ├── passes_icp_filter()  → br_icp_score >= 60 + senior title
│   ├── passes_anti_pollution_check() → opt-out/bounce/max-seq/company limits
│   ├── passes_hq_filter() → USA/Canada only
│   └── exclusion_set check → skip if domain matches active client
│
├── Step 4: Warmup gate
│   └── Read warmup_tracker.json → get daily_email_limit (5/10/20/25)
│
├── Step 5: Email send (up to daily_email_limit contacts)
│   ├── Build subject + HTML body (cold_dtc_savings or expansion_signal copy)
│   ├── POST /crm/v3/objects/emails  (HubSpot Engagements API direct send)
│   └── PATCH /crm/v3/objects/contacts/{id} → mark br_sequence_assigned, increment counter
│
├── Step 6: LinkedIn push (all qualified contacts with LinkedIn URL)
│   ├── Route: cold_dtc_savings → Campaign A (770808) → EXPANDI_CAMPAIGN_A_WEBHOOK
│   ├── Route: expansion_signal → Campaign B (770814) → EXPANDI_CAMPAIGN_B_WEBHOOK
│   ├── POST api.liaufa.com reversed webhook with contact payload
│   └── PATCH HubSpot contact → br_expandi_status = pushed_campaign_a/b
│
└── Step 7: Notion dashboard update
    ├── PATCH api.notion.com/pages/{dashboard_id} → write run stats
    └── Append to daily_cron_run_log.json (last 90 entries)

08:00 AM – 06:00 PM EST (hourly, Mon–Fri) — hot_lead_monitor.py
│
├── Query 1: contacts with hs_email_last_reply_date >= last 75 min
├── Query 2: contacts with notes_last_updated >= last 75 min
│   └── Fetch note body → filter system-generated prefixes
├── Skip: already alerted (hot_lead_seen_contacts.json, 48h expiry)
├── Skip: opted_out / bounced / blocked contacts
└── Send alert email → craig@brdrch.com (SMTP, high priority flag)

Monday 08:00 AM EST — weekly_report_cron.py
│
├── HubSpot: full BR contact snapshot (totals, LinkedIn coverage, Expandi status)
├── HubSpot: enrolled-this-week contacts (br_last_outreach_date in window)
├── HubSpot: replied-this-week contacts (hs_email_last_reply_date in window)
├── Read daily_cron_run_log.json → ground-truth send/push counts
├── Format Slack markdown report
├── POST to SLACK_WEBHOOK_URL (or Slack bot API)
└── PATCH Notion dashboard → weekly summary properties
```

---

## Safety Systems

### 1. Exclusion List Integrity Check (Hard Halt)

Before any outreach logic runs, the cron checks that `active_clients_exclusion_list.txt` contains at least 100 entries. If it has fewer, the entire run is **aborted** and an alert email is sent to `craig@brdrch.com`. This prevents the catastrophic scenario of contacting active paying clients if the Notion sync fails and the file is corrupted or empty.

The 100-entry threshold is a heuristic minimum. Broad Reach currently has more than 100 clients; if the list ever legitimately shrank below 100, the threshold should be adjusted.

**The current exclusion list has 22 entries, which means the cron will trip this guard on every run until the Notion database is populated with real client domains.**

### 2. Anti-Pollution Cooldowns

Four rules enforced in `passes_anti_pollution_check()`:

| Rule | Threshold | Scope | Action |
|---|---|---|---|
| Opted-out or bounced | Any | Contact | Permanent suppression — never enroll again |
| Max sequences enrolled | 3 lifetime | Contact | Hard block — skip contact |
| Max contacts touched | 3 in 90-day window | Company | Block additional contacts at that company |
| Same-company cooldown | 14 days | Company | Block until cooldown clears |

Company-level rules use an in-memory `company_touch_log` dict built during each run. For full accuracy across runs, this should be pre-populated from HubSpot's `br_last_outreach_date` property (a noted gap in the current implementation — see Known Limitations).

### 3. Warmup Volume Gating

The daily send volume is capped by the warmup ramp schedule. The cron reads `warmup_tracker.json` on every run and applies the cap before the email loop. If the file is missing or unreadable, it defaults to 25/day (assumes warmup is complete). Do not modify this file directly — it is managed by Instantly.ai.

| Week | Daily limit |
|---|---|
| 1 | 5 |
| 2 | 10 |
| 3 | 20 |
| 4+ (steady-state) | 25 |

### 4. Alert Emails on Safety Guard Trips

`send_alert_email()` is called when the exclusion list integrity check fails. It sends via SMTP (Gmail by default). If `SMTP_PASSWORD` is not configured, the alert is printed to stdout only — useful for local testing, but insufficient for production monitoring. Set `SMTP_PASSWORD` in production.

### 5. Expandi Daily Rate Limits

LinkedIn account safety is enforced at the Expandi level (not in this code). The Expandi dashboard is configured for max 25 connection requests/day and max 50 messages/day — within LinkedIn's published safe-use thresholds for a warmed account. The reversed webhook pushes contacts into the Expandi queue; Expandi handles the pacing.

---

## External Service Dependencies

### HubSpot CRM — Account 6282372

The central data store for all contacts, companies, deals, and engagement activity.

| Usage | API endpoint | Called by |
|---|---|---|
| Contact search (Apollo contacts) | `POST /crm/v3/objects/contacts/search` | daily_cron_v10.py, hot_lead_monitor.py, weekly_report_cron.py |
| Send outbound email (direct send) | `POST /crm/v3/objects/emails` | daily_cron_v10.py, hubspot_sequence_enroll.py |
| Update contact properties | `PATCH /crm/v3/objects/contacts/{id}` | daily_cron_v10.py, hubspot_sequence_enroll.py |
| Sequence enrollment | `POST /automation/v4/sequences/enrollments` | hubspot_sequence_enroll.py |
| Fetch contact notes | `GET /crm/v3/objects/notes` | hot_lead_monitor.py |

**Required custom contact properties:** `br_source`, `br_sequence_assigned`, `br_icp_score`, `br_shipping_pain_score`, `br_icp_vertical`, `br_expandi_status`, `br_last_sequence_outcome`, `br_total_sequences_enrolled`, `br_last_outreach_date`, `br_contact_cooldown_until`, `br_deal_tier`. These must be created in HubSpot Settings → Properties → Contact properties before the scripts will function correctly.

**Auth:** Private App token (`HUBSPOT_PAT`). No OAuth flow — a single long-lived PAT with CRM read/write and email send scopes.

### Apollo.io — Contact sourcing and enrichment

Apollo is the upstream source for all contacts in the pipeline. Contacts are sourced in Apollo using saved search filters (industry, employee count, geography, revenue, job titles), exported to HubSpot with `br_source=apollo`, and ICP-scored during the import process. The Outbound Machine only reads Apollo-sourced contacts — it does not call the Apollo API directly. Apollo API key is in `.env.example` for completeness but is used by a separate enrichment job, not these cron scripts.

### Expandi — LinkedIn automation (api.liaufa.com)

Manages Craig's LinkedIn account for automated connection requests and follow-up messages. The Outbound Machine pushes contacts via reversed webhooks; Expandi handles the actual LinkedIn actions, rate limiting, and response detection.

| Setting | Value |
|---|---|
| API domain | `api.liaufa.com` (NOT `api.expandi.io`) |
| Campaign A | ID 770808 — Cold DTC Savings |
| Campaign B | ID 770814 — 3PL Focused |
| Max connections/day | 25 |
| Max messages/day | 50 |
| Min delay between actions | 60 seconds |

The reversed webhook pattern: `POST https://api.liaufa.com/api/v1/open-api/campaign-instance/{campaign_id}/assign/?key=...&secret=...` with a JSON payload containing the prospect's LinkedIn URL. Expandi adds the person to the campaign queue immediately.

### Notion — Active client exclusion list + dashboard

Two uses:
1. **Clients database** (`NOTION_CLIENTS_DATABASE_ID`): Source of truth for active client domains. Queried at Step 1 of every daily run to refresh `active_clients_exclusion_list.txt`.
2. **Outbound dashboard page** (`NOTION_DASHBOARD_PAGE_ID`): Updated at Step 7 of every daily run and by the weekly report with performance stats. Gives Craig a human-readable view without logging into HubSpot.

### Slack — Notifications and alerts

Used by `weekly_report_cron.py` for the Monday morning performance digest. Two delivery methods supported:
- `SLACK_WEBHOOK_URL` — incoming webhook (preferred, simpler)
- `SLACK_BOT_TOKEN` + `SLACK_CHANNEL` — bot API (`chat.postMessage`)

Hot lead alerts are currently sent via email (SMTP), not Slack. Slack could be added to `hot_lead_monitor.py` as a faster delivery channel using the same webhook pattern from `weekly_report_cron.py`.

### Instantly.ai — Email warmup

Manages the email warmup ramp for `craig@brdrch.com` / `brdrch.com`. Writes warmup status to `warmup_tracker.json` which the daily cron reads to enforce the send limit. The Outbound Machine does not call the Instantly.ai API — it only reads the JSON file written by Instantly.

---

## Environment Variables Reference

Full list from `.env.example`. All scripts read from environment variables (via `os.environ.get()`). For local development, copy `.env.example` to `.env` — `python-dotenv` will load it automatically.

| Variable | Used by | Required | Description |
|---|---|---|---|
| `HUBSPOT_PAT` | All scripts | Yes | HubSpot Private App token (account 6282372) |
| `EXPANDI_CAMPAIGN_A_WEBHOOK` | daily_cron_v10.py | Yes | Reversed webhook URL for Campaign 770808 |
| `EXPANDI_CAMPAIGN_B_WEBHOOK` | daily_cron_v10.py | Yes | Reversed webhook URL for Campaign 770814 |
| `EXPANDI_API_KEY` | daily_cron_v10.py | Yes | Expandi API key (embedded in webhook URL) |
| `EXPANDI_API_SECRET` | daily_cron_v10.py | Yes | Expandi API secret (embedded in webhook URL) |
| `NOTION_TOKEN` | daily_cron_v10.py, weekly_report_cron.py | Recommended | Notion integration token |
| `NOTION_CLIENTS_DATABASE_ID` | daily_cron_v10.py | Recommended | Notion DB ID for active clients list |
| `NOTION_DASHBOARD_PAGE_ID` | daily_cron_v10.py, weekly_report_cron.py | Recommended | Notion page ID for dashboard |
| `SLACK_WEBHOOK_URL` | weekly_report_cron.py | Recommended | Slack incoming webhook URL |
| `SLACK_BOT_TOKEN` | weekly_report_cron.py | Optional | Slack bot token (alt to webhook) |
| `SLACK_CHANNEL` | weekly_report_cron.py | Optional | Slack channel (e.g. `#outbound-machine`) |
| `GMAIL_SENDER` | All scripts | Yes | Outbound sender address (`craig@brdrch.com`) |
| `HUBSPOT_SENDER_USER_ID` | hubspot_sequence_enroll.py | Recommended | Craig's HubSpot user ID for sequence enrollment |
| `SMTP_HOST` | daily_cron_v10.py, hot_lead_monitor.py | Optional | SMTP server (default: `smtp.gmail.com`) |
| `SMTP_PORT` | daily_cron_v10.py, hot_lead_monitor.py | Optional | SMTP port (default: `587`) |
| `SMTP_USER` | daily_cron_v10.py, hot_lead_monitor.py | Optional | SMTP username |
| `SMTP_PASSWORD` | daily_cron_v10.py, hot_lead_monitor.py | Recommended | SMTP password — required for alert emails |
| `ALERT_TO_EMAIL` | daily_cron_v10.py, hot_lead_monitor.py | Optional | Alert recipient (default: `craig@brdrch.com`) |
| `PHYSICAL_ADDRESS` | daily_cron_v10.py, hubspot_sequence_enroll.py | Optional | CAN-SPAM address fallback if file missing |
| `WORKSPACE_DIR` | All scripts | Optional | Base path for state files (default: `/home/user/workspace`) |
| `ZAPIER_WEBHOOK_URL` | (referenced) | Optional | Zapier webhook for Expandi → Slack routing |

---

## HubSpot Custom Properties

These contact properties must exist in HubSpot account 6282372 before the scripts will work. Create them at Settings → Properties → Contact properties.

| Property | Type | Set by | Description |
|---|---|---|---|
| `br_source` | Text | Apollo import | Set to `apollo` for all pipeline contacts |
| `br_sequence_assigned` | Text | daily_cron_v10.py | Sequence name: `cold_dtc_savings` or `expansion_signal` |
| `br_icp_score` | Number | Apollo enrichment job | ICP score 0–100 |
| `br_shipping_pain_score` | Number | Apollo enrichment job | Shipping cost pain signal score |
| `br_icp_vertical` | Text | Apollo enrichment job | Industry vertical (Beauty, Apparel, 3PL, etc.) |
| `br_expandi_status` | Text | daily_cron_v10.py | `pushed_campaign_a`, `pushed_campaign_b`, or empty |
| `br_last_sequence_outcome` | Text | Manual / workflows | `opted_out`, `bounced`, `blocked_manual`, `removed_manual` |
| `br_total_sequences_enrolled` | Number | daily_cron_v10.py | Lifetime sequence enrollment count (anti-spam counter) |
| `br_last_outreach_date` | Date | daily_cron_v10.py | Date of most recent outreach email send |
| `br_contact_cooldown_until` | Date | Manual | Manual cooldown end date |
| `br_deal_tier` | Text | Manual / workflows | `enterprise`, `mid-market`, or `smb` |

---

## Known Limitations & Technical Debt

| Issue | Severity | Notes |
|---|---|---|
| Company-level anti-pollution is in-memory only | High | The `company_touch_log` dict in `run_daily_cycle()` is rebuilt each run from scratch. It only tracks companies touched in the current run, not the full 90-day history from HubSpot. To fully enforce the 90-day rule across runs, pre-populate from `br_last_outreach_date` filtered by company domain before the qualification loop. |
| Exclusion list currently below safety threshold | High | `active_clients_exclusion_list.txt` has 22 entries. The cron will trip the Step 0.5 safety halt on every run. Populate the Notion clients database with real client domains and the list will grow on the next sync. |
| State files reset on Azure Functions restart | High | `warmup_tracker.json`, `active_clients_exclusion_list.txt`, and run log files live on local disk. Azure Functions have ephemeral storage. Replace with Azure Blob Storage reads/writes before deploying to Azure. |
| HubSpot sequence IDs are null | Medium | `sequence_ids.json` has `hubspot_sequence_id: null` for both sequences. The enrollment call in `hubspot_sequence_enroll.py` will warn but continue with property updates only. Set real sequence IDs from HubSpot to enable full CRM pipeline visibility. |
| Email body copy is placeholder HTML | Medium | Step 5 in `daily_cron_v10.py` uses simplified placeholder email copy. Replace with production-ready copy from the outreach messaging templates per `config/linkedin_outreach_rules.md` (max 20 words body, required phrases, subject line rules). |
| French variant logic not yet implemented | Medium | `config/linkedin_outreach_rules.md` specifies French-language email variants for Quebec prospects (postal codes G/H/J). The detection and routing logic is documented but not implemented in `daily_cron_v10.py`. |
| Hot lead alerts via email only | Low | `hot_lead_monitor.py` sends alerts via SMTP. Slack would be faster (mobile push notification vs. email). Add a Slack webhook POST using the same pattern in `weekly_report_cron.py`. |
| No Expandi response sync back to HubSpot | Low | LinkedIn replies in Expandi are not automatically synced back to HubSpot. The hot lead monitor catches notes updated by the Expandi → HubSpot integration, but there is no guaranteed bidirectional sync. Review Expandi's HubSpot native integration or use Zapier (`ZAPIER_WEBHOOK_URL` is in `.env.example`). |
| Apollo enrichment job not in this kit | Info | The Apollo sourcing and ICP scoring job (which sets `br_source=apollo` and `br_icp_score`) is a separate system not included in this migration kit. The Outbound Machine assumes contacts have already been sourced, imported to HubSpot, and scored. |
| `daily_cron_run_log.json` not seeded | Info | The run log starts empty. On first run, `weekly_report_cron.py` will return 0 for all email/LinkedIn send counts from the log. This self-resolves after 7 days of daily cron runs. |

---

## Migration Checklist (Perplexity → Azure)

### Step 1: Code Repository

- [ ] Push all files to GitHub repo (`shipwizmo/outbound-machine`)
- [ ] Confirm `.env.example` is committed and `.env` is in `.gitignore`
- [ ] Verify `requirements.txt` is complete: `requests==2.31.0`, `python-dotenv==1.0.1`, `azure-functions==1.18.0`

### Step 2: Convert Crons to Azure Functions (Timer Triggers)

Convert each cron to an Azure Function using the stubs in `azure-functions/`:

```python
# azure-functions/DailyOutboundCycle/__init__.py
import sys; sys.path.insert(0, '/path/to/crons')
from daily_cron_v10 import run_daily_cycle
import azure.functions as func

def main(timer: func.TimerRequest) -> None:
    if timer.past_due:
        logging.warning("Timer is past due")
    run_daily_cycle()
```

| Function | Schedule (NCRONTAB) | UTC time |
|---|---|---|
| `DailyOutboundCycle` | `0 0 12 * * *` | 12:00 UTC = 7:00 AM EST |
| `HotLeadMonitor` | `0 0 13-23 * * 1-5` | 13:00–23:00 UTC Mon–Fri = 8 AM–6 PM EST |
| `WeeklyPerformanceReport` | `0 0 13 * * 1` | 13:00 UTC Monday = 8:00 AM EST |

- [ ] Create `DailyOutboundCycle` Function (Timer Trigger, `0 0 12 * * *`)
- [ ] Create `HotLeadMonitor` Function (Timer Trigger, `0 0 13-23 * * 1-5`)
- [ ] Create `WeeklyPerformanceReport` Function (Timer Trigger, `0 0 13 * * 1`)
- [ ] Set `WEBSITE_TIME_ZONE = Eastern Standard Time` in Function App configuration (for readable log timestamps)

### Step 3: Replace File-Based State with Azure Blob Storage

All state files currently written to local disk must move to Azure Blob Storage. The `azure-storage-blob` package is already commented out in `azure-functions/requirements.txt`.

- [ ] Add `azure-storage-blob==12.19.0` to `azure-functions/requirements.txt`
- [ ] Create Azure Storage Account + Blob container (e.g., `outbound-machine-state`)
- [ ] Replace `warmup_tracker.json` file reads with blob reads (`ContainerClient.download_blob()`)
- [ ] Replace `active_clients_exclusion_list.txt` file reads/writes with blob reads/writes
- [ ] Replace `daily_cron_run_log.json` file reads/writes with blob reads/writes
- [ ] Replace `hot_lead_seen_contacts.json` file reads/writes with blob reads/writes
- [ ] Replace `physical_address.txt` read with a hardcoded constant or `PHYSICAL_ADDRESS` env var
- [ ] Replace `hubspot_enrollment_log.json` file writes with blob writes

**Blob container structure:**
```
outbound-machine-state/
├── warmup_tracker.json
├── active_clients_exclusion_list.txt
├── daily_cron_run_log.json
├── hot_lead_seen_contacts.json
└── hubspot_enrollment_log.json
```

### Step 4: Secrets Management

- [ ] Create Azure Key Vault (`outbound-machine-keyvault`)
- [ ] Add all secrets from `.env.example` as Key Vault secrets
- [ ] Enable managed identity on the Function App
- [ ] Grant Key Vault `Secrets User` role to the managed identity
- [ ] Update Function App configuration to reference Key Vault secrets using `@Microsoft.KeyVault(...)` syntax

### Step 5: Monitoring and Alerting

- [ ] Enable Application Insights on the Function App
- [ ] Create alert rule: function execution failure → email to `craig@brdrch.com`
- [ ] Create alert rule: function duration > 5 minutes (potential hang) → email alert
- [ ] Create dashboard showing daily cron success/failure run history
- [ ] Verify the Step 0.5 safety halt alert email is operational (`SMTP_PASSWORD` configured)

### Step 6: HubSpot Configuration

- [ ] Verify all 11 custom contact properties exist in account 6282372 (see HubSpot Custom Properties table above)
- [ ] Set real HubSpot sequence IDs in `sequence_ids.json` (currently `null`)
- [ ] Confirm `HUBSPOT_SENDER_USER_ID` is Craig's actual HubSpot user ID
- [ ] Test `send_hubspot_email()` end-to-end with a test contact before enabling daily cron

### Step 7: Exclusion List Bootstrap

- [ ] Populate Notion clients database with all active Broad Reach client domains
- [ ] Run `sync_exclusion_list_from_notion()` manually to seed the file
- [ ] Verify `active_clients_exclusion_list.txt` has > 100 entries before enabling the daily cron

### Step 8: Email Copy

- [ ] Replace placeholder email copy in `daily_cron_v10.py` Step 5 with production-ready templates
- [ ] Implement French variant detection and routing for Quebec prospects

---

*System designer: Craig Radford — craig@brdrch.com*  
*HubSpot Account: 6282372 | Sender domain: brdrch.com (SPF/DKIM/DMARC configured)*  
*Original platform: Perplexity Computer scheduled tasks | Migration target: Azure Functions*
