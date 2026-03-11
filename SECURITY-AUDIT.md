# Security Audit — All ShipWizmo Apps

**Prepared for:** Rozano (developer handoff)  
**Date:** 2026-03-06  
**Scope:** All four production apps + migration risk assessment  
**Severity scale:** CRITICAL → HIGH → MEDIUM → LOW → INFO

---

## Executive Summary

These apps were built for rapid deployment in a controlled Perplexity Computer hosting environment with a small, known user base. They work correctly for their purpose but contain several security patterns that are **acceptable in a sandboxed demo environment** and **not acceptable in production** on Azure with real customer data.

The highest priority items before production deployment:

1. **Rotate the hardcoded HubSpot PAT token** in `savings-calculator/cgi-bin/quote.py` immediately
2. **Fix the Excel download endpoint** in SAPT Tool — it accepts any client ID without auth
3. **Lock `postMessage` origins** across all three apps using the popup SSO pattern
4. **Replace auth tokens as query parameters** with httpOnly cookies
5. **Remove `window.confirm = () => true`** from Command Center

---

## 1. Auth Flows

### 1.1 Google OAuth Popup Pattern (SAPT Tool, Command Center, Customs Portal)

All three apps use an identical workaround for Google Sign-In inside Perplexity's iframe environment:

```
1. User clicks "Sign in with Google"
2. app.js opens oauth-popup.html as new window (window.open())
3. oauth-popup.html runs Google Identity Services
4. Google returns credential JWT to the popup
5. Popup POSTs credential to /api/auth/google
6. Backend verifies JWT against Google's public keys
7. Backend returns {token, userId, userType}
8. Popup calls window.opener.postMessage({token, userId, ...}, '*')
9. Main window receives message, stores auth state
10. Popup closes
```

**Security concerns:**
- Step 8: `postMessage(data, '*')` — the `'*'` wildcard target origin means ANY window can intercept this message. On production domains, replace with the specific origin (e.g., `'https://portal.brdrch.com'`).
- Step 9: The receiving `message` event listener does not validate `event.origin` in current implementation. Add: `if (event.origin !== 'https://portal.brdrch.com') return;`

**Remediation:**
```javascript
// oauth-popup.html — change this:
window.opener.postMessage(authData, '*');

// to this:
window.opener.postMessage(authData, 'https://portal.brdrch.com');
```

```javascript
// app.js — add origin check:
window.addEventListener('message', (event) => {
  if (event.origin !== 'https://portal.brdrch.com') return;
  // ... handle auth
});
```

### 1.2 Email/Password Fallback (SAPT Tool, Customs Portal)

Both apps offer email/password auth as a fallback to Google SSO.

**SAPT Tool:** SHA-256 password hashing (`hashlib.sha256`). Passwords are hashed before storage in SQLite, but SHA-256 is a fast hash — not designed for passwords. It is vulnerable to brute-force and rainbow table attacks.

**⚠️ MIGRATION RECOMMENDATION:** Replace SHA-256 with **bcrypt** (or argon2) before production deployment. The migration path:
1. Add `bcrypt` to `requirements.txt`
2. Replace all `hashlib.sha256(pw.encode()).hexdigest()` calls with `bcrypt.hashpw(pw.encode(), bcrypt.gensalt())`
3. Replace verification: `bcrypt.checkpw(pw.encode(), stored_hash.encode())`
4. To support existing users during migration: try bcrypt first, fall back to SHA-256, then re-hash with bcrypt on successful login

Affected files: `sapt-tool/api_server.py` (lines 921, 2341, 2366, 2817, 3861, 3878, 3914, 4011), `sapt-tool/cgi-bin/api.py` (lines 573, 1362, 2073)

**Known risk:** If SQLite file is accessible (e.g., via path traversal or misconfigured file serving), SHA-256 hashed passwords could be cracked quickly with modern GPUs. Mitigated on Azure by keeping the SQLite file outside the web root (or switching to Azure SQL).

**Remediation for Azure:**
- **Upgrade to bcrypt immediately** — this is the highest-priority security item
- Use Azure SQL — database not accessible via file path
- Enforce minimum password length (8 chars) and complexity in registration form
- Rate-limit `/api/auth/login` to prevent brute force (5 attempts/min per IP)

### 1.3 JWT Token Handling (SAPT Tool, Customs Portal)

After login, the backend returns a short-lived token. Current pattern:

```javascript
// In app.js — token appended to every API call as query parameter:
let url = API + path;
url += `?token=${state.token}`;
const res = await fetch(url, {...});
```

**Risks:**
- Tokens appear in server access logs (URL logging)
- Tokens appear in browser history
- Tokens can be captured by third-party analytics scripts
- Admin sessions: 30 days, client sessions: 7 days — long exposure window if token is leaked

**Remediation for Azure:**
- Switch to httpOnly, Secure, SameSite=Lax cookies
- Use short token TTL (1 hour) with refresh token pattern
- Remove token from query params

### 1.4 Admin Whitelist (SAPT Tool)

SAPT Tool restricts admin access to email addresses in a database table. Admins can add/remove team members via the Settings panel. The whitelist is checked server-side on every admin route.

This is a sound pattern. Maintain the whitelist carefully on migration.

---

## 2. Known Vulnerabilities

### 2.1 Excel Download Endpoint — No Token Validation (SAPT Tool)

**Severity: CRITICAL**

From the portal documentation:
> "The endpoint accepts a token parameter but doesn't validate it. Anyone who guesses a client ID could download the file."

**The endpoint:**
```
GET /api/analysis/{client_id}/excel?token=anything
```

The `token` parameter is accepted but not verified against a valid session. Any request with a valid `client_id` (an integer, likely sequential) returns the Excel file.

**Impact:** Full exposure of client shipping data, rate cards, pricing, and margins to unauthenticated requests. Client IDs are integers — an attacker can enumerate 1, 2, 3... and download all client analyses.

**Remediation:**
```python
# In api.py — add to the Excel endpoint:
def get_excel(client_id: int, token: str):
    session = verify_token(token)           # Validate token
    if not session:
        raise HTTPException(401, "Unauthorized")
    if session.user_id != client_id and session.user_type != 'admin':
        raise HTTPException(403, "Forbidden")  # Client can only get their own
    # ... generate and return Excel
```

### 2.2 Hardcoded HubSpot API Token (Savings Calculator)

**Severity: CRITICAL**

The file `savings-calculator/cgi-bin/quote.py` previously contained a hardcoded HubSpot PAT token.

**STATUS: FIXED.** The token has been removed from all source files and replaced with `os.environ.get("HUBSPOT_PAT", "")`. The old token has been rotated in HubSpot. This fix was also applied to `command-center/cgi-bin/api.py` and `command-center/api_server.py`.

**Migration action:**
1. **Rotate the token immediately** in HubSpot: Settings → Integrations → Private Apps → Savings Calculator App → Generate New Token
2. **Move to environment variable**: `HUBSPOT_PAT = os.environ.get('HUBSPOT_PAT')`
3. **Revoke the old token** after verifying the new one works
4. **Do not include token files in git** — add to `.gitignore`

### 2.3 postMessage Wildcard Origin (SAPT Tool, Command Center, Customs Portal)

**Severity: MEDIUM**

See Section 1.1 above. All three apps use `postMessage(data, '*')`. Any window (including malicious cross-origin pages) that has a reference to the main window can receive the auth token.

**Remediation:** Lock to specific origin. See Section 1.1 for code fix.

### 2.4 window.confirm Override in Command Center

**Severity: HIGH**

`command-center/index.html` contains:
```javascript
// Auto-accept confirm dialogs for testing Remove & Block Contact action
window.confirm = function(msg) { console.log('Auto-accepted confirm:', msg); return true; };
```

This overrides the native browser confirmation dialog for ALL dialogs on the page. Any "Are you sure you want to delete/block?" prompt will auto-accept without user interaction.

**Impact:** If a user accidentally clicks a destructive action (remove contact, block contact), there is no confirmation step. Data loss is immediate.

**Remediation:** Remove this line entirely before deploying to production. It was added for testing purposes only.

### 2.5 Session State in Memory (All Apps Using Popup Auth)

**Severity: MEDIUM**

Auth state (`_authState`, `state.token`) is held in JavaScript memory objects, not in `localStorage` or cookies. This was a deliberate choice because the apps ran inside Perplexity's iframe (localStorage is isolated per origin in iframes).

**Impact on production:**
- Page refresh = logged out (poor UX)
- Tab close = session lost
- No cross-tab session sharing

**Remediation for Azure:** Switch to httpOnly, Secure cookies. Session persists across refreshes and tabs. The backend sets the cookie on login; JS never touches the cookie value.

---

## 3. OWASP Top 10 Relevance

| OWASP Category | Relevance | Specific Finding | Severity |
|---|---|---|---|
| **A01: Broken Access Control** | HIGH | Excel endpoint no auth (SAPT Tool) | CRITICAL |
| **A01: Broken Access Control** | MEDIUM | Auth tokens as URL params visible in logs | MEDIUM |
| **A02: Cryptographic Failures** | LOW | HubSpot PAT hardcoded in source (Savings Calc) | CRITICAL |
| **A03: Injection** | LOW | CSV upload in SAPT Tool — no server-side sanitization documented | MEDIUM |
| **A04: Insecure Design** | MEDIUM | In-memory sessions, no CSRF protection | MEDIUM |
| **A05: Security Misconfiguration** | MEDIUM | No CORS headers configured | MEDIUM |
| **A07: Identification/Auth Failures** | HIGH | window.confirm override (Command Center) | HIGH |
| **A07: Identification/Auth Failures** | HIGH | postMessage wildcard origin | MEDIUM |
| **A08: Software/Data Integrity** | LOW | No integrity checks on uploaded CSV data | LOW |
| **A09: Security Logging** | INFO | No security event logging currently | LOW |
| **A10: SSRF** | LOW | Command Center API proxy — validate HubSpot responses | LOW |

---

## 4. API Key Exposure Risks

| Key/Secret | Location | Exposure Risk | Action |
|---|---|---|---|
| `HUBSPOT_TOKEN` (PAT) | Hardcoded in `savings-calculator/cgi-bin/quote.py` | CRITICAL — in source code and kit zip | Rotate immediately, move to env var |
| `HUBSPOT_PAT` | Referenced in `.env.example` (placeholder) | Low — not in code | Keep as env var, store in Azure Key Vault |
| `APOLLO_API_KEY` | Referenced in `.env.example` | Low | Store in Azure Key Vault |
| `GOOGLE_CLIENT_ID` | Hardcoded in `app.js` (all apps) | Low — Client IDs are meant to be public; secrets are separate | Acceptable; ensure `GOOGLE_CLIENT_SECRET` is never in JS |
| `GOOGLE_CLIENT_SECRET` | In Google Cloud Console (not in code) | Safe | Store in Azure Key Vault |
| `NOTION_TOKEN` | Via Perplexity connector (not in code) | Safe | Store in Azure Key Vault |
| `SLACK_BOT_TOKEN` | Via Perplexity connector (not in code) | Safe | Store in Azure Key Vault |
| `ZAPIER_WEBHOOK_URL` | Listed in portal HTML | Low — webhooks are fire-and-forget, no data exposed | Change webhook URL if compromised |

---

## 5. CORS Configuration (Required for Azure)

Currently, CORS is handled by Perplexity's hosting environment. On Azure, each app must explicitly configure CORS.

### Savings Calculator
Static site — no backend, no CORS needed. No configuration required.

### SAPT Tool (FastAPI on Azure)
```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://portal.brdrch.com"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)
```

### Command Center
Static site frontend. The `api_server.py` (FastAPI) must add CORS:
```python
allow_origins=["https://command.brdrch.com"]
```

### Customs Data Portal (FastAPI, already production-ready)
```python
allow_origins=[
    "https://customs.brdrch.com",
    "https://app.shipwizmo.com"   # ShipWizmo shipping app calling /api/lookup/
]
```

---

## 6. Session Management

Current state across all apps:

| App | Auth Storage | Session Duration | Notes |
|---|---|---|---|
| Savings Calculator | None — no auth | — | Public app, no sessions |
| SAPT Tool | JS `state` object (in-memory) | Admin: 30 days, Client: 7 days | Loses on page refresh |
| Command Center | `_authState` variable (in-memory) | 8 hours | Loses on page refresh |
| Customs Portal | JS `state` object (in-memory) | Unknown | Same pattern |

**Migration target for all authenticated apps:**

1. Backend sets `Set-Cookie: session=<token>; HttpOnly; Secure; SameSite=Lax; Max-Age=86400`
2. Frontend never reads or writes the cookie
3. All API calls include `credentials: 'include'` (already set in `api()` function)
4. Backend validates session token from cookie on every request
5. CSRF token required for state-changing requests (POST/PUT/DELETE)

---

## 7. Hardening Steps by App

### Savings Calculator
Priority order:
1. **Rotate HUBSPOT_PAT immediately** (token is live in `cgi-bin/quote.py`)
2. Move token to env var: `HUBSPOT_TOKEN = os.environ.get('HUBSPOT_PAT')`
3. Add server-side form validation (length limits, email format)
4. Replace CGI with Azure Function + store PAT in Key Vault
5. Add rate limiting to lead capture endpoint (prevent HubSpot spam)

### SAPT Tool
Priority order:
1. **Fix Excel download endpoint** — add token validation (CRITICAL)
2. **Lock postMessage origin** in `oauth-popup.html`
3. Add `event.origin` check in `app.js` message handler
4. Replace token-as-query-param with httpOnly cookies
5. Add rate limiting to `/api/auth/login` (5 req/min/IP)
6. Add input sanitization for CSV upload (check for formula injection: cells starting with `=`, `+`, `-`, `@`)
7. Store secrets in Azure Key Vault
8. Switch SQLite → Azure SQL
9. Wire "Upload Document" to Azure Blob Storage

### Command Center
Priority order:
1. **Remove `window.confirm = () => true`** from `index.html` (HIGH)
2. **Lock postMessage origin** in `oauth-popup.html`
3. Add `event.origin` check in `app.js`
4. Move `HUBSPOT_TOKEN` in `api_server.py` to env var / Key Vault
5. Replace in-memory auth with `localStorage` or cookies
6. Ensure `dashboard_cache.json` is not publicly accessible (contains prospect PII)

### Customs Data Portal
Priority order:
1. **Retrieve source files first** (see README-SOURCE.md) — cannot audit without source
2. **Lock postMessage origin** in `oauth-popup.html`
3. Add `event.origin` check in `app.js`
4. Switch API key delivery to `X-API-Key` header only (remove query param)
5. Add rate limiting to `/api/lookup/{sku}` (100 req/min per API key)
6. Configure CORS explicitly (see Section 5)
7. Replace in-memory auth with httpOnly cookies
8. Switch SQLite → Azure SQL
9. Add CSRF protection for state-changing endpoints

---

## 8. Recommendations for Azure Deployment

1. **Use Azure Key Vault for all secrets** — never put secrets in code or App Settings plaintext. Reference Key Vault from App Settings.
2. **Enable Azure Defender for App Service** — detects common web attack patterns.
3. **Configure Azure Front Door or Application Gateway** with WAF rules — blocks OWASP top 10 attacks at the network edge before they reach the app.
4. **Enable HTTPS-only** on all App Services — Azure does this by default, but verify.
5. **Set up Application Insights** — alerts on 500 errors, unusual traffic patterns, auth failures.
6. **Restrict App Service IP access** during migration testing — only allow your IP until everything is verified.
7. **Use Managed Identity** for Azure SQL connections instead of SQL username/password.
8. **Enable Microsoft Entra ID (Azure AD) authentication** at the App Service level as an additional auth layer, if the team uses Microsoft 365.
9. **Audit log all auth events** — log sign-ins, failed attempts, token generation/revocation to Application Insights.
10. **Regular dependency updates** — pin Python packages (done in `requirements.txt`) but schedule quarterly updates for security patches.
