#!/usr/bin/env python3
"""
ShipWizmo Migration Kit — App Launcher
Pick an app and it starts automatically.
"""
import subprocess, sys, os

APPS = {
    "1": {
        "name": "Savings Calculator",
        "desc": "Static HTML + Python CGI — shipping cost estimator",
        "dir":  "savings-calculator",
        "cmd":  ["python", "-m", "http.server", "8000", "--cgi"],
        "deps": False,
    },
    "2": {
        "name": "SAPT Tool (Customer Portal)",
        "desc": "FastAPI + SQLite — rate card analysis, 144 rate cards, Google OAuth",
        "dir":  "sapt-tool",
        "cmd":  ["uvicorn", "api_server:app", "--host", "0.0.0.0", "--port", "8000"],
        "deps": True,
    },
    "3": {
        "name": "Command Center",
        "desc": "Bloomberg-style dashboard — HubSpot/Apollo/Expandi feeds",
        "dir":  "command-center",
        "cmd":  ["uvicorn", "api_server:app", "--host", "0.0.0.0", "--port", "8000"],
        "deps": True,
    },
    "4": {
        "name": "Customs Data Portal",
        "desc": "FastAPI + SQLite — customs declarations, Google OAuth",
        "dir":  "customs-data-portal",
        "cmd":  ["uvicorn", "api_server:app", "--host", "0.0.0.0", "--port", "8000"],
        "deps": True,
    },
    "5": {
        "name": "Outbound Machine",
        "desc": "Python cron scripts — 9-step daily outbound cycle",
        "dir":  "outbound-machine",
        "cmd":  ["python", "run_daily_cycle.py"],
        "deps": True,
    },
}

BLUE = "\033[94m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"

def main():
    print(f"""
{BLUE}{'═' * 60}{RESET}
{BOLD}  🚀  ShipWizmo Migration Kit — App Launcher{RESET}
{DIM}  5 apps · Built by Craig via Perplexity Computer{RESET}
{BLUE}{'═' * 60}{RESET}
""")
    for key, app in APPS.items():
        print(f"  {GREEN}{key}{RESET}  {BOLD}{app['name']}{RESET}")
        print(f"     {DIM}{app['desc']}{RESET}")
        print()

    print(f"  {YELLOW}0{RESET}  Exit")
    print()

    choice = input(f"  {CYAN}Pick an app (1-5): {RESET}").strip()

    if choice == "0" or not choice:
        print(f"\n  {DIM}Goodbye!{RESET}\n")
        return

    if choice not in APPS:
        print(f"\n  {YELLOW}Invalid choice. Run again and pick 1-5.{RESET}\n")
        return

    app = APPS[choice]
    app_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), app["dir"])

    print(f"\n  {GREEN}▶ Starting {app['name']}...{RESET}")
    print(f"  {DIM}Directory: {app['dir']}/{RESET}")

    if app["deps"]:
        req_file = os.path.join(app_dir, "requirements.txt")
        if os.path.exists(req_file):
            print(f"  {DIM}Installing dependencies...{RESET}")
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "-q", "-r", req_file],
                cwd=app_dir,
            )

    print(f"  {DIM}Running: {' '.join(app['cmd'])}{RESET}")
    print(f"  {BLUE}{'─' * 60}{RESET}\n")

    try:
        subprocess.run(app["cmd"], cwd=app_dir)
    except KeyboardInterrupt:
        print(f"\n\n  {YELLOW}Stopped {app['name']}.{RESET}\n")


if __name__ == "__main__":
    main()
