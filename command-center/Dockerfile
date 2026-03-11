# Broad Reach Command Center — Docker Image
# Two components: static dashboard (index.html/app.js) + FastAPI proxy (api_server.py)
#
# Build:  docker build -t br-command-center .
# Run:    docker run -p 8000:8000 --env-file .env br-command-center
#
# The dashboard itself is a static site (can deploy to Azure Static Web Apps).
# The api_server.py is a FastAPI proxy that forwards requests to HubSpot API
# (used for feed actions: block/remove/unblock contacts from the dashboard).
#
# For production:
#   - Deploy static files (index.html, app.js, style.css) to Azure Static Web Apps
#   - Deploy api_server.py to Azure App Service or Azure Functions
#   - Set HUBSPOT_PAT and CORS_ORIGINS in App Settings

FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY index.html app.js style.css oauth-popup.html ./
COPY api_server.py .
COPY dashboard_cache.json .

# Cache updater scripts (run these via cron or Azure Functions Timer Trigger)
COPY update_dashboard_cache.py .
COPY update_cache_fast.py .

# CGI backend (legacy — for reference only, use api_server.py instead)
COPY cgi-bin/ ./cgi-bin/

EXPOSE 8000

# Start the FastAPI API proxy server
# The static dashboard files should be served by a separate static server
# or by adding StaticFiles mount to api_server.py
CMD ["uvicorn", "api_server:app", "--host", "0.0.0.0", "--port", "8000"]
