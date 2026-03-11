# SOURCE-INVENTORY.md — Complete File Manifest

Broadreach Migration Kit — every file in this repository, with line counts and descriptions.

**Last regenerated:** March 7, 2026

## Summary

| Component | Files | Source Lines | Data Lines | Notes |
|---|---|---|---|---|
| Savings Calculator | 13 | 2,290 | — | |
| SAPT Tool (Shipping Analysis & Pricing Tool) | 44 | 35,192 | 544,211 | Includes rate card data |
| Command Center | 20 | 5,806 | — | |
| Customs Data Portal | 18 | 9,335 | — | |
| Outbound Machine | 21 | 5,184 | — | |
| Azure Functions (Migration Templates) | 13 | 224 | — | |
| Test Suite | 8 | 4,321 | — | |
| Root-level docs & scripts | 7 | 1,716 | — | README, setup scripts, audit docs |
| **TOTAL** | **144** | **608,279** | | |

## Savings Calculator

**13 files — 2,290 total lines**

| File | Path | Lines | Type |
|---|---|---|---|
| `.env.example` | `savings-calculator/.env.example` | 11 | Env config |
| `.gitignore` | `savings-calculator/.gitignore` | 3 | Git config |
| `.replit` | `savings-calculator/.replit` | 16 | Replit config |
| `ARCHITECTURE.md` | `savings-calculator/ARCHITECTURE.md` | 183 | Markdown |
| `Dockerfile` | `savings-calculator/Dockerfile` | 37 | Docker |
| `app.js` | `savings-calculator/app.js` | 352 | JavaScript |
| `base.css` | `savings-calculator/base.css` | 58 | CSS |
| `docker-compose.yml` | `savings-calculator/docker-compose.yml` | 14 | YAML |
| `index.html` | `savings-calculator/index.html` | 323 | HTML |
| `page.css` | `savings-calculator/page.css` | 952 | CSS |
| `style.css` | `savings-calculator/style.css` | 94 | CSS |
| `deploy-static.yml` | `savings-calculator/.github/workflows/deploy-static.yml` | 25 | YAML |
| `quote.py` | `savings-calculator/cgi-bin/quote.py` | 222 | Python |

## SAPT Tool (Shipping Analysis & Pricing Tool)

**44 files — 579,403 total lines**

| File | Path | Lines | Type |
|---|---|---|---|
| `.env.example` | `sapt-tool/.env.example` | 25 | Env config |
| `.gitignore` | `sapt-tool/.gitignore` | 8 | Git config |
| `.replit` | `sapt-tool/.replit` | 19 | Replit config |
| `ARCHITECTURE.md` | `sapt-tool/ARCHITECTURE.md` | 242 | Markdown |
| `Dockerfile` | `sapt-tool/Dockerfile` | 17 | Docker |
| `MIGRATION_SPEC.md` | `sapt-tool/MIGRATION_SPEC.md` | 97 | Markdown |
| `api_server.py` | `sapt-tool/api_server.py` | 4,723 | Python |
| `app.js` | `sapt-tool/app.js` | 7,881 | JavaScript |
| `base.css` | `sapt-tool/base.css` | 58 | CSS |
| `docker-compose.yml` | `sapt-tool/docker-compose.yml` | 14 | YAML |
| `excel_generator.py` | `sapt-tool/excel_generator.py` | 906 | Python |
| `google-callback.html` | `sapt-tool/google-callback.html` | 81 | HTML |
| `index.html` | `sapt-tool/index.html` | 49 | HTML |
| `mock_client_data.js` | `sapt-tool/mock_client_data.js` | 49 | JavaScript |
| `oauth-popup.html` | `sapt-tool/oauth-popup.html` | 167 | HTML |
| `rate_cards_seed.json` | `sapt-tool/rate_cards_seed.json` | 12,703 | JSON |
| `replit.nix` | `sapt-tool/replit.nix` | 7 | Nix |
| `requirements.txt` | `sapt-tool/requirements.txt` | 12 | Text |
| `results-demo.html` | `sapt-tool/results-demo.html` | 102 | HTML |
| `style.css` | `sapt-tool/style.css` | 5,734 | CSS |
| `ci.yml` | `sapt-tool/.github/workflows/ci.yml` | 47 | YAML |
| `deploy-azure.yml` | `sapt-tool/.github/workflows/deploy-azure.yml` | 42 | YAML |
| `api.py` | `sapt-tool/cgi-bin/api.py` | 2,209 | Python |
| `amazon_rates.json` | `sapt-tool/data/amazon_rates.json` | 104,792 | JSON |
| `ca_zones.json` | `sapt-tool/data/ca_zones.json` | 1 | JSON |
| `cross_border_rates.json` | `sapt-tool/data/cross_border_rates.json` | 5,815 | JSON |
| `fedex_2day_internal.json` | `sapt-tool/data/fedex_2day_internal.json` | 2,794 | JSON |
| `fedex_accessorials.json` | `sapt-tool/data/fedex_accessorials.json` | 716 | JSON |
| `fedex_net_rates.json` | `sapt-tool/data/fedex_net_rates.json` | 65,422 | JSON |
| `fedex_sendle_summary.txt` | `sapt-tool/data/fedex_sendle_summary.txt` | 166 | Text |
| `other_carriers_summary.txt` | `sapt-tool/data/other_carriers_summary.txt` | 73 | Text |
| `peak_surcharges.json` | `sapt-tool/data/peak_surcharges.json` | 109 | JSON |
| `sendle_rates.json` | `sapt-tool/data/sendle_rates.json` | 202 | JSON |
| `spring_gds_rates.json` | `sapt-tool/data/spring_gds_rates.json` | 254,388 | JSON |
| `uniuni_rates.json` | `sapt-tool/data/uniuni_rates.json` | 600 | JSON |
| `ups_canada_accessorials.json` | `sapt-tool/data/ups_canada_accessorials.json` | 742 | JSON |
| `ups_canada_rates.json` | `sapt-tool/data/ups_canada_rates.json` | 32,772 | JSON |
| `ups_intl_zones.json` | `sapt-tool/data/ups_intl_zones.json` | 5,003 | JSON |
| `ups_summary.txt` | `sapt-tool/data/ups_summary.txt` | 128 | Text |
| `ups_transit_times.json` | `sapt-tool/data/ups_transit_times.json` | 776 | JSON |
| `ups_us_bid_rates.json` | `sapt-tool/data/ups_us_bid_rates.json` | 39,764 | JSON |
| `ups_us_list_rates.json` | `sapt-tool/data/ups_us_list_rates.json` | 28,793 | JSON |
| `us_zones.json` | `sapt-tool/data/us_zones.json` | 1 | JSON |
| `wizmo_service_catalog.json` | `sapt-tool/data/wizmo_service_catalog.json` | 1,154 | JSON |

## Command Center

**20 files — 5,806 total lines**

| File | Path | Lines | Type |
|---|---|---|---|
| `.env.example` | `command-center/.env.example` | 25 | Env config |
| `.gitignore` | `command-center/.gitignore` | 6 | Git config |
| `.replit` | `command-center/.replit` | 20 | Replit config |
| `ARCHITECTURE.md` | `command-center/ARCHITECTURE.md` | 196 | Markdown |
| `Dockerfile` | `command-center/Dockerfile` | 41 | Docker |
| `api_server.py` | `command-center/api_server.py` | 215 | Python |
| `app.js` | `command-center/app.js` | 1,192 | JavaScript |
| `dashboard_cache.json` | `command-center/dashboard_cache.json` | 1 | JSON |
| `docker-compose.yml` | `command-center/docker-compose.yml` | 16 | YAML |
| `index.html` | `command-center/index.html` | 386 | HTML |
| `oauth-popup.html` | `command-center/oauth-popup.html` | 106 | HTML |
| `replit.nix` | `command-center/replit.nix` | 8 | Nix |
| `requirements.txt` | `command-center/requirements.txt` | 12 | Text |
| `style.css` | `command-center/style.css` | 1,880 | CSS |
| `update_cache_fast.py` | `command-center/update_cache_fast.py` | 376 | Python |
| `update_dashboard_cache.py` | `command-center/update_dashboard_cache.py` | 969 | Python |
| `ci.yml` | `command-center/.github/workflows/ci.yml` | 47 | YAML |
| `deploy-azure.yml` | `command-center/.github/workflows/deploy-azure.yml` | 51 | YAML |
| `deploy-static.yml` | `command-center/.github/workflows/deploy-static.yml` | 25 | YAML |
| `api.py` | `command-center/cgi-bin/api.py` | 234 | Python |

## Customs Data Portal

**18 files — 9,335 total lines**

| File | Path | Lines | Type |
|---|---|---|---|
| `.env.example` | `customs-data-portal/.env.example` | 25 | Env config |
| `.gitignore` | `customs-data-portal/.gitignore` | 8 | Git config |
| `.replit` | `customs-data-portal/.replit` | 19 | Replit config |
| `ARCHITECTURE.md` | `customs-data-portal/ARCHITECTURE.md` | 202 | Markdown |
| `Dockerfile` | `customs-data-portal/Dockerfile` | 17 | Docker |
| `README-SOURCE.md` | `customs-data-portal/README-SOURCE.md` | 103 | Markdown |
| `api_server.py` | `customs-data-portal/api_server.py` | 3,184 | Python |
| `app.css` | `customs-data-portal/app.css` | 1,994 | CSS |
| `app.js` | `customs-data-portal/app.js` | 3,203 | JavaScript |
| `base.css` | `customs-data-portal/base.css` | 98 | CSS |
| `docker-compose.yml` | `customs-data-portal/docker-compose.yml` | 14 | YAML |
| `index.html` | `customs-data-portal/index.html` | 34 | HTML |
| `oauth-callback.html` | `customs-data-portal/oauth-callback.html` | 112 | HTML |
| `replit.nix` | `customs-data-portal/replit.nix` | 7 | Nix |
| `requirements.txt` | `customs-data-portal/requirements.txt` | 18 | Text |
| `style.css` | `customs-data-portal/style.css` | 208 | CSS |
| `ci.yml` | `customs-data-portal/.github/workflows/ci.yml` | 47 | YAML |
| `deploy-azure.yml` | `customs-data-portal/.github/workflows/deploy-azure.yml` | 42 | YAML |

## Outbound Machine

**21 files — 5,184 total lines**

| File | Path | Lines | Type |
|---|---|---|---|
| `.env.example` | `outbound-machine/.env.example` | 54 | Env config |
| `.gitignore` | `outbound-machine/.gitignore` | 9 | Git config |
| `.replit` | `outbound-machine/.replit` | 12 | Replit config |
| `ARCHITECTURE.md` | `outbound-machine/ARCHITECTURE.md` | 629 | Markdown |
| `active_clients_exclusion_list.txt` | `outbound-machine/active_clients_exclusion_list.txt` | 22 | Text |
| `expandi_config.json` | `outbound-machine/expandi_config.json` | 32 | JSON |
| `physical_address.txt` | `outbound-machine/physical_address.txt` | 2 | Text |
| `replit.nix` | `outbound-machine/replit.nix` | 8 | Nix |
| `requirements.txt` | `outbound-machine/requirements.txt` | 7 | Text |
| `run_daily_cycle.py` | `outbound-machine/run_daily_cycle.py` | 43 | Python |
| `sequence_ids.json` | `outbound-machine/sequence_ids.json` | 33 | JSON |
| `warmup_tracker.json` | `outbound-machine/warmup_tracker.json` | 13 | JSON |
| `ci.yml` | `outbound-machine/.github/workflows/ci.yml` | 47 | YAML |
| `deploy-azure.yml` | `outbound-machine/.github/workflows/deploy-azure.yml` | 42 | YAML |
| `icp_analysis.md` | `outbound-machine/config/icp_analysis.md` | 593 | Markdown |
| `linkedin_outreach_rules.md` | `outbound-machine/config/linkedin_outreach_rules.md` | 347 | Markdown |
| `README.md` | `outbound-machine/crons/README.md` | 369 | Markdown |
| `daily_cron_v10.py` | `outbound-machine/crons/daily_cron_v10.py` | 979 | Python |
| `hot_lead_monitor.py` | `outbound-machine/crons/hot_lead_monitor.py` | 570 | Python |
| `hubspot_sequence_enroll.py` | `outbound-machine/crons/hubspot_sequence_enroll.py` | 738 | Python |
| `weekly_report_cron.py` | `outbound-machine/crons/weekly_report_cron.py` | 635 | Python |

## Azure Functions (Migration Templates)

**13 files — 224 total lines**

| File | Path | Lines | Type |
|---|---|---|---|
| `host.json` | `azure-functions/host.json` | 15 | JSON |
| `local.settings.json` | `azure-functions/local.settings.json` | 13 | JSON |
| `requirements.txt` | `azure-functions/requirements.txt` | 5 | Text |
| `__init__.py` | `azure-functions/CommandCenterCacheUpdate/__init__.py` | 27 | Python |
| `function.json` | `azure-functions/CommandCenterCacheUpdate/function.json` | 12 | JSON |
| `__init__.py` | `azure-functions/DailyOutboundCycle/__init__.py` | 26 | Python |
| `function.json` | `azure-functions/DailyOutboundCycle/function.json` | 12 | JSON |
| `__init__.py` | `azure-functions/HotLeadMonitor/__init__.py` | 26 | Python |
| `function.json` | `azure-functions/HotLeadMonitor/function.json` | 12 | JSON |
| `__init__.py` | `azure-functions/InvitationEmailSender/__init__.py` | 25 | Python |
| `function.json` | `azure-functions/InvitationEmailSender/function.json` | 12 | JSON |
| `__init__.py` | `azure-functions/WeeklyPerformanceReport/__init__.py` | 27 | Python |
| `function.json` | `azure-functions/WeeklyPerformanceReport/function.json` | 12 | JSON |

## Test Suite

**8 files — 4,321 total lines**

| File | Path | Lines | Type |
|---|---|---|---|
| `README.md` | `tests/README.md` | 191 | Markdown |
| `conftest.py` | `tests/conftest.py` | 405 | Python |
| `requirements.txt` | `tests/requirements.txt` | 9 | Text |
| `test_command_center.py` | `tests/test_command_center.py` | 813 | Python |
| `test_customs_portal.py` | `tests/test_customs_portal.py` | 930 | Python |
| `test_outbound_machine.py` | `tests/test_outbound_machine.py` | 611 | Python |
| `test_sapt_tool.py` | `tests/test_sapt_tool.py` | 667 | Python |
| `test_savings_calculator.py` | `tests/test_savings_calculator.py` | 695 | Python |

## Root-Level Files

**7 files**

| File | Lines | Type | Description |
|---|---|---|---|
| `README.md` | 228 | Markdown | Master README with setup instructions |
| `SECURITY-AUDIT.md` | 345 | Markdown | Security audit findings and recommendations |
| `SOURCE-INVENTORY.md` | 199 | Markdown | This file — complete manifest |
| `TESTING.md` | 525 | Markdown | Manual smoke tests + automated test suite docs |
| `git-setup.sh` | 125 | Shell | Initialize Git repos for each app |
| `setup-azure.sh` | 225 | Shell | Azure infrastructure provisioning script |
| `setup-replit.sh` | 69 | Shell | Replit environment setup script |

---

**Completeness: ALL 5 APPS AT 100%.** Every source file, config, test, data file, deployment template, and documentation file is included. Zero known gaps.