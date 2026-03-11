#!/bin/bash
# ============================================================
# Broad Reach — GitHub Repository Setup
# Creates repos and pushes code for all apps.
#
# Prerequisites:
#   1. GitHub CLI installed and authenticated (gh auth login)
#   2. Git configured with your identity:
#        git config --global user.name "Your Name"
#        git config --global user.email "your@email.com"
# ============================================================

set -e

GITHUB_ORG="shipwizmo"  # Change to your GitHub org or username
REPO_VISIBILITY="--public"  # Use --public for Azure Deploy buttons to work
                              # Change to --private if you don't need one-click Azure deployment
                              # (Private repos require Azure DevOps or GitHub Actions for deployment instead)

# --- Preflight checks ---
if ! command -v gh &> /dev/null; then
    echo "ERROR: GitHub CLI (gh) is not installed."
    echo "Install: https://cli.github.com/"
    exit 1
fi

if ! gh auth status &> /dev/null 2>&1; then
    echo "ERROR: GitHub CLI is not authenticated."
    echo "Run: gh auth login"
    exit 1
fi

if [ -z "$(git config user.name)" ] || [ -z "$(git config user.email)" ]; then
    echo "ERROR: Git user identity not configured."
    echo "Run:"
    echo "  git config --global user.name \"Your Name\""
    echo "  git config --global user.email \"your@email.com\""
    exit 1
fi

echo "============================================"
echo " Broad Reach — GitHub Repository Setup"
echo "============================================"
echo ""
echo " GitHub org: $GITHUB_ORG"
echo " Git user:   $(git config user.name) <$(git config user.email)>"
echo ""

# --- 1. Savings Calculator ---
echo "→ Setting up savings-calculator repo"
cd savings-calculator/
git init
# .gitignore already exists in the kit — don't overwrite
git add -A
git commit -m "Initial commit — Broad Reach Savings Calculator"
gh repo create $GITHUB_ORG/savings-calculator $REPO_VISIBILITY --source=. --push
cd ..
echo "  ✓ savings-calculator pushed"

# --- 2. SAPT Tool (Shipping Analysis & Pricing Tool) ---
echo "→ Setting up sapt-tool repo"
cd sapt-tool/
git init
# .gitignore already exists in the kit — don't overwrite
git add -A
git commit -m "Initial commit — SAPT Tool (Shipping Analysis & Pricing Tool)"
gh repo create $GITHUB_ORG/sapt-tool $REPO_VISIBILITY --source=. --push
cd ..
echo "  ✓ sapt-tool pushed"

# --- 3. Customs Data Portal ---
echo "→ Setting up customs-data-portal repo"
cd customs-data-portal/
git init
# .gitignore already exists in the kit — don't overwrite
git add -A
git commit -m "Initial commit — Broad Reach Customs Data Portal"
gh repo create $GITHUB_ORG/customs-data-portal $REPO_VISIBILITY --source=. --push
cd ..
echo "  ✓ customs-data-portal pushed"

# --- 4. Outbound Machine ---
echo "→ Setting up outbound-machine repo"
cd outbound-machine/
git init
# .gitignore already exists in the kit — don't overwrite
git add -A
git commit -m "Initial commit — Broad Reach Outbound Machine (v10)"
gh repo create $GITHUB_ORG/outbound-machine $REPO_VISIBILITY --source=. --push
cd ..
echo "  ✓ outbound-machine pushed"

# --- 5. Command Center ---
echo "→ Setting up command-center repo"
cd command-center/
git init
# .gitignore already exists in the kit — don't overwrite
git add -A
git commit -m "Initial commit — Broad Reach Command Center Dashboard"
gh repo create $GITHUB_ORG/command-center $REPO_VISIBILITY --source=. --push
cd ..
echo "  ✓ command-center pushed"

# --- 6. Azure Functions ---
echo "→ Setting up azure-functions repo"
cd azure-functions/
git init
# .gitignore already exists in the kit — don't overwrite
git add -A
git commit -m "Initial commit — Broad Reach Azure Functions (5 Timer Triggers)"
gh repo create $GITHUB_ORG/azure-functions $REPO_VISIBILITY --source=. --push
cd ..
echo "  ✓ azure-functions pushed"

echo ""
echo "============================================"
echo " ✓ All repositories created and pushed!"
echo "============================================"
echo ""
echo " Repos created:"
echo "   https://github.com/$GITHUB_ORG/savings-calculator"
echo "   https://github.com/$GITHUB_ORG/sapt-tool"
echo "   https://github.com/$GITHUB_ORG/customs-data-portal"
echo "   https://github.com/$GITHUB_ORG/outbound-machine"
echo "   https://github.com/$GITHUB_ORG/command-center"
echo "   https://github.com/$GITHUB_ORG/azure-functions"
echo ""
