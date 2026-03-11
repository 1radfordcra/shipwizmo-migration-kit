# FastAPI Migration Spec

## Overview
Convert `/home/user/workspace/br-portal/cgi-bin/api.py` (CGI script) to `/home/user/workspace/br-portal/api_server.py` (FastAPI server on port 8000).

## Critical Requirements

### 1. Database Persistence
- The DB file must be at `/home/user/workspace/br-portal/portal.db`
- On startup, run `init_db()` and `seed_demo_data()` ONLY if tables are empty (check `SELECT COUNT(*) FROM admins`)
- This means data survives server restarts — the key difference from CGI

### 2. Google OAuth for Client Login
- Use Google OAuth 2.0 via the ID token approach (frontend uses Google Sign-In JS library)
- Flow:
  1. Frontend loads Google Sign-In button with client ID
  2. User signs in with Google → gets an ID token (JWT)
  3. Frontend sends ID token to `POST /api/auth/google` endpoint
  4. Backend verifies the token with Google (using `google.oauth2.id_token` from `google-auth` package)
  5. Extract email from token, look up in `clients` table
  6. If found → create session, return token
  7. If not found → return 401 "No invitation found for this email"
- For demo/development: also keep the existing email-only client login as fallback
- Admin login stays password-based (no change)

### 3. All Existing Endpoints (preserve exact paths and behavior)
Convert ALL routes from CGI `main()` router to FastAPI routes:

```
POST /api/auth/login          → handle_auth_login
POST /api/auth/google         → NEW: Google OAuth token verification
GET  /api/clients             → list clients
POST /api/clients             → create client
GET  /api/clients/{id}        → get client detail
PUT  /api/clients/{id}        → update client
POST /api/clients/{id}/documents       → update client docs
POST /api/clients/{id}/shipping-data   → upload shipping data
GET  /api/clients/{id}/shipping-data   → get shipping data
DELETE /api/clients/{id}/shipping-data → delete shipping data
POST /api/clients/{id}/analysis        → run analysis
POST /api/clients/{id}/analysis/publish → publish analysis
POST /api/clients/{id}/setup           → save setup info
GET  /api/clients/{id}/setup           → get setup info
GET  /api/clients/{id}/notifications   → get client notifications
POST /api/clients/{id}/notifications/read → mark read
GET  /api/rate-cards          → list rate cards
POST /api/rate-cards          → create rate card (handles CSV & JSON)
GET  /api/rate-cards/{id}     → get rate card detail
PUT  /api/rate-cards/{id}     → update rate card
DELETE /api/rate-cards/{id}   → delete rate card
GET  /api/zone-charts         → list zone charts
POST /api/zone-charts         → create zone chart
GET  /api/zone-charts/{id}    → get zone chart detail
DELETE /api/zone-charts/{id}  → delete zone chart
GET  /api/documents           → list documents
POST /api/documents           → create document
GET  /api/settings            → get settings
POST /api/settings            → save settings
GET  /api/notifications       → list notifications
POST /api/notifications/read  → mark all read
GET  /api/dashboard           → dashboard stats
GET  /api/zones/lookup        → zone lookup (query params: zip, carrier)
GET  /api/service-catalog     → service catalog
GET  /api/transit-times       → transit times (query params: origin_zip, dest_zip)
GET  /api/peak-surcharges     → peak surcharges
GET  /api/accessorials        → accessorials (query params: carrier)
```

### 4. Copy ALL business logic verbatim
These functions must be copied exactly from the CGI script:
- `_load_zone_data()`, `lookup_us_zone()`, `lookup_ca_zone()`
- `determine_zone()`, `calc_dim_weight()`, `round_billable_weight()`, `calc_cubic_feet()`
- `lookup_rate()`, `get_weight_band()`, `run_rate_analysis()`
- `parse_wizmo_csv()`, `is_wizmo_format()`
- All `_seed_*` functions and `seed_rate_cards()`
- `seed_demo_data()` (but only run if DB is empty)
- The `CARRIER_DISPLAY`, `CARRIER_ZONE_KEY` constants
- `US_ZONES`, `CA_ZONES` globals

### 5. CORS
Add permissive CORS middleware (allow all origins) for development.

### 6. Request/Response Format
- Keep JSON request/response bodies identical to CGI version
- Token auth via query param `?token=xxx` (same as current)
- Error responses: `{"error": "message"}` with appropriate status codes

## File Locations
- New server: `/home/user/workspace/br-portal/api_server.py`
- Keep CGI file as-is (don't modify or delete it)
- DB: `/home/user/workspace/br-portal/portal.db`
- Data dir: `/home/user/workspace/br-portal/data/`
- Seed file: `/home/user/workspace/br-portal/rate_cards_seed.json`

## Dependencies
Already installed: fastapi, uvicorn
Need to install: google-auth (for ID token verification)
