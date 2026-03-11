#!/bin/bash
# ============================================================
# Broad Reach — Azure Infrastructure Setup
# Run this script to create all Azure resources in one shot.
# Prerequisites: Azure CLI installed and logged in (az login)
# ============================================================

set -e

# --- CONFIGURATION (edit these) ---
RESOURCE_GROUP="broadreach-rg"
LOCATION="eastus"
STORAGE_ACCOUNT="broadreachstorage"
KEYVAULT_NAME="broadreach-kv"
FUNCAPP_NAME="broadreach-functions"
WEBAPP_PORTAL="broadreach-sapt-tool"
WEBAPP_CUSTOMS="broadreach-customs-portal"
STATIC_CALCULATOR="broadreach-savings-calc"
STATIC_COMMAND="broadreach-command-center"
STATIC_HANDOFF="broadreach-dev-handoff"

echo "============================================"
echo " Broad Reach — Azure Infrastructure Setup"
echo "============================================"
echo ""

# --- 1. Resource Group ---
echo "→ Creating resource group: $RESOURCE_GROUP"
az group create --name $RESOURCE_GROUP --location $LOCATION

# --- 2. Key Vault ---
echo "→ Creating Key Vault: $KEYVAULT_NAME"
az keyvault create \
  --name $KEYVAULT_NAME \
  --resource-group $RESOURCE_GROUP \
  --location $LOCATION

echo "→ Adding secrets to Key Vault (you will be prompted for values)"
echo "  Paste each secret value when prompted. Press Enter after each."
echo ""

for SECRET in HUBSPOT-PAT APOLLO-API-KEY GOOGLE-CLIENT-SECRET SLACK-BOT-TOKEN NOTION-TOKEN; do
  echo -n "  Enter value for $SECRET: "
  read -s SECRET_VALUE
  echo ""
  az keyvault secret set \
    --vault-name $KEYVAULT_NAME \
    --name $SECRET \
    --value "$SECRET_VALUE" \
    --output none
  echo "  ✓ $SECRET stored"
done

# --- 3. Storage Account (for Azure Functions + Blob Storage) ---
echo ""
echo "→ Creating storage account: $STORAGE_ACCOUNT"
az storage account create \
  --name $STORAGE_ACCOUNT \
  --resource-group $RESOURCE_GROUP \
  --location $LOCATION \
  --sku Standard_LRS

# --- 4. Azure Function App (for all cron jobs) ---
echo ""
echo "→ Creating Function App: $FUNCAPP_NAME"
az functionapp create \
  --name $FUNCAPP_NAME \
  --resource-group $RESOURCE_GROUP \
  --storage-account $STORAGE_ACCOUNT \
  --consumption-plan-location $LOCATION \
  --runtime python \
  --runtime-version 3.11 \
  --functions-version 4 \
  --os-type linux

echo "→ Configuring Function App settings"
STORAGE_CONN=$(az storage account show-connection-string \
  --name $STORAGE_ACCOUNT \
  --resource-group $RESOURCE_GROUP \
  --query connectionString -o tsv)

az functionapp config appsettings set \
  --name $FUNCAPP_NAME \
  --resource-group $RESOURCE_GROUP \
  --settings \
    ZAPIER_WEBHOOK_URL="https://hooks.zapier.com/hooks/catch/1360401/u0giijd/" \
    GMAIL_SENDER="craig@brdrch.com" \
    AZURE_STORAGE_CONNECTION_STRING="$STORAGE_CONN"

echo "→ Linking Key Vault secrets to Function App"
VAULT_URI="https://$KEYVAULT_NAME.vault.azure.net"
az functionapp config appsettings set \
  --name $FUNCAPP_NAME \
  --resource-group $RESOURCE_GROUP \
  --settings \
    HUBSPOT_PAT="@Microsoft.KeyVault(SecretUri=$VAULT_URI/secrets/HUBSPOT-PAT/)" \
    APOLLO_API_KEY="@Microsoft.KeyVault(SecretUri=$VAULT_URI/secrets/APOLLO-API-KEY/)" \
    SLACK_BOT_TOKEN="@Microsoft.KeyVault(SecretUri=$VAULT_URI/secrets/SLACK-BOT-TOKEN/)" \
    NOTION_TOKEN="@Microsoft.KeyVault(SecretUri=$VAULT_URI/secrets/NOTION-TOKEN/)"

# Enable managed identity for Key Vault access
echo "→ Enabling managed identity for Function App"
az functionapp identity assign \
  --name $FUNCAPP_NAME \
  --resource-group $RESOURCE_GROUP

FUNC_PRINCIPAL=$(az functionapp identity show \
  --name $FUNCAPP_NAME \
  --resource-group $RESOURCE_GROUP \
  --query principalId -o tsv)

az keyvault set-policy \
  --name $KEYVAULT_NAME \
  --object-id $FUNC_PRINCIPAL \
  --secret-permissions get list

# --- 5. App Services (SAPT Tool + Customs Portal) ---
echo ""
echo "→ Creating App Service Plan"
az appservice plan create \
  --name broadreach-plan \
  --resource-group $RESOURCE_GROUP \
  --sku B1 \
  --is-linux

echo "→ Creating SAPT Tool: $WEBAPP_PORTAL"
az webapp create \
  --name $WEBAPP_PORTAL \
  --resource-group $RESOURCE_GROUP \
  --plan broadreach-plan \
  --runtime "PYTHON:3.11"

az webapp config appsettings set \
  --name $WEBAPP_PORTAL \
  --resource-group $RESOURCE_GROUP \
  --settings \
    GOOGLE_CLIENT_ID="105648453442-gjnirc4fa4tmii07lt1lmd353serh4ng.apps.googleusercontent.com" \
    ADMIN_EMAIL="craig@shipwizmo.com" \
    SCM_DO_BUILD_DURING_DEPLOYMENT="true" \
    GOOGLE_CLIENT_SECRET="@Microsoft.KeyVault(SecretUri=$VAULT_URI/secrets/GOOGLE-CLIENT-SECRET/)"

az webapp config set \
  --name $WEBAPP_PORTAL \
  --resource-group $RESOURCE_GROUP \
  --startup-file "uvicorn api_server:app --host 0.0.0.0 --port 8000"

echo "→ Creating Customs Data Portal: $WEBAPP_CUSTOMS"
az webapp create \
  --name $WEBAPP_CUSTOMS \
  --resource-group $RESOURCE_GROUP \
  --plan broadreach-plan \
  --runtime "PYTHON:3.11"

az webapp config appsettings set \
  --name $WEBAPP_CUSTOMS \
  --resource-group $RESOURCE_GROUP \
  --settings \
    GOOGLE_CLIENT_ID="105648453442-gjnirc4fa4tmii07lt1lmd353serh4ng.apps.googleusercontent.com" \
    SCM_DO_BUILD_DURING_DEPLOYMENT="true" \
    GOOGLE_CLIENT_SECRET="@Microsoft.KeyVault(SecretUri=$VAULT_URI/secrets/GOOGLE-CLIENT-SECRET/)"

az webapp config set \
  --name $WEBAPP_CUSTOMS \
  --resource-group $RESOURCE_GROUP \
  --startup-file "uvicorn api_server:app --host 0.0.0.0 --port 8000"

# Enable managed identity for both web apps
for APP in $WEBAPP_PORTAL $WEBAPP_CUSTOMS; do
  az webapp identity assign --name $APP --resource-group $RESOURCE_GROUP
  PRINCIPAL=$(az webapp identity show --name $APP --resource-group $RESOURCE_GROUP --query principalId -o tsv)
  az keyvault set-policy --name $KEYVAULT_NAME --object-id $PRINCIPAL --secret-permissions get list
done

# --- 6. Static Web Apps (Calculator, Command Center, Handoff) ---
echo ""
echo "→ Creating Static Web Apps"
for STATIC in $STATIC_CALCULATOR $STATIC_COMMAND $STATIC_HANDOFF; do
  echo "  → $STATIC"
  az staticwebapp create \
    --name $STATIC \
    --resource-group $RESOURCE_GROUP \
    --location $LOCATION \
    --sku Free
done

# --- 7. Application Insights ---
echo ""
echo "→ Creating Application Insights"
az monitor app-insights component create \
  --app broadreach-insights \
  --location $LOCATION \
  --resource-group $RESOURCE_GROUP \
  --application-type web

INSIGHTS_KEY=$(az monitor app-insights component show \
  --app broadreach-insights \
  --resource-group $RESOURCE_GROUP \
  --query instrumentationKey -o tsv)

az functionapp config appsettings set \
  --name $FUNCAPP_NAME \
  --resource-group $RESOURCE_GROUP \
  --settings APPINSIGHTS_INSTRUMENTATIONKEY="$INSIGHTS_KEY"

# --- DONE ---
echo ""
echo "============================================"
echo " ✓ All Azure resources created!"
echo "============================================"
echo ""
echo " Resource Group:    $RESOURCE_GROUP"
echo " Key Vault:         $KEYVAULT_NAME"
echo " Function App:      $FUNCAPP_NAME.azurewebsites.net"
echo " SAPT Tool:        $WEBAPP_PORTAL.azurewebsites.net"
echo " Customs Portal:    $WEBAPP_CUSTOMS.azurewebsites.net"
echo " Savings Calculator: $STATIC_CALCULATOR (Static Web App)"
echo " Command Center:     $STATIC_COMMAND (Static Web App)"
echo " Dev Handoff:        $STATIC_HANDOFF (Static Web App)"
echo ""
echo " Next steps:"
echo "   1. Update Google Cloud Console OAuth origins with new Azure domains"
echo "   2. Deploy code: az webapp deployment source config-zip ..."
echo "   3. Deploy functions: func azure functionapp publish $FUNCAPP_NAME"
echo "   4. Configure custom domains (portal.brdrch.com, etc.)"
echo ""
