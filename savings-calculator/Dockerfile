# Broad Reach Savings Calculator — Docker Image
# Lightweight static site with Python CGI backend for quote generation.
#
# Build:  docker build -t br-savings-calculator .
# Run:    docker run -p 8000:8000 --env-file .env br-savings-calculator
#
# For production (Azure App Service):
#   - Set HUBSPOT_PAT in App Settings
#   - Deploy via GitHub Actions (see .github/workflows/deploy-static.yml)

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Copy application files
COPY index.html app.js base.css style.css page.css ./
COPY cgi-bin/ ./cgi-bin/

# No pip dependencies — quote.py uses only stdlib (json, os, urllib)
# If you add a requirements.txt later, uncomment:
# COPY requirements.txt .
# RUN pip install --no-cache-dir -r requirements.txt

# The savings calculator is a static frontend + CGI backend.
# For Azure migration, replace CGI with FastAPI:
#   1. Convert cgi-bin/quote.py to a FastAPI app
#   2. Add fastapi + uvicorn to requirements.txt
#   3. Change CMD to: uvicorn main:app --host 0.0.0.0 --port 8000
#
# For now, serve static files with Python's built-in HTTP server:
EXPOSE 8000
# --cgi flag enables CGI script execution from cgi-bin/ directory
CMD ["python", "-m", "http.server", "8000", "--cgi"]
