# Broad Reach Outbound Machine — Docker Image
# Script runner for the 9-step daily outbound cycle. Not a web server.
#
# Build:  docker build -t br-outbound-machine .
# Run:    docker run --env-file .env br-outbound-machine
#
# For production (Azure Functions):
#   - Deploy using the azure-functions/ directory (Timer Triggers)
#   - Set all env vars in Azure Function App Settings
#
# For testing (dry run mode):
#   docker run --env-file .env -e DRY_RUN=1 br-outbound-machine

FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Default: run the full daily cycle
# Override with: docker run ... python crons/hot_lead_monitor.py
CMD ["python", "run_daily_cycle.py"]
