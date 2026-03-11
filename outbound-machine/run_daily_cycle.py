#!/usr/bin/env python3
"""
Run Daily Outbound Cycle — Convenience wrapper for Replit.

This is the entrypoint referenced by .replit config. It imports and runs
the daily cron from the crons/ directory.

Usage (Replit):
    Click "Run" button — .replit config invokes this file.

Usage (CLI):
    python run_daily_cycle.py

Usage (test mode — no actual sends):
    DRY_RUN=1 python run_daily_cycle.py

Required env vars: See .env.example
"""
import os
import sys

# Add crons directory to Python path so we can import daily_cron_v10
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "crons"))

from daily_cron_v10 import run_daily_cycle, HUBSPOT_PAT

if __name__ == "__main__":
    if not HUBSPOT_PAT:
        print("ERROR: HUBSPOT_PAT environment variable is not set.")
        print("Set it in Replit Secrets (padlock icon in sidebar) or in .env file.")
        print("Get your PAT from: https://app.hubspot.com/private-apps/6282372")
        sys.exit(1)

    if os.environ.get("DRY_RUN"):
        print("DRY RUN MODE — no emails will be sent, no contacts will be updated.")
        print("(Remove DRY_RUN env var to run for real)")
        # TODO: Add dry-run flag to run_daily_cycle()
        sys.exit(0)

    result = run_daily_cycle()
    print("\n── Run Summary ──")
    import json
    print(json.dumps(result, indent=2))
