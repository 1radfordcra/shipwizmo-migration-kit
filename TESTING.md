# Testing Guide — Smoke Tests for All Apps

**Purpose:** Verify each app works correctly after migration to Azure (or any new environment).  
**When to run:** After every deployment. After changing environment variables. After updating any backend code.  
**How to read this:** Each test has: Setup → Steps → Expected Output → Pass/Fail Criteria.

---

## Testing Philosophy

These are **smoke tests** — fast, end-to-end checks that confirm the critical path works. They are not unit tests or load tests. Each test should take 2–5 minutes. Run them in order because some tests verify dependencies between systems.

**A passing smoke test means:** The app is up, auth works, the main user flow completes without errors, and data persists correctly.

---

## App 1: Savings Calculator

**URL (after migration):** `https://savings.brdrch.com`  
**Type:** Static site, no auth  
**Dependencies:** HubSpot API (for lead capture only — calculator works without it)

### Test SC-1: Page loads correctly

**Setup:** No setup required.

**Steps:**
1. Navigate to `https://savings.brdrch.com`
2. Observe the page load

**Expected output:**
- Page loads in under 3 seconds
- Header shows "BROAD REACH — An Asendia Company"
- Calculator form is visible with: volume dropdown, weight profile checkboxes, carrier checkboxes, destination sliders
- No JavaScript errors in browser console

**Pass criteria:** All elements visible, no console errors.  
**Fail criteria:** Blank page, CSS not loaded (unstyled HTML), JS errors.

---

### Test SC-2: Calculator produces savings results

**Setup:** None.

**Steps:**
1. Select **Monthly Volume:** `1,000 – 2,500`
2. Select **Weight Profile:** check "Under 1 lb" and "1–2 lbs"
3. Select **Current Carrier:** check `USPS`
4. Set destination mix to **80% Domestic, 20% Canada**
5. Click **Calculate My Savings**

**Expected output:**
- Results panel animates into view
- Annual savings figure displayed (should be positive, e.g., ~$25,000–$75,000 range for this volume)
- Savings percentage shown (should be 50–70% range)
- Per-package savings shown
- USPS comparison row visible in carrier breakdown
- No JavaScript errors

**Pass criteria:** Savings figure > $0, percentage > 0%, breakdown shows USPS row.  
**Fail criteria:** Results panel never appears, $0 savings, NaN displayed, JS error.

---

### Test SC-3: Lead capture submits to HubSpot

**Setup:** HubSpot PAT must be configured as `HUBSPOT_PAT` env var (Azure Function or CGI). Have a HubSpot test contact list ready.

**Steps:**
1. Run Test SC-2 to generate results
2. Fill in the lead capture form:
   - Name: `Test Rozano`
   - Email: `rozano+test@shipwizmo.com` (use a test address — this creates a real HubSpot contact)
   - Company: `Test Migration Check`
   - Phone: `416-555-0001`
3. Click **Get My Full Savings Report** (or equivalent submit button)

**Expected output:**
- Success message appears on page ("Thanks — we'll be in touch")
- In HubSpot: New contact created with email `rozano+test@shipwizmo.com`
- Contact has properties set: `br_source = hot_inbound_lead`, shipping volume, savings estimate
- No JS errors

**Pass criteria:** Contact appears in HubSpot within 30 seconds.  
**Fail criteria:** Error message on page, no contact in HubSpot, network error in console.

**Cleanup:** Delete the test contact from HubSpot after verification.

---

## App 2: SAPT Tool

**URL (after migration):** `https://portal.brdrch.com`  
**Type:** Full-stack app (FastAPI + SQLite/Azure SQL)  
**Dependencies:** Google OAuth (Google Cloud project buoyant-silicon-345213), SQLite/Azure SQL

### Test ST-1: App loads and auth gate appears

**Steps:**
1. Navigate to `https://portal.brdrch.com`
2. Observe the page

**Expected output:**
- Auth gate visible with Broad Reach logo
- "Sign in with Google" button visible
- "Admin" login option visible (or toggle to show admin view)
- No console errors

**Pass criteria:** Auth gate rendered, Google button present.  
**Fail criteria:** Blank page, 500 error, CSS not loaded.

---

### Test ST-2: Google SSO login (admin)

**Setup:** Must have admin email (`craig@shipwizmo.com`) added to admin whitelist in the database.

**Steps:**
1. Click the Admin sign-in path
2. Click "Sign in with Google"
3. Complete Google sign-in for `craig@shipwizmo.com`
4. Return to main app window

**Expected output:**
- Popup opens, Google sign-in completes
- Popup closes automatically
- Main window transitions to admin dashboard
- Admin header visible (client list, rate cards, etc.)
- No console errors

**Pass criteria:** Logged in as admin, correct view displayed.  
**Fail criteria:** Popup opens but closes without signing in, error message, redirects to access request form.

---

### Test ST-3: Client login via email/password

**Setup:** A test client account must exist in the database. Create one via admin panel first, or use an existing client.

**Steps:**
1. Navigate to `https://portal.brdrch.com`
2. Click the email/password login section (collapsible)
3. Enter test client credentials
4. Click Login

**Expected output:**
- Successfully logged in as client
- Client dashboard visible with upload prompt or existing analyses
- `userType = 'client'` (admin controls not visible)

**Pass criteria:** Client view loads with correct role.  
**Fail criteria:** "Invalid credentials", 401 error, admin view shown to client.

---

### Test ST-4: CSV upload and data processing

**Setup:**  
Create a minimal test CSV (`test_shipments.csv`) with these columns:
```csv
Ship Date,Actual Weight (lbs),Billed Weight (lbs),Length (in),Width (in),Height (in),Tracking Number,Destination Zip
2026-01-15,0.5,0.5,8,6,2,1Z999AA10123456784,90210
2026-01-16,1.2,1.5,10,8,4,1Z999AA10123456785,10001
2026-01-17,3.0,3.0,12,10,6,1Z999AA10123456786,77001
```

**Steps:**
1. Log in as admin or client
2. Click "Upload CSV" or drag the file onto the upload zone
3. Wait for column mapping to appear
4. Verify auto-mapping detected: Ship Date, Actual Weight, Billed Weight, Dimensions

**Expected output:**
- File accepted, columns auto-mapped
- Data summary shows: 3 shipments, avg weight ~1.6 lbs, carrier mix
- No parsing errors

**Pass criteria:** 3 shipments processed, columns mapped correctly, summary displayed.  
**Fail criteria:** Upload rejected, 0 shipments parsed, column mapping fails.

---

### Test ST-5: Rate card loading and analysis generation

**Setup:** At least one rate card must exist in the system. If starting fresh, import a test rate card via the admin Rate Cards panel.

**Steps:**
1. Log in as admin
2. Open an existing upload (from Test ST-4 or a real client analysis)
3. Open the Analysis Workbench
4. Select one rate card from the list
5. Wait for results to populate

**Expected output:**
- Rate card checkbox toggles to selected
- Results table populates with: buy cost, sell price, profit per shipment
- KPI cards update: Avg Cost to Service, Avg Sell Rate, Avg Margin Per Piece
- No errors in console or UI

**Pass criteria:** Results appear within 10 seconds, KPI cards show non-zero values.  
**Fail criteria:** Results never load, KPI cards show NaN/undefined, 500 error.

---

### Test ST-6: Excel download

**Setup:** An analysis must exist with at least one rate card selected and results computed.

**Steps:**
1. With an analysis open in the Workbench, click "Download Excel"
2. Open the downloaded file in Excel or LibreOffice

**Expected output:**
- File downloads with `.xlsx` extension
- File has 3 sheets: Executive Summary, Detail, Summary
- Executive Summary has Broad Reach navy banner and 5 KPI cards
- Detail sheet has one row per shipment with before/after comparison

**Pass criteria:** File opens without errors, 3 sheets present, data visible.  
**Fail criteria:** Download fails, file is corrupt, fewer than 3 sheets, empty sheets.

---

### Test ST-7: Publish analysis to client

**Setup:** Admin must be logged in. A completed analysis must exist.

**Steps:**
1. In the Analysis Workbench, click "Publish to Client"
2. Log out, then log in as the client whose analysis was published
3. Navigate to the analysis

**Expected output:**
- Client view shows the published analysis
- Excel download button visible to client
- Published rate selection and savings summary visible (buy/profit columns hidden)

**Pass criteria:** Client can see and download the published analysis.  
**Fail criteria:** Client sees "no analyses" or unpublished draft.

---

## App 3: Command Center

**URL (after migration):** `https://command.brdrch.com`  
**Type:** Static dashboard + API proxy backend  
**Dependencies:** HubSpot API, Google OAuth, `dashboard_cache.json`

### Test CC-1: Dashboard loads with cached data

**Steps:**
1. Navigate to `https://command.brdrch.com`
2. Sign in with Google (authorized Broad Reach email)

**Expected output:**
- Auth gate replaced by dashboard
- KPI cards visible: Contacts, Companies, Deals, Pipeline Value
- Pipeline Value shows ~$26.25M (or current value)
- Activity feed shows recent prospect discoveries / LinkedIn pushes
- System health grid shows status for 7+ systems
- "Last synced" timestamp visible in sidebar

**Pass criteria:** All 4 KPI cards show non-zero values, activity feed has entries.  
**Fail criteria:** KPI cards show 0 or "–", activity feed empty, blank dashboard.

---

### Test CC-2: Activity feed filtering

**Steps:**
1. With dashboard loaded, click the "LinkedIn" filter button in the Activity Feed
2. Click the "Email" filter button
3. Click "All" to reset

**Expected output:**
- LinkedIn filter: shows only LinkedIn push events
- Email filter: shows only email sequence events
- All filter: shows all events
- Filter state is highlighted visually

**Pass criteria:** Filtering works correctly, counts change.  
**Fail criteria:** Filter buttons don't respond, all events always shown.

---

### Test CC-3: Activity feed expandable rows

**Steps:**
1. Click on any activity feed row

**Expected output:**
- Row expands to show full event details
- For LinkedIn pushes: shows contact name, title, company, ICP score, connection message, InMail message
- For prospect discoveries: shows full ICP profile, pain signals, shipping signals

**Pass criteria:** Expansion works, correct data shown.  
**Fail criteria:** Click has no effect, empty expansion panel.

---

### Test CC-4: Block contact action

**Setup:** Identify a test contact in the "Blocked Contacts" table or the activity feed.

**Steps:**
1. Navigate to the Blocked Contacts section
2. Click "Unblock" on a test contact (this will call the HubSpot API via the proxy)

**Expected output:**
- Confirm that the `window.confirm` override has been **removed** (should now show real dialog)
- Confirmation dialog appears asking "Are you sure?"
- On confirm: contact status updates in HubSpot
- Row removed from blocked contacts table

**Pass criteria:** Confirmation dialog appears (not auto-accepted), HubSpot updated.  
**Fail criteria:** Action executes without confirmation, HubSpot not updated, 500 error.

---

### Test CC-5: Cache freshness

**Steps:**
1. Note the "Last synced" timestamp in the sidebar
2. Confirm timestamp is within the last 24 hours

**Expected output:**
- Timestamp from today or yesterday
- If stale (> 24 hours): check if the cache updater cron ran. Trigger manual refresh if available.

**Pass criteria:** Data is less than 24 hours old.  
**Fail criteria:** Data is days or weeks old.

---

## App 4: Customs Data Portal

**URL (after migration):** `https://customs.brdrch.com`  
**Type:** Full-stack (FastAPI + SQLite/Azure SQL)  
**Dependencies:** Google OAuth, SQLite/Azure SQL, API key system

> **Note:** All source files must be retrieved from the deployed server before testing a migrated instance. See `customs-data-portal/README-SOURCE.md`.

### Test CP-1: App loads and auth gate appears

**Steps:**
1. Navigate to `https://customs.brdrch.com`

**Expected output:**
- Login/registration page visible
- "Sign in with Google" button present
- Email/password registration form available
- No console errors

**Pass criteria:** Auth UI renders.  
**Fail criteria:** 500 error, blank page, CSS not loaded.

---

### Test CP-2: Google SSO — new user auto-registration

**Steps:**
1. Click "Sign in with Google"
2. Use a Google account NOT previously registered
3. Complete sign-in

**Expected output:**
- New account created automatically
- Redirected to dashboard (empty SKU list)
- Welcome or onboarding state visible

**Pass criteria:** Account created, dashboard visible, no error.  
**Fail criteria:** "Access denied", 500 error, infinite loading.

---

### Test CP-3: SKU CRUD operations

**Setup:** Log in as a test user.

**Steps:**
1. Click "Add SKU"
2. Fill in:
   - SKU Code: `TEST-SKU-001`
   - Description: `Test Widget`
   - HS Code: `8517.12.00`
   - Country of Origin: `CA`
   - Customs Value: `15.00`
   - Currency: `CAD`
3. Click Save
4. Verify the SKU appears in the list
5. Click Edit, change the customs value to `18.00`, Save
6. Verify the update
7. Delete the SKU
8. Verify it's gone

**Expected output:** All CRUD operations complete without errors.  
**Pass criteria:** Create, read, update, delete all work.  
**Fail criteria:** Any operation fails, data not persisted, 500 error.

---

### Test CP-4: CUSMA certificate generation

**Setup:** Create at least 2 SKUs with different countries of origin and HS codes.

**Steps:**
1. Click "Generate Certificate" (or equivalent button)
2. Select 2 SKUs
3. Set blanket period: 2026-01-01 to 2026-12-31
4. Enter importer details (test data OK)
5. Click Generate

**Expected output:**
- Certificate created with status "Draft"
- Certificate detail view shows all 9 CUSMA minimum data elements
- HS codes and countries of origin pulled correctly from SKU data
- Blanket period set correctly

**Pass criteria:** Certificate created, all 9 fields populated.  
**Fail criteria:** Certificate empty, missing required fields, 500 error.

---

### Test CP-5: Certificate activation and status lifecycle

**Steps:**
1. Open the draft certificate from Test CP-4
2. Click "Activate"
3. Verify status changes to "Active"
4. Manually set the blanket end date to yesterday
5. Verify status changes to "Expired" (or trigger the expiry check)

**Pass criteria:** Status transitions Draft → Active → Expired work.  
**Fail criteria:** Status doesn't update, buttons have no effect.

---

### Test CP-6: SKU lookup API (external REST endpoint)

**Setup:** Generate an API key in the Customs Portal Settings page. Note the key value.

**Steps:**
1. Open a terminal or Postman
2. Run:
   ```bash
   curl -H "X-API-Key: YOUR_API_KEY_HERE" \
     "https://customs.brdrch.com/api/lookup/TEST-SKU-001?include_cusma=true"
   ```
3. Or with `?api_key=` query param:
   ```bash
   curl "https://customs.brdrch.com/api/lookup/TEST-SKU-001?api_key=YOUR_API_KEY_HERE&include_cusma=true"
   ```

**Expected output:**
```json
{
  "sku": "TEST-SKU-001",
  "description": "Test Widget",
  "hs_code": "8517.12.00",
  "country_of_origin": "CA",
  "customs_value": 18.00,
  "currency": "CAD",
  "cusma_eligible": true,
  "certificate_id": "cert_abc123",
  "blanket_period": {
    "start": "2026-01-01",
    "end": "2026-12-31"
  }
}
```

**Pass criteria:** 200 response, all fields present, data matches what was entered.  
**Fail criteria:** 401 (auth failure), 404 (SKU not found), 500 error.

**Test invalid API key:**
```bash
curl -H "X-API-Key: invalid_key" "https://customs.brdrch.com/api/lookup/TEST-SKU-001"
```
Expected: `{"error": "Unauthorized"}` with HTTP 401.

---

### Test CP-7: CSV bulk import

**Setup:** Prepare a test CSV:
```csv
sku_code,description,hs_code,country_of_origin,customs_value,currency
BULK-001,Widget A,6109.10.00,CA,12.50,CAD
BULK-002,Widget B,6110.20.10,US,8.75,USD
BULK-003,Widget C,8517.12.00,CA,45.00,CAD
```

**Steps:**
1. Navigate to SKU management
2. Click "Import CSV" or drag the file
3. Confirm the import

**Expected output:**
- 3 new SKUs created
- All fields correctly populated
- Duplicate detection: if `BULK-001` already exists, should warn (not silently overwrite)

**Pass criteria:** 3 SKUs created, correct data.  
**Fail criteria:** Import fails, 0 SKUs created, data corruption.

---

## Post-Migration Full Regression: Run All Tests

After completing a full Azure migration, run tests in this order:

1. SC-1, SC-2 (Savings Calc loads and calculates)
2. ST-1, ST-2, ST-3 (SAPT Tool auth)
3. ST-4, ST-5 (SAPT Tool analysis engine)
4. ST-6, ST-7 (SAPT Tool Excel and publish)
5. CC-1, CC-2, CC-3 (Command Center dashboard)
6. CC-4, CC-5 (Command Center actions and freshness)
7. CP-1, CP-2 (Customs Portal auth)
8. CP-3, CP-4, CP-5 (Customs Portal CRUD and certificates)
9. CP-6, CP-7 (Customs Portal API and bulk import)
10. SC-3 (Savings Calc lead capture — run last to avoid HubSpot clutter)

**Total estimated time:** 45–60 minutes for full regression.  
**Recommend:** Run after every significant code change or Azure config change.
