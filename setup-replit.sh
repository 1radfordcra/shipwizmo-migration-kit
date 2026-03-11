#!/bin/bash
# ============================================================
# Broad Reach — Replit Import Setup
# Import all apps from GitHub into Replit in one shot.
# Prerequisites: 
#   - GitHub repos already created (run git-setup.sh first)
#   - Replit account connected to GitHub
# ============================================================

set -e

GITHUB_ORG="shipwizmo"  # Change to your GitHub org or username

echo "============================================"
echo " Broad Reach — Replit Import Guide"
echo "============================================"
echo ""
echo " This script generates the Replit import URLs for each app."
echo " Click each URL to create a new Repl from the GitHub repo."
echo ""
echo " Replit will automatically detect the .replit config file"
echo " and set up the correct run command, language, and ports."
echo ""
echo "============================================"
echo ""

# List of repos and their types
declare -A REPOS
REPOS=(
  ["savings-calculator"]="Static site — no backend"
  ["sapt-tool"]="Python web app (FastAPI + SQLite)"
  ["customs-data-portal"]="Python web app (FastAPI + SQLite)"
  ["outbound-machine"]="Python script (cron runner)"
  ["command-center"]="FastAPI dashboard + API proxy + cache updater"
)

for REPO in "${!REPOS[@]}"; do
  DESC="${REPOS[$REPO]}"
  echo "  $REPO"
  echo "    Type: $DESC"
  echo "    Import URL: https://replit.com/github.com/$GITHUB_ORG/$REPO"
  echo ""
done

echo "============================================"
echo ""
echo " After importing each repo into Replit:"
echo ""
echo "   1. Go to the Repl's Secrets tab (lock icon in sidebar)"
echo "   2. Add the environment variables from the app's .env.example"
echo "   3. Click Run — the .replit config handles the rest"
echo ""
echo " For web apps (sapt-tool, customs-data-portal):"
echo "   - Replit auto-provisions a public URL (*.repl.co)"
echo "   - Add that URL to Google Cloud Console → OAuth origins"
echo ""
echo " For the outbound-machine:"
echo "   - This is a script, not a web server"
echo "   - Use Replit's Shell to run individual steps"
echo "   - Or set up a Replit Scheduled Job for daily runs"
echo ""
echo " For static sites (savings-calculator):"
echo "   - Replit serves them instantly — just click Run"
echo "   - Deploy via Replit Deployments for a production URL"
echo ""
echo "============================================"
echo " Tip: Connect your GitHub repos to Replit for auto-sync."
echo " Every push to main in GitHub will update the Repl."
echo "============================================"
