"""
Broad Reach Customs Data Portal — api_server.py
================================================
Complete FastAPI backend for customs data management, CUSMA certificate generation,
HTS code validation, duty estimation, team collaboration, and webhook integrations.

Uses SQLite (WAL mode) with direct sqlite3 module, JWT auth, Google OAuth,
bcrypt password hashing, HMAC-SHA256 webhook signing, and optional WeasyPrint PDF generation.
"""

# ---------------------------------------------------------------------------
# Standard library imports
# ---------------------------------------------------------------------------
import os
import json
import sqlite3
import hashlib
import hmac
import secrets
import time
import re
import html
import io
import zipfile
import csv
import base64
import ipaddress
from datetime import datetime, timedelta
from typing import Optional, List
from contextlib import contextmanager
from urllib.parse import urlparse

# ---------------------------------------------------------------------------
# Third-party imports
# ---------------------------------------------------------------------------
import jwt
import bcrypt
import httpx
from fastapi import (
    FastAPI,
    HTTPException,
    Depends,
    Request,
    UploadFile,
    File,
    Query,
    Header,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse, HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from pydantic import BaseModel, EmailStr

# ---------------------------------------------------------------------------
# Optional imports — graceful degradation
# ---------------------------------------------------------------------------
try:
    from google.oauth2 import id_token
    from google.auth.transport import requests as google_requests
    HAS_GOOGLE_AUTH = True
except ImportError:
    HAS_GOOGLE_AUTH = False

try:
    from weasyprint import HTML as WeasyHTML
    HAS_WEASYPRINT = True
except ImportError:
    HAS_WEASYPRINT = False

# ---------------------------------------------------------------------------
# App creation & CORS
# ---------------------------------------------------------------------------
app = FastAPI(title="Broad Reach Customs Data Portal")

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "https://www.perplexity.ai,https://sites.pplx.app").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Configuration constants
# ---------------------------------------------------------------------------
JWT_SECRET = os.environ.get("JWT_SECRET", secrets.token_hex(32))
JWT_EXPIRY_HOURS = 24
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "105648453442-gjnirc4fa4tmii07lt1lmd353serh4ng.apps.googleusercontent.com")
DB_PATH = os.environ.get("DATABASE_PATH", "customs.db")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# ---------------------------------------------------------------------------
# Database context manager
# ---------------------------------------------------------------------------
@contextmanager
def get_db():
    """Yield a sqlite3 connection with WAL mode and Row factory.
    Commits on success, rolls back on exception, always closes."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Database initialisation — create tables if they don't exist
# ---------------------------------------------------------------------------
def init_db():
    """Create all required tables."""
    with get_db() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                password_hash TEXT,
                google_id TEXT,
                created_at TEXT NOT NULL,
                last_login_at TEXT,
                login_count INTEGER DEFAULT 0,
                reset_token TEXT,
                reset_token_expires TEXT
            );

            CREATE TABLE IF NOT EXISTS skus (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                sku_code TEXT NOT NULL,
                description TEXT,
                hts_code TEXT,
                hts_valid INTEGER,
                hts_description TEXT,
                country_of_origin TEXT,
                customs_value REAL,
                currency TEXT DEFAULT 'USD',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS cusma_certificates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                cert_number TEXT UNIQUE NOT NULL,
                cert_type TEXT NOT NULL DEFAULT 'blanket',
                status TEXT NOT NULL DEFAULT 'draft',
                certifier_name TEXT,
                certifier_title TEXT,
                certifier_company TEXT,
                certifier_address TEXT,
                certifier_phone TEXT,
                certifier_email TEXT,
                exporter_name TEXT,
                exporter_company TEXT,
                exporter_address TEXT,
                importer_name TEXT,
                importer_company TEXT,
                importer_address TEXT,
                producer_name TEXT,
                producer_company TEXT,
                producer_address TEXT,
                blanket_start TEXT,
                blanket_end TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS cusma_certificate_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                certificate_id INTEGER NOT NULL,
                sku_id INTEGER,
                sku_code TEXT,
                description TEXT,
                hts_code TEXT,
                country_of_origin TEXT,
                customs_value REAL,
                currency TEXT DEFAULT 'USD',
                origin_criterion TEXT,
                FOREIGN KEY (certificate_id) REFERENCES cusma_certificates(id),
                FOREIGN KEY (sku_id) REFERENCES skus(id)
            );

            CREATE TABLE IF NOT EXISTS api_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                key_hash TEXT NOT NULL,
                key_prefix TEXT NOT NULL,
                created_at TEXT NOT NULL,
                last_used_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS webhooks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                url TEXT NOT NULL,
                events TEXT NOT NULL DEFAULT '[]',
                secret TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS teams (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                owner_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (owner_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS team_members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                team_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                role TEXT NOT NULL DEFAULT 'member',
                joined_at TEXT NOT NULL,
                FOREIGN KEY (team_id) REFERENCES teams(id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                entity_type TEXT,
                entity_id INTEGER,
                changes TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS duty_rates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hts_code TEXT NOT NULL,
                rate_type TEXT,
                rate_value REAL,
                country TEXT,
                description TEXT,
                source TEXT,
                cached_at TEXT NOT NULL
            );
        """)


# Run init on import
init_db()


# ===========================================================================================
# Pydantic request / response models
# ===========================================================================================

class RegisterRequest(BaseModel):
    email: EmailStr
    name: str
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class GoogleAuthRequest(BaseModel):
    id_token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class SkuCreate(BaseModel):
    sku_code: str
    description: Optional[str] = None
    hts_code: Optional[str] = None
    country_of_origin: Optional[str] = None
    customs_value: Optional[float] = None
    currency: Optional[str] = "USD"


class SkuUpdate(BaseModel):
    sku_code: Optional[str] = None
    description: Optional[str] = None
    hts_code: Optional[str] = None
    country_of_origin: Optional[str] = None
    customs_value: Optional[float] = None
    currency: Optional[str] = None


class CusmaItemCreate(BaseModel):
    sku_id: Optional[int] = None
    sku_code: Optional[str] = None
    description: Optional[str] = None
    hts_code: Optional[str] = None
    country_of_origin: Optional[str] = None
    customs_value: Optional[float] = None
    currency: Optional[str] = "USD"
    origin_criterion: Optional[str] = None


class CusmaCreate(BaseModel):
    cert_type: Optional[str] = "blanket"
    certifier_name: Optional[str] = None
    certifier_title: Optional[str] = None
    certifier_company: Optional[str] = None
    certifier_address: Optional[str] = None
    certifier_phone: Optional[str] = None
    certifier_email: Optional[str] = None
    exporter_name: Optional[str] = None
    exporter_company: Optional[str] = None
    exporter_address: Optional[str] = None
    importer_name: Optional[str] = None
    importer_company: Optional[str] = None
    importer_address: Optional[str] = None
    producer_name: Optional[str] = None
    producer_company: Optional[str] = None
    producer_address: Optional[str] = None
    blanket_start: Optional[str] = None
    blanket_end: Optional[str] = None
    items: Optional[List[CusmaItemCreate]] = []


class CusmaUpdate(BaseModel):
    cert_type: Optional[str] = None
    status: Optional[str] = None
    certifier_name: Optional[str] = None
    certifier_title: Optional[str] = None
    certifier_company: Optional[str] = None
    certifier_address: Optional[str] = None
    certifier_phone: Optional[str] = None
    certifier_email: Optional[str] = None
    exporter_name: Optional[str] = None
    exporter_company: Optional[str] = None
    exporter_address: Optional[str] = None
    importer_name: Optional[str] = None
    importer_company: Optional[str] = None
    importer_address: Optional[str] = None
    producer_name: Optional[str] = None
    producer_company: Optional[str] = None
    producer_address: Optional[str] = None
    blanket_start: Optional[str] = None
    blanket_end: Optional[str] = None
    items: Optional[List[CusmaItemCreate]] = None


class WebhookCreate(BaseModel):
    url: str
    events: List[str]


class WebhookUpdate(BaseModel):
    url: Optional[str] = None
    events: Optional[List[str]] = None
    active: Optional[bool] = None


class TeamCreate(BaseModel):
    name: str


class TeamInvite(BaseModel):
    email: EmailStr


class TeamMemberUpdate(BaseModel):
    role: str


class HtsRecommendRequest(BaseModel):
    description: str
    sku_code: Optional[str] = None


class BatchLookupRequest(BaseModel):
    sku_codes: List[str]


class AutoGenerateRequest(BaseModel):
    sku_ids: List[int]


# ===========================================================================================
# Authentication dependency
# ===========================================================================================

async def get_current_user(request: Request):
    """Extract and validate JWT from Authorization header or query param."""
    auth_header = request.headers.get("Authorization", "")
    token_param = request.query_params.get("token", "")

    # Prefer Bearer token from header, fall back to query parameter
    if auth_header.startswith("Bearer "):
        token = auth_header.replace("Bearer ", "")
    else:
        token = token_param

    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


# ===========================================================================================
# Rate limiting (in-memory)
# ===========================================================================================
rate_limits: dict = {}  # key -> list of timestamps


def check_rate_limit(key: str, max_requests: int = 120, window: int = 60):
    """Sliding-window rate limiter. Raises HTTP 429 if limit is exceeded."""
    now = time.time()
    if key not in rate_limits:
        rate_limits[key] = []

    # Prune expired timestamps
    rate_limits[key] = [t for t in rate_limits[key] if t > now - window]

    if len(rate_limits[key]) >= max_requests:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Max {max_requests} requests per {window}s.",
        )
    rate_limits[key].append(now)


# ===========================================================================================
# Scope filter — team-based data isolation
# ===========================================================================================

def get_scope_filter(user_id: int, db) -> List[int]:
    """Return list of user IDs whose data this user can see (self + team members)."""
    team_ids = [
        r["team_id"]
        for r in db.execute(
            "SELECT team_id FROM team_members WHERE user_id = ?", (user_id,)
        ).fetchall()
    ]
    if not team_ids:
        return [user_id]

    placeholders = ",".join("?" * len(team_ids))
    members = db.execute(
        f"SELECT DISTINCT user_id FROM team_members WHERE team_id IN ({placeholders})",
        team_ids,
    ).fetchall()
    return list(set([user_id] + [r["user_id"] for r in members]))


# ===========================================================================================
# Webhook firing — HMAC-SHA256 signed payloads
# ===========================================================================================

def fire_webhooks(user_id: int, event: str, payload: dict, db):
    """Fire all active webhooks matching the event for users in the caller's scope."""
    scope = get_scope_filter(user_id, db)
    placeholders = ",".join("?" * len(scope))
    hooks = db.execute(
        f"SELECT * FROM webhooks WHERE user_id IN ({placeholders}) AND active = 1",
        scope,
    ).fetchall()

    for hook in hooks:
        events = json.loads(hook["events"])
        if event in events:
            body = json.dumps(
                {
                    "event": event,
                    "data": payload,
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )
            signature = hmac.new(
                hook["secret"].encode(), body.encode(), hashlib.sha256
            ).hexdigest()
            try:
                httpx.post(
                    hook["url"],
                    content=body,
                    headers={
                        "Content-Type": "application/json",
                        "X-Webhook-Signature": signature,
                    },
                    timeout=5.0,
                )
            except Exception:
                pass  # Fire-and-forget; don't let webhook failures break main flow


# ===========================================================================================
# Audit logging
# ===========================================================================================

def log_audit(user_id: int, action: str, entity_type: str, entity_id, changes: dict, db):
    """Insert an audit log entry."""
    db.execute(
        "INSERT INTO audit_log (user_id, action, entity_type, entity_id, changes, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            user_id,
            action,
            entity_type,
            entity_id,
            json.dumps(changes),
            datetime.utcnow().isoformat(),
        ),
    )


# ===========================================================================================
# SSRF protection for webhook URLs
# ===========================================================================================

def validate_webhook_url(url: str):
    """Ensure webhook URL uses HTTPS and doesn't point to private/loopback addresses."""
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise HTTPException(status_code=422, detail="Webhook URL must use HTTPS")
    hostname = parsed.hostname
    if not hostname:
        raise HTTPException(status_code=422, detail="Invalid webhook URL")
    try:
        ip = ipaddress.ip_address(hostname)
        if ip.is_private or ip.is_loopback or ip.is_link_local:
            raise HTTPException(
                status_code=422,
                detail="Webhook URL cannot point to private/loopback addresses",
            )
    except ValueError:
        pass  # It's a hostname, not a raw IP — acceptable


# ===========================================================================================
# Country validation — common trade-partner ISO 3166-1 alpha-2 codes
# ===========================================================================================

VALID_COUNTRIES = {
    "US", "CA", "MX", "CN", "JP", "KR", "TW", "VN", "IN", "DE", "FR", "GB",
    "IT", "ES", "NL", "BE", "AU", "NZ", "BR", "AR", "CL", "CO", "PE", "TH",
    "MY", "SG", "PH", "ID", "BD", "PK", "TR", "PL", "CZ", "HU", "RO", "BG",
    "HR", "SE", "NO", "DK", "FI", "IE", "PT", "AT", "CH", "IL", "AE", "SA",
    "ZA", "EG", "NG", "KE", "GH", "MA", "TN",
}


# ===========================================================================================
# HTS validation cache (in-memory, keyed by code/query with TTL)
# ===========================================================================================
hts_cache: dict = {}  # key -> (timestamp, data)
HTS_CACHE_TTL = 3600  # 1 hour


def get_hts_cached(key: str):
    """Return cached HTS result if still fresh, else None."""
    if key in hts_cache:
        cached_at, data = hts_cache[key]
        if time.time() - cached_at < HTS_CACHE_TTL:
            return data
    return None


def set_hts_cached(key: str, data):
    """Store an HTS result in cache."""
    hts_cache[key] = (time.time(), data)


# ===========================================================================================
# JWT helper
# ===========================================================================================

def create_jwt(user_id: int, email: str, name: str) -> str:
    """Generate a signed JWT with 24-hour expiry."""
    payload = {
        "user_id": user_id,
        "email": email,
        "name": name,
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRY_HOURS),
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


# ===========================================================================================
# HTS code validation against USITC API
# ===========================================================================================

def validate_hts_code(code: str) -> dict:
    """Validate an HTS code against the USITC API.
    Returns { valid: bool, description: str | None, official_code: str | None }."""
    if not code:
        return {"valid": False, "description": None, "official_code": None}

    cache_key = f"validate:{code}"
    cached = get_hts_cached(cache_key)
    if cached is not None:
        return cached

    try:
        # Query the USITC search API with the exact code
        resp = httpx.get(
            "https://hts.usitc.gov/api/search",
            params={"query": code},
            timeout=10.0,
        )
        if resp.status_code == 200:
            data = resp.json()
            results = data if isinstance(data, list) else data.get("results", [])
            # Look for exact or close match
            clean_code = re.sub(r"[.\-\s]", "", code)
            for item in results:
                item_code = re.sub(r"[.\-\s]", "", str(item.get("htsno", item.get("hts_code", ""))))
                if item_code == clean_code or item_code.startswith(clean_code):
                    result = {
                        "valid": True,
                        "description": item.get("description", item.get("desc", "")),
                        "official_code": item.get("htsno", item.get("hts_code", code)),
                    }
                    set_hts_cached(cache_key, result)
                    return result
        # Not found
        result = {"valid": False, "description": None, "official_code": None}
        set_hts_cached(cache_key, result)
        return result
    except Exception:
        # On network/API error, return unknown (don't mark as invalid)
        return {"valid": None, "description": None, "official_code": None}


# ===========================================================================================
# CUSMA certificate helpers
# ===========================================================================================

def generate_cert_number(db) -> str:
    """Generate a unique certificate number in the format CUSMA-YYYY-NNNN."""
    year = datetime.utcnow().strftime("%Y")
    row = db.execute(
        "SELECT COUNT(*) as cnt FROM cusma_certificates WHERE cert_number LIKE ?",
        (f"CUSMA-{year}-%",),
    ).fetchone()
    seq = (row["cnt"] if row else 0) + 1
    return f"CUSMA-{year}-{seq:04d}"


def _cert_to_dict(row, items) -> dict:
    """Convert a certificate Row + items list to a serialisable dict.
    Auto-sets status to 'expired' if blanket_end is in the past."""
    cert = dict(row)
    today = datetime.utcnow().strftime("%Y-%m-%d")
    if cert.get("blanket_end") and cert["blanket_end"] < today and cert["status"] != "expired":
        cert["status"] = "expired"
    cert["items"] = [dict(i) for i in items]
    return cert


# ===========================================================================================
# AUTH ENDPOINTS
# ===========================================================================================

@app.post("/api/auth/register")
async def register(req: RegisterRequest):
    """Register a new user with email and password."""
    # Validate password length
    if len(req.password) < 8:
        raise HTTPException(status_code=422, detail="Password must be at least 8 characters")

    # Validate email format (Pydantic EmailStr already does basic validation)
    email = req.email.lower().strip()
    name = req.name.strip()

    # Hash password
    password_hash = bcrypt.hashpw(req.password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    now = datetime.utcnow().isoformat()

    with get_db() as db:
        # Check for existing user
        existing = db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if existing:
            raise HTTPException(status_code=409, detail="Email already registered")

        cursor = db.execute(
            "INSERT INTO users (email, name, password_hash, created_at, last_login_at, login_count) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (email, name, password_hash, now, now, 1),
        )
        user_id = cursor.lastrowid
        token = create_jwt(user_id, email, name)

    return {
        "token": token,
        "user": {"id": user_id, "email": email, "name": name},
    }


@app.post("/api/auth/login")
async def login(req: LoginRequest):
    """Authenticate with email and password."""
    email = req.email.lower().strip()

    with get_db() as db:
        user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if not user:
            raise HTTPException(status_code=401, detail="Invalid email or password")

        # Verify password
        if not user["password_hash"]:
            raise HTTPException(
                status_code=401,
                detail="This account uses Google sign-in. Please use Google to log in.",
            )

        if not bcrypt.checkpw(req.password.encode("utf-8"), user["password_hash"].encode("utf-8")):
            raise HTTPException(status_code=401, detail="Invalid email or password")

        # Update login metadata
        now = datetime.utcnow().isoformat()
        db.execute(
            "UPDATE users SET last_login_at = ?, login_count = login_count + 1 WHERE id = ?",
            (now, user["id"]),
        )

        token = create_jwt(user["id"], user["email"], user["name"])

    return {
        "token": token,
        "user": {"id": user["id"], "email": user["email"], "name": user["name"]},
    }


@app.post("/api/auth/google")
async def google_auth(req: GoogleAuthRequest):
    """Authenticate or register via Google OAuth 2.0 ID token."""
    token_str = req.id_token

    if HAS_GOOGLE_AUTH:
        # Verify with official Google library
        try:
            idinfo = id_token.verify_oauth2_token(
                token_str, google_requests.Request(), GOOGLE_CLIENT_ID
            )
        except Exception as e:
            raise HTTPException(status_code=401, detail=f"Invalid Google token: {str(e)}")
    else:
        # Manual JWT decode (base64 payload extraction, no signature verification)
        try:
            parts = token_str.split(".")
            if len(parts) != 3:
                raise HTTPException(status_code=401, detail="Invalid Google token format")
            # Decode payload (add padding)
            payload_b64 = parts[1]
            padding = 4 - len(payload_b64) % 4
            if padding != 4:
                payload_b64 += "=" * padding
            idinfo = json.loads(base64.urlsafe_b64decode(payload_b64))
        except Exception as e:
            raise HTTPException(status_code=401, detail=f"Invalid Google token: {str(e)}")

    email = idinfo.get("email", "").lower().strip()
    name = idinfo.get("name", email.split("@")[0])
    google_id = idinfo.get("sub", "")

    if not email:
        raise HTTPException(status_code=401, detail="No email in Google token")

    now = datetime.utcnow().isoformat()

    with get_db() as db:
        # Try to find existing user by google_id or email
        user = db.execute(
            "SELECT * FROM users WHERE google_id = ? OR email = ?", (google_id, email)
        ).fetchone()

        if user:
            # Update existing user
            db.execute(
                "UPDATE users SET google_id = ?, last_login_at = ?, login_count = login_count + 1 WHERE id = ?",
                (google_id, now, user["id"]),
            )
            user_id = user["id"]
            user_name = user["name"]
        else:
            # Create new user
            cursor = db.execute(
                "INSERT INTO users (email, name, google_id, created_at, last_login_at, login_count) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (email, name, google_id, now, now, 1),
            )
            user_id = cursor.lastrowid
            user_name = name

        token = create_jwt(user_id, email, user_name)

    return {
        "token": token,
        "user": {"id": user_id, "email": email, "name": user_name},
    }


@app.post("/api/auth/forgot-password")
async def forgot_password(req: ForgotPasswordRequest):
    """Initiate a password reset. Always returns success to prevent email enumeration."""
    email = req.email.lower().strip()
    reset_token = secrets.token_urlsafe(32)
    expires = (datetime.utcnow() + timedelta(hours=1)).isoformat()

    with get_db() as db:
        user = db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if user:
            db.execute(
                "UPDATE users SET reset_token = ?, reset_token_expires = ? WHERE id = ?",
                (reset_token, expires, user["id"]),
            )
            # In production, send email with reset link here
            # e.g. send_email(email, f"Reset link: .../reset?token={reset_token}")

    # Always return the same message to avoid leaking account existence
    return {"message": "If an account exists, a reset link has been sent"}


@app.post("/api/auth/reset-password")
async def reset_password(req: ResetPasswordRequest):
    """Reset password using a valid reset token."""
    if len(req.new_password) < 8:
        raise HTTPException(status_code=422, detail="Password must be at least 8 characters")

    now = datetime.utcnow().isoformat()

    with get_db() as db:
        user = db.execute(
            "SELECT * FROM users WHERE reset_token = ? AND reset_token_expires > ?",
            (req.token, now),
        ).fetchone()

        if not user:
            raise HTTPException(status_code=400, detail="Invalid or expired reset token")

        password_hash = bcrypt.hashpw(
            req.new_password.encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")

        db.execute(
            "UPDATE users SET password_hash = ?, reset_token = NULL, reset_token_expires = NULL WHERE id = ?",
            (password_hash, user["id"]),
        )

    return {"message": "Password reset successful"}


@app.post("/api/auth/change-password")
async def change_password(
    req: ChangePasswordRequest, current_user: dict = Depends(get_current_user)
):
    """Change password for the authenticated user."""
    if len(req.new_password) < 8:
        raise HTTPException(status_code=422, detail="Password must be at least 8 characters")

    user_id = current_user["user_id"]

    with get_db() as db:
        user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        if not user["password_hash"]:
            raise HTTPException(
                status_code=400,
                detail="Cannot change password for Google-only accounts",
            )

        if not bcrypt.checkpw(
            req.current_password.encode("utf-8"),
            user["password_hash"].encode("utf-8"),
        ):
            raise HTTPException(status_code=401, detail="Current password is incorrect")

        new_hash = bcrypt.hashpw(
            req.new_password.encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")

        db.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?", (new_hash, user_id)
        )

    return {"message": "Password changed"}


# ===========================================================================================
# API KEY MANAGEMENT
# ===========================================================================================

@app.post("/api/api-keys")
async def create_api_key(current_user: dict = Depends(get_current_user)):
    """Generate a new API key for the authenticated user."""
    user_id = current_user["user_id"]
    raw_key = secrets.token_hex(32)
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    key_prefix = raw_key[:8]
    now = datetime.utcnow().isoformat()

    with get_db() as db:
        cursor = db.execute(
            "INSERT INTO api_keys (user_id, key_hash, key_prefix, created_at) VALUES (?, ?, ?, ?)",
            (user_id, key_hash, key_prefix, now),
        )
        key_id = cursor.lastrowid

    return {
        "id": key_id,
        "key": raw_key,  # Only shown once at creation
        "prefix": key_prefix,
        "created_at": now,
    }


@app.get("/api/api-keys")
async def list_api_keys(current_user: dict = Depends(get_current_user)):
    """List all API keys for the authenticated user (prefix only, no full key)."""
    user_id = current_user["user_id"]
    with get_db() as db:
        rows = db.execute(
            "SELECT id, key_prefix, created_at, last_used_at FROM api_keys WHERE user_id = ?",
            (user_id,),
        ).fetchall()
    return [dict(r) for r in rows]


@app.delete("/api/api-keys/{key_id}")
async def delete_api_key(key_id: int, current_user: dict = Depends(get_current_user)):
    """Delete an API key belonging to the authenticated user."""
    user_id = current_user["user_id"]
    with get_db() as db:
        row = db.execute(
            "SELECT id FROM api_keys WHERE id = ? AND user_id = ?", (key_id, user_id)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="API key not found")
        db.execute("DELETE FROM api_keys WHERE id = ?", (key_id,))
    return {"message": "API key deleted"}


# ===========================================================================================
# Helper: authenticate via API key (for external lookup endpoints)
# ===========================================================================================

def authenticate_api_key(api_key: str, db) -> dict:
    """Validate an API key and return the associated user info."""
    if not api_key:
        raise HTTPException(status_code=401, detail="API key required")

    key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    row = db.execute(
        "SELECT ak.*, u.email, u.name FROM api_keys ak "
        "JOIN users u ON ak.user_id = u.id WHERE ak.key_hash = ?",
        (key_hash,),
    ).fetchone()

    if not row:
        raise HTTPException(status_code=401, detail="Invalid API key")

    # Update last_used_at
    db.execute(
        "UPDATE api_keys SET last_used_at = ? WHERE id = ?",
        (datetime.utcnow().isoformat(), row["id"]),
    )

    return {"user_id": row["user_id"], "email": row["email"], "name": row["name"]}


# ===========================================================================================
# SKU CRUD ENDPOINTS
# ===========================================================================================

@app.get("/api/skus")
async def list_skus(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    search: Optional[str] = Query(None),
    sort: Optional[str] = Query("sku_code"),
    order: Optional[str] = Query("asc"),
    current_user: dict = Depends(get_current_user),
):
    """List SKUs with pagination, search, and sort.  Respects team data isolation."""
    user_id = current_user["user_id"]

    # Whitelist allowed sort columns to prevent SQL injection
    allowed_sort = {"sku_code", "description", "hts_code", "country_of_origin", "customs_value", "created_at", "updated_at"}
    if sort not in allowed_sort:
        sort = "sku_code"
    if order not in ("asc", "desc"):
        order = "asc"

    with get_db() as db:
        scope = get_scope_filter(user_id, db)
        placeholders = ",".join("?" * len(scope))

        # Base query
        base_where = f"user_id IN ({placeholders})"
        params: list = list(scope)

        # Optional search filter
        if search:
            search_term = f"%{search}%"
            base_where += " AND (sku_code LIKE ? OR description LIKE ? OR hts_code LIKE ?)"
            params.extend([search_term, search_term, search_term])

        # Count total
        count_row = db.execute(
            f"SELECT COUNT(*) as cnt FROM skus WHERE {base_where}", params
        ).fetchone()
        total = count_row["cnt"]

        # Paginated query
        offset = (page - 1) * page_size
        rows = db.execute(
            f"SELECT * FROM skus WHERE {base_where} ORDER BY {sort} {order} LIMIT ? OFFSET ?",
            params + [page_size, offset],
        ).fetchall()

    pages = max(1, (total + page_size - 1) // page_size)
    return {
        "items": [dict(r) for r in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": pages,
    }


@app.post("/api/skus")
async def create_sku(
    sku: SkuCreate, current_user: dict = Depends(get_current_user)
):
    """Create a new SKU. Auto-validates HTS code if provided."""
    user_id = current_user["user_id"]
    now = datetime.utcnow().isoformat()

    # Validate country of origin
    if sku.country_of_origin and sku.country_of_origin.upper() not in VALID_COUNTRIES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid country code: {sku.country_of_origin}. Use ISO 3166-1 alpha-2.",
        )

    # Auto-validate HTS code
    hts_valid = None
    hts_description = None
    if sku.hts_code:
        hts_result = validate_hts_code(sku.hts_code)
        hts_valid = 1 if hts_result["valid"] else (0 if hts_result["valid"] is False else None)
        hts_description = hts_result.get("description")

    with get_db() as db:
        cursor = db.execute(
            "INSERT INTO skus (user_id, sku_code, description, hts_code, hts_valid, hts_description, "
            "country_of_origin, customs_value, currency, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                user_id,
                sku.sku_code,
                sku.description,
                sku.hts_code,
                hts_valid,
                hts_description,
                sku.country_of_origin.upper() if sku.country_of_origin else None,
                sku.customs_value,
                sku.currency or "USD",
                now,
                now,
            ),
        )
        sku_id = cursor.lastrowid
        created = db.execute("SELECT * FROM skus WHERE id = ?", (sku_id,)).fetchone()

        # Audit log
        log_audit(user_id, "sku.created", "sku", sku_id, {"sku_code": sku.sku_code}, db)

        # Fire webhooks
        fire_webhooks(user_id, "sku.created", dict(created), db)

    return dict(created)


@app.put("/api/skus/{sku_id}")
async def update_sku(
    sku_id: int, sku: SkuUpdate, current_user: dict = Depends(get_current_user)
):
    """Update an existing SKU. Tracks changes for audit logging."""
    user_id = current_user["user_id"]
    now = datetime.utcnow().isoformat()

    with get_db() as db:
        scope = get_scope_filter(user_id, db)
        placeholders = ",".join("?" * len(scope))
        existing = db.execute(
            f"SELECT * FROM skus WHERE id = ? AND user_id IN ({placeholders})",
            [sku_id] + scope,
        ).fetchone()

        if not existing:
            raise HTTPException(status_code=404, detail="SKU not found")

        # Build changes dict — only include fields that actually changed
        changes = {}
        update_fields = []
        update_values = []

        update_data = sku.model_dump(exclude_unset=True)

        for field, new_value in update_data.items():
            old_value = existing[field]
            if field == "country_of_origin" and new_value:
                new_value = new_value.upper()
                if new_value not in VALID_COUNTRIES:
                    raise HTTPException(
                        status_code=422,
                        detail=f"Invalid country code: {new_value}. Use ISO 3166-1 alpha-2.",
                    )
            if new_value != old_value:
                changes[field] = {"old": old_value, "new": new_value}
                update_fields.append(f"{field} = ?")
                update_values.append(new_value)

        # Re-validate HTS if changed
        hts_valid = existing["hts_valid"]
        hts_description = existing["hts_description"]
        if "hts_code" in changes:
            hts_result = validate_hts_code(update_data["hts_code"])
            hts_valid = 1 if hts_result["valid"] else (0 if hts_result["valid"] is False else None)
            hts_description = hts_result.get("description")
            update_fields.extend(["hts_valid = ?", "hts_description = ?"])
            update_values.extend([hts_valid, hts_description])

        if update_fields:
            update_fields.append("updated_at = ?")
            update_values.append(now)
            update_values.append(sku_id)
            db.execute(
                f"UPDATE skus SET {', '.join(update_fields)} WHERE id = ?",
                update_values,
            )

        updated = db.execute("SELECT * FROM skus WHERE id = ?", (sku_id,)).fetchone()

        # Audit log
        if changes:
            log_audit(user_id, "sku.updated", "sku", sku_id, changes, db)

        # Fire webhooks
        fire_webhooks(user_id, "sku.updated", dict(updated), db)

    return dict(updated)


@app.delete("/api/skus/{sku_id}")
async def delete_sku(sku_id: int, current_user: dict = Depends(get_current_user)):
    """Delete a SKU. Verifies ownership via scope filter."""
    user_id = current_user["user_id"]

    with get_db() as db:
        scope = get_scope_filter(user_id, db)
        placeholders = ",".join("?" * len(scope))
        existing = db.execute(
            f"SELECT * FROM skus WHERE id = ? AND user_id IN ({placeholders})",
            [sku_id] + scope,
        ).fetchone()

        if not existing:
            raise HTTPException(status_code=404, detail="SKU not found")

        db.execute("DELETE FROM skus WHERE id = ?", (sku_id,))

        # Audit log
        log_audit(
            user_id, "sku.deleted", "sku", sku_id,
            {"sku_code": existing["sku_code"]}, db,
        )

        # Fire webhooks
        fire_webhooks(user_id, "sku.deleted", {"id": sku_id, "sku_code": existing["sku_code"]}, db)

    return {"message": "Deleted"}


@app.post("/api/skus/import")
async def import_skus(
    file: UploadFile = File(...), current_user: dict = Depends(get_current_user)
):
    """Bulk-import SKUs from a CSV file.
    Expected columns: sku_code, description, hts_code, country_of_origin, customs_value, currency."""
    user_id = current_user["user_id"]
    now = datetime.utcnow().isoformat()

    # Read and parse CSV
    content = await file.read()
    try:
        text = content.decode("utf-8-sig")  # Handle BOM
    except UnicodeDecodeError:
        text = content.decode("latin-1")

    reader = csv.DictReader(io.StringIO(text))
    imported = 0
    errors = []

    with get_db() as db:
        for row_num, row in enumerate(reader, start=2):  # Row 1 is headers
            try:
                sku_code = row.get("sku_code", "").strip()
                if not sku_code:
                    errors.append({"row": row_num, "error": "Missing sku_code"})
                    continue

                description = row.get("description", "").strip()
                hts_code = row.get("hts_code", "").strip() or None
                country = row.get("country_of_origin", "").strip().upper() or None
                customs_value_str = row.get("customs_value", "").strip()
                currency = row.get("currency", "USD").strip().upper() or "USD"

                # Validate country
                if country and country not in VALID_COUNTRIES:
                    errors.append({"row": row_num, "error": f"Invalid country: {country}"})
                    continue

                # Parse customs value
                customs_value = None
                if customs_value_str:
                    try:
                        customs_value = float(customs_value_str)
                    except ValueError:
                        errors.append({"row": row_num, "error": f"Invalid customs_value: {customs_value_str}"})
                        continue

                # Auto-validate HTS
                hts_valid = None
                hts_description = None
                if hts_code:
                    hts_result = validate_hts_code(hts_code)
                    hts_valid = 1 if hts_result["valid"] else (0 if hts_result["valid"] is False else None)
                    hts_description = hts_result.get("description")

                db.execute(
                    "INSERT INTO skus (user_id, sku_code, description, hts_code, hts_valid, hts_description, "
                    "country_of_origin, customs_value, currency, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (user_id, sku_code, description, hts_code, hts_valid, hts_description,
                     country, customs_value, currency, now, now),
                )
                imported += 1

            except Exception as e:
                errors.append({"row": row_num, "error": str(e)})

    return {"imported": imported, "errors": errors}


@app.post("/api/skus/validate-all")
async def validate_all_skus(current_user: dict = Depends(get_current_user)):
    """Validate all SKUs for the user where hts_valid is null or false."""
    user_id = current_user["user_id"]
    validated = 0
    valid_count = 0
    invalid_count = 0

    with get_db() as db:
        scope = get_scope_filter(user_id, db)
        placeholders = ",".join("?" * len(scope))
        rows = db.execute(
            f"SELECT * FROM skus WHERE user_id IN ({placeholders}) "
            "AND hts_code IS NOT NULL AND hts_code != '' "
            "AND (hts_valid IS NULL OR hts_valid = 0)",
            scope,
        ).fetchall()

        for row in rows:
            hts_result = validate_hts_code(row["hts_code"])
            hts_valid = 1 if hts_result["valid"] else (0 if hts_result["valid"] is False else None)
            hts_description = hts_result.get("description")

            db.execute(
                "UPDATE skus SET hts_valid = ?, hts_description = ?, updated_at = ? WHERE id = ?",
                (hts_valid, hts_description, datetime.utcnow().isoformat(), row["id"]),
            )
            validated += 1
            if hts_valid == 1:
                valid_count += 1
            elif hts_valid == 0:
                invalid_count += 1

    return {"validated": validated, "valid": valid_count, "invalid": invalid_count}


@app.get("/api/skus/export")
async def export_skus(current_user: dict = Depends(get_current_user)):
    """Export all user SKUs as a CSV download."""
    user_id = current_user["user_id"]

    with get_db() as db:
        scope = get_scope_filter(user_id, db)
        placeholders = ",".join("?" * len(scope))
        rows = db.execute(
            f"SELECT * FROM skus WHERE user_id IN ({placeholders}) ORDER BY sku_code",
            scope,
        ).fetchall()

    # Build CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "sku_code", "description", "hts_code", "hts_valid",
                      "hts_description", "country_of_origin", "customs_value", "currency",
                      "created_at", "updated_at"])
    for r in rows:
        writer.writerow([
            r["id"], r["sku_code"], r["description"], r["hts_code"], r["hts_valid"],
            r["hts_description"], r["country_of_origin"], r["customs_value"], r["currency"],
            r["created_at"], r["updated_at"],
        ])

    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=skus_export.csv"},
    )


# ===========================================================================================
# CUSMA CERTIFICATE ENDPOINTS
# ===========================================================================================

@app.get("/api/cusma")
async def list_certificates(current_user: dict = Depends(get_current_user)):
    """List all CUSMA certificates for the user with item counts and summary stats."""
    user_id = current_user["user_id"]

    with get_db() as db:
        scope = get_scope_filter(user_id, db)
        placeholders = ",".join("?" * len(scope))
        rows = db.execute(
            f"SELECT c.*, COUNT(ci.id) as item_count "
            f"FROM cusma_certificates c "
            f"LEFT JOIN cusma_certificate_items ci ON ci.certificate_id = c.id "
            f"WHERE c.user_id IN ({placeholders}) "
            f"GROUP BY c.id ORDER BY c.created_at DESC",
            scope,
        ).fetchall()

    today = datetime.utcnow().strftime("%Y-%m-%d")
    certs = []
    total = 0
    active = 0
    draft = 0
    expired = 0

    for r in rows:
        cert = dict(r)
        # Auto-expire check
        if cert.get("blanket_end") and cert["blanket_end"] < today and cert["status"] != "expired":
            cert["status"] = "expired"
        certs.append(cert)
        total += 1
        if cert["status"] == "active":
            active += 1
        elif cert["status"] == "draft":
            draft += 1
        elif cert["status"] == "expired":
            expired += 1

    return {
        "items": certs,
        "total": total,
        "active": active,
        "draft": draft,
        "expired": expired,
    }


@app.post("/api/cusma")
async def create_certificate(
    req: CusmaCreate, current_user: dict = Depends(get_current_user)
):
    """Create a new CUSMA certificate with optional line items."""
    user_id = current_user["user_id"]
    now = datetime.utcnow().isoformat()

    # Validate blanket dates
    if req.cert_type == "blanket":
        if req.blanket_start and req.blanket_end:
            if req.blanket_end <= req.blanket_start:
                raise HTTPException(status_code=422, detail="Blanket end date must be after start date")

    with get_db() as db:
        cert_number = generate_cert_number(db)

        cursor = db.execute(
            "INSERT INTO cusma_certificates "
            "(user_id, cert_number, cert_type, status, "
            "certifier_name, certifier_title, certifier_company, certifier_address, certifier_phone, certifier_email, "
            "exporter_name, exporter_company, exporter_address, "
            "importer_name, importer_company, importer_address, "
            "producer_name, producer_company, producer_address, "
            "blanket_start, blanket_end, created_at, updated_at) "
            "VALUES (?, ?, ?, 'draft', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                user_id, cert_number, req.cert_type or "blanket",
                req.certifier_name, req.certifier_title, req.certifier_company,
                req.certifier_address, req.certifier_phone, req.certifier_email,
                req.exporter_name, req.exporter_company, req.exporter_address,
                req.importer_name, req.importer_company, req.importer_address,
                req.producer_name, req.producer_company, req.producer_address,
                req.blanket_start, req.blanket_end, now, now,
            ),
        )
        cert_id = cursor.lastrowid

        # Insert items
        if req.items:
            for item in req.items:
                # If sku_id provided, look up the SKU for auto-fill
                if item.sku_id:
                    sku_row = db.execute("SELECT * FROM skus WHERE id = ?", (item.sku_id,)).fetchone()
                    if sku_row:
                        db.execute(
                            "INSERT INTO cusma_certificate_items "
                            "(certificate_id, sku_id, sku_code, description, hts_code, "
                            "country_of_origin, customs_value, currency, origin_criterion) "
                            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                            (
                                cert_id, item.sku_id,
                                item.sku_code or sku_row["sku_code"],
                                item.description or sku_row["description"],
                                item.hts_code or sku_row["hts_code"],
                                item.country_of_origin or sku_row["country_of_origin"],
                                item.customs_value if item.customs_value is not None else sku_row["customs_value"],
                                item.currency or sku_row["currency"],
                                item.origin_criterion,
                            ),
                        )
                    else:
                        raise HTTPException(status_code=404, detail=f"SKU with id {item.sku_id} not found")
                else:
                    # Manual item entry
                    db.execute(
                        "INSERT INTO cusma_certificate_items "
                        "(certificate_id, sku_id, sku_code, description, hts_code, "
                        "country_of_origin, customs_value, currency, origin_criterion) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            cert_id, None,
                            item.sku_code, item.description, item.hts_code,
                            item.country_of_origin, item.customs_value,
                            item.currency or "USD", item.origin_criterion,
                        ),
                    )

        # Fetch the created certificate with items
        cert = db.execute("SELECT * FROM cusma_certificates WHERE id = ?", (cert_id,)).fetchone()
        items = db.execute(
            "SELECT * FROM cusma_certificate_items WHERE certificate_id = ?", (cert_id,)
        ).fetchall()

        result = _cert_to_dict(cert, items)

        # Audit log
        log_audit(user_id, "cusma.created", "cusma", cert_id, {"cert_number": cert_number}, db)

        # Fire webhooks
        fire_webhooks(user_id, "cusma.created", result, db)

    return result


@app.get("/api/cusma/status")
async def certificate_status(current_user: dict = Depends(get_current_user)):
    """Return aggregate certificate status counts."""
    user_id = current_user["user_id"]
    today = datetime.utcnow().strftime("%Y-%m-%d")

    with get_db() as db:
        scope = get_scope_filter(user_id, db)
        placeholders = ",".join("?" * len(scope))
        rows = db.execute(
            f"SELECT * FROM cusma_certificates WHERE user_id IN ({placeholders})",
            scope,
        ).fetchall()

    total = 0
    active = 0
    draft = 0
    expired = 0

    for r in rows:
        total += 1
        status = r["status"]
        # Auto-expire
        if r["blanket_end"] and r["blanket_end"] < today and status != "expired":
            status = "expired"
        if status == "active":
            active += 1
        elif status == "draft":
            draft += 1
        elif status == "expired":
            expired += 1

    return {"total": total, "active": active, "draft": draft, "expired": expired}


@app.get("/api/cusma/expiring")
async def expiring_certificates(current_user: dict = Depends(get_current_user)):
    """Return certificates expiring within the next 30 days."""
    user_id = current_user["user_id"]
    today = datetime.utcnow().strftime("%Y-%m-%d")
    thirty_days = (datetime.utcnow() + timedelta(days=30)).strftime("%Y-%m-%d")

    with get_db() as db:
        scope = get_scope_filter(user_id, db)
        placeholders = ",".join("?" * len(scope))
        rows = db.execute(
            f"SELECT * FROM cusma_certificates "
            f"WHERE user_id IN ({placeholders}) "
            f"AND blanket_end >= ? AND blanket_end <= ? "
            f"AND status != 'expired' "
            f"ORDER BY blanket_end ASC",
            scope + [today, thirty_days],
        ).fetchall()

    return [dict(r) for r in rows]


@app.get("/api/cusma/{cert_id}")
async def get_certificate(cert_id: int, current_user: dict = Depends(get_current_user)):
    """Get a single certificate with all its items."""
    user_id = current_user["user_id"]

    with get_db() as db:
        scope = get_scope_filter(user_id, db)
        placeholders = ",".join("?" * len(scope))
        cert = db.execute(
            f"SELECT * FROM cusma_certificates WHERE id = ? AND user_id IN ({placeholders})",
            [cert_id] + scope,
        ).fetchone()

        if not cert:
            raise HTTPException(status_code=404, detail="Certificate not found")

        items = db.execute(
            "SELECT * FROM cusma_certificate_items WHERE certificate_id = ?", (cert_id,)
        ).fetchall()

    return _cert_to_dict(cert, items)


@app.put("/api/cusma/{cert_id}")
async def update_certificate(
    cert_id: int, req: CusmaUpdate, current_user: dict = Depends(get_current_user)
):
    """Update certificate fields and/or status."""
    user_id = current_user["user_id"]
    now = datetime.utcnow().isoformat()

    with get_db() as db:
        scope = get_scope_filter(user_id, db)
        placeholders_scope = ",".join("?" * len(scope))
        existing = db.execute(
            f"SELECT * FROM cusma_certificates WHERE id = ? AND user_id IN ({placeholders_scope})",
            [cert_id] + scope,
        ).fetchone()

        if not existing:
            raise HTTPException(status_code=404, detail="Certificate not found")

        # Build update
        update_data = req.model_dump(exclude_unset=True)
        # Remove items from update_data — handled separately
        items_data = update_data.pop("items", None)

        changes = {}
        update_fields = []
        update_values = []

        for field, new_value in update_data.items():
            old_value = existing[field]
            if new_value != old_value:
                changes[field] = {"old": old_value, "new": new_value}
                update_fields.append(f"{field} = ?")
                update_values.append(new_value)

        if update_fields:
            update_fields.append("updated_at = ?")
            update_values.append(now)
            update_values.append(cert_id)
            db.execute(
                f"UPDATE cusma_certificates SET {', '.join(update_fields)} WHERE id = ?",
                update_values,
            )

        # If items provided, replace all items
        if items_data is not None:
            db.execute("DELETE FROM cusma_certificate_items WHERE certificate_id = ?", (cert_id,))
            for item in items_data:
                item_dict = item.model_dump() if hasattr(item, 'model_dump') else item
                if item_dict.get("sku_id"):
                    sku_row = db.execute("SELECT * FROM skus WHERE id = ?", (item_dict["sku_id"],)).fetchone()
                    if sku_row:
                        db.execute(
                            "INSERT INTO cusma_certificate_items "
                            "(certificate_id, sku_id, sku_code, description, hts_code, "
                            "country_of_origin, customs_value, currency, origin_criterion) "
                            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                            (
                                cert_id, item_dict["sku_id"],
                                item_dict.get("sku_code") or sku_row["sku_code"],
                                item_dict.get("description") or sku_row["description"],
                                item_dict.get("hts_code") or sku_row["hts_code"],
                                item_dict.get("country_of_origin") or sku_row["country_of_origin"],
                                item_dict.get("customs_value") if item_dict.get("customs_value") is not None else sku_row["customs_value"],
                                item_dict.get("currency") or sku_row["currency"],
                                item_dict.get("origin_criterion"),
                            ),
                        )
                else:
                    db.execute(
                        "INSERT INTO cusma_certificate_items "
                        "(certificate_id, sku_id, sku_code, description, hts_code, "
                        "country_of_origin, customs_value, currency, origin_criterion) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            cert_id, None,
                            item_dict.get("sku_code"), item_dict.get("description"),
                            item_dict.get("hts_code"), item_dict.get("country_of_origin"),
                            item_dict.get("customs_value"), item_dict.get("currency", "USD"),
                            item_dict.get("origin_criterion"),
                        ),
                    )

        # Fetch updated
        cert = db.execute("SELECT * FROM cusma_certificates WHERE id = ?", (cert_id,)).fetchone()
        items = db.execute(
            "SELECT * FROM cusma_certificate_items WHERE certificate_id = ?", (cert_id,)
        ).fetchall()

        result = _cert_to_dict(cert, items)

        # Audit log
        if changes:
            log_audit(user_id, "cusma.updated", "cusma", cert_id, changes, db)

        # Fire webhooks
        fire_webhooks(user_id, "cusma.updated", result, db)

    return result


@app.delete("/api/cusma/{cert_id}")
async def delete_certificate(cert_id: int, current_user: dict = Depends(get_current_user)):
    """Delete a certificate and all its items."""
    user_id = current_user["user_id"]

    with get_db() as db:
        scope = get_scope_filter(user_id, db)
        placeholders = ",".join("?" * len(scope))
        existing = db.execute(
            f"SELECT * FROM cusma_certificates WHERE id = ? AND user_id IN ({placeholders})",
            [cert_id] + scope,
        ).fetchone()

        if not existing:
            raise HTTPException(status_code=404, detail="Certificate not found")

        # Delete items first (FK integrity)
        db.execute("DELETE FROM cusma_certificate_items WHERE certificate_id = ?", (cert_id,))
        db.execute("DELETE FROM cusma_certificates WHERE id = ?", (cert_id,))

        # Audit log
        log_audit(
            user_id, "cusma.deleted", "cusma", cert_id,
            {"cert_number": existing["cert_number"]}, db,
        )

    return {"message": "Deleted"}


@app.post("/api/cusma/{cert_id}/items")
async def add_certificate_item(
    cert_id: int, item: CusmaItemCreate, current_user: dict = Depends(get_current_user)
):
    """Add an item to an existing certificate."""
    user_id = current_user["user_id"]

    with get_db() as db:
        scope = get_scope_filter(user_id, db)
        placeholders = ",".join("?" * len(scope))
        cert = db.execute(
            f"SELECT * FROM cusma_certificates WHERE id = ? AND user_id IN ({placeholders})",
            [cert_id] + scope,
        ).fetchone()

        if not cert:
            raise HTTPException(status_code=404, detail="Certificate not found")

        # Auto-fill from SKU if sku_id provided
        if item.sku_id:
            sku_row = db.execute("SELECT * FROM skus WHERE id = ?", (item.sku_id,)).fetchone()
            if not sku_row:
                raise HTTPException(status_code=404, detail=f"SKU with id {item.sku_id} not found")
            cursor = db.execute(
                "INSERT INTO cusma_certificate_items "
                "(certificate_id, sku_id, sku_code, description, hts_code, "
                "country_of_origin, customs_value, currency, origin_criterion) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    cert_id, item.sku_id,
                    item.sku_code or sku_row["sku_code"],
                    item.description or sku_row["description"],
                    item.hts_code or sku_row["hts_code"],
                    item.country_of_origin or sku_row["country_of_origin"],
                    item.customs_value if item.customs_value is not None else sku_row["customs_value"],
                    item.currency or sku_row["currency"],
                    item.origin_criterion,
                ),
            )
        else:
            cursor = db.execute(
                "INSERT INTO cusma_certificate_items "
                "(certificate_id, sku_id, sku_code, description, hts_code, "
                "country_of_origin, customs_value, currency, origin_criterion) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    cert_id, None,
                    item.sku_code, item.description, item.hts_code,
                    item.country_of_origin, item.customs_value,
                    item.currency or "USD", item.origin_criterion,
                ),
            )

        item_id = cursor.lastrowid
        created_item = db.execute(
            "SELECT * FROM cusma_certificate_items WHERE id = ?", (item_id,)
        ).fetchone()

    return dict(created_item)


@app.delete("/api/cusma/{cert_id}/items/{item_id}")
async def remove_certificate_item(
    cert_id: int, item_id: int, current_user: dict = Depends(get_current_user)
):
    """Remove an item from a certificate."""
    user_id = current_user["user_id"]

    with get_db() as db:
        scope = get_scope_filter(user_id, db)
        placeholders = ",".join("?" * len(scope))
        cert = db.execute(
            f"SELECT * FROM cusma_certificates WHERE id = ? AND user_id IN ({placeholders})",
            [cert_id] + scope,
        ).fetchone()

        if not cert:
            raise HTTPException(status_code=404, detail="Certificate not found")

        item = db.execute(
            "SELECT * FROM cusma_certificate_items WHERE id = ? AND certificate_id = ?",
            (item_id, cert_id),
        ).fetchone()

        if not item:
            raise HTTPException(status_code=404, detail="Item not found")

        db.execute("DELETE FROM cusma_certificate_items WHERE id = ?", (item_id,))

    return {"message": "Item removed"}


@app.post("/api/cusma/auto-generate")
async def auto_generate_certificate(
    req: AutoGenerateRequest, current_user: dict = Depends(get_current_user)
):
    """Auto-generate a CUSMA certificate from selected SKU IDs.
    Creates a blanket certificate covering the current calendar year."""
    user_id = current_user["user_id"]
    now = datetime.utcnow()
    now_iso = now.isoformat()

    with get_db() as db:
        # Look up user for certifier info
        user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Generate cert number
        cert_number = generate_cert_number(db)

        # Blanket period: Jan 1 – Dec 31 of current year
        year = now.strftime("%Y")
        blanket_start = f"{year}-01-01"
        blanket_end = f"{year}-12-31"

        cursor = db.execute(
            "INSERT INTO cusma_certificates "
            "(user_id, cert_number, cert_type, status, "
            "certifier_name, certifier_email, "
            "blanket_start, blanket_end, created_at, updated_at) "
            "VALUES (?, ?, 'blanket', 'draft', ?, ?, ?, ?, ?, ?)",
            (
                user_id, cert_number,
                user["name"], user["email"],
                blanket_start, blanket_end, now_iso, now_iso,
            ),
        )
        cert_id = cursor.lastrowid

        # Add selected SKUs as items
        for sku_id in req.sku_ids:
            scope = get_scope_filter(user_id, db)
            placeholders = ",".join("?" * len(scope))
            sku_row = db.execute(
                f"SELECT * FROM skus WHERE id = ? AND user_id IN ({placeholders})",
                [sku_id] + scope,
            ).fetchone()
            if sku_row:
                db.execute(
                    "INSERT INTO cusma_certificate_items "
                    "(certificate_id, sku_id, sku_code, description, hts_code, "
                    "country_of_origin, customs_value, currency, origin_criterion) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        cert_id, sku_row["id"],
                        sku_row["sku_code"], sku_row["description"], sku_row["hts_code"],
                        sku_row["country_of_origin"], sku_row["customs_value"],
                        sku_row["currency"], None,
                    ),
                )

        # Fetch result
        cert = db.execute("SELECT * FROM cusma_certificates WHERE id = ?", (cert_id,)).fetchone()
        items = db.execute(
            "SELECT * FROM cusma_certificate_items WHERE certificate_id = ?", (cert_id,)
        ).fetchall()

        result = _cert_to_dict(cert, items)

        # Audit
        log_audit(user_id, "cusma.created", "cusma", cert_id,
                  {"cert_number": cert_number, "auto_generated": True}, db)

        # Webhooks
        fire_webhooks(user_id, "cusma.created", result, db)

    return result


# ===========================================================================================
# CUSMA PDF GENERATION
# ===========================================================================================

@app.get("/api/cusma/{cert_id}/pdf")
async def generate_certificate_pdf(
    cert_id: int, current_user: dict = Depends(get_current_user)
):
    """Generate a PDF (or HTML fallback) of a CUSMA certificate.
    All user-provided fields are escaped with html.escape() for XSS protection."""
    user_id = current_user["user_id"]

    with get_db() as db:
        scope = get_scope_filter(user_id, db)
        placeholders = ",".join("?" * len(scope))
        cert = db.execute(
            f"SELECT * FROM cusma_certificates WHERE id = ? AND user_id IN ({placeholders})",
            [cert_id] + scope,
        ).fetchone()

        if not cert:
            raise HTTPException(status_code=404, detail="Certificate not found")

        items = db.execute(
            "SELECT * FROM cusma_certificate_items WHERE certificate_id = ?", (cert_id,)
        ).fetchall()

    cert = dict(cert)
    today = datetime.utcnow().strftime("%Y-%m-%d")
    if cert.get("blanket_end") and cert["blanket_end"] < today and cert["status"] != "expired":
        cert["status"] = "expired"

    # Escape helper
    def esc(val):
        """Safely escape a value for HTML rendering."""
        if val is None:
            return ""
        return html.escape(str(val))

    # Build items table rows
    items_rows = ""
    for idx, item in enumerate(items, 1):
        item = dict(item)
        items_rows += f"""
        <tr>
            <td>{idx}</td>
            <td>{esc(item.get('sku_code'))}</td>
            <td>{esc(item.get('description'))}</td>
            <td>{esc(item.get('hts_code'))}</td>
            <td>{esc(item.get('country_of_origin'))}</td>
            <td>{esc(item.get('customs_value'))} {esc(item.get('currency'))}</td>
            <td>{esc(item.get('origin_criterion'))}</td>
        </tr>"""

    # Build HTML template
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>CUSMA Certificate — {esc(cert.get('cert_number'))}</title>
    <style>
        @page {{
            size: letter;
            margin: 1in;
        }}
        body {{
            font-family: 'Helvetica Neue', Arial, sans-serif;
            font-size: 11px;
            color: #222;
            line-height: 1.5;
        }}
        .header {{
            text-align: center;
            border-bottom: 3px double #333;
            padding-bottom: 15px;
            margin-bottom: 20px;
        }}
        .header h1 {{
            font-size: 20px;
            margin: 0 0 5px 0;
            color: #1a3a5c;
        }}
        .header h2 {{
            font-size: 14px;
            margin: 0;
            color: #555;
            font-weight: normal;
        }}
        .cert-info {{
            display: flex;
            justify-content: space-between;
            margin-bottom: 20px;
        }}
        .cert-info div {{
            font-size: 11px;
        }}
        .cert-info strong {{
            color: #1a3a5c;
        }}
        .party-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
            margin-bottom: 20px;
        }}
        .party-box {{
            border: 1px solid #ccc;
            padding: 12px;
            border-radius: 4px;
        }}
        .party-box h3 {{
            font-size: 12px;
            margin: 0 0 8px 0;
            color: #1a3a5c;
            text-transform: uppercase;
            border-bottom: 1px solid #eee;
            padding-bottom: 4px;
        }}
        .party-box p {{
            margin: 2px 0;
            font-size: 10px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 20px;
        }}
        th, td {{
            border: 1px solid #ccc;
            padding: 6px 8px;
            text-align: left;
            font-size: 10px;
        }}
        th {{
            background-color: #1a3a5c;
            color: white;
            font-weight: bold;
        }}
        tr:nth-child(even) {{
            background-color: #f9f9f9;
        }}
        .signature-block {{
            margin-top: 40px;
            border-top: 1px solid #ccc;
            padding-top: 20px;
        }}
        .signature-line {{
            border-bottom: 1px solid #333;
            width: 300px;
            margin: 30px 0 5px 0;
        }}
        .status-badge {{
            display: inline-block;
            padding: 3px 10px;
            border-radius: 3px;
            font-size: 10px;
            font-weight: bold;
            text-transform: uppercase;
        }}
        .status-active {{ background: #d4edda; color: #155724; }}
        .status-draft {{ background: #fff3cd; color: #856404; }}
        .status-expired {{ background: #f8d7da; color: #721c24; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>CUSMA / USMCA Certificate of Origin</h1>
        <h2>Canada–United States–Mexico Agreement</h2>
    </div>

    <div class="cert-info">
        <div>
            <strong>Certificate No:</strong> {esc(cert.get('cert_number'))}<br>
            <strong>Type:</strong> {esc(cert.get('cert_type', '').title())}<br>
            <strong>Status:</strong> <span class="status-badge status-{esc(cert.get('status'))}">{esc(cert.get('status', '').upper())}</span>
        </div>
        <div>
            <strong>Blanket Period:</strong><br>
            {esc(cert.get('blanket_start'))} to {esc(cert.get('blanket_end'))}<br>
            <strong>Issued:</strong> {esc(cert.get('created_at', '')[:10])}
        </div>
    </div>

    <div class="party-grid">
        <div class="party-box">
            <h3>Certifier</h3>
            <p><strong>{esc(cert.get('certifier_name'))}</strong></p>
            <p>{esc(cert.get('certifier_title'))}</p>
            <p>{esc(cert.get('certifier_company'))}</p>
            <p>{esc(cert.get('certifier_address'))}</p>
            <p>Phone: {esc(cert.get('certifier_phone'))}</p>
            <p>Email: {esc(cert.get('certifier_email'))}</p>
        </div>
        <div class="party-box">
            <h3>Exporter</h3>
            <p><strong>{esc(cert.get('exporter_name'))}</strong></p>
            <p>{esc(cert.get('exporter_company'))}</p>
            <p>{esc(cert.get('exporter_address'))}</p>
        </div>
        <div class="party-box">
            <h3>Producer</h3>
            <p><strong>{esc(cert.get('producer_name'))}</strong></p>
            <p>{esc(cert.get('producer_company'))}</p>
            <p>{esc(cert.get('producer_address'))}</p>
        </div>
        <div class="party-box">
            <h3>Importer</h3>
            <p><strong>{esc(cert.get('importer_name'))}</strong></p>
            <p>{esc(cert.get('importer_company'))}</p>
            <p>{esc(cert.get('importer_address'))}</p>
        </div>
    </div>

    <h3 style="color: #1a3a5c;">Description of Good(s)</h3>
    <table>
        <thead>
            <tr>
                <th>#</th>
                <th>SKU Code</th>
                <th>Description</th>
                <th>HTS Code</th>
                <th>Country of Origin</th>
                <th>Customs Value</th>
                <th>Origin Criterion</th>
            </tr>
        </thead>
        <tbody>
            {items_rows if items_rows else '<tr><td colspan="7" style="text-align:center;">No items</td></tr>'}
        </tbody>
    </table>

    <div class="signature-block">
        <p><strong>I certify that the goods described in this document qualify as originating
        and the information contained in this document is true and accurate. I assume
        responsibility for proving such representations and agree to maintain and present
        upon request or to make available during a verification visit, documentation necessary
        to support this certification.</strong></p>

        <div class="signature-line"></div>
        <p><strong>Authorised Signature</strong></p>
        <p>{esc(cert.get('certifier_name'))} — {esc(cert.get('certifier_title'))}</p>
        <p>Date: {datetime.utcnow().strftime('%B %d, %Y')}</p>
    </div>
</body>
</html>"""

    if HAS_WEASYPRINT:
        # Render to PDF
        try:
            pdf_bytes = WeasyHTML(string=html_content).write_pdf()
            return StreamingResponse(
                io.BytesIO(pdf_bytes),
                media_type="application/pdf",
                headers={
                    "Content-Disposition": f'attachment; filename="cusma_{esc(cert.get("cert_number"))}.pdf"'
                },
            )
        except Exception:
            # Fall back to HTML if WeasyPrint fails
            pass

    # HTML fallback
    return StreamingResponse(
        io.BytesIO(html_content.encode("utf-8")),
        media_type="text/html",
        headers={
            "Content-Disposition": f'attachment; filename="cusma_{esc(cert.get("cert_number"))}.html"'
        },
    )


# ===========================================================================================
# EXTERNAL LOOKUP API (API-key authenticated)
# ===========================================================================================

@app.get("/api/lookup/{sku_code}")
async def lookup_sku(
    sku_code: str,
    request: Request,
    include_cusma: Optional[bool] = Query(False),
    x_api_key: Optional[str] = Header(None),
    api_key: Optional[str] = Query(None),
):
    """Look up a SKU by code. Authenticated via API key (header or query param)."""
    key = x_api_key or api_key
    if not key:
        raise HTTPException(status_code=401, detail="API key required")

    # Rate limit per key prefix
    check_rate_limit(f"lookup:{key[:8]}", max_requests=120, window=60)

    with get_db() as db:
        user_info = authenticate_api_key(key, db)
        user_id = user_info["user_id"]

        scope = get_scope_filter(user_id, db)
        placeholders = ",".join("?" * len(scope))
        sku = db.execute(
            f"SELECT * FROM skus WHERE sku_code = ? AND user_id IN ({placeholders})",
            [sku_code] + scope,
        ).fetchone()

        if not sku:
            raise HTTPException(status_code=404, detail="SKU not found")

        result = dict(sku)

        # Optionally include CUSMA certificate data
        if include_cusma:
            today = datetime.utcnow().strftime("%Y-%m-%d")
            cert_items = db.execute(
                "SELECT ci.*, cc.cert_number, cc.status, cc.blanket_start, cc.blanket_end "
                "FROM cusma_certificate_items ci "
                "JOIN cusma_certificates cc ON ci.certificate_id = cc.id "
                "WHERE ci.sku_code = ? AND cc.status = 'active' "
                "AND (cc.blanket_end IS NULL OR cc.blanket_end >= ?)",
                (sku_code, today),
            ).fetchall()
            result["cusma_certificates"] = [dict(ci) for ci in cert_items]

    return result


@app.post("/api/lookup/batch")
async def batch_lookup(
    req: BatchLookupRequest,
    request: Request,
    x_api_key: Optional[str] = Header(None),
    api_key: Optional[str] = Query(None),
):
    """Batch look up multiple SKUs by code. Authenticated via API key."""
    key = x_api_key or api_key
    if not key:
        raise HTTPException(status_code=401, detail="API key required")

    check_rate_limit(f"lookup:{key[:8]}", max_requests=120, window=60)

    with get_db() as db:
        user_info = authenticate_api_key(key, db)
        user_id = user_info["user_id"]

        scope = get_scope_filter(user_id, db)
        scope_ph = ",".join("?" * len(scope))

        results = []
        for sku_code in req.sku_codes:
            sku = db.execute(
                f"SELECT * FROM skus WHERE sku_code = ? AND user_id IN ({scope_ph})",
                [sku_code] + scope,
            ).fetchone()

            if sku:
                results.append(dict(sku))
            else:
                results.append({"sku_code": sku_code, "error": "Not found"})

    return results


# ===========================================================================================
# HTS CODE SERVICES
# ===========================================================================================

@app.get("/api/hts/search")
async def hts_search(
    q: str = Query(..., min_length=1),
    current_user: dict = Depends(get_current_user),
):
    """Search HTS codes via the USITC API. Results cached for 1 hour."""
    check_rate_limit(f"hts:{current_user['user_id']}", max_requests=60, window=60)

    cache_key = f"search:{q}"
    cached = get_hts_cached(cache_key)
    if cached is not None:
        return cached

    try:
        resp = httpx.get(
            "https://hts.usitc.gov/api/search",
            params={"query": q},
            timeout=10.0,
        )

        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail="USITC API error")

        data = resp.json()
        raw_results = data if isinstance(data, list) else data.get("results", [])

        # Return top 10 results
        results = []
        for item in raw_results[:10]:
            results.append({
                "hts_code": item.get("htsno", item.get("hts_code", "")),
                "description": item.get("description", item.get("desc", "")),
                "indent": item.get("indent", item.get("level", 0)),
            })

        set_hts_cached(cache_key, results)
        return results

    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="USITC API timeout")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"USITC API error: {str(e)}")


@app.get("/api/hts/validate")
async def hts_validate(
    code: str = Query(..., min_length=1),
    current_user: dict = Depends(get_current_user),
):
    """Validate an HTS code against the USITC API."""
    check_rate_limit(f"hts:{current_user['user_id']}", max_requests=60, window=60)

    result = validate_hts_code(code)
    return {
        "valid": result["valid"],
        "description": result["description"],
        "official_code": result["official_code"],
    }


@app.post("/api/hts/recommend")
async def hts_recommend(
    req: HtsRecommendRequest,
    current_user: dict = Depends(get_current_user),
):
    """Get an AI-powered HTS code recommendation using Anthropic Claude Haiku.
    Requires ANTHROPIC_API_KEY environment variable to be set."""
    if not ANTHROPIC_API_KEY:
        raise HTTPException(
            status_code=503, detail="AI recommendations not configured"
        )

    check_rate_limit(f"hts_ai:{current_user['user_id']}", max_requests=20, window=60)

    # Build prompt for Claude
    prompt = (
        f"You are an expert in customs classification and the Harmonized Tariff Schedule (HTS) "
        f"of the United States. Given the following product description, provide the most likely "
        f"6-digit or 10-digit HTS code.\n\n"
        f"Product Description: {req.description}\n"
    )
    if req.sku_code:
        prompt += f"SKU Code: {req.sku_code}\n"

    prompt += (
        "\nRespond in JSON format with these fields:\n"
        '{"hts_code": "XXXX.XX.XXXX", "description": "official HTS description", '
        '"confidence": "high/medium/low", "reasoning": "brief explanation"}\n'
        "Only return the JSON, no other text."
    )

    try:
        resp = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            json={
                "model": "claude-3-haiku-20240307",
                "max_tokens": 500,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=30.0,
        )

        if resp.status_code != 200:
            raise HTTPException(
                status_code=502, detail=f"Anthropic API error: {resp.status_code}"
            )

        ai_data = resp.json()
        ai_text = ai_data.get("content", [{}])[0].get("text", "{}")

        # Parse AI response
        try:
            recommendation = json.loads(ai_text)
        except json.JSONDecodeError:
            # Try to extract JSON from the response
            json_match = re.search(r'\{[^}]+\}', ai_text)
            if json_match:
                recommendation = json.loads(json_match.group())
            else:
                raise HTTPException(status_code=502, detail="Could not parse AI recommendation")

        recommended_code = recommendation.get("hts_code", "")

        # Verify against USITC
        usitc_result = validate_hts_code(recommended_code)

        return {
            "recommended_code": recommended_code,
            "description": recommendation.get("description", ""),
            "confidence": recommendation.get("confidence", "medium"),
            "reasoning": recommendation.get("reasoning", ""),
            "usitc_verified": usitc_result["valid"] is True,
        }

    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="AI service timeout")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI recommendation error: {str(e)}")


# ===========================================================================================
# HEALTH CHECK
# ===========================================================================================

@app.get("/api/health")
async def health_check():
    """Simple health check endpoint — no auth required."""
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


# ===========================================================================================
# DASHBOARD
# ===========================================================================================

@app.get("/api/dashboard")
async def dashboard(current_user: dict = Depends(get_current_user)):
    """Aggregate dashboard statistics for the authenticated user."""
    user_id = current_user["user_id"]
    today = datetime.utcnow().strftime("%Y-%m-%d")
    thirty_days = (datetime.utcnow() + timedelta(days=30)).strftime("%Y-%m-%d")

    with get_db() as db:
        scope = get_scope_filter(user_id, db)
        placeholders = ",".join("?" * len(scope))

        # SKU stats
        total_skus = db.execute(
            f"SELECT COUNT(*) as cnt FROM skus WHERE user_id IN ({placeholders})", scope
        ).fetchone()["cnt"]

        validated_skus = db.execute(
            f"SELECT COUNT(*) as cnt FROM skus WHERE user_id IN ({placeholders}) AND hts_valid = 1",
            scope,
        ).fetchone()["cnt"]

        invalid_skus = db.execute(
            f"SELECT COUNT(*) as cnt FROM skus WHERE user_id IN ({placeholders}) AND hts_valid = 0",
            scope,
        ).fetchone()["cnt"]

        pending_validation = db.execute(
            f"SELECT COUNT(*) as cnt FROM skus WHERE user_id IN ({placeholders}) AND hts_valid IS NULL",
            scope,
        ).fetchone()["cnt"]

        # Certificate stats
        certs = db.execute(
            f"SELECT * FROM cusma_certificates WHERE user_id IN ({placeholders})", scope
        ).fetchall()

        total_certs = 0
        active_certs = 0
        draft_certs = 0
        expired_certs = 0

        for c in certs:
            total_certs += 1
            status = c["status"]
            if c["blanket_end"] and c["blanket_end"] < today and status != "expired":
                status = "expired"
            if status == "active":
                active_certs += 1
            elif status == "draft":
                draft_certs += 1
            elif status == "expired":
                expired_certs += 1

        # Expiring soon
        expiring_soon = db.execute(
            f"SELECT COUNT(*) as cnt FROM cusma_certificates "
            f"WHERE user_id IN ({placeholders}) "
            f"AND blanket_end >= ? AND blanket_end <= ? "
            f"AND status != 'expired'",
            scope + [today, thirty_days],
        ).fetchone()["cnt"]

        # Compliance score
        compliance_score = 0.0
        if total_skus > 0:
            compliance_score = round((validated_skus / total_skus) * 100, 1)

        # Recent activity (last 10 audit log entries)
        recent_activity = db.execute(
            f"SELECT * FROM audit_log WHERE user_id IN ({placeholders}) "
            f"ORDER BY created_at DESC LIMIT 10",
            scope,
        ).fetchall()

        # API key info (prefix only)
        api_keys = db.execute(
            "SELECT id, key_prefix, created_at, last_used_at FROM api_keys WHERE user_id = ?",
            (user_id,),
        ).fetchall()

    return {
        "total_skus": total_skus,
        "validated_skus": validated_skus,
        "invalid_skus": invalid_skus,
        "pending_validation": pending_validation,
        "total_certs": total_certs,
        "active_certs": active_certs,
        "draft_certs": draft_certs,
        "expired_certs": expired_certs,
        "compliance_score": compliance_score,
        "expiring_soon": expiring_soon,
        "recent_activity": [dict(r) for r in recent_activity],
        "api_keys": [dict(k) for k in api_keys],
    }


# ===========================================================================================
# AUDIT LOG
# ===========================================================================================

@app.get("/api/audit-log")
async def get_audit_log(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    search: Optional[str] = Query(None),
    type: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
):
    """Paginated audit log with optional search and type filter."""
    user_id = current_user["user_id"]

    with get_db() as db:
        scope = get_scope_filter(user_id, db)
        placeholders = ",".join("?" * len(scope))

        base_where = f"user_id IN ({placeholders})"
        params: list = list(scope)

        # Filter by entity type
        if type:
            base_where += " AND entity_type = ?"
            params.append(type)

        # Search across action and changes
        if search:
            search_term = f"%{search}%"
            base_where += " AND (action LIKE ? OR changes LIKE ?)"
            params.extend([search_term, search_term])

        # Count total
        total = db.execute(
            f"SELECT COUNT(*) as cnt FROM audit_log WHERE {base_where}", params
        ).fetchone()["cnt"]

        # Paginated results
        offset = (page - 1) * page_size
        rows = db.execute(
            f"SELECT * FROM audit_log WHERE {base_where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            params + [page_size, offset],
        ).fetchall()

    pages = max(1, (total + page_size - 1) // page_size)
    return {
        "items": [dict(r) for r in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": pages,
    }


# ===========================================================================================
# DUTY ESTIMATION
# ===========================================================================================

@app.get("/api/duty/estimate")
async def estimate_duty(
    hts_code: str = Query(..., min_length=1),
    country: str = Query(..., min_length=2),
    value: float = Query(..., gt=0),
    current_user: dict = Depends(get_current_user),
):
    """Estimate duty for a given HTS code, country, and value.
    Checks local cache first, then queries USITC."""
    check_rate_limit(f"duty:{current_user['user_id']}", max_requests=60, window=60)

    country = country.upper()

    with get_db() as db:
        # Check local duty_rates table
        local_rate = db.execute(
            "SELECT * FROM duty_rates WHERE hts_code = ? AND country = ? "
            "ORDER BY cached_at DESC LIMIT 1",
            (hts_code, country),
        ).fetchone()

        if local_rate:
            rate_value = local_rate["rate_value"]
            rate_type = local_rate["rate_type"]
            source = local_rate["source"]
        else:
            # Try to get rate from USITC
            rate_value = None
            rate_type = "ad_valorem"
            source = "estimated"

            try:
                resp = httpx.get(
                    "https://hts.usitc.gov/api/search",
                    params={"query": hts_code},
                    timeout=10.0,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    results = data if isinstance(data, list) else data.get("results", [])
                    clean_code = re.sub(r"[.\-\s]", "", hts_code)

                    for item in results:
                        item_code = re.sub(r"[.\-\s]", "", str(item.get("htsno", item.get("hts_code", ""))))
                        if item_code == clean_code or item_code.startswith(clean_code):
                            # Try to extract general rate
                            general = item.get("general", item.get("rate", ""))
                            if general:
                                # Parse percentage rates like "5.0%"
                                pct_match = re.search(r'(\d+\.?\d*)%', str(general))
                                if pct_match:
                                    rate_value = float(pct_match.group(1))
                                    rate_type = "ad_valorem"
                                    source = "usitc"
                                elif general.lower() == "free":
                                    rate_value = 0.0
                                    rate_type = "free"
                                    source = "usitc"
                            break

                    # Cache the rate if found
                    if rate_value is not None:
                        db.execute(
                            "INSERT INTO duty_rates (hts_code, rate_type, rate_value, country, "
                            "description, source, cached_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                            (
                                hts_code, rate_type, rate_value, country,
                                "", source, datetime.utcnow().isoformat(),
                            ),
                        )

            except Exception:
                pass  # Fall through to estimated rate

            # Default estimate if no rate found
            if rate_value is None:
                rate_value = 3.5  # Conservative default estimate
                rate_type = "ad_valorem"
                source = "estimated"

    # Calculate estimated duty
    if rate_type == "free":
        estimated_duty = 0.0
    else:
        estimated_duty = round(value * (rate_value / 100), 2)

    return {
        "hts_code": hts_code,
        "country": country,
        "value": value,
        "duty_rate": rate_value,
        "duty_type": rate_type,
        "estimated_duty": estimated_duty,
        "source": source,
    }


# ===========================================================================================
# WEBHOOKS CRUD
# ===========================================================================================

@app.get("/api/webhooks")
async def list_webhooks(current_user: dict = Depends(get_current_user)):
    """List all webhooks for the authenticated user."""
    user_id = current_user["user_id"]

    with get_db() as db:
        rows = db.execute(
            "SELECT id, user_id, url, events, active, created_at FROM webhooks WHERE user_id = ?",
            (user_id,),
        ).fetchall()

    result = []
    for r in rows:
        wh = dict(r)
        wh["events"] = json.loads(wh["events"]) if isinstance(wh["events"], str) else wh["events"]
        result.append(wh)

    return result


@app.post("/api/webhooks")
async def create_webhook(
    req: WebhookCreate, current_user: dict = Depends(get_current_user)
):
    """Create a new webhook. Secret is shown only once at creation time."""
    user_id = current_user["user_id"]

    # Validate URL (SSRF protection)
    validate_webhook_url(req.url)

    webhook_secret = secrets.token_hex(32)
    now = datetime.utcnow().isoformat()

    with get_db() as db:
        cursor = db.execute(
            "INSERT INTO webhooks (user_id, url, events, secret, active, created_at) "
            "VALUES (?, ?, ?, ?, 1, ?)",
            (user_id, req.url, json.dumps(req.events), webhook_secret, now),
        )
        webhook_id = cursor.lastrowid

    return {
        "id": webhook_id,
        "url": req.url,
        "events": req.events,
        "secret": webhook_secret,  # Only time secret is shown in full
        "active": True,
        "created_at": now,
    }


@app.put("/api/webhooks/{webhook_id}")
async def update_webhook(
    webhook_id: int, req: WebhookUpdate, current_user: dict = Depends(get_current_user)
):
    """Update webhook URL and/or events."""
    user_id = current_user["user_id"]

    with get_db() as db:
        existing = db.execute(
            "SELECT * FROM webhooks WHERE id = ? AND user_id = ?", (webhook_id, user_id)
        ).fetchone()

        if not existing:
            raise HTTPException(status_code=404, detail="Webhook not found")

        update_fields = []
        update_values = []

        if req.url is not None:
            validate_webhook_url(req.url)
            update_fields.append("url = ?")
            update_values.append(req.url)

        if req.events is not None:
            update_fields.append("events = ?")
            update_values.append(json.dumps(req.events))

        if req.active is not None:
            update_fields.append("active = ?")
            update_values.append(1 if req.active else 0)

        if update_fields:
            update_values.append(webhook_id)
            db.execute(
                f"UPDATE webhooks SET {', '.join(update_fields)} WHERE id = ?",
                update_values,
            )

        updated = db.execute("SELECT * FROM webhooks WHERE id = ?", (webhook_id,)).fetchone()

    result = dict(updated)
    result["events"] = json.loads(result["events"]) if isinstance(result["events"], str) else result["events"]
    # Don't include the secret in update responses
    result.pop("secret", None)
    return result


@app.delete("/api/webhooks/{webhook_id}")
async def delete_webhook(webhook_id: int, current_user: dict = Depends(get_current_user)):
    """Delete a webhook."""
    user_id = current_user["user_id"]

    with get_db() as db:
        existing = db.execute(
            "SELECT * FROM webhooks WHERE id = ? AND user_id = ?", (webhook_id, user_id)
        ).fetchone()

        if not existing:
            raise HTTPException(status_code=404, detail="Webhook not found")

        db.execute("DELETE FROM webhooks WHERE id = ?", (webhook_id,))

    return {"message": "Webhook deleted"}


@app.post("/api/webhooks/{webhook_id}/test")
async def test_webhook(webhook_id: int, current_user: dict = Depends(get_current_user)):
    """Send a test event to a webhook URL and report success/failure."""
    user_id = current_user["user_id"]

    with get_db() as db:
        hook = db.execute(
            "SELECT * FROM webhooks WHERE id = ? AND user_id = ?", (webhook_id, user_id)
        ).fetchone()

        if not hook:
            raise HTTPException(status_code=404, detail="Webhook not found")

    # Build test payload
    body = json.dumps({
        "event": "test",
        "data": {"message": "This is a test webhook event"},
        "timestamp": datetime.utcnow().isoformat(),
    })
    signature = hmac.new(
        hook["secret"].encode(), body.encode(), hashlib.sha256
    ).hexdigest()

    start_time = time.time()
    try:
        resp = httpx.post(
            hook["url"],
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Webhook-Signature": signature,
            },
            timeout=10.0,
        )
        elapsed = round((time.time() - start_time) * 1000, 1)
        return {
            "success": 200 <= resp.status_code < 300,
            "status_code": resp.status_code,
            "response_time_ms": elapsed,
        }
    except Exception as e:
        elapsed = round((time.time() - start_time) * 1000, 1)
        return {
            "success": False,
            "status_code": None,
            "response_time_ms": elapsed,
            "error": str(e),
        }


# ===========================================================================================
# FULL DATA EXPORT (ZIP)
# ===========================================================================================

@app.get("/api/export")
async def full_export(current_user: dict = Depends(get_current_user)):
    """Export all user data as a ZIP file containing multiple CSVs and a manifest."""
    user_id = current_user["user_id"]

    with get_db() as db:
        scope = get_scope_filter(user_id, db)
        placeholders = ",".join("?" * len(scope))

        # Fetch all data
        skus = db.execute(
            f"SELECT * FROM skus WHERE user_id IN ({placeholders})", scope
        ).fetchall()

        certs = db.execute(
            f"SELECT * FROM cusma_certificates WHERE user_id IN ({placeholders})", scope
        ).fetchall()

        cert_ids = [c["id"] for c in certs]
        cert_items = []
        if cert_ids:
            ci_ph = ",".join("?" * len(cert_ids))
            cert_items = db.execute(
                f"SELECT * FROM cusma_certificate_items WHERE certificate_id IN ({ci_ph})",
                cert_ids,
            ).fetchall()

        audit_entries = db.execute(
            f"SELECT * FROM audit_log WHERE user_id IN ({placeholders}) ORDER BY created_at DESC",
            scope,
        ).fetchall()

        webhooks = db.execute(
            "SELECT id, user_id, url, events, active, created_at FROM webhooks WHERE user_id = ?",
            (user_id,),
        ).fetchall()

    # Build ZIP in memory
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        # skus.csv
        sku_csv = io.StringIO()
        writer = csv.writer(sku_csv)
        writer.writerow(["id", "user_id", "sku_code", "description", "hts_code", "hts_valid",
                          "hts_description", "country_of_origin", "customs_value", "currency",
                          "created_at", "updated_at"])
        for s in skus:
            writer.writerow([s["id"], s["user_id"], s["sku_code"], s["description"],
                             s["hts_code"], s["hts_valid"], s["hts_description"],
                             s["country_of_origin"], s["customs_value"], s["currency"],
                             s["created_at"], s["updated_at"]])
        zf.writestr("skus.csv", sku_csv.getvalue())

        # cusma_certificates.csv
        cert_csv = io.StringIO()
        writer = csv.writer(cert_csv)
        cert_columns = ["id", "user_id", "cert_number", "cert_type", "status",
                         "certifier_name", "certifier_title", "certifier_company",
                         "certifier_address", "certifier_phone", "certifier_email",
                         "exporter_name", "exporter_company", "exporter_address",
                         "importer_name", "importer_company", "importer_address",
                         "producer_name", "producer_company", "producer_address",
                         "blanket_start", "blanket_end", "created_at", "updated_at"]
        writer.writerow(cert_columns)
        for c in certs:
            writer.writerow([c[col] for col in cert_columns])
        zf.writestr("cusma_certificates.csv", cert_csv.getvalue())

        # cusma_certificate_items.csv
        items_csv = io.StringIO()
        writer = csv.writer(items_csv)
        writer.writerow(["id", "certificate_id", "sku_id", "sku_code", "description",
                          "hts_code", "country_of_origin", "customs_value", "currency",
                          "origin_criterion"])
        for i in cert_items:
            writer.writerow([i["id"], i["certificate_id"], i["sku_id"], i["sku_code"],
                             i["description"], i["hts_code"], i["country_of_origin"],
                             i["customs_value"], i["currency"], i["origin_criterion"]])
        zf.writestr("cusma_certificate_items.csv", items_csv.getvalue())

        # audit_log.csv
        audit_csv = io.StringIO()
        writer = csv.writer(audit_csv)
        writer.writerow(["id", "user_id", "action", "entity_type", "entity_id",
                          "changes", "created_at"])
        for a in audit_entries:
            writer.writerow([a["id"], a["user_id"], a["action"], a["entity_type"],
                             a["entity_id"], a["changes"], a["created_at"]])
        zf.writestr("audit_log.csv", audit_csv.getvalue())

        # webhooks.csv (without secrets)
        wh_csv = io.StringIO()
        writer = csv.writer(wh_csv)
        writer.writerow(["id", "user_id", "url", "events", "active", "created_at"])
        for w in webhooks:
            writer.writerow([w["id"], w["user_id"], w["url"], w["events"],
                             w["active"], w["created_at"]])
        zf.writestr("webhooks.csv", wh_csv.getvalue())

        # manifest.json
        manifest = {
            "exported_at": datetime.utcnow().isoformat(),
            "user_email": current_user.get("email", ""),
            "counts": {
                "skus": len(skus),
                "certs": len(certs),
                "items": len(cert_items),
                "audit_entries": len(audit_entries),
            },
        }
        zf.writestr("manifest.json", json.dumps(manifest, indent=2))

    zip_buffer.seek(0)
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=customs_export.zip"},
    )


# ===========================================================================================
# TEAMS
# ===========================================================================================

@app.post("/api/teams")
async def create_team(req: TeamCreate, current_user: dict = Depends(get_current_user)):
    """Create a new team. The creator is automatically added as the owner."""
    user_id = current_user["user_id"]
    now = datetime.utcnow().isoformat()

    with get_db() as db:
        cursor = db.execute(
            "INSERT INTO teams (name, owner_id, created_at) VALUES (?, ?, ?)",
            (req.name, user_id, now),
        )
        team_id = cursor.lastrowid

        # Add creator as owner member
        db.execute(
            "INSERT INTO team_members (team_id, user_id, role, joined_at) VALUES (?, ?, 'owner', ?)",
            (team_id, user_id, now),
        )

        team = db.execute("SELECT * FROM teams WHERE id = ?", (team_id,)).fetchone()

    return dict(team)


@app.get("/api/teams/mine")
async def my_teams(current_user: dict = Depends(get_current_user)):
    """List all teams the authenticated user belongs to."""
    user_id = current_user["user_id"]

    with get_db() as db:
        rows = db.execute(
            "SELECT t.*, tm.role FROM teams t "
            "JOIN team_members tm ON tm.team_id = t.id "
            "WHERE tm.user_id = ?",
            (user_id,),
        ).fetchall()

    result = []
    for r in rows:
        team = dict(r)
        # Get member count
        with get_db() as db:
            members = db.execute(
                "SELECT COUNT(*) as cnt FROM team_members WHERE team_id = ?",
                (team["id"],),
            ).fetchone()
            team["member_count"] = members["cnt"]
        result.append(team)

    return result


@app.post("/api/teams/{team_id}/invite")
async def invite_to_team(
    team_id: int, req: TeamInvite, current_user: dict = Depends(get_current_user)
):
    """Invite a user to a team by email. The user must already have an account."""
    user_id = current_user["user_id"]
    now = datetime.utcnow().isoformat()

    with get_db() as db:
        # Verify team exists and current user is owner
        team = db.execute("SELECT * FROM teams WHERE id = ?", (team_id,)).fetchone()
        if not team:
            raise HTTPException(status_code=404, detail="Team not found")

        membership = db.execute(
            "SELECT * FROM team_members WHERE team_id = ? AND user_id = ? AND role = 'owner'",
            (team_id, user_id),
        ).fetchone()
        if not membership:
            raise HTTPException(status_code=403, detail="Only team owners can invite members")

        # Find the invitee
        invitee = db.execute(
            "SELECT * FROM users WHERE email = ?", (req.email.lower().strip(),)
        ).fetchone()
        if not invitee:
            raise HTTPException(status_code=404, detail="User not found. They must create an account first.")

        # Check if already a member
        existing = db.execute(
            "SELECT * FROM team_members WHERE team_id = ? AND user_id = ?",
            (team_id, invitee["id"]),
        ).fetchone()
        if existing:
            raise HTTPException(status_code=409, detail="User is already a team member")

        # Add as member
        cursor = db.execute(
            "INSERT INTO team_members (team_id, user_id, role, joined_at) VALUES (?, ?, 'member', ?)",
            (team_id, invitee["id"], now),
        )

    return {
        "team_id": team_id,
        "user_id": invitee["id"],
        "email": invitee["email"],
        "role": "member",
        "joined_at": now,
    }


@app.post("/api/teams/{team_id}/join")
async def join_team(team_id: int, current_user: dict = Depends(get_current_user)):
    """Join a team by ID (if the user has been invited / team exists)."""
    user_id = current_user["user_id"]
    now = datetime.utcnow().isoformat()

    with get_db() as db:
        team = db.execute("SELECT * FROM teams WHERE id = ?", (team_id,)).fetchone()
        if not team:
            raise HTTPException(status_code=404, detail="Team not found")

        # Check if already a member
        existing = db.execute(
            "SELECT * FROM team_members WHERE team_id = ? AND user_id = ?",
            (team_id, user_id),
        ).fetchone()
        if existing:
            raise HTTPException(status_code=409, detail="Already a team member")

        db.execute(
            "INSERT INTO team_members (team_id, user_id, role, joined_at) VALUES (?, ?, 'member', ?)",
            (team_id, user_id, now),
        )

    return {"team_id": team_id, "user_id": user_id, "role": "member", "joined_at": now}


@app.delete("/api/teams/{team_id}/members/{member_user_id}")
async def remove_team_member(
    team_id: int, member_user_id: int, current_user: dict = Depends(get_current_user)
):
    """Remove a member from a team. Only owners can remove; cannot remove yourself."""
    user_id = current_user["user_id"]

    with get_db() as db:
        # Verify current user is owner
        ownership = db.execute(
            "SELECT * FROM team_members WHERE team_id = ? AND user_id = ? AND role = 'owner'",
            (team_id, user_id),
        ).fetchone()
        if not ownership:
            raise HTTPException(status_code=403, detail="Only team owners can remove members")

        # Cannot remove yourself
        if member_user_id == user_id:
            raise HTTPException(status_code=400, detail="Cannot remove yourself from the team")

        # Check member exists
        member = db.execute(
            "SELECT * FROM team_members WHERE team_id = ? AND user_id = ?",
            (team_id, member_user_id),
        ).fetchone()
        if not member:
            raise HTTPException(status_code=404, detail="Team member not found")

        db.execute(
            "DELETE FROM team_members WHERE team_id = ? AND user_id = ?",
            (team_id, member_user_id),
        )

    return {"message": "Member removed"}


@app.put("/api/teams/{team_id}/members/{member_user_id}")
async def update_team_member_role(
    team_id: int,
    member_user_id: int,
    req: TeamMemberUpdate,
    current_user: dict = Depends(get_current_user),
):
    """Update a team member's role. Only owners can change roles."""
    user_id = current_user["user_id"]

    if req.role not in ("owner", "member"):
        raise HTTPException(status_code=422, detail="Role must be 'owner' or 'member'")

    with get_db() as db:
        # Verify current user is owner
        ownership = db.execute(
            "SELECT * FROM team_members WHERE team_id = ? AND user_id = ? AND role = 'owner'",
            (team_id, user_id),
        ).fetchone()
        if not ownership:
            raise HTTPException(status_code=403, detail="Only team owners can update roles")

        # Check member exists
        member = db.execute(
            "SELECT * FROM team_members WHERE team_id = ? AND user_id = ?",
            (team_id, member_user_id),
        ).fetchone()
        if not member:
            raise HTTPException(status_code=404, detail="Team member not found")

        db.execute(
            "UPDATE team_members SET role = ? WHERE team_id = ? AND user_id = ?",
            (req.role, team_id, member_user_id),
        )

    return {"team_id": team_id, "user_id": member_user_id, "role": req.role}


# ===========================================================================================
# USER PROFILE
# ===========================================================================================

@app.get("/api/profile")
async def get_profile(current_user: dict = Depends(get_current_user)):
    """Get the authenticated user's profile."""
    user_id = current_user["user_id"]

    with get_db() as db:
        user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

    return {
        "id": user["id"],
        "email": user["email"],
        "name": user["name"],
        "created_at": user["created_at"],
        "last_login_at": user["last_login_at"],
        "login_count": user["login_count"],
        "has_password": user["password_hash"] is not None,
        "has_google": user["google_id"] is not None,
    }


# ---------------------------------------------------------------------------
# Static file serving — frontend HTML/JS/CSS
# Mount AFTER API routes so /api/* takes priority
# ---------------------------------------------------------------------------
_static_dir = Path(__file__).parent

@app.get("/")
def serve_index():
    """Serve the portal index.html."""
    return FileResponse(_static_dir / "index.html")

# Serve static assets (JS, CSS, callback pages)
app.mount("/", StaticFiles(directory=str(_static_dir), html=False), name="static")


# ===========================================================================================
# ENTRYPOINT
# ===========================================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
