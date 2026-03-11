#!/usr/bin/env python3
"""Broad Reach Customer Portal — FastAPI Server
Migrated from CGI-bin api.py. Enhanced Analysis Engine v3 with real zone data and full rate card integration.
"""
import json, os, sqlite3, hashlib, uuid, math, re
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional, Any

from fastapi import FastAPI, Request, Query, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, HTMLResponse, StreamingResponse

# ─── Path Constants ────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOADS_DIR, exist_ok=True)
DB_PATH  = os.path.join(BASE_DIR, "portal.db")

# ─── Zone Data (loaded once at module start) ───────────────────────────────────
US_ZONES = {}   # zip3 -> {zip5 -> {carrier_key: zone, 's': state, ...}}
CA_ZONES = {}   # FSA  -> {carrier_key: zone, 'p': province, ...}

def _load_zone_data():
    global US_ZONES, CA_ZONES
    try:
        us_path = os.path.join(DATA_DIR, "us_zones.json")
        with open(us_path) as f:
            US_ZONES = json.load(f)
    except Exception:
        US_ZONES = {}
    try:
        ca_path = os.path.join(DATA_DIR, "ca_zones.json")
        with open(ca_path) as f:
            CA_ZONES = json.load(f)
    except Exception:
        CA_ZONES = {}

_load_zone_data()

# Carrier display name mapping
CARRIER_DISPLAY = {
    "OSM":              "OSM",
    "DHL":              "DHL eCommerce",
    "OnTrac":           "OnTrac",
    "UPS_2DA":          "UPS (master zone)",
    "USPS":             "USPS",
    "FedEx":            "FedEx",
    "SmartKargo_Std":   "SmartKargo Standard",
    "SmartKargo_2Day":  "SmartKargo 2Day",
    "Amazon":           "Amazon Shipping",
    "UniUni":           "UniUni",
    "UPS_Gnd":          "UPS Ground",
    "UPS_NDA":          "UPS Next Day Air",
    "UPS_NDA_Svr":      "UPS NDA Saver",
}

# Carrier → zone key mapping for rate analysis
# Maps a rate-card carrier name to the key in US_ZONES entries
CARRIER_ZONE_KEY = {
    "USPS":     "USPS",
    "FedEx":    "FedEx",
    "UPS":      "UPS_2DA",      # master zone (202-208)
    "UPS Ground": "UPS_Gnd",
    "UPS NDA":  "UPS_NDA",
    "UPS NDA Saver": "UPS_NDA_Svr",
    "Amazon":   "Amazon",
    "UniUni":   "UniUni",
    "DHL":      "DHL",
    "OnTrac":   "OnTrac",
    "OSM":      "OSM",
    "SmartKargo Standard": "SmartKargo_Std",
    "SmartKargo 2Day": "SmartKargo_2Day",
    "Sendle":   "USPS",         # Sendle uses USPS-equivalent zones
}


# ─── Database Setup ────────────────────────────────────────────────────────────
def get_db():
    db = sqlite3.connect(DB_PATH, check_same_thread=False)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=ON")
    return db

def init_db():
    db = get_db()
    db.executescript("""
    CREATE TABLE IF NOT EXISTS admins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        name TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS clients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        contact_name TEXT,
        logo_url TEXT,
        status TEXT DEFAULT 'Invited',
        invited_at TEXT DEFAULT (datetime('now')),
        documents_json TEXT DEFAULT '[]',
        setup_info_json TEXT DEFAULT '{}',
        password_hash TEXT DEFAULT NULL,
        invitation_sent_at TEXT DEFAULT NULL
    );
    CREATE TABLE IF NOT EXISTS rate_cards (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        service_type TEXT,
        carrier TEXT,
        pricing_type TEXT DEFAULT 'WEIGHT_POUNDS',
        description TEXT,
        rate_grid_json TEXT DEFAULT '{}',
        zone_mapping_json TEXT DEFAULT '{}',
        zone_key TEXT DEFAULT '',
        dim_divisor REAL DEFAULT 166,
        currency TEXT DEFAULT 'USD',
        country TEXT DEFAULT 'US',
        effective_date TEXT,
        expiration_date TEXT,
        version TEXT DEFAULT 'v1',
        status TEXT DEFAULT 'active',
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS shipping_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_id INTEGER NOT NULL,
        data_json TEXT NOT NULL,
        uploaded_at TEXT DEFAULT (datetime('now')),
        row_count INTEGER DEFAULT 0,
        summary_json TEXT DEFAULT '{}',
        FOREIGN KEY (client_id) REFERENCES clients(id)
    );
    CREATE TABLE IF NOT EXISTS analyses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_id INTEGER NOT NULL,
        config_json TEXT DEFAULT '{}',
        results_json TEXT DEFAULT '{}',
        status TEXT DEFAULT 'draft',
        created_at TEXT DEFAULT (datetime('now')),
        published_at TEXT,
        FOREIGN KEY (client_id) REFERENCES clients(id)
    );
    CREATE TABLE IF NOT EXISTS documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        category TEXT DEFAULT 'Other',
        filename TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        token TEXT UNIQUE NOT NULL,
        user_type TEXT NOT NULL,
        user_id INTEGER NOT NULL,
        created_at TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS zone_charts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        carrier TEXT,
        origin_zip TEXT,
        description TEXT,
        data_json TEXT DEFAULT '[]',
        row_count INTEGER DEFAULT 0,
        created_at TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        type TEXT NOT NULL,
        message TEXT NOT NULL,
        client_id INTEGER,
        read INTEGER DEFAULT 0,
        created_at TEXT DEFAULT (datetime('now')),
        FOREIGN KEY (client_id) REFERENCES clients(id)
    );
    CREATE TABLE IF NOT EXISTS client_notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_id INTEGER NOT NULL,
        type TEXT NOT NULL,
        message TEXT NOT NULL,
        read INTEGER DEFAULT 0,
        created_at TEXT DEFAULT (datetime('now')),
        FOREIGN KEY (client_id) REFERENCES clients(id)
    );
    CREATE TABLE IF NOT EXISTS access_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT NOT NULL,
        name TEXT,
        status TEXT DEFAULT 'pending',
        created_at TEXT DEFAULT (datetime('now')),
        reviewed_at TEXT,
        reviewed_by INTEGER
    );
    CREATE TABLE IF NOT EXISTS pending_emails (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_id INTEGER,
        to_email TEXT NOT NULL,
        to_name TEXT,
        subject TEXT NOT NULL,
        body TEXT NOT NULL,
        email_type TEXT DEFAULT 'invitation',
        status TEXT DEFAULT 'pending',
        created_at TEXT DEFAULT (datetime('now')),
        sent_at TEXT,
        FOREIGN KEY (client_id) REFERENCES clients(id)
    );
    """)
    # Add zone_key column if it doesn't exist (migration)
    try:
        db.execute("ALTER TABLE rate_cards ADD COLUMN zone_key TEXT DEFAULT ''")
    except Exception:
        pass
    # Add client password and invitation columns (migration)
    for col, default in [("password_hash", "NULL"), ("invitation_sent_at", "NULL")]:
        try:
            db.execute(f"ALTER TABLE clients ADD COLUMN {col} TEXT DEFAULT {default}")
        except Exception:
            pass
    # Add confirmed_at to shipping_data (migration)
    try:
        db.execute("ALTER TABLE shipping_data ADD COLUMN confirmed_at TEXT DEFAULT NULL")
    except Exception:
        pass
    # Add activity tracking, archive, invite count columns (migration)
    for col in ["last_login_at TEXT DEFAULT NULL", "login_count INTEGER DEFAULT 0",
                "archived INTEGER DEFAULT 0", "invite_count INTEGER DEFAULT 0"]:
        try:
            db.execute(f"ALTER TABLE clients ADD COLUMN {col}")
        except Exception:
            pass
    # Add expires_at to sessions (migration)
    try:
        db.execute("ALTER TABLE sessions ADD COLUMN expires_at TEXT DEFAULT NULL")
    except Exception:
        pass
    # Migrate pending_emails: make client_id nullable (for admin access approval emails)
    try:
        # Check if the column is NOT NULL by trying to insert NULL
        db.execute("INSERT INTO pending_emails (client_id, to_email, subject, body) VALUES (NULL, '__test__', '__test__', '__test__')")
        db.execute("DELETE FROM pending_emails WHERE to_email = '__test__'")
    except Exception:
        # client_id is NOT NULL — recreate table without that constraint
        try:
            db.execute("ALTER TABLE pending_emails RENAME TO pending_emails_old")
            db.execute("""
                CREATE TABLE pending_emails (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    client_id INTEGER,
                    to_email TEXT NOT NULL,
                    to_name TEXT,
                    subject TEXT NOT NULL,
                    body TEXT NOT NULL,
                    email_type TEXT DEFAULT 'invitation',
                    status TEXT DEFAULT 'pending',
                    created_at TEXT DEFAULT (datetime('now')),
                    sent_at TEXT
                )
            """)
            db.execute("INSERT INTO pending_emails SELECT * FROM pending_emails_old")
            db.execute("DROP TABLE pending_emails_old")
        except Exception:
            pass
    db.commit()

    # Migrate documents: add file_path and file_size columns
    try:
        db.execute("ALTER TABLE documents ADD COLUMN file_path TEXT DEFAULT ''")
    except Exception:
        pass
    try:
        db.execute("ALTER TABLE documents ADD COLUMN file_size INTEGER DEFAULT 0")
    except Exception:
        pass
    db.commit()
    return db


def migrate_db_sapt():
    """SAPT parity migration: adds new columns and tables for fuel, accessorials, service costs."""
    db = get_db()

    # ── Add new columns to rate_cards ──
    for col_def in [
        "fuel_rate REAL DEFAULT 0",
        "fuel_type TEXT DEFAULT 'percentage'",
        "fuel_discount REAL DEFAULT 0",
        "dim_threshold_cu_in REAL DEFAULT 0",
        "dim_divisor_alt REAL DEFAULT 0",
        "transit_days_json TEXT DEFAULT '{}'",
        "accessorials_json TEXT DEFAULT '{}'",
        "service_class TEXT DEFAULT 'economy'",
        "card_type TEXT DEFAULT 'sell_current'",
        "fuel_rate_buy REAL DEFAULT 0",
        "fuel_rate_sell REAL DEFAULT 0",
        "dim_divisor_buy REAL DEFAULT 166",
    ]:
        col_name = col_def.split()[0]
        try:
            db.execute(f"ALTER TABLE rate_cards ADD COLUMN {col_def}")
        except Exception:
            pass  # column already exists

    # ── Seed service_class for express cards ──
    express_keywords = ['Next Day', 'Overnight', '2Day', '2nd Day', 'Express', 'Priority Mail', 'Xpresspost']
    for kw in express_keywords:
        try:
            db.execute(
                "UPDATE rate_cards SET service_class = 'express' WHERE service_class = 'economy' AND name LIKE ?",
                (f'%{kw}%',)
            )
        except Exception:
            pass

    # ── Copy existing fuel_rate to fuel_rate_buy and fuel_rate_sell ──
    try:
        db.execute(
            "UPDATE rate_cards SET fuel_rate_buy = fuel_rate, fuel_rate_sell = fuel_rate "
            "WHERE fuel_rate_buy = 0 AND fuel_rate > 0"
        )
    except Exception:
        pass

    # ── Set card_type = 'sell_current' for all existing cards ──
    try:
        db.execute("UPDATE rate_cards SET card_type = 'sell_current' WHERE card_type IS NULL OR card_type = ''")
    except Exception:
        pass

    # ── Create accessorial_rules table ──
    db.execute("""
        CREATE TABLE IF NOT EXISTS accessorial_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            carrier TEXT,
            fee_type TEXT NOT NULL,
            condition_json TEXT DEFAULT '{}',
            amount REAL DEFAULT 0,
            amount_type TEXT DEFAULT 'flat',
            zone_rates_json TEXT DEFAULT '{}',
            apply_to_carriers TEXT DEFAULT '',
            active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)

    # ── Create service_cost_config table ──
    db.execute("""
        CREATE TABLE IF NOT EXISTS service_cost_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            line_haul_cost REAL DEFAULT 0.11,
            daily_pickup_cost REAL DEFAULT 100.0,
            pickup_days INTEGER DEFAULT 1,
            sort_cost REAL DEFAULT 0.06,
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """)

    # Insert default service cost row if none exists
    if db.execute("SELECT COUNT(*) FROM service_cost_config").fetchone()[0] == 0:
        db.execute("""
            INSERT INTO service_cost_config (line_haul_cost, daily_pickup_cost, pickup_days, sort_cost)
            VALUES (0.11, 100.0, 1, 0.06)
        """)

    # ── Seed accessorial rules if none exist ──
    if db.execute("SELECT COUNT(*) FROM accessorial_rules").fetchone()[0] == 0:
        rules = [
            # UPS rules
            ("UPS Additional Handling (weight >50 lbs)", "UPS", "additional_handling",
             json.dumps({"weight_over": 50}), 32.00, "flat", "{}", "UPS"),
            ("UPS Additional Handling (longest side >48\")", "UPS", "additional_handling",
             json.dumps({"length_over": 48}), 32.00, "flat", "{}", "UPS"),
            ("UPS Additional Handling (L+G >105\")", "UPS", "additional_handling",
             json.dumps({"lg_over": 105}), 32.00, "flat", "{}", "UPS"),
            ("UPS Large Package (L+G >130\")", "UPS", "oversize",
             json.dumps({"lg_over": 130}), 110.00, "flat", "{}", "UPS"),
            ("UPS Over Maximum Limits", "UPS", "over_max",
             json.dumps({"weight_over": 150, "length_over": 108, "lg_over": 165}), 1325.00, "flat", "{}", "UPS"),
            ("UPS Residential Surcharge", "UPS", "residential",
             json.dumps({}), 6.45, "flat", "{}", "UPS"),
            # FedEx rules
            ("FedEx Additional Handling (weight >50)", "FedEx", "additional_handling",
             json.dumps({"weight_over": 50}), 35.00, "flat", "{}", "FedEx"),
            ("FedEx Additional Handling (L+G >105)", "FedEx", "additional_handling",
             json.dumps({"lg_over": 105}), 35.00, "flat", "{}", "FedEx"),
            ("FedEx Oversize (L+G >130)", "FedEx", "oversize",
             json.dumps({"lg_over": 130}), 115.00, "flat", "{}", "FedEx"),
            ("FedEx Residential Surcharge", "FedEx", "residential",
             json.dumps({}), 6.90, "flat", "{}", "FedEx"),
            # DHL rules
            ("DHL NDQ Surcharge (Jan-Sep)", "DHL", "demand_surcharge",
             json.dumps({"month_min": 1, "month_max": 9}), 2.00, "flat", "{}", "DHL"),
            ("DHL NDQ Surcharge (Oct-Dec)", "DHL", "demand_surcharge",
             json.dumps({"month_min": 10, "month_max": 12}), 2.50, "flat", "{}", "DHL"),
            ("DHL Extra Length >22\"", "DHL", "nonstandard_length_22",
             json.dumps({"length_over": 22}), 4.50, "flat", "{}", "DHL"),
            ("DHL Extra Length >30\"", "DHL", "nonstandard_length_30",
             json.dumps({"length_over": 30}), 15.50, "flat", "{}", "DHL"),
            ("DHL Extra Volume >2cuft", "DHL", "nonstandard_volume",
             json.dumps({"volume_over_cuft": 2}), 18.00, "flat", "{}", "DHL"),
            # Amazon rules
            ("Amazon Additional Handling (weight >50)", "Amazon", "additional_handling",
             json.dumps({"weight_over": 50}), 30.00, "flat", "{}", "Amazon"),
            # USPS rules
            ("USPS Non-Standard Length >22\"", "USPS", "nonstandard_length_22",
             json.dumps({"length_over": 22}), 4.00, "flat", "{}", "USPS"),
            ("USPS Non-Standard Length >30\"", "USPS", "nonstandard_length_30",
             json.dumps({"length_over": 30}), 15.00, "flat", "{}", "USPS"),
            ("USPS Non-Standard Volume >2cuft", "USPS", "nonstandard_volume",
             json.dumps({"volume_over_cuft": 2}), 18.00, "flat", "{}", "USPS"),
        ]
        for (name, carrier, fee_type, cond_json, amount, amount_type, zone_rates, apply_carriers) in rules:
            db.execute("""
                INSERT INTO accessorial_rules
                    (name, carrier, fee_type, condition_json, amount, amount_type,
                     zone_rates_json, apply_to_carriers, active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
            """, (name, carrier, fee_type, cond_json, amount, amount_type,
                  zone_rates, apply_carriers))

    # ── Set fuel rates on existing cards based on carrier ──
    fuel_defaults = {
        "DHL":        {"fuel_rate": 0.07,   "fuel_type": "per_lb",     "fuel_discount": 0},
        "FedEx":      {"fuel_rate": 0.1825, "fuel_type": "percentage", "fuel_discount": 0.05},
        "UPS":        {"fuel_rate": 0.18,   "fuel_type": "percentage", "fuel_discount": 0},
        "USPS":       {"fuel_rate": 0,      "fuel_type": "percentage", "fuel_discount": 0},
        "OSM":        {"fuel_rate": 0.08,   "fuel_type": "percentage", "fuel_discount": 0.5},
        "OnTrac":     {"fuel_rate": 0.1775, "fuel_type": "percentage", "fuel_discount": 0.2},
        "Amazon":     {"fuel_rate": 0.16,   "fuel_type": "percentage", "fuel_discount": 0},
        "Smartkargo": {"fuel_rate": 0.05,   "fuel_type": "percentage", "fuel_discount": 0},
        "UniUni":     {"fuel_rate": 0,      "fuel_type": "percentage", "fuel_discount": 0},
        "Sendle":     {"fuel_rate": 0,      "fuel_type": "percentage", "fuel_discount": 0},
    }
    for carrier_name, fuel_cfg in fuel_defaults.items():
        try:
            db.execute("""
                UPDATE rate_cards SET fuel_rate = ?, fuel_type = ?, fuel_discount = ?
                WHERE carrier LIKE ? AND (fuel_rate IS NULL OR fuel_rate = 0)
            """, (fuel_cfg["fuel_rate"], fuel_cfg["fuel_type"], fuel_cfg["fuel_discount"],
                  f"%{carrier_name}%"))
        except Exception:
            pass

    # ── Phase 4: Zone file versions table ──
    db.execute("""
        CREATE TABLE IF NOT EXISTS zone_file_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            carrier TEXT NOT NULL,
            country TEXT DEFAULT 'US',
            file_name TEXT,
            effective_date TEXT,
            data_json TEXT,
            is_active INTEGER DEFAULT 1,
            uploaded_at TEXT DEFAULT (datetime('now'))
        )
    """)

    # ── Phase 4: DAS versions table ──
    db.execute("""
        CREATE TABLE IF NOT EXISTS das_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            carrier TEXT NOT NULL,
            file_name TEXT,
            effective_date TEXT,
            data_json TEXT,
            is_active INTEGER DEFAULT 1,
            uploaded_at TEXT DEFAULT (datetime('now'))
        )
    """)

    # ── Phase 5: Service cost overrides (per rate card) ──
    db.execute("""
        CREATE TABLE IF NOT EXISTS service_cost_overrides (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rate_card_id INTEGER,
            line_haul_cost REAL,
            line_haul_type TEXT DEFAULT 'per_piece',
            pickup_cost REAL,
            sort_cost REAL,
            FOREIGN KEY (rate_card_id) REFERENCES rate_cards(id)
        )
    """)

    # ── Phase 4: Add start_date/end_date to accessorial_rules ──
    for col in ["start_date TEXT", "end_date TEXT"]:
        try:
            db.execute(f"ALTER TABLE accessorial_rules ADD COLUMN {col}")
        except Exception:
            pass

    # ── Create induction_locations table ──
    db.execute("""
        CREATE TABLE IF NOT EXISTS induction_locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            display_name TEXT,
            country TEXT DEFAULT 'US',
            zip_or_postal TEXT,
            is_primary INTEGER DEFAULT 0,
            active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)

    # ── Create zone_skip_config table ──
    db.execute("""
        CREATE TABLE IF NOT EXISTS zone_skip_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            induction_location_id INTEGER,
            carrier TEXT,
            service_name TEXT DEFAULT '',
            zone_skip_allowed INTEGER DEFAULT 1,
            zone_skip_fixed REAL DEFAULT 0,
            zone_skip_per_lb REAL DEFAULT 0,
            service_available INTEGER DEFAULT 1,
            FOREIGN KEY (induction_location_id) REFERENCES induction_locations(id)
        )
    """)

    # ── Seed default induction locations if empty ──
    if db.execute("SELECT COUNT(*) FROM induction_locations").fetchone()[0] == 0:
        db.execute("INSERT INTO induction_locations (name, display_name, country, zip_or_postal, is_primary) VALUES ('NJ', 'New Jersey', 'US', '07001', 1)")
        db.execute("INSERT INTO induction_locations (name, display_name, country, zip_or_postal, is_primary) VALUES ('LA', 'Los Angeles', 'US', '90001', 0)")
        db.execute("INSERT INTO induction_locations (name, display_name, country, zip_or_postal, is_primary) VALUES ('YYZ', 'Toronto (YYZ)', 'CA', 'M5V', 1)")
        db.execute("INSERT INTO induction_locations (name, display_name, country, zip_or_postal, is_primary) VALUES ('YVR', 'Vancouver (YVR)', 'CA', 'V6B', 0)")
        db.execute("INSERT INTO induction_locations (name, display_name, country, zip_or_postal, is_primary) VALUES ('YYC', 'Calgary (YYC)', 'CA', 'T2P', 0)")

    db.commit()
    db.close()


# ─── Rate Card Seeding Helpers ─────────────────────────────────────────────────

def _insert_rate_card(db, name, carrier, service_type, pricing_type, description,
                      rate_grid, zone_key="", dim_divisor=166, currency="USD",
                      country="US", effective_date="2026-01-01", version="v1"):
    """Insert a single rate card, ignoring duplicates by name."""
    existing = db.execute("SELECT id FROM rate_cards WHERE name = ?", (name,)).fetchone()
    if existing:
        return existing["id"]
    db.execute("""
        INSERT INTO rate_cards
            (name, service_type, carrier, pricing_type, description, rate_grid_json,
             zone_mapping_json, zone_key, dim_divisor, currency, country,
             effective_date, version, status)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,'active')
    """, (name, service_type, carrier, pricing_type, description,
          json.dumps(rate_grid), '{}', zone_key, float(dim_divisor),
          currency, country, effective_date, version))
    return db.execute("SELECT last_insert_rowid()").fetchone()[0]


def _carrier_to_zone_key(carrier):
    """Map rate card carrier name to the zone key in US_ZONES entries."""
    m = {
        "USPS":       "USPS",
        "FedEx":      "FedEx",
        "UPS":        "UPS_Gnd",   # default UPS to Ground zone key
        "UPS Canada": "UPS_CA",
        "Amazon":     "Amazon",
        "UniUni":     "UniUni",
        "DHL":        "DHL",
        "OnTrac":     "OnTrac",
        "OSM":        "OSM",
        "Sendle":     "USPS",
    }
    return m.get(carrier, "USPS")

def _seed_usps_cards(db):
    """Load USPS rate cards from the existing rate_cards_seed.json."""
    seed_path = os.path.join(BASE_DIR, "rate_cards_seed.json")
    try:
        with open(seed_path) as f:
            all_rate_cards = json.load(f)
        for card in all_rate_cards:
            existing = db.execute("SELECT id FROM rate_cards WHERE name = ?",
                                  (card["name"],)).fetchone()
            if existing:
                continue
            db.execute("""INSERT INTO rate_cards
                (name, service_type, carrier, pricing_type, description,
                 rate_grid_json, zone_mapping_json, zone_key, dim_divisor,
                 currency, country, version, status)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,'active')""",
                (card["name"], card["service_type"], card["carrier"],
                 card["pricing_type"], card["description"],
                 json.dumps(card["rate_grid"]), json.dumps(card["zone_mapping"]),
                 _carrier_to_zone_key(card.get("carrier", "USPS")),
                 float(card["dim_divisor"]),
                 card.get("currency", "USD"), card.get("country", "US"),
                 card.get("version", "v1")))
        return True
    except Exception as e:
        # Fallback minimal USPS card
        _insert_rate_card(db, "USPS Ground Advantage", "USPS", "Ground Advantage",
                          "WEIGHT_POUNDS", "Fallback rate card", {}, "USPS")
        return False


def _seed_fedex_cards(db):
    """Load FedEx rate cards from fedex_net_rates.json.
    Converts weight -> zone structure into standard rate_grid."""
    path = os.path.join(DATA_DIR, "fedex_net_rates.json")
    try:
        with open(path) as f:
            fn = json.load(f)
    except Exception:
        return 0
    count = 0
    for svc_name, svc_data in fn.items():
        # Rate grid is already weight -> zone -> price
        rates = svc_data.get("rates", {})
        if not rates:
            continue
        # Normalise weight keys: FedEx uses 'Package_N' style; we store as-is
        # The lookup_rate function will handle string keys by float cast where possible
        name = f"FedEx {svc_name}" if not svc_name.startswith("FedEx") else svc_name
        _insert_rate_card(db, name, "FedEx", svc_name, "WEIGHT_POUNDS",
                          f"FedEx net rate — {svc_name}",
                          rates, "FedEx", 139, "USD", "US", "2026-01-01")
        count += 1
    return count


def _seed_fedex_2day_internal(db):
    """Load FedEx 2Day internal cost card."""
    path = os.path.join(DATA_DIR, "fedex_2day_internal.json")
    try:
        with open(path) as f:
            fi = json.load(f)
    except Exception:
        return 0
    rates = fi.get("rates", {})
    if not rates:
        return 0
    _insert_rate_card(db, "FedEx 2Day (Internal Cost)", "FedEx",
                      "2Day Internal", "WEIGHT_POUNDS",
                      "FedEx 2Day Wizmo internal cost",
                      rates, "FedEx", 139, "USD", "US",
                      fi.get("effective_date", "2026-01-01"))
    return 1


def _seed_ups_bid_cards(db):
    """Load UPS US Bid rate cards from ups_us_bid_rates.json.
    Rates are indexed zone -> weight -> price; we transpose to weight -> zone -> price."""
    path = os.path.join(DATA_DIR, "ups_us_bid_rates.json")
    try:
        with open(path) as f:
            ub = json.load(f)
    except Exception:
        return 0
    count = 0
    # Skip niche freight drop-off variants that aren't needed for customer analysis
    SKIP_BID = {"Freight TM-Drop Off"}
    for svc_name, svc_data in ub.items():
        if any(skip in svc_name for skip in SKIP_BID):
            continue
        raw_rates = svc_data.get("rates", {})
        if not raw_rates:
            continue
        # raw_rates: {zone_str: {weight_str: price}}
        # transpose to weight -> zone -> price for standard lookup
        rate_grid = {}
        for zone_str, weight_dict in raw_rates.items():
            for weight_str, price in weight_dict.items():
                if weight_str not in rate_grid:
                    rate_grid[weight_str] = {}
                rate_grid[weight_str][zone_str] = price
        # Determine which zone key to use based on service name
        if "Next Day Air Saver" in svc_name or "NDA Saver" in svc_name:
            zone_key = "UPS_NDA_Svr"
        elif "Next Day Air" in svc_name:
            zone_key = "UPS_NDA"
        elif "2nd Day" in svc_name or "2 Day" in svc_name:
            zone_key = "UPS_2DA"
        elif "Ground Saver" in svc_name:
            zone_key = "UPS_Gnd"
        elif "Ground" in svc_name:
            zone_key = "UPS_Gnd"
        else:
            zone_key = "UPS_2DA"
        metadata = svc_data.get("metadata", {})
        eff_date = "2026-01-01"
        name = f"UPS Bid — {svc_name}"
        _insert_rate_card(db, name, "UPS", svc_name, "WEIGHT_POUNDS",
                          f"UPS Wizmo bid rate — {svc_name}",
                          rate_grid, zone_key, 139, "USD", "US", eff_date)
        count += 1
    return count


def _seed_ups_list_cards(db):
    """Load UPS US List rate cards from ups_us_list_rates.json.
    Rates are indexed zone -> weight -> price (where zone = 'Zone 102' etc.).
    Skips 'List Rates' and 'CWT List' sheets that were badly parsed (zone keys are prices)."""
    path = os.path.join(DATA_DIR, "ups_us_list_rates.json")
    try:
        with open(path) as f:
            ul = json.load(f)
    except Exception:
        return 0
    # Skip sheets with broken zone parsing (zone keys are prices, not zone numbers)
    SKIP_SHEETS = {
        "SURCHARGES",
        "1DA List Rates",
        "Saver List Rates",
        "2DA AM List Rates",
        "2DA List Rates",
        "3DS List Rates",
        "Ground Comm List Rates",
        "Ground Resi List Rates",
        "Ground CWT List",
    }
    count = 0
    for sheet_name, svc_data in ul.items():
        if sheet_name in SKIP_SHEETS:
            continue
        raw_rates = svc_data.get("rates", {})
        if not raw_rates:
            continue
        # raw_rates: {"Zone 102": {"1.0": price, ...}, ...}
        # Normalise zone keys: strip "Zone " prefix -> "102", "103", etc.
        rate_grid = {}
        for zone_str, weight_dict in raw_rates.items():
            clean_zone = zone_str.replace("Zone ", "").strip()
            for weight_str, price in weight_dict.items():
                if price is None:
                    continue
                if weight_str not in rate_grid:
                    rate_grid[weight_str] = {}
                rate_grid[weight_str][clean_zone] = price
        sn_lower = sheet_name.lower()
        if "next day" in sn_lower or "1da" in sn_lower:
            zone_key = "UPS_NDA"
        elif "saver" in sn_lower:
            zone_key = "UPS_NDA_Svr"
        elif "2nd day am" in sn_lower or "2da am" in sn_lower:
            zone_key = "UPS_2DA"
        elif "2nd day" in sn_lower or "2da" in sn_lower:
            zone_key = "UPS_2DA"
        elif "ground" in sn_lower:
            zone_key = "UPS_Gnd"
        else:
            zone_key = "UPS_Gnd"
        name = f"UPS List — {sheet_name}"
        _insert_rate_card(db, name, "UPS", sheet_name, "WEIGHT_POUNDS",
                          f"UPS 2026 Daily Rate — {sheet_name}",
                          rate_grid, zone_key, 139, "USD", "US", "2026-01-01")
        count += 1
    return count


def _seed_ups_canada_cards(db):
    """Load UPS Canada rate cards (CAD).
    Rates indexed zone -> weight -> price."""
    path = os.path.join(DATA_DIR, "ups_canada_rates.json")
    try:
        with open(path) as f:
            uc = json.load(f)
    except Exception:
        return 0
    count = 0
    for sheet_name, svc_data in uc.items():
        svc_display = svc_data.get("service_name", sheet_name)
        raw_rates = svc_data.get("rates", {})
        if not raw_rates:
            continue
        # raw_rates: {zone_str: {weight_str: price}}
        rate_grid = {}
        for zone_str, weight_dict in raw_rates.items():
            for weight_str, price in weight_dict.items():
                if price is None:
                    continue
                if weight_str not in rate_grid:
                    rate_grid[weight_str] = {}
                rate_grid[weight_str][zone_str] = price
        # envelope rates if present
        env_rates = svc_data.get("envelope_rates", {})
        if env_rates:
            for zone_str, price in env_rates.items():
                if "Envelope" not in rate_grid:
                    rate_grid["Envelope"] = {}
                rate_grid["Envelope"][zone_str] = price
        name = f"UPS Canada — {svc_display}"
        _insert_rate_card(db, name, "UPS Canada", svc_display, "WEIGHT_POUNDS",
                          f"UPS Canada 2026 rates (CAD) — {svc_display}",
                          rate_grid, "UPS_CA", 139, "CAD", "CA", "2026-01-01")
        count += 1
    return count


def _seed_amazon_cards(db):
    """Load Amazon rates from amazon_rates.json.
    Rates are a list of {weight_lb, zone_1, zone_2.0, ...}."""
    path = os.path.join(DATA_DIR, "amazon_rates.json")
    try:
        with open(path) as f:
            ar = json.load(f)
    except Exception:
        return 0
    count = 0
    services = ar.get("services", {})
    for svc_key, svc_data in services.items():
        rate_list = svc_data.get("rates", [])
        if not rate_list:
            continue
        # Convert list to weight -> zone -> price
        # Zone keys like "zone_2.0" -> normalise to "2", "3", etc.
        rate_grid = {}
        for row in rate_list:
            weight = str(row.get("weight_lb", ""))
            if not weight:
                continue
            rate_grid[weight] = {}
            for k, v in row.items():
                if k.startswith("zone_") and v is not None:
                    zone_raw = k[5:]  # e.g. "2.0", "3.0", "1", "9"
                    try:
                        zone_clean = str(int(float(zone_raw)))
                    except (ValueError, TypeError):
                        zone_clean = zone_raw
                    rate_grid[weight][zone_clean] = v
        svc_name = svc_data.get("service_name", svc_key)
        name = f"Amazon — {svc_name}"
        eff = ar.get("effective_date", "2026-01-01")
        _insert_rate_card(db, name, "Amazon", svc_name, "WEIGHT_POUNDS",
                          f"Amazon Shipping via RocketShip — {svc_name}",
                          rate_grid, "Amazon", 139, "USD", "US", eff)
        count += 1
    return count


def _seed_uniuni_cards(db):
    """Load UniUni rates from uniuni_rates.json.
    Rates are a list of {weight, unit, Zone1, Zone2, ...} in ounces."""
    path = os.path.join(DATA_DIR, "uniuni_rates.json")
    try:
        with open(path) as f:
            uu = json.load(f)
    except Exception:
        return 0
    rate_list = uu.get("rates", [])
    if not rate_list:
        return 0
    # UniUni uses ounce weights, Zone1-Zone8
    rate_grid = {}
    for row in rate_list:
        weight_oz = row.get("weight", "")
        if not weight_oz:
            continue
        weight_key = str(weight_oz)
        rate_grid[weight_key] = {}
        for zone_k in ["Zone1", "Zone2", "Zone3", "Zone4",
                        "Zone5", "Zone6", "Zone7", "Zone8"]:
            if zone_k in row and row[zone_k] is not None:
                # Map Zone1 -> "1", Zone2 -> "2", etc.
                zone_num = zone_k.replace("Zone", "")
                rate_grid[weight_key][zone_num] = row[zone_k]
    _insert_rate_card(db, "UniUni 2026", "UniUni", "Standard",
                      "WEIGHT_OUNCES",
                      "UniUni 2026 rates (oz-based, zones 1-8)",
                      rate_grid, "UniUni", 139, "USD", "US", "2026-01-01")
    return 1


def _seed_sendle_cards(db):
    """Load Sendle Saver rates."""
    path = os.path.join(DATA_DIR, "sendle_rates.json")
    try:
        with open(path) as f:
            sr = json.load(f)
    except Exception:
        return 0
    raw_rates = sr.get("rates", {})
    if not raw_rates:
        return 0
    # rates: {weight_key: {weight_lb, size_ft3, prices: {zone: price}}}
    rate_grid = {}
    for weight_key, wdata in raw_rates.items():
        prices = wdata.get("prices", {})
        if not prices:
            continue
        rate_grid[weight_key] = prices
    _insert_rate_card(db, "Sendle Saver", "Sendle", "Saver",
                      "WEIGHT_POUNDS",
                      "Sendle Saver 2025 rates",
                      rate_grid, "USPS", 139, "USD", "US", "2025-01-01")
    return 1


def seed_rate_cards(db):
    """Seed all rate cards from data files. Called once at init."""
    counts = {}
    counts["usps"]   = 23 if _seed_usps_cards(db) else 1
    counts["fedex"]  = _seed_fedex_cards(db)
    counts["fedex2day_internal"] = _seed_fedex_2day_internal(db)
    counts["ups_bid"]    = _seed_ups_bid_cards(db)
    counts["ups_list"]   = _seed_ups_list_cards(db)
    counts["ups_canada"] = _seed_ups_canada_cards(db)
    counts["amazon"]     = _seed_amazon_cards(db)
    counts["uniuni"]     = _seed_uniuni_cards(db)
    counts["sendle"]     = _seed_sendle_cards(db)
    db.commit()
    return counts


# ─── Demo Data Seeding ────────────────────────────────────────────────────────
def seed_demo_data(db):
    if db.execute("SELECT COUNT(*) FROM admins").fetchone()[0] > 0:
        return

    # SECURITY: Default password now read from env var. Fall back to random UUID if not set.
    default_pw = os.environ.get("ADMIN_DEFAULT_PASSWORD", str(uuid.uuid4()))
    pw_hash = hashlib.sha256(default_pw.encode()).hexdigest()
    db.execute("INSERT INTO admins (email, password_hash, name) VALUES (?, ?, ?)",
               ("craig@shipwizmo.com", pw_hash, "Craig"))
    # NOTE: SHA-256 password hashing is legacy from CGI. Migration to bcrypt is recommended.
    # See ARCHITECTURE.md section 'Security Migration Notes'.

    docs = [
        ("Broad Reach Service Overview", "Service Guide", "br-service-overview.pdf"),
        ("Cross-Border Shipping Guide",  "Service Guide", "cross-border-guide.pdf"),
        ("Pricing Proposal Template",    "Proposal",      "pricing-proposal.pdf"),
        ("Asendia Network Map",          "Service Guide", "network-map.pdf"),
        ("Onboarding Checklist",         "Other",         "onboarding-checklist.pdf"),
    ]
    for name, cat, fn in docs:
        db.execute("INSERT INTO documents (name, category, filename) VALUES (?, ?, ?)",
                   (name, cat, fn))

    # Seed all rate cards
    seed_rate_cards(db)

    # ── Clients ──
    db.execute("""INSERT INTO clients (company_name, email, contact_name, logo_url, status, invited_at, documents_json)
                  VALUES (?, ?, ?, ?, ?, ?, ?)""",
               ("Acme Commerce", "sarah@acmecommerce.com", "Sarah Chen", "",
                "Analysis Pending", "2026-02-15T10:00:00", json.dumps([1, 2, 3])))

    db.execute("""INSERT INTO clients (company_name, email, contact_name, logo_url, status, invited_at, documents_json)
                  VALUES (?, ?, ?, ?, ?, ?, ?)""",
               ("Beta Brands", "mike@betabrands.com", "Mike Torres", "",
                "Analysis Pending", "2026-02-20T14:00:00", json.dumps([1, 2])))

    # ── Sample shipping data for Acme Commerce (50 shipments with realistic data) ──
    import random
    random.seed(42)
    carriers = ["UPS", "FedEx", "USPS"]
    services_map = {
        "UPS":   ["UPS Ground", "UPS 2nd Day Air"],
        "FedEx": ["FedEx Home Delivery", "FedEx Ground"],
        "USPS":  ["Ground Advantage", "Priority Mail"]
    }
    states = ["CA", "NY", "TX", "FL", "IL", "WA", "OH", "PA", "GA", "NC"]
    zips_origin = ["90210", "10001", "73301", "33101", "60601"]
    zips_dest   = ["98101", "30301", "43201", "19101", "27601",
                   "85001", "55401", "80201", "97201", "84101"]

    shipments = []
    for i in range(50):
        w   = round(random.uniform(0.5, 35), 1)
        bw  = round(w * random.uniform(1.0, 1.25), 1)
        carrier = random.choice(carriers)
        service = random.choice(services_map[carrier])
        orig_zip  = random.choice(zips_origin)
        dest_zip  = random.choice(zips_dest)
        orig_state = random.choice(states[:5])
        dest_state = random.choice(states[5:])
        zone = random.randint(2, 8)
        l = random.randint(6, 24)
        w_dim = random.randint(4, 18)
        h = random.randint(2, 12)
        current_price = round(5 + bw * 0.95 + zone * 1.80 + random.uniform(1, 8), 2)
        ship_date = f"2026-{random.randint(1,2):02d}-{random.randint(1,28):02d}"
        shipments.append({
            "ship_date": ship_date,
            "tracking":  f"1Z{random.randint(100000,999999)}{random.randint(1000,9999)}",
            "carrier": carrier, "service": service,
            "weight": w, "billed_weight": bw,
            "length": l, "width": w_dim, "height": h,
            "origin_zip": orig_zip, "origin_state": orig_state, "origin_country": "US",
            "dest_zip": dest_zip, "dest_state": dest_state, "dest_country": "US",
            "price": current_price
        })

    summary = {
        "row_count":       50,
        "date_range":      "2026-01-01 to 2026-02-28",
        "carriers":        list(set(s["carrier"] for s in shipments)),
        "total_spend":     round(sum(s["price"] for s in shipments), 2),
        "avg_weight":      round(sum(s["weight"] for s in shipments) / 50, 1),
        "avg_billed_weight": round(sum(s["billed_weight"] for s in shipments) / 50, 1),
        "weight_unit":     "lbs",
        "unit_system":     {"weight": "lbs", "dimensions": "in"},
        "currency":        "USD",
        "origin_mode":     "multi",
        "origin_defaults": None
    }

    db.execute("""INSERT INTO shipping_data (client_id, data_json, row_count, summary_json)
                  VALUES (?, ?, ?, ?)""",
               (1, json.dumps(shipments), 50, json.dumps(summary)))

    # ── Pre-run analysis for Acme Commerce ──
    # Try to pick real card IDs: USPS PM (1), USPS GA (3), first UPS card, first FedEx card
    usps_pm = db.execute("SELECT id FROM rate_cards WHERE name LIKE 'USPS Priority Mail%' LIMIT 1").fetchone()
    usps_ga = db.execute("SELECT id FROM rate_cards WHERE name LIKE 'USPS Ground Advantage%' LIMIT 1").fetchone()
    ups_gnd = db.execute("SELECT id FROM rate_cards WHERE name LIKE 'UPS Bid%Ground Commercial%' LIMIT 1").fetchone()
    if not ups_gnd:
        ups_gnd = db.execute("SELECT id FROM rate_cards WHERE carrier = 'UPS' LIMIT 1").fetchone()
    fedex_h = db.execute("SELECT id FROM rate_cards WHERE name LIKE 'FedEx%Ground%' LIMIT 1").fetchone()
    if not fedex_h:
        fedex_h = db.execute("SELECT id FROM rate_cards WHERE carrier = 'FedEx' LIMIT 1").fetchone()

    rc_ids = [r["id"] for r in [usps_pm, usps_ga, ups_gnd, fedex_h] if r]
    if not rc_ids:
        rc_ids = [1]

    markups = {str(i): {"pct": 0.15, "per_lb": 0.10, "per_shipment": 1.00} for i in rc_ids}
    config  = {"rate_card_ids": rc_ids, "markups": markups}
    results = run_rate_analysis(shipments, config, db, unit_system={"weight": "lbs", "dimensions": "in"})
    results["currency"] = "USD"
    db.execute("""INSERT INTO analyses (client_id, config_json, results_json, status)
                  VALUES (?, ?, ?, 'draft')""",
               (1, json.dumps(config), json.dumps(results)))

    # ── Beta Brands shipping data ──
    shipments2 = []
    for i in range(30):
        w   = round(random.uniform(0.3, 25), 1)
        bw  = round(w * random.uniform(1.0, 1.30), 1)
        carrier = random.choice(carriers)
        service = random.choice(services_map[carrier])
        orig_zip  = random.choice(zips_origin)
        dest_zip  = random.choice(zips_dest)
        orig_state = random.choice(states[:5])
        dest_state = random.choice(states[5:])
        zone = random.randint(2, 7)
        current_price = round(4 + bw * 0.90 + zone * 1.40 + random.uniform(1, 7), 2)
        ship_date = f"2026-{random.randint(1,2):02d}-{random.randint(1,28):02d}"
        shipments2.append({
            "ship_date": ship_date,
            "tracking":  f"1Z{random.randint(100000,999999)}{random.randint(1000,9999)}",
            "carrier": carrier, "service": service,
            "weight": w, "billed_weight": bw,
            "length": random.randint(6, 20), "width": random.randint(4, 14),
            "height": random.randint(2, 10),
            "origin_zip": orig_zip, "origin_state": orig_state, "origin_country": "US",
            "dest_zip": dest_zip, "dest_state": dest_state, "dest_country": "US",
            "price": current_price
        })

    summary2 = {
        "row_count":         30,
        "date_range":        "2026-01-15 to 2026-02-25",
        "carriers":          list(set(s["carrier"] for s in shipments2)),
        "total_spend":       round(sum(s["price"] for s in shipments2), 2),
        "avg_weight":        round(sum(s["weight"] for s in shipments2) / 30, 1),
        "avg_billed_weight": round(sum(s["billed_weight"] for s in shipments2) / 30, 1),
        "weight_unit":       "lbs",
        "unit_system":       {"weight": "lbs", "dimensions": "in"},
        "currency":          "CAD",
        "origin_mode":       "multi",
        "origin_defaults":   None
    }

    db.execute("""INSERT INTO shipping_data (client_id, data_json, row_count, summary_json)
                  VALUES (?, ?, ?, ?)""",
               (2, json.dumps(shipments2), 30, json.dumps(summary2)))

    # ── Seed zone chart demo data ──
    sample_zone_data = []
    zone_map = [
        ("0",2),("1",7),("2",7),("3",6),("4",5),("5",5),("6",4),("7",4),
        ("8",3),("9",2),("10",8),("11",8),("12",8),("13",8),("14",8),("15",8),
        ("19",8),("20",8),("21",8),("22",8),("27",7),("28",7),("29",7),
        ("30",6),("31",6),("32",6),("33",6),("34",6),("35",6),("36",6),
        ("37",5),("38",5),("39",5),("43",5),("44",5),("45",5),("46",5),
        ("47",5),("48",5),("49",5),("50",4),("51",4),("52",4),("53",4),
        ("54",4),("55",4),("56",4),("57",4),("58",4),("59",4),("60",3),
        ("61",3),("62",3),("63",3),("64",3),("65",3),("66",3),("67",3),
        ("68",3),("69",3),("70",4),("71",4),("72",4),("73",4),("74",4),
        ("75",4),("76",4),("77",4),("78",4),("79",4),("80",3),("81",3),
        ("83",3),("84",2),("85",2),("86",2),("87",3),("88",3),("89",3),
        ("90",2),("91",2),("92",2),("93",2),("94",2),("95",2),("96",2),
        ("97",3),("98",3),("99",3),
    ]
    for prefix, zone in zone_map:
        dest_zip = prefix.zfill(3) + "01"
        sample_zone_data.append({
            "dest_zip_prefix": prefix.zfill(3),
            "dest_zip": dest_zip,
            "zone": str(zone)
        })
    db.execute("""
        INSERT INTO zone_charts (name, carrier, origin_zip, description, data_json, row_count)
        VALUES (?, ?, ?, ?, ?, ?)""",
        ("USPS Ground Advantage Zones (from 90210)", "USPS", "90210",
         "Sample zone chart for origin zip 90210 (Beverly Hills, CA). Maps dest zip prefixes to zones.",
         json.dumps(sample_zone_data), len(sample_zone_data)))

    db.commit()


# ─── Zone Lookup ──────────────────────────────────────────────────────────────

def lookup_us_zone(dest_zip, carrier_key=None):
    """Look up zone from US_ZONES for a given dest ZIP and optional carrier key.
    Returns (zone_str, state, das_flag) or (None, None, False) if not found."""
    zip5 = str(dest_zip).strip().zfill(5)
    zip3 = zip5[:3]
    if zip3 not in US_ZONES:
        return None, None, False
    zip5_data = US_ZONES[zip3].get(zip5)
    if not zip5_data:
        # Try the first entry in this zip3 group as a fallback
        first_z5 = next(iter(US_ZONES[zip3]), None)
        zip5_data = US_ZONES[zip3].get(first_z5) if first_z5 else None
    if not zip5_data:
        return None, None, False
    state = zip5_data.get("s", "")
    das = False
    if carrier_key:
        das_key = f"{carrier_key}_DAS"
        das = zip5_data.get(das_key) == "DAS"
        zone = zip5_data.get(carrier_key)
        if zone is None:
            # Fallback chain: UPS sub-keys fall back to UPS_2DA master
            if carrier_key in ("UPS_Gnd", "UPS_NDA", "UPS_NDA_Svr"):
                master = zip5_data.get("UPS_2DA")
                if master is not None:
                    # UPS_2DA gives 3-digit zone (202-208)
                    # UPS_Gnd uses 2-8, UPS_NDA uses 102-108, UPS_NDA_Svr uses 132-138
                    try:
                        base = int(str(master)) % 100  # 203 -> 3
                        if carrier_key == "UPS_Gnd":
                            zone = str(base)
                        elif carrier_key == "UPS_NDA":
                            zone = str(100 + base)
                        elif carrier_key == "UPS_NDA_Svr":
                            zone = str(130 + base)
                    except (ValueError, TypeError):
                        zone = master
        return zone, state, das
    # Return all zones if no specific carrier requested
    return zip5_data, state, das


def lookup_ca_zone(postal_code, carrier_key=None):
    """Look up zone from CA_ZONES using the FSA (first 3 chars)."""
    fsa = str(postal_code)[:3].upper()
    if fsa not in CA_ZONES:
        return None, None
    fsa_data = CA_ZONES[fsa]
    province = fsa_data.get("p", "")
    if carrier_key:
        return fsa_data.get(carrier_key), province
    return fsa_data, province


# ─── Rate Analysis Engine V3 ──────────────────────────────────────────────────
DIM_DIVISOR = 166

def determine_zone(origin_zip, dest_zip, carrier_key=None,
                   zone_mapping=None, zone_chart_data=None):
    """Determine shipping zone. Priority order:
      1. Real SAPT zone data (US_ZONES / CA_ZONES)
      2. Zone chart data (uploaded CSV)
      3. Zone mapping ranges
      4. Heuristic fallback
    Returns an integer zone (or zone string for carriers with 3-digit zones).
    """
    dest_str = str(dest_zip).strip() if dest_zip else ""

    # ── 1. Real zone data ──────────────────────────────────────────────────────
    if dest_str:
        is_canadian = len(dest_str) >= 1 and dest_str[0].isalpha()
        if is_canadian:
            zone_val, _ = lookup_ca_zone(dest_str, carrier_key)
            if zone_val:
                try:
                    return int(zone_val)
                except (ValueError, TypeError):
                    return zone_val
        else:
            zone_val, state, _ = lookup_us_zone(dest_str, carrier_key)
            if zone_val is not None:
                try:
                    return int(zone_val)
                except (ValueError, TypeError):
                    return zone_val
            # If no carrier_key, try USPS as default
            if not carrier_key:
                zone_val, state, _ = lookup_us_zone(dest_str, "USPS")
                if zone_val is not None:
                    try:
                        return int(zone_val)
                    except (ValueError, TypeError):
                        return zone_val

    # ── 2. Zone chart data ─────────────────────────────────────────────────────
    if zone_chart_data and isinstance(zone_chart_data, list):
        try:
            dest_prefix3 = dest_str[:3].lstrip('0') if dest_str else ""
            dest_prefix5 = dest_str[:5] if dest_str else ""
            for entry in zone_chart_data:
                ep  = str(entry.get("dest_zip_prefix", "")).lstrip('0')
                edz = str(entry.get("dest_zip", ""))[:5]
                if ep == dest_prefix3 or edz == dest_prefix5:
                    return int(entry["zone"])
        except (ValueError, TypeError, KeyError):
            pass

    # ── 3. Zone mapping ranges ─────────────────────────────────────────────────
    if zone_mapping and isinstance(zone_mapping, dict) and zone_mapping.get("ranges"):
        try:
            d_prefix = dest_str[:3] if dest_str else ""
            for entry in zone_mapping["ranges"]:
                if entry.get("from", "") <= d_prefix <= entry.get("to", ""):
                    return int(entry["zone"])
        except (ValueError, TypeError, KeyError):
            pass

    # ── 4. Heuristic fallback ──────────────────────────────────────────────────
    try:
        o = int(str(origin_zip)[:3]) if origin_zip else 500
        d = int(dest_str[:3]) if dest_str and dest_str[:3].isdigit() else 500
    except (ValueError, TypeError):
        return 4
    diff = abs(o - d)
    if diff < 50:   return 2
    elif diff < 100: return 3
    elif diff < 200: return 4
    elif diff < 300: return 5
    elif diff < 400: return 6
    elif diff < 500: return 7
    elif diff < 700: return 8
    else:            return 9


def calc_dim_weight(length, width, height, dim_factor=1.0, dim_divisor=166):
    try:
        l = float(length or 0) * dim_factor
        w = float(width  or 0) * dim_factor
        h = float(height or 0) * dim_factor
        if l > 0 and w > 0 and h > 0:
            return round((l * w * h) / dim_divisor, 2)
    except (ValueError, TypeError):
        pass
    return 0


def round_billable_weight(raw_weight):
    """Sub-pound uses 1/16 increments, 1+ uses whole lbs."""
    if raw_weight <= 0:
        return 1
    if raw_weight < 1:
        sixteenths = math.ceil(raw_weight * 16)
        result = sixteenths / 16
        if result >= 1.0:
            result = 0.99
        return result
    else:
        return math.ceil(raw_weight)


def calc_cubic_feet(length, width, height, dim_factor=1.0):
    try:
        l = float(length or 0) * dim_factor
        w = float(width  or 0) * dim_factor
        h = float(height or 0) * dim_factor
        if l > 0 and w > 0 and h > 0:
            return round((l * w * h) / 1728, 4)
    except (ValueError, TypeError):
        pass
    return 0


def lookup_rate(rate_grid, value, zone, pricing_type="WEIGHT_POUNDS"):
    """Look up rate from grid given a billable value and zone.
    Weight keys can be numeric strings ("1", "2.5") or label strings ("Package_1").
    Zone can be int or string.
    For UPS-style grids: the zone in the grid is like "102"/"202" and we pass
    the numeric zone from SAPT (e.g. 202). Handles both.
    """
    if not rate_grid:
        return None

    zone_str = str(zone)

    # Try to get numeric weight keys; label keys sort at the end
    def _weight_sort_key(k):
        try:
            return float(k)
        except (ValueError, TypeError):
            # E.g. "Package_1" -> treat as weight 1; "Envelope_flat" -> 0
            m = re.search(r'(\d+(?:\.\d+)?)', str(k))
            return float(m.group(1)) if m else 0.0

    weight_keys = sorted(rate_grid.keys(), key=_weight_sort_key)
    if not weight_keys:
        return None

    # Find the first weight key >= value
    target_key = None
    for wk in weight_keys:
        try:
            wk_val = float(wk)
        except (ValueError, TypeError):
            m = re.search(r'(\d+(?:\.\d+)?)', str(wk))
            wk_val = float(m.group(1)) if m else 0.0
        if wk_val >= value:
            target_key = wk
            break

    if target_key is None:
        if pricing_type in ("CUBICFEET", "WEIGHT_OUNCES"):
            return None
        target_key = weight_keys[-1]

    row = rate_grid.get(target_key, {})

    # Direct zone lookup
    if zone_str in row:
        return row[zone_str]

    # UPS zone translation: SAPT gives 3-digit zone (102, 202, etc.)
    # Rate grids can have "102" or simple "2" etc.
    # Try stripping prefix: 102->2, 202->2 (last digit(s))
    if len(zone_str) == 3 and zone_str.isdigit():
        simple_zone = str(int(zone_str) % 100)  # 202 -> 2
        if simple_zone in row:
            return row[simple_zone]
        # Also try as "0" + simple_zone
        if "0" + simple_zone in row:
            return row["0" + simple_zone]

    # Try integer zone key
    try:
        int_zone = int(float(zone_str))
        if str(int_zone) in row:
            return row[str(int_zone)]
    except (ValueError, TypeError):
        pass

    return None


def get_weight_band(billable):
    if billable <= 1:  return "0-1 lbs"
    elif billable <= 2: return "1-2 lbs"
    elif billable <= 5: return "2-5 lbs"
    elif billable <= 10: return "5-10 lbs"
    elif billable <= 20: return "10-20 lbs"
    elif billable <= 40: return "20-40 lbs"
    else: return "40+ lbs"


def _is_express_service(service_name):
    """Return True if the service name matches known express service keywords."""
    if not service_name:
        return False
    s = service_name.lower()
    express_kw = ['next day', 'overnight', '2day', '2nd day', 'express', 'priority', 'xpresspost', '1-day', 'one day']
    return any(kw in s for kw in express_kw)


def run_rate_analysis(shipments, config, db, unit_system=None):
    """Core rate analysis engine v3.
    Uses real zone data from US_ZONES / CA_ZONES when available."""
    rate_card_ids = config.get("rate_card_ids", [])
    markups       = config.get("markups", {})

    if unit_system is None:
        unit_system = {"weight": "lbs", "dimensions": "in"}
    weight_unit = unit_system.get("weight", "lbs")
    dim_unit    = unit_system.get("dimensions", "in")
    wt_factor   = 2.20462 if weight_unit == "kg" else 1.0
    dim_factor  = 0.393701 if dim_unit == "cm" else 1.0

    # Load zone chart if specified in config
    zone_chart_data = None
    zone_chart_id = config.get("zone_chart_id")
    if zone_chart_id:
        zc_row = db.execute(
            "SELECT data_json FROM zone_charts WHERE id = ?", (zone_chart_id,)
        ).fetchone()
        if zc_row:
            zone_chart_data = json.loads(zc_row["data_json"])

    config_dim_divisor = config.get("dim_divisor")
    use_per_card_dim   = not config_dim_divisor
    effective_dim_divisor = float(config_dim_divisor) if config_dim_divisor else 166

    # Load rate cards with their zone_key
    cards = {}
    for rc_id in rate_card_ids:
        row = db.execute("SELECT * FROM rate_cards WHERE id = ?", (rc_id,)).fetchone()
        if row:
            rc_keys = row.keys()
            rc_dim   = float(row["dim_divisor"]) if "dim_divisor" in rc_keys and row["dim_divisor"] else 166
            zone_key = row["zone_key"] if "zone_key" in rc_keys and row["zone_key"] else ""
            cards[rc_id] = {
                "id":           row["id"],
                "name":         row["name"],
                "service_type": row["service_type"],
                "carrier":      row["carrier"],
                "pricing_type": row["pricing_type"] if "pricing_type" in rc_keys else "WEIGHT_POUNDS",
                "rate_grid":    json.loads(row["rate_grid_json"]),
                "zone_mapping": json.loads(row["zone_mapping_json"]) if row["zone_mapping_json"] else {},
                "dim_divisor":  rc_dim,
                "zone_key":     zone_key,
                "fuel_rate":    float(row["fuel_rate"]) if "fuel_rate" in rc_keys and row["fuel_rate"] else 0,
                "fuel_rate_sell": float(row["fuel_rate_sell"]) if "fuel_rate_sell" in rc_keys and row["fuel_rate_sell"] else (float(row["fuel_rate"]) if "fuel_rate" in rc_keys and row["fuel_rate"] else 0),
                "fuel_type":    row["fuel_type"] if "fuel_type" in rc_keys and row["fuel_type"] else "percentage",
                "fuel_discount": float(row["fuel_discount"]) if "fuel_discount" in rc_keys and row["fuel_discount"] else 0,
                "dim_threshold_cu_in": float(row["dim_threshold_cu_in"]) if "dim_threshold_cu_in" in rc_keys and row["dim_threshold_cu_in"] else 0,
                "dim_divisor_alt": float(row["dim_divisor_alt"]) if "dim_divisor_alt" in rc_keys and row["dim_divisor_alt"] else 0,
                "dim_divisor_buy": float(row["dim_divisor_buy"]) if "dim_divisor_buy" in rc_keys and row["dim_divisor_buy"] else rc_dim,
                "transit_days_json": json.loads(row["transit_days_json"]) if "transit_days_json" in rc_keys and row["transit_days_json"] else {},
                "service_class": row["service_class"] if "service_class" in rc_keys and row["service_class"] else "economy",
                "card_type":    row["card_type"] if "card_type" in rc_keys and row["card_type"] else "sell_current",
                "country":      row["country"] if "country" in rc_keys and row["country"] else "US",
            }

    # Load buy cards alongside sell cards (keyed by corresponding sell card ID)
    buy_cards = {}
    for rc_id, sell_card in cards.items():
        try:
            buy_row = db.execute(
                "SELECT * FROM rate_cards WHERE carrier = ? AND service_type = ? "
                "AND card_type = 'buy_current' AND status = 'active' LIMIT 1",
                (sell_card["carrier"], sell_card["service_type"])
            ).fetchone()
            if buy_row:
                buy_cards[rc_id] = {
                    "rate_grid":    json.loads(buy_row["rate_grid_json"]),
                    "fuel_rate":    float(buy_row["fuel_rate_buy"]) if buy_row["fuel_rate_buy"] else float(buy_row["fuel_rate"] or 0),
                    "fuel_type":    buy_row["fuel_type"] if buy_row["fuel_type"] else "percentage",
                    "fuel_discount": float(buy_row["fuel_discount"]) if buy_row["fuel_discount"] else 0,
                    "dim_divisor":  float(buy_row["dim_divisor_buy"]) if buy_row["dim_divisor_buy"] else float(buy_row["dim_divisor"] or 166),
                }
        except Exception:
            pass

    # Multi-induction config
    multi_induction = config.get("multi_induction", False)
    induction_locs = []
    zone_skip_rules = []
    induction_breakdown = {}
    if multi_induction:
        try:
            loc_rows = db.execute(
                "SELECT * FROM induction_locations WHERE active = 1 ORDER BY is_primary DESC, name"
            ).fetchall()
            induction_locs = [dict(r) for r in loc_rows]
        except Exception:
            induction_locs = []
        try:
            zsc_rows = db.execute("SELECT * FROM zone_skip_config").fetchall()
            zone_skip_rules = [dict(r) for r in zsc_rows]
        except Exception:
            zone_skip_rules = []

    results         = []
    total_original  = 0
    total_br        = 0
    total_base_cost = 0
    total_weight_lbs = 0
    total_cubic_ft  = 0
    total_fuel      = 0
    total_accessorials = 0
    total_buy       = 0
    service_savings     = {}
    carrier_savings     = {}
    zone_breakdown      = {}
    br_service_mix      = {}
    weight_band_breakdown = {}
    dim_weight_flags    = 0
    zone_weight_pivot   = {}

    # Get first zone mapping for fallback
    first_zone_map = None
    for c in cards.values():
        if c.get("zone_mapping") and isinstance(c["zone_mapping"], dict) \
                and c["zone_mapping"].get("ranges"):
            first_zone_map = c["zone_mapping"]
            break

    # Load accessorial rules once
    try:
        acc_rules_rows = db.execute("SELECT * FROM accessorial_rules WHERE active = 1").fetchall()
        acc_rules = [dict(r) for r in acc_rules_rows]
    except Exception:
        acc_rules = []

    # Load service cost config once
    try:
        scc_row = db.execute("SELECT * FROM service_cost_config LIMIT 1").fetchone()
        scc = dict(scc_row) if scc_row else {"line_haul_cost": 0.11, "daily_pickup_cost": 100, "pickup_days": 1, "sort_cost": 0.06}
    except Exception:
        scc = {"line_haul_cost": 0.11, "daily_pickup_cost": 100, "pickup_days": 1, "sort_cost": 0.06}

    for ship in shipments:
        raw_actual = float(ship.get("weight",       1) or 1)
        raw_billed = float(ship.get("billed_weight",0) or 0)

        dim_wt   = calc_dim_weight(
            ship.get("length", 0), ship.get("width", 0), ship.get("height", 0),
            dim_factor, dim_divisor=effective_dim_divisor)
        cubic_ft = calc_cubic_feet(
            ship.get("length", 0), ship.get("width", 0), ship.get("height", 0), dim_factor)

        # Pre-compute sorted dimensions (longest first) for accessorial checks
        try:
            _l = float(ship.get("length", 0) or 0) * dim_factor
            _w = float(ship.get("width",  0) or 0) * dim_factor
            _h = float(ship.get("height", 0) or 0) * dim_factor
            _dims_sorted = sorted([_l, _w, _h], reverse=True)
            length_in = _dims_sorted[0]
            width_in  = _dims_sorted[1]
            height_in = _dims_sorted[2]
        except Exception:
            length_in = width_in = height_in = 0
        lg = length_in + 2 * width_in + 2 * height_in  # length + girth
        cubic_inches = length_in * width_in * height_in
        cubic_ft_dim = cubic_inches / 1728 if cubic_inches > 0 else 0

        # Extract ship month for seasonal accessorial rules
        ship_month = 1
        try:
            ship_date_str = ship.get("ship_date", "")
            if ship_date_str:
                ship_month = int(str(ship_date_str)[5:7])
        except Exception:
            ship_month = 1

        actual_lbs  = round(raw_actual * wt_factor, 2)
        billed_lbs  = round(raw_billed * wt_factor, 2) if raw_billed > 0 else actual_lbs
        billable    = max(actual_lbs, dim_wt, billed_lbs)
        billable_ceil = round_billable_weight(billable)

        if dim_wt > actual_lbs and dim_wt > billed_lbs:
            dim_weight_flags += 1

        # Default zone using USPS key
        default_zone = determine_zone(
            ship.get("origin_zip", ""), ship.get("dest_zip", ""),
            carrier_key="USPS",
            zone_mapping=first_zone_map,
            zone_chart_data=zone_chart_data
        )

        original_price = float(ship.get("price", 0) or 0)
        total_original += original_price
        wband = get_weight_band(billable_ceil)

        best_price = None
        best_card  = None
        all_card_prices = {}

        # Determine shipment's service class for express/economy filtering
        original_class = 'express' if _is_express_service(ship.get('service', '')) else 'economy'

        for rc_id, card in cards.items():
            # Express/economy filtering: express shipments only compare against express cards
            card_class = card.get('service_class', 'economy')
            if original_class == 'express' and card_class == 'economy':
                continue  # skip economy cards for express shipments

            pricing_type = card.get("pricing_type", "WEIGHT_POUNDS")
            card_zone_key = card.get("zone_key", "")

            # Per-card zone lookup using the card's zone_key
            if card_zone_key:
                card_zone = determine_zone(
                    ship.get("origin_zip", ""), ship.get("dest_zip", ""),
                    carrier_key=card_zone_key,
                    zone_mapping=card.get("zone_mapping"),
                    zone_chart_data=zone_chart_data
                )
            else:
                card_zone = default_zone

            # Per-card DIM weight with conditional divisor
            card_dim_divisor = card.get("dim_divisor", 166) if use_per_card_dim else effective_dim_divisor
            dim_thresh = float(card.get("dim_threshold_cu_in", 0) or 0)
            dim_alt    = float(card.get("dim_divisor_alt", 0) or 0)
            if dim_thresh > 0 and cubic_inches > 0:
                if cubic_inches < dim_thresh and dim_alt > 0:
                    card_dim_divisor = dim_alt
            card_dim_wt   = calc_dim_weight(
                ship.get("length", 0), ship.get("width", 0), ship.get("height", 0),
                dim_factor, dim_divisor=card_dim_divisor)
            card_billable      = max(actual_lbs, card_dim_wt, billed_lbs)
            card_billable_ceil = round_billable_weight(card_billable)

            if pricing_type == "CUBICFEET":
                lookup_val = cubic_ft if cubic_ft > 0 else 0.1
                base_rate  = lookup_rate(card["rate_grid"], lookup_val, card_zone, pricing_type)
            elif pricing_type == "WEIGHT_OUNCES":
                lookup_oz  = card_billable_ceil * 16
                if lookup_oz > 16:
                    base_rate = None
                else:
                    base_rate = lookup_rate(card["rate_grid"], lookup_oz, card_zone, pricing_type)
            else:
                base_rate = lookup_rate(card["rate_grid"], card_billable_ceil, card_zone, pricing_type)

            if base_rate is None:
                continue

            markup_cfg = markups.get(str(rc_id),
                                     {"pct": 0.15, "per_lb": 0.10, "per_shipment": 1.00})
            pct      = float(markup_cfg.get("pct",          0.15))
            per_lb   = float(markup_cfg.get("per_lb",       0.10))
            per_ship = float(markup_cfg.get("per_shipment", 1.00))

            # ── Fuel surcharge ──
            # Use fuel_rate_sell if available, fall back to fuel_rate
            fuel_rate_val   = float(card.get("fuel_rate_sell", 0) or card.get("fuel_rate", 0) or 0)
            fuel_type_val   = card.get("fuel_type", "percentage") or "percentage"
            fuel_discount_val = float(card.get("fuel_discount", 0) or 0)
            fuel_charge = 0

            # ── Accessorials ──
            acc_total = 0
            demand_total = 0
            acc_details = []
            carrier_name = card.get("carrier", "")
            for rule in acc_rules:
                rule_carriers = rule.get("apply_to_carriers", "") or ""
                if rule_carriers and carrier_name not in rule_carriers:
                    continue
                try:
                    cond = json.loads(rule.get("condition_json", "{}") or "{}")
                except Exception:
                    cond = {}
                fee_type = rule.get("fee_type", "")
                applies = False

                if fee_type == "DAS":
                    _, _, das_flag = lookup_us_zone(ship.get("dest_zip", ""),
                                                    _carrier_to_zone_key(carrier_name))
                    applies = das_flag
                elif fee_type == "residential":
                    applies = True  # Apply to all by default
                elif fee_type == "additional_handling":
                    weight_over = cond.get("weight_over", 0)
                    length_over = cond.get("length_over", 0)
                    lg_over     = cond.get("lg_over", 0)
                    if (weight_over > 0 and actual_lbs > weight_over) or \
                       (length_over > 0 and length_in > length_over) or \
                       (lg_over > 0 and lg > lg_over):
                        applies = True
                elif fee_type == "oversize":
                    lg_over     = cond.get("lg_over", 0)
                    length_over = cond.get("length_over", 0)
                    if (lg_over > 0 and lg > lg_over) or (length_over > 0 and length_in > length_over):
                        applies = True
                elif fee_type == "over_max":
                    if actual_lbs > 150 or length_in > 108 or lg > 165:
                        applies = True
                elif fee_type == "nonstandard_length_22":
                    if length_in > 22:
                        applies = True
                elif fee_type == "nonstandard_length_30":
                    if length_in > 30:
                        applies = True
                elif fee_type == "nonstandard_volume":
                    if cubic_ft_dim > 2:
                        applies = True
                elif fee_type == "demand_surcharge":
                    rule_start = rule.get("start_date", "") or ""
                    rule_end   = rule.get("end_date", "") or ""
                    if rule_start and rule_end:
                        ship_date_str = ship.get("ship_date", "") or ""
                        if ship_date_str and rule_start <= ship_date_str <= rule_end:
                            applies = True
                        elif not ship_date_str:
                            month_min = cond.get("month_min", 1)
                            month_max = cond.get("month_max", 12)
                            if month_min <= ship_month <= month_max:
                                applies = True
                    else:
                        month_min = cond.get("month_min", 1)
                        month_max = cond.get("month_max", 12)
                        if month_min <= ship_month <= month_max:
                            applies = True
                elif fee_type == "dim_noncompliance":
                    if card_dim_wt > actual_lbs:
                        applies = True

                if applies:
                    fee_amount = float(rule.get("amount", 0) or 0)
                    try:
                        zone_rates = json.loads(rule.get("zone_rates_json", "{}") or "{}")
                    except Exception:
                        zone_rates = {}
                    if zone_rates:
                        fee_amount = float(zone_rates.get(str(card_zone), fee_amount))
                    if fee_type == 'demand_surcharge':
                        demand_total += fee_amount
                    else:
                        acc_total += fee_amount
                    acc_details.append({"name": rule["name"], "amount": fee_amount})

            # ── Final price calculation (SAPT formula) ──
            card_country = card.get("country", "US") or "US"
            zone_skip_charge = 0  # populated later if multi-induction

            if card_country == "CA" and fuel_type_val == "percentage":
                # Canada fuel formula: Postage = (rate + accessorials + zone_skip) * (1 + fuel%)
                effective_fuel_pct = fuel_rate_val * (1 - fuel_discount_val)
                subtotal = (base_rate + acc_total + zone_skip_charge)
                marked_up = (subtotal * (1 + pct)) + (card_billable_ceil * per_lb) + per_ship
                final = round(marked_up * (1 + effective_fuel_pct) + demand_total, 2)
                fuel_charge = round(marked_up * effective_fuel_pct, 2)
            elif fuel_type_val == "percentage":
                # % fuel wraps AROUND the marked-up price
                marked_up = ((base_rate + acc_total) * (1 + pct)) + (card_billable_ceil * per_lb) + per_ship
                effective_fuel_pct = fuel_rate_val * (1 - fuel_discount_val)
                final = round(marked_up * (1 + effective_fuel_pct) + demand_total, 2)
                fuel_charge = round(marked_up * effective_fuel_pct, 2)
            else:
                # per-lb fuel added to base BEFORE markup
                fuel_charge = round(fuel_rate_val * (1 - fuel_discount_val) * card_billable_ceil, 2)
                base_with_fuel = base_rate + acc_total + fuel_charge
                final = round((base_with_fuel * (1 + pct)) + (card_billable_ceil * per_lb) + per_ship + demand_total, 2)

            # Transit days lookup by dest state
            transit_days_map = card.get("transit_days_json", {})
            dest_state = ship.get("dest_state", "") or ""
            transit_days = transit_days_map.get(dest_state.upper()) if dest_state else None

            all_card_prices[card["name"]] = {
                "base":                round(base_rate, 2),
                "fuel":                round(fuel_charge, 2),
                "accessorials":        round(acc_total, 2),
                "demand_surcharge":    round(demand_total, 2),
                "accessorial_details": acc_details,
                "postage":             round(base_rate + fuel_charge + acc_total + demand_total, 2),
                "final":               final,
                "id":                  rc_id,
                "billable_wt":         card_billable_ceil,
                "zone":                card_zone,
                "transit_days":        transit_days,
            }

            # ── Buy price computation ──
            buy_price = None
            buy_base = None
            buy_fuel = 0
            if rc_id in buy_cards:
                bc = buy_cards[rc_id]
                buy_base = lookup_rate(bc["rate_grid"], card_billable_ceil, card_zone, pricing_type)
                if buy_base is not None:
                    buy_fuel_rate = float(bc.get("fuel_rate", 0) or 0)
                    buy_fuel_type = bc.get("fuel_type", "percentage")
                    buy_fuel_disc = float(bc.get("fuel_discount", 0) or 0)
                    if buy_fuel_type == "percentage":
                        buy_fuel = round(buy_base * buy_fuel_rate * (1 - buy_fuel_disc), 2)
                    else:
                        buy_fuel = round(buy_fuel_rate * (1 - buy_fuel_disc) * card_billable_ceil, 2)
                    buy_price = round(buy_base + buy_fuel + acc_total, 2)
            else:
                # No buy card — use base_rate as buy cost estimate
                buy_base = base_rate
                buy_price = round(base_rate + fuel_charge + acc_total, 2) if base_rate else None

            # Update all_card_prices with buy/profit fields
            all_card_prices[card["name"]]["base_buy"] = round(buy_base, 2) if buy_base is not None else None
            all_card_prices[card["name"]]["fuel_buy"] = round(buy_fuel, 2)
            all_card_prices[card["name"]]["buy_price"] = buy_price
            all_card_prices[card["name"]]["profit"] = round(final - buy_price, 2) if buy_price is not None else None
            all_card_prices[card["name"]]["margin_pct"] = round((final - buy_price) / final * 100, 1) if (buy_price is not None and final > 0) else None

            if best_price is None or final < best_price:
                best_price = final
                best_card  = card

        # ── Multi-induction: re-rate from each additional induction location ──
        best_induction_loc = None
        if multi_induction and induction_locs:
            # Identify primary location (skip it, already done above)
            primary_zip = ship.get("origin_zip", "")
            if induction_locs:
                primary_loc = next((l for l in induction_locs if l["is_primary"]), induction_locs[0])
                primary_zip = primary_loc.get("zip_or_postal", primary_zip) or primary_zip
                best_induction_loc = primary_loc["name"] if best_price is not None else None

            for ind_loc in induction_locs:
                if ind_loc.get("is_primary"):
                    continue  # already rated from primary
                ind_zip = ind_loc.get("zip_or_postal", "") or ""
                ind_name = ind_loc["name"]
                ind_id   = ind_loc["id"]

                for rc_id2, card2 in cards.items():
                    card_class2 = card2.get('service_class', 'economy')
                    if original_class == 'express' and card_class2 == 'economy':
                        continue

                    # Check service_available for this induction location
                    svc_rule = next(
                        (r for r in zone_skip_rules
                         if r["induction_location_id"] == ind_id
                         and r["carrier"] == card2.get("carrier", "")
                         and (not r["service_name"] or r["service_name"] == card2.get("service_type", ""))),
                        None
                    )
                    if svc_rule and not svc_rule.get("service_available", 1):
                        continue

                    pricing_type2 = card2.get("pricing_type", "WEIGHT_POUNDS")
                    card_zone_key2 = card2.get("zone_key", "")
                    if card_zone_key2:
                        ind_zone = determine_zone(
                            ind_zip, ship.get("dest_zip", ""),
                            carrier_key=card_zone_key2,
                            zone_mapping=card2.get("zone_mapping"),
                            zone_chart_data=zone_chart_data
                        )
                    else:
                        ind_zone = determine_zone(
                            ind_zip, ship.get("dest_zip", ""),
                            carrier_key="USPS",
                            zone_mapping=first_zone_map,
                            zone_chart_data=zone_chart_data
                        )

                    card_dim_divisor2 = card2.get("dim_divisor", 166) if use_per_card_dim else effective_dim_divisor
                    card_dim_wt2 = calc_dim_weight(
                        ship.get("length", 0), ship.get("width", 0), ship.get("height", 0),
                        dim_factor, dim_divisor=card_dim_divisor2)
                    card_billable2     = max(actual_lbs, card_dim_wt2, billed_lbs)
                    card_billable_ceil2 = round_billable_weight(card_billable2)

                    if pricing_type2 == "CUBICFEET":
                        base_rate2 = lookup_rate(card2["rate_grid"], cubic_ft if cubic_ft > 0 else 0.1, ind_zone, pricing_type2)
                    elif pricing_type2 == "WEIGHT_OUNCES":
                        lookup_oz2 = card_billable_ceil2 * 16
                        base_rate2 = lookup_rate(card2["rate_grid"], lookup_oz2, ind_zone, pricing_type2) if lookup_oz2 <= 16 else None
                    else:
                        base_rate2 = lookup_rate(card2["rate_grid"], card_billable_ceil2, ind_zone, pricing_type2)

                    if base_rate2 is None:
                        continue

                    markup_cfg2 = markups.get(str(rc_id2), {"pct": 0.15, "per_lb": 0.10, "per_shipment": 1.00})
                    pct2      = float(markup_cfg2.get("pct",          0.15))
                    per_lb2   = float(markup_cfg2.get("per_lb",       0.10))
                    per_ship2 = float(markup_cfg2.get("per_shipment", 1.00))

                    fuel_rate_val2   = float(card2.get("fuel_rate_sell", 0) or card2.get("fuel_rate", 0) or 0)
                    fuel_type_val2   = card2.get("fuel_type", "percentage") or "percentage"
                    fuel_discount_val2 = float(card2.get("fuel_discount", 0) or 0)

                    # Accessorials for this location (reuse same acc_total logic)
                    acc_total2 = 0
                    demand_total2 = 0
                    carrier_name2 = card2.get("carrier", "")
                    for rule2 in acc_rules:
                        rule_carriers2 = rule2.get("apply_to_carriers", "") or ""
                        if rule_carriers2 and carrier_name2 not in rule_carriers2:
                            continue
                        try:
                            cond2 = json.loads(rule2.get("condition_json", "{}") or "{}")
                        except Exception:
                            cond2 = {}
                        fee_type2 = rule2.get("fee_type", "")
                        applies2 = False
                        if fee_type2 == "residential":
                            applies2 = True
                        elif fee_type2 == "additional_handling":
                            wo = cond2.get("weight_over", 0)
                            lo = cond2.get("length_over", 0)
                            lgo = cond2.get("lg_over", 0)
                            if (wo > 0 and actual_lbs > wo) or (lo > 0 and length_in > lo) or (lgo > 0 and lg > lgo):
                                applies2 = True
                        elif fee_type2 == "oversize":
                            lgo = cond2.get("lg_over", 0)
                            lo  = cond2.get("length_over", 0)
                            if (lgo > 0 and lg > lgo) or (lo > 0 and length_in > lo):
                                applies2 = True
                        elif fee_type2 == "demand_surcharge":
                            mm = cond2.get("month_min", 1)
                            mx = cond2.get("month_max", 12)
                            if mm <= ship_month <= mx:
                                applies2 = True
                        if applies2:
                            fa2 = float(rule2.get("amount", 0) or 0)
                            if fee_type2 == 'demand_surcharge':
                                demand_total2 += fa2
                            else:
                                acc_total2 += fa2

                    # Zone skip surcharge for non-primary locations
                    zone_skip_charge = 0
                    if svc_rule and svc_rule.get("zone_skip_allowed", 1):
                        zone_skip_charge = float(svc_rule.get("zone_skip_fixed", 0) or 0)
                        zone_skip_charge += float(svc_rule.get("zone_skip_per_lb", 0) or 0) * card_billable_ceil2

                    # Final price with zone_skip
                    if fuel_type_val2 == "percentage":
                        marked_up2 = ((base_rate2 + acc_total2) * (1 + pct2)) + (card_billable_ceil2 * per_lb2) + per_ship2
                        eff_fuel2 = fuel_rate_val2 * (1 - fuel_discount_val2)
                        final2 = round(marked_up2 * (1 + eff_fuel2) + demand_total2 + zone_skip_charge, 2)
                    else:
                        fuel_charge2 = round(fuel_rate_val2 * (1 - fuel_discount_val2) * card_billable_ceil2, 2)
                        base_with_fuel2 = base_rate2 + acc_total2 + fuel_charge2
                        final2 = round((base_with_fuel2 * (1 + pct2)) + (card_billable_ceil2 * per_lb2) + per_ship2 + demand_total2 + zone_skip_charge, 2)

                    ind_key = f"{card2['name']}@{ind_name}"
                    if best_price is None or final2 < best_price:
                        best_price = final2
                        best_card  = card2
                        best_induction_loc = ind_name
                        all_card_prices[ind_key] = {
                            "base": round(base_rate2, 2),
                            "final": final2,
                            "zone": ind_zone,
                            "induction_location": ind_name,
                            "zone_skip_charge": round(zone_skip_charge, 2),
                            "accessorials": round(acc_total2, 2),
                            "demand_surcharge": round(demand_total2, 2),
                            "id": rc_id2,
                            "billable_wt": card_billable_ceil2,
                        }

            # Track induction breakdown
            if best_induction_loc and best_price is not None:
                if best_induction_loc not in induction_breakdown:
                    induction_breakdown[best_induction_loc] = {"count": 0, "total": 0}
                induction_breakdown[best_induction_loc]["count"] += 1

        has_savings = best_price is not None and best_price < original_price
        savings     = round(original_price - best_price, 2) if has_savings else 0
        if not has_savings and best_price is None:
            best_price = original_price

        effective_br = best_price if has_savings else original_price
        total_br    += effective_br

        # Extract fuel/accessorial values from the winning card for per-shipment display
        ship_fuel = 0
        ship_acc  = 0
        if has_savings and best_card:
            best_rates = all_card_prices.get(best_card["name"], {})
            best_base = best_rates.get("base", 0)
            ship_fuel = best_rates.get("fuel", 0)
            ship_acc  = best_rates.get("accessorials", 0)
            total_base_cost += best_base
            total_fuel += ship_fuel
            total_accessorials += ship_acc
            # Accumulate buy cost for winning card
            buy_p = best_rates.get("buy_price")
            if buy_p is not None:
                total_buy += buy_p
        else:
            total_base_cost += original_price
        total_weight_lbs += billable_ceil
        total_cubic_ft   += cubic_ft if cubic_ft > 0 else 0

        carrier  = ship.get("carrier", "Unknown")
        br_name  = best_card["name"] if (has_savings and best_card) else "Current rate"

        svc = ship.get("service", "Unknown")
        service_savings.setdefault(svc, {"original": 0, "br": 0, "count": 0})
        service_savings[svc]["original"] += original_price
        service_savings[svc]["br"]       += effective_br
        service_savings[svc]["count"]    += 1

        carrier_savings.setdefault(carrier, {"original": 0, "br": 0, "count": 0})
        carrier_savings[carrier]["original"] += original_price
        carrier_savings[carrier]["br"]       += effective_br
        carrier_savings[carrier]["count"]    += 1

        zone_key_str = str(default_zone)
        zone_breakdown.setdefault(zone_key_str, {"count": 0, "original": 0, "br": 0})
        zone_breakdown[zone_key_str]["count"]    += 1
        zone_breakdown[zone_key_str]["original"] += original_price
        zone_breakdown[zone_key_str]["br"]       += effective_br

        weight_band_breakdown.setdefault(wband, {"count": 0, "original": 0, "br": 0})
        weight_band_breakdown[wband]["count"]    += 1
        weight_band_breakdown[wband]["original"] += original_price
        weight_band_breakdown[wband]["br"]       += effective_br

        if has_savings and best_card:
            br_service_mix.setdefault(best_card["name"], {"count": 0, "total": 0, "total_buy": 0, "total_profit": 0})
            br_service_mix[best_card["name"]]["count"] += 1
            br_service_mix[best_card["name"]]["total"] += best_price
            if buy_p is not None:
                br_service_mix[best_card["name"]]["total_buy"] += buy_p
                br_service_mix[best_card["name"]]["total_profit"] += (best_price - buy_p)

        zone_weight_pivot.setdefault(wband, {})
        zone_weight_pivot[wband].setdefault(zone_key_str, 0)
        zone_weight_pivot[wband][zone_key_str] += 1

        results.append({
            **ship,
            "dim_weight":      round(dim_wt, 2),
            "cubic_ft":        round(cubic_ft, 4),
            "billable_weight": billable_ceil,
            "zone":            default_zone,
            "br_service":      br_name,
            "br_price":        round(effective_br, 2),
            "fuel":            round(ship_fuel, 2),
            "accessorials":    round(ship_acc, 2),
            "savings":         savings,
            "savings_pct":     round((savings / original_price) * 100, 1)
                               if original_price > 0 and savings > 0 else 0,
            "all_rates":       all_card_prices,
            "induction_location": best_induction_loc,
        })

    # Finalize breakdowns
    total_count = len(results)

    # Service cost / profitability per BR service
    # Load per-card service cost overrides
    try:
        sco_rows = db.execute("SELECT * FROM service_cost_overrides").fetchall()
        sco_map = {r["rate_card_id"]: dict(r) for r in sco_rows}
    except Exception:
        sco_map = {}

    for svc_name, mix_data in br_service_mix.items():
        count = mix_data["count"]
        pct_win = count / total_count if total_count > 0 else 0
        # Check for per-card override
        # Try to find the rate card id for this service name
        svc_card_id = None
        for rc_id, rc_data in cards.items():
            if rc_data.get("name") == svc_name:
                svc_card_id = rc_id
                break
        sco = sco_map.get(svc_card_id) if svc_card_id else None
        lh_cost = sco["line_haul_cost"] if sco and sco.get("line_haul_cost") else scc.get("line_haul_cost", 0.11)
        pu_cost = sco["pickup_cost"] if sco and sco.get("pickup_cost") else scc.get("daily_pickup_cost", 100)
        so_cost = sco["sort_cost"] if sco and sco.get("sort_cost") else scc.get("sort_cost", 0.06)
        pu_days = scc.get("pickup_days", 1)
        svc_cost = (
            (count * lh_cost) +
            (pct_win * pu_cost * pu_days) +
            (count * so_cost)
        )
        mix_data["service_cost"]  = round(svc_cost, 2)
        mix_data["margin_gross"]  = round(mix_data.get("total", 0) - svc_cost, 2)
        mix_data["total_buy"]     = round(mix_data.get("total_buy", 0), 2)
        mix_data["total_profit"]  = round(mix_data.get("total_profit", 0), 2)
        mix_data["margin_pct"]    = round(mix_data["total_profit"] / mix_data["total"] * 100, 1) if mix_data.get("total", 0) > 0 else 0

    total_service_cost = sum(m.get("service_cost", 0) for m in br_service_mix.values())
    total_margin_gross = sum(m.get("margin_gross", 0) for m in br_service_mix.values())

    for k in service_savings:
        s = service_savings[k]
        s["original"]    = round(s["original"], 2)
        s["br"]          = round(s["br"], 2)
        s["savings"]     = round(s["original"] - s["br"], 2)
        s["savings_pct"] = round((s["savings"] / s["original"]) * 100, 1) if s["original"] > 0 else 0

    for k in carrier_savings:
        c = carrier_savings[k]
        c["original"]    = round(c["original"], 2)
        c["br"]          = round(c["br"], 2)
        c["savings"]     = round(c["original"] - c["br"], 2)
        c["savings_pct"] = round((c["savings"] / c["original"]) * 100, 1) if c["original"] > 0 else 0

    for z in zone_breakdown:
        zb = zone_breakdown[z]
        zb["original"]     = round(zb["original"], 2)
        zb["br"]           = round(zb["br"], 2)
        zb["savings"]      = round(zb["original"] - zb["br"], 2)
        zb["savings_pct"]  = round((zb["savings"] / zb["original"]) * 100, 1) if zb["original"] > 0 else 0
        zb["distribution"] = round((zb["count"] / total_count) * 100, 1) if total_count > 0 else 0
        zb["avg_original"] = round(zb["original"] / zb["count"], 2) if zb["count"] > 0 else 0
        zb["avg_br"]       = round(zb["br"] / zb["count"], 2) if zb["count"] > 0 else 0

    for wb in weight_band_breakdown:
        wbb = weight_band_breakdown[wb]
        wbb["original"]    = round(wbb["original"], 2)
        wbb["br"]          = round(wbb["br"], 2)
        wbb["savings"]     = round(wbb["original"] - wbb["br"], 2)
        wbb["savings_pct"] = round((wbb["savings"] / wbb["original"]) * 100, 1) if wbb["original"] > 0 else 0

    total_savings         = round(total_original - total_br, 2)
    savings_pct           = round((total_savings / total_original) * 100, 1) if total_original > 0 else 0
    shipments_with_savings = len([r for r in results if r["savings"] > 0])

    return {
        "shipments": results,
        "summary": {
            "total_original":           round(total_original, 2),
            "total_br":                 round(total_br, 2),
            "total_savings":            total_savings,
            "savings_pct":              savings_pct,
            "shipment_count":           total_count,
            "shipments_with_savings":   shipments_with_savings,
            "shipments_no_savings":     total_count - shipments_with_savings,
            "avg_savings_per_shipment": round(total_savings / total_count, 2) if total_count > 0 else 0,
            "avg_original":             round(total_original / total_count, 2) if total_count > 0 else 0,
            "avg_br":                   round(total_br / total_count, 2) if total_count > 0 else 0,
            "dim_weight_flags":         dim_weight_flags,
            "unit_system":              unit_system,
            "total_base_cost":          round(total_base_cost, 2),
            "total_weight_lbs":         round(total_weight_lbs, 2),
            "total_cubic_ft":           round(total_cubic_ft, 4),
            "total_markup_revenue":     round(total_br - total_base_cost, 2),
            "total_fuel":               round(total_fuel, 2),
            "total_accessorials":       round(total_accessorials, 2),
            "total_service_cost":       round(total_service_cost, 2),
            "margin_gross":             round(total_margin_gross, 2),
            "total_buy_cost":           round(total_buy, 2),
            "total_profit_actual":      round(total_br - total_buy, 2),
            "actual_margin_pct":        round((total_br - total_buy) / total_br * 100, 1) if total_br > 0 else 0,
        },
        "by_zone":         zone_breakdown,
        "by_service":      service_savings,
        "by_carrier":      carrier_savings,
        "by_weight_band":  weight_band_breakdown,
        "br_service_mix":  br_service_mix,
        "zone_weight_pivot": zone_weight_pivot,
        "induction_breakdown": induction_breakdown,
    }


# ─── CSV Parsing Helpers ──────────────────────────────────────────────────────

def parse_wizmo_csv(csv_data):
    """Parse Wizmo 4-header-row CSV format into rate_grid dict."""
    lines = csv_data.strip().replace('\r\n', '\n').replace('\r', '\n').split('\n')
    if len(lines) < 5:
        return None, None, None, None, None, None
    service_name     = lines[0].split(',')[0].strip().strip('"')
    row2             = lines[1].split(',')
    min_days         = row2[1].strip() if len(row2) > 1 else ""
    row3             = lines[2].split(',')
    max_days         = row3[1].strip() if len(row3) > 1 else ""
    header           = lines[3].split(',')
    pricing_type_key = header[0].strip().upper()
    zones            = [h.strip() for h in header[1:] if h.strip()]
    if pricing_type_key in ('CUBICFEET', 'CUBIC_FEET', 'CUBIC'):
        pricing_type = 'CUBICFEET'
    else:
        pricing_type = 'WEIGHT_POUNDS'
    rate_grid = {}
    for line in lines[4:]:
        if not line.strip():
            continue
        parts = line.split(',')
        weight = parts[0].strip().strip('"')
        if not weight:
            continue
        rate_grid[weight] = {}
        for i, z in enumerate(zones):
            val = parts[i+1].strip() if i+1 < len(parts) else ''
            try:
                rate_grid[weight][z] = float(val) if val else 0
            except ValueError:
                rate_grid[weight][z] = 0
    return rate_grid, service_name, min_days, max_days, pricing_type, zones


def is_wizmo_format(csv_data):
    lines = csv_data.strip().replace('\r\n', '\n').replace('\r', '\n').split('\n')
    if len(lines) < 4:
        return False
    row2 = lines[1].split(',')[0].strip().upper()
    row3 = lines[2].split(',')[0].strip().upper()
    return row2.startswith('MIN_DELIVERY') or row3.startswith('MAX_DELIVERY')


# ─── Auth Helper ──────────────────────────────────────────────────────────────

def check_auth(db, token: Optional[str], required_type: Optional[str] = None):
    if not token:
        return None
    sess = db.execute("SELECT * FROM sessions WHERE token = ?", (token,)).fetchone()
    if not sess:
        return None
    # Check session expiry
    expires = sess["expires_at"] if "expires_at" in sess.keys() else None
    if expires:
        from datetime import datetime as _dt
        try:
            exp_dt = _dt.fromisoformat(expires)
            if _dt.utcnow() > exp_dt:
                db.execute("DELETE FROM sessions WHERE token = ?", (token,))
                db.commit()
                return None
        except Exception:
            pass
    if required_type and sess["user_type"] != required_type:
        return None
    return {"user_type": sess["user_type"], "user_id": sess["user_id"], "token": sess["token"]}


# ─── FastAPI App Setup ────────────────────────────────────────────────────────

# Shared persistent DB connection
_db = None

def get_persistent_db():
    global _db
    if _db is None:
        _db = init_db()
        migrate_db_sapt()
        seed_demo_data(_db)
    return _db

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB on startup
    get_persistent_db()
    yield

app = FastAPI(title="Broad Reach Portal API", version="3.0", lifespan=lifespan)

# SECURITY: Restrict CORS to known origins in production.
# For local dev, override with CORS_ORIGINS=* environment variable.
_cors_origins = os.environ.get("CORS_ORIGINS", "https://www.perplexity.ai,https://sites.pplx.app").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files mount moved to end of file (after all API routes)
# to prevent it from catching /api/* requests

# ─── Root ────────────────────────────────────────────────────────────────────

@app.get("/auth/google-callback")
def google_callback_page():
    """Serves the Google OAuth callback page. Google redirects here after auth.
    The page extracts the access_token from the URL fragment and relays it
    back to the opener window via postMessage + localStorage."""
    return HTMLResponse("""
<!DOCTYPE html>
<html>
<head>
  <title>Signing in...</title>
  <style>
    body { font-family: system-ui, -apple-system, sans-serif; display: flex; align-items: center; justify-content: center; min-height: 100vh; margin: 0; background: #f8fafc; color: #334155; }
    .card { text-align: center; padding: 40px; background: white; border-radius: 16px; box-shadow: 0 4px 24px rgba(0,0,0,0.08); max-width: 400px; }
    .spinner { width: 40px; height: 40px; border: 3px solid #e2e8f0; border-top-color: #3b82f6; border-radius: 50%; animation: spin 0.8s linear infinite; margin: 0 auto 16px; }
    @keyframes spin { to { transform: rotate(360deg); } }
    h2 { margin: 0 0 8px; font-size: 18px; font-weight: 600; }
    p { margin: 0; font-size: 14px; color: #64748b; }
    .error { color: #dc2626; }
  </style>
</head>
<body>
  <div class="card">
    <div class="spinner" id="spinner"></div>
    <h2 id="title">Completing sign-in...</h2>
    <p id="message">Please wait, this window will close automatically.</p>
  </div>
  <script>
    (function() {
      try {
        var hash = window.location.hash.substring(1);
        var params = new URLSearchParams(hash);
        var accessToken = params.get('access_token');
        var error = params.get('error');
        if (error) {
          document.getElementById('spinner').style.display = 'none';
          document.getElementById('title').textContent = 'Sign-in cancelled';
          document.getElementById('message').textContent = error;
          document.getElementById('message').className = 'error';
          if (window.opener) { try { window.opener.postMessage({ type: 'google-sso-error', error: error }, '*'); } catch(e){} }
          setTimeout(function() { window.close(); }, 2000);
          return;
        }
        if (!accessToken) {
          document.getElementById('spinner').style.display = 'none';
          document.getElementById('title').textContent = 'Sign-in issue';
          document.getElementById('message').textContent = 'No token received. Close this window and try again.';
          document.getElementById('message').className = 'error';
          if (window.opener) { try { window.opener.postMessage({ type: 'google-sso-error', error: 'no_token' }, '*'); } catch(e){} }
          return;
        }
        document.getElementById('title').textContent = 'Sign-in successful!';
        document.getElementById('message').textContent = 'Redirecting you now...';
        var sent = false;
        if (window.opener) {
          try { window.opener.postMessage({ type: 'google-sso-token', access_token: accessToken }, '*'); sent = true; } catch(e){}
        }
        if (sent) {
          setTimeout(function() { window.close(); }, 800);
        } else {
          document.getElementById('spinner').style.display = 'none';
          document.getElementById('message').textContent = 'Please close this window and return to the portal.';
        }
      } catch(e) {
        document.getElementById('spinner').style.display = 'none';
        document.getElementById('title').textContent = 'Error';
        document.getElementById('message').textContent = e.message;
        document.getElementById('message').className = 'error';
      }
    })();
  </script>
</body>
</html>
""")

@app.get("/api/")
@app.get("/api")
def api_root():
    return {
        "status": "ok",
        "version": "3.0",
        "us_zones_loaded": len(US_ZONES),
        "ca_zones_loaded": len(CA_ZONES),
    }


# ─── Auth ─────────────────────────────────────────────────────────────────────

@app.post("/api/auth/login")
async def auth_login(request: Request, token: Optional[str] = Query(None)):
    db = get_persistent_db()
    body = await request.json()
    email      = body.get("email", "").strip().lower()
    password   = body.get("password", "")
    login_type = body.get("type", "client")

    if login_type == "admin":
        pw_hash = hashlib.sha256(password.encode()).hexdigest()
        admin = db.execute(
            "SELECT * FROM admins WHERE email = ? AND password_hash = ?",
            (email, pw_hash)).fetchone()
        if not admin:
            return JSONResponse({"error": "Invalid admin credentials"}, status_code=401)
        sess_token = str(uuid.uuid4())
        db.execute("INSERT INTO sessions (token, user_type, user_id, expires_at) VALUES (?, ?, ?, datetime('now', '+30 days'))",
                   (sess_token, "admin", admin["id"]))
        db.commit()
        return {"token": sess_token, "user_type": "admin", "user_id": admin["id"],
                "name": admin["name"], "email": admin["email"]}
    else:
        client = db.execute(
            "SELECT * FROM clients WHERE LOWER(email) = ?", (email,)).fetchone()
        if not client:
            return JSONResponse(
                {"error": "No invitation found for this email. Please contact your Broad Reach representative."},
                status_code=401)
        # If client has a password set, require it
        if client["password_hash"]:
            if not password:
                return JSONResponse(
                    {"error": "Password required. Check your invitation email for login details."},
                    status_code=401)
            pw_hash = hashlib.sha256(password.encode()).hexdigest()
            if pw_hash != client["password_hash"]:
                return JSONResponse(
                    {"error": "Incorrect password. Check your invitation email for the correct password."},
                    status_code=401)
        # Track login activity
        is_first_login = (client["login_count"] or 0) == 0 if "login_count" in client.keys() else True
        db.execute("UPDATE clients SET last_login_at = datetime('now'), login_count = COALESCE(login_count, 0) + 1 WHERE id = ?", (client["id"],))
        if is_first_login:
            db.execute("INSERT INTO notifications (type, message, client_id) VALUES (?, ?, ?)",
                       ("first_login", f"{client['contact_name'] or client['company_name']} just logged in for the first time!", client["id"]))
        sess_token = str(uuid.uuid4())
        db.execute("INSERT INTO sessions (token, user_type, user_id, expires_at) VALUES (?, ?, ?, datetime('now', '+7 days'))",
                   (sess_token, "client", client["id"]))
        db.commit()
        return {
            "token":        sess_token,
            "user_type":    "client",
            "user_id":      client["id"],
            "company_name": client["company_name"],
            "email":        client["email"],
            "contact_name": client["contact_name"],
            "logo_url":     client["logo_url"],
            "status":       client["status"]
        }


GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', '105648453442-gjnirc4fa4tmii07lt1lmd353serh4ng.apps.googleusercontent.com')
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', '')  # SECURITY: Set via environment variable

def _exchange_google_code(code: str):
    """Exchange a Google authorization code for access token and user info.
    Uses redirect_uri='postmessage' which is the standard for popup-based SPA flows."""
    import urllib.request, urllib.parse
    # Step 1: Exchange code for tokens
    token_data = urllib.parse.urlencode({
        'code': code,
        'client_id': GOOGLE_CLIENT_ID,
        'client_secret': GOOGLE_CLIENT_SECRET,
        'redirect_uri': 'postmessage',
        'grant_type': 'authorization_code'
    }).encode()
    req = urllib.request.Request('https://oauth2.googleapis.com/token',
                                 data=token_data,
                                 headers={'Content-Type': 'application/x-www-form-urlencoded'})
    with urllib.request.urlopen(req, timeout=10) as resp:
        tokens = json.loads(resp.read().decode())
    access_token = tokens.get('access_token', '')
    if not access_token:
        raise ValueError('No access token in code exchange response')
    # Step 2: Get user info
    req2 = urllib.request.Request('https://www.googleapis.com/oauth2/v3/userinfo',
                                  headers={'Authorization': f'Bearer {access_token}'})
    with urllib.request.urlopen(req2, timeout=10) as resp2:
        userinfo = json.loads(resp2.read().decode())
    return userinfo.get('email', '').strip().lower(), userinfo.get('name', ''), access_token


@app.post("/api/auth/google")
async def auth_google(request: Request, token: Optional[str] = Query(None)):
    """Google OAuth: verify ID token or access token, look up client by email, create session."""
    db = get_persistent_db()
    body = await request.json()
    id_token_str = body.get("credential", "") or body.get("id_token", "")
    access_token = body.get("access_token", "")
    auth_code = body.get("code", "")

    email = None

    if auth_code:
        # Authorization code flow (from initCodeClient popup)
        try:
            email, _, _ = _exchange_google_code(auth_code)
        except Exception as e:
            return JSONResponse({"error": f"Failed to exchange Google auth code: {e}"}, status_code=401)
    elif id_token_str:
        # Verify ID token (original flow)
        try:
            from google.oauth2 import id_token as google_id_token
            from google.auth.transport import requests as google_requests
            idinfo = google_id_token.verify_oauth2_token(
                id_token_str,
                google_requests.Request(),
                '105648453442-gjnirc4fa4tmii07lt1lmd353serh4ng.apps.googleusercontent.com'
            )
            email = idinfo.get("email", "").strip().lower()
        except Exception as e:
            return JSONResponse({"error": f"Invalid Google token: {e}"}, status_code=401)
    elif access_token:
        # Verify access token via Google's tokeninfo endpoint
        import urllib.request
        try:
            req = urllib.request.Request(f"https://www.googleapis.com/oauth2/v3/userinfo",
                                         headers={"Authorization": f"Bearer {access_token}"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                userinfo = json.loads(resp.read().decode())
                email = userinfo.get("email", "").strip().lower()
        except Exception as e:
            return JSONResponse({"error": f"Failed to verify Google access token: {e}"}, status_code=401)
    else:
        return JSONResponse({"error": "Google credential or access token required"}, status_code=400)

    if not email:
        return JSONResponse({"error": "No email in token"}, status_code=400)

    client = db.execute(
        "SELECT * FROM clients WHERE LOWER(email) = ?", (email,)).fetchone()
    if not client:
        return JSONResponse(
            {"error": "No invitation found for this email"},
            status_code=401)

    # Track login activity
    is_first_login = (client["login_count"] or 0) == 0 if "login_count" in client.keys() else True
    db.execute("UPDATE clients SET last_login_at = datetime('now'), login_count = COALESCE(login_count, 0) + 1 WHERE id = ?", (client["id"],))
    if is_first_login:
        db.execute("INSERT INTO notifications (type, message, client_id) VALUES (?, ?, ?)",
                   ("first_login", f"{client['contact_name'] or client['company_name']} just logged in for the first time!", client["id"]))

    sess_token = str(uuid.uuid4())
    db.execute("INSERT INTO sessions (token, user_type, user_id, expires_at) VALUES (?, ?, ?, datetime('now', '+7 days'))",
               (sess_token, "client", client["id"]))
    db.commit()
    return {
        "token":        sess_token,
        "user_type":    "client",
        "user_id":      client["id"],
        "company_name": client["company_name"],
        "email":        client["email"],
        "contact_name": client["contact_name"],
        "logo_url":     client["logo_url"],
        "status":       client["status"]
    }


@app.post("/api/auth/google-admin")
async def auth_google_admin(request: Request, token: Optional[str] = Query(None)):
    """Google OAuth for admin login — verify ID token or access token, match admin by email."""
    db = get_persistent_db()
    body = await request.json()
    id_token_str = body.get("credential", "") or body.get("id_token", "")
    access_token = body.get("access_token", "")
    auth_code = body.get("code", "")

    email = None
    name_from_google = ""

    if auth_code:
        # Authorization code flow (from initCodeClient popup)
        try:
            email, name_from_google, _ = _exchange_google_code(auth_code)
        except Exception as e:
            return JSONResponse({"error": f"Failed to exchange Google auth code: {e}"}, status_code=401)
    elif id_token_str:
        try:
            from google.oauth2 import id_token as google_id_token
            from google.auth.transport import requests as google_requests
            idinfo = google_id_token.verify_oauth2_token(
                id_token_str,
                google_requests.Request(),
                '105648453442-gjnirc4fa4tmii07lt1lmd353serh4ng.apps.googleusercontent.com'
            )
            email = idinfo.get("email", "").strip().lower()
            name_from_google = idinfo.get("name", "")
        except Exception as e:
            return JSONResponse({"error": f"Invalid Google token: {e}"}, status_code=401)
    elif access_token:
        import urllib.request
        try:
            req = urllib.request.Request(f"https://www.googleapis.com/oauth2/v3/userinfo",
                                         headers={"Authorization": f"Bearer {access_token}"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                userinfo = json.loads(resp.read().decode())
                email = userinfo.get("email", "").strip().lower()
                name_from_google = userinfo.get("name", "")
        except Exception as e:
            return JSONResponse({"error": f"Failed to verify Google access token: {e}"}, status_code=401)
    else:
        return JSONResponse({"error": "Google credential or access token required"}, status_code=400)

    if not email:
        return JSONResponse({"error": "No email in token"}, status_code=400)

    admin = db.execute("SELECT * FROM admins WHERE LOWER(email) = ?", (email,)).fetchone()
    if not admin:
        # Check if they already have a pending request
        existing_req = db.execute("SELECT * FROM access_requests WHERE LOWER(email) = ? AND status = 'pending'", (email,)).fetchone()
        return JSONResponse(
            {"error": "not_recognized", "email": email, "name": name_from_google,
             "already_requested": existing_req is not None},
            status_code=403)

    sess_token = str(uuid.uuid4())
    db.execute("INSERT INTO sessions (token, user_type, user_id, expires_at) VALUES (?, ?, ?, datetime('now', '+30 days'))",
               (sess_token, "admin", admin["id"]))
    db.commit()
    return {
        "token": sess_token,
        "user_type": "admin",
        "user_id": admin["id"],
        "name": admin["name"],
        "email": admin["email"]
    }


# ─── Clients ──────────────────────────────────────────────────────────────────

@app.get("/api/clients")
def list_clients(token: Optional[str] = Query(None)):
    db = get_persistent_db()
    rows = db.execute("SELECT * FROM clients WHERE COALESCE(archived, 0) = 0 ORDER BY invited_at DESC").fetchall()
    clients = []
    for r in rows:
        c = dict(r)
        c["documents_json"] = json.loads(c["documents_json"])
        sd = db.execute(
            "SELECT summary_json, row_count FROM shipping_data WHERE client_id = ? ORDER BY id DESC LIMIT 1",
            (r["id"],)).fetchone()
        c["has_shipping_data"] = sd is not None
        if sd:
            c["shipping_summary"] = json.loads(sd["summary_json"])
        an = db.execute(
            "SELECT status FROM analyses WHERE client_id = ? ORDER BY id DESC LIMIT 1",
            (r["id"],)).fetchone()
        c["analysis_status"] = an["status"] if an else None
        clients.append(c)
    return clients


@app.get("/api/archived-clients")
def list_archived_clients(token: Optional[str] = Query(None)):
    db = get_persistent_db()
    rows = db.execute("SELECT * FROM clients WHERE archived = 1 ORDER BY invited_at DESC").fetchall()
    clients = []
    for r in rows:
        c = dict(r)
        c["documents_json"] = json.loads(c["documents_json"])
        clients.append(c)
    return clients


@app.post("/api/clients", status_code=201)
async def create_client(request: Request, token: Optional[str] = Query(None)):
    db = get_persistent_db()
    body = await request.json()
    name  = body.get("company_name", "")
    email = body.get("email", "")
    if not name or not email:
        return JSONResponse({"error": "Company name and email required"}, status_code=400)
    try:
        db.execute("""INSERT INTO clients (company_name, email, contact_name, logo_url, documents_json)
                      VALUES (?, ?, ?, ?, ?)""",
                   (name, email, body.get("contact_name", ""),
                    body.get("logo_url", ""), json.dumps(body.get("documents", []))))
        db.commit()
        client_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        return {"id": client_id, "message": "Client invited"}
    except sqlite3.IntegrityError:
        return JSONResponse({"error": "Client with this email already exists"}, status_code=400)


@app.get("/api/clients/{client_id}")
def get_client(client_id: int, token: Optional[str] = Query(None), role: Optional[str] = Query(None)):
    db = get_persistent_db()
    c = db.execute("SELECT * FROM clients WHERE id = ?", (client_id,)).fetchone()
    if not c:
        return JSONResponse({"error": "Client not found"}, status_code=404)
    result = dict(c)
    result["documents_json"]  = json.loads(result["documents_json"])
    result["setup_info_json"] = json.loads(result["setup_info_json"])
    sd = db.execute(
        "SELECT * FROM shipping_data WHERE client_id = ? ORDER BY id DESC LIMIT 1",
        (client_id,)).fetchone()
    if sd:
        result["shipping_data"] = {
            "id":           sd["id"],
            "data":         json.loads(sd["data_json"]),
            "row_count":    sd["row_count"],
            "summary":      json.loads(sd["summary_json"]),
            "uploaded_at":  sd["uploaded_at"],
            "confirmed_at": sd["confirmed_at"] if "confirmed_at" in sd.keys() else None
        }
    else:
        result["shipping_data"] = None
    an = db.execute(
        "SELECT * FROM analyses WHERE client_id = ? ORDER BY id DESC LIMIT 1",
        (client_id,)).fetchone()
    if an:
        analysis_results = json.loads(an["results_json"])
        # Strip internal cost/profit data when serving to client users
        if role == "client":
            analysis_results = _strip_internal_fields(analysis_results)
        result["analysis"] = {
            "id":          an["id"],
            "config":      json.loads(an["config_json"]),
            "results":     analysis_results,
            "status":      an["status"],
            "created_at":  an["created_at"],
            "published_at": an["published_at"]
        }
    else:
        result["analysis"] = None
    return result


def _strip_internal_fields(results):
    """Remove buy price, profit, margin, and other internal cost fields
    from analysis results before sending to client users."""
    INTERNAL_SUMMARY_KEYS = {
        "total_base_cost", "total_markup_revenue", "total_service_cost",
        "margin_gross", "total_buy_cost", "total_profit_actual",
        "actual_margin_pct"
    }
    INTERNAL_RATE_KEYS = {
        "base_buy", "fuel_buy", "buy_price", "profit", "margin_pct",
        "base",  # base is the pre-markup cost
    }
    INTERNAL_MIX_KEYS = {
        "total_buy", "total_profit", "service_cost", "margin_gross", "margin_pct"
    }
    # Strip summary-level internal fields
    if "summary" in results and isinstance(results["summary"], dict):
        for k in INTERNAL_SUMMARY_KEYS:
            results["summary"].pop(k, None)
    # Strip shipment-level internal fields
    if "shipments" in results:
        for ship in results["shipments"]:
            for k in ("buy_price", "profit", "margin_pct"):
                ship.pop(k, None)
            if "all_rates" in ship:
                for svc_name, rate in ship["all_rates"].items():
                    for k in INTERNAL_RATE_KEYS:
                        rate.pop(k, None)
    # Strip service mix internal fields
    if "br_service_mix" in results:
        for svc_name, mix in results["br_service_mix"].items():
            for k in INTERNAL_MIX_KEYS:
                mix.pop(k, None)
    return results


@app.get("/api/clients/{client_id}/analysis-excel")
async def download_analysis_excel(client_id: int, token: Optional[str] = Query(None), role: Optional[str] = Query(None),
                                   analysis_id: Optional[int] = Query(None)):
    """Generate and return a branded Excel analysis workbook."""
    import io
    from excel_generator import generate_analysis_excel
    db = get_persistent_db()
    # Require valid session
    auth = check_auth(db, token)
    if not auth:
        raise HTTPException(status_code=401, detail="Authentication required")
    # Clients can only download their own analysis
    if auth["user_type"] == "client" and auth["user_id"] != client_id:
        raise HTTPException(status_code=403, detail="Access denied")
    client = db.execute("SELECT * FROM clients WHERE id = ?", (client_id,)).fetchone()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    if analysis_id:
        an = db.execute(
            "SELECT * FROM analyses WHERE id = ? AND client_id = ?",
            (analysis_id, client_id)).fetchone()
    else:
        an = db.execute(
            "SELECT * FROM analyses WHERE client_id = ? ORDER BY id DESC LIMIT 1",
            (client_id,)).fetchone()
    if not an:
        raise HTTPException(status_code=404, detail="No analysis found")
    results = json.loads(an["results_json"])
    if role == "client":
        results = _strip_internal_fields(results)
    company = client["company_name"] or "Company"
    cur = results.get("currency", "USD")
    xlsx_bytes = generate_analysis_excel(results, company, currency=cur, role=role or "admin")
    slug = re.sub(r'[^a-zA-Z0-9]', '-', company).strip('-').lower()
    filename = f"broad-reach-{slug}-analysis.xlsx"
    return StreamingResponse(
        io.BytesIO(xlsx_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@app.put("/api/clients/{client_id}")
async def update_client(client_id: int, request: Request, token: Optional[str] = Query(None)):
    db = get_persistent_db()
    auth = check_auth(db, token, "admin")
    if not auth:
        raise HTTPException(status_code=401, detail="Admin authentication required")
    body = await request.json()
    fields = []
    vals   = []
    for f in ["company_name", "email", "contact_name", "logo_url", "status"]:
        if f in body:
            fields.append(f"{f} = ?")
            vals.append(body[f])
    if fields:
        vals.append(client_id)
        db.execute(f"UPDATE clients SET {', '.join(fields)} WHERE id = ?", vals)
        db.commit()
    return {"message": "Client updated"}


@app.post("/api/clients/{client_id}/archive")
async def archive_client(client_id: int, request: Request, token: Optional[str] = Query(None)):
    db = get_persistent_db()
    body = await request.json()
    archived = 1 if body.get("archived", True) else 0
    db.execute("UPDATE clients SET archived = ? WHERE id = ?", (archived, client_id))
    client = db.execute("SELECT company_name FROM clients WHERE id = ?", (client_id,)).fetchone()
    name = client["company_name"] if client else "Unknown"
    action = "archived" if archived else "restored"
    db.execute("INSERT INTO notifications (type, message, client_id) VALUES (?, ?, ?)",
               ("client_archived", f"{name} {action}", client_id))
    db.commit()
    return {"message": f"Client {action}"}


@app.post("/api/clients/{client_id}/documents")
async def update_client_documents(client_id: int, request: Request, token: Optional[str] = Query(None)):
    db = get_persistent_db()
    body = await request.json()
    doc_ids = body.get("document_ids", [])
    db.execute("UPDATE clients SET documents_json = ? WHERE id = ?",
               (json.dumps(doc_ids), client_id))
    db.commit()
    return {"message": "Documents updated"}


import secrets, string
def _generate_password(length=10):
    """Generate a friendly, readable password."""
    # Use a mix that avoids confusing chars (0/O, 1/l/I)
    chars = 'abcdefghjkmnpqrstuvwxyz' + 'ABCDEFGHJKMNPQRSTUVWXYZ' + '23456789'
    return ''.join(secrets.choice(chars) for _ in range(length))


@app.post("/api/clients/{client_id}/generate-invitation")
async def generate_invitation(client_id: int, request: Request, token: Optional[str] = Query(None)):
    """Generate a password for a client and return invitation email content."""
    db = get_persistent_db()
    client = db.execute("SELECT * FROM clients WHERE id = ?", (client_id,)).fetchone()
    if not client:
        return JSONResponse({"error": "Client not found"}, status_code=404)

    body = await request.json()
    portal_url = body.get("portal_url", "")
    sender_name = body.get("sender_name", "Craig")

    # Generate a new password
    raw_password = _generate_password(10)
    pw_hash = hashlib.sha256(raw_password.encode()).hexdigest()

    # Store the hashed password
    db.execute("UPDATE clients SET password_hash = ? WHERE id = ?", (pw_hash, client_id))
    db.commit()

    contact_name = client["contact_name"] or client["company_name"]
    first_name = contact_name.split()[0] if contact_name else "there"
    company = client["company_name"]
    email_addr = client["email"]

    # Build the email content
    portal_link = portal_url if portal_url else '[Portal link will be shared]'
    email_subject = f"{sender_name} from Broad Reach — Your Shipping Savings Portal"
    email_body = f"""Hi {first_name},

I hope this message finds you well! I'm reaching out because I'd love to show you how much {company} could save on shipping.

I've set up a personal portal for you where we can collect your shipping data, analyze it against our carrier network, and show you exactly how much you could save.


━━━  HERE'S HOW IT WORKS  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

   Step 1 ▸ YOU UPLOAD
   Share your shipping history — just a CSV file.
   Takes about 5 minutes.

   Step 2 ▸ WE ANALYZE
   Our team rates your data against 145+ carrier
   rate cards across 9 carriers.

   Step 3 ▸ YOU DECIDE
   Review your personalized savings report
   and see your potential.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


Your portal is ready:

   {portal_link}

Just click the link and sign in with your Google account ({email_addr}) — that's it. The portal will walk you through everything step by step. The whole upload process takes about 5 minutes, and you'll have your savings analysis back within 1-2 business days.

If you have any questions at all, just reply to this email. I'm here to help.

Looking forward to working with you!

Best,
{sender_name}
Broad Reach Logistics

—
Can't use Google Sign-In? You can also log in with your email and this temporary password: {raw_password}
"""

    return {
        "password": raw_password,
        "email_subject": email_subject,
        "email_body": email_body,
        "client_email": email_addr,
        "client_name": contact_name,
        "company_name": company,
        "invite_count": client["invite_count"] if "invite_count" in client.keys() else 0,
        "last_invited_at": client["invitation_sent_at"]
    }


@app.post("/api/clients/{client_id}/mark-invitation-sent")
async def mark_invitation_sent(client_id: int, request: Request, token: Optional[str] = Query(None)):
    """Mark that the invitation email was sent."""
    db = get_persistent_db()
    db.execute("UPDATE clients SET invitation_sent_at = datetime('now') WHERE id = ?", (client_id,))
    db.commit()
    return {"message": "Invitation marked as sent"}


@app.post("/api/clients/{client_id}/send-invitation")
async def send_invitation_email(client_id: int, request: Request, token: Optional[str] = Query(None)):
    """Queue an invitation email for sending and mark it sent."""
    db = get_persistent_db()
    client = db.execute("SELECT * FROM clients WHERE id = ?", (client_id,)).fetchone()
    if not client:
        return JSONResponse({"error": "Client not found"}, status_code=404)

    body = await request.json()
    to_email = body.get("to_email", client["email"])
    to_name = body.get("to_name", client["contact_name"] or client["company_name"])
    subject = body.get("subject", "")
    email_body = body.get("body", "")

    if not subject or not email_body:
        return JSONResponse({"error": "Subject and body are required"}, status_code=400)

    # Insert into pending_emails queue
    cur = db.execute(
        "INSERT INTO pending_emails (client_id, to_email, to_name, subject, body, email_type, status) VALUES (?, ?, ?, ?, ?, 'invitation', 'pending')",
        (client_id, to_email, to_name, subject, email_body)
    )
    email_id = cur.lastrowid

    # Mark invitation sent on the client
    db.execute("UPDATE clients SET invitation_sent_at = datetime('now'), invite_count = COALESCE(invite_count, 0) + 1 WHERE id = ?", (client_id,))
    db.commit()

    # Create a notification for admin
    db.execute(
        "INSERT INTO notifications (type, message, client_id) VALUES (?, ?, ?)",
        ("email_queued", f"Invitation email queued for {to_name} ({to_email})", client_id)
    )
    db.commit()

    return {"message": "Email queued for sending", "email_id": email_id}


@app.get("/api/pending-emails")
def get_pending_emails(status: str = "pending", token: Optional[str] = Query(None)):
    """Get pending emails (for the agent to send via Gmail)."""
    db = get_persistent_db()
    rows = db.execute(
        "SELECT pe.*, c.company_name FROM pending_emails pe LEFT JOIN clients c ON pe.client_id = c.id WHERE pe.status = ? ORDER BY pe.created_at ASC",
        (status,)
    ).fetchall()
    return [{**dict(r)} for r in rows]


@app.post("/api/pending-emails/{email_id}/mark-sent")
async def mark_email_sent(email_id: int, request: Request, token: Optional[str] = Query(None)):
    """Mark an email as sent after the agent sends it via Gmail."""
    db = get_persistent_db()
    db.execute(
        "UPDATE pending_emails SET status = 'sent', sent_at = datetime('now') WHERE id = ?",
        (email_id,)
    )
    db.commit()
    return {"message": "Email marked as sent"}


@app.post("/api/clients/{client_id}/shipping-data", status_code=201)
async def upload_shipping_data(client_id: int, request: Request, token: Optional[str] = Query(None)):
    db = get_persistent_db()
    body = await request.json()
    data = body.get("data", [])
    if not data:
        return JSONResponse({"error": "No shipping data provided"}, status_code=400)
    origin_mode      = body.get("origin_mode", "single")
    origin_defaults  = body.get("origin_defaults") or {}
    unit_system      = body.get("unit_system", {"weight": "lbs", "dimensions": "in"})
    currency         = body.get("currency", "USD")
    carriers_found   = list(set(s.get("carrier", "Unknown") for s in data))
    total_spend      = round(sum(float(s.get("price", 0)) for s in data), 2)
    avg_weight       = round(sum(float(s.get("weight", 0)) for s in data) / len(data), 1) if data else 0
    avg_billed       = round(sum(float(s.get("billed_weight", 0) or s.get("weight", 0)) for s in data) / len(data), 1) if data else 0
    weight_unit      = unit_system.get("weight", "lbs")
    summary = {
        "row_count":         len(data),
        "date_range":        "Uploaded " + datetime.now().strftime("%Y-%m-%d"),
        "carriers":          carriers_found,
        "total_spend":       total_spend,
        "avg_weight":        avg_weight,
        "avg_billed_weight": avg_billed,
        "weight_unit":       weight_unit,
        "unit_system":       unit_system,
        "currency":          currency,
        "origin_mode":       origin_mode,
        "origin_defaults":   origin_defaults
    }
    db.execute("""INSERT INTO shipping_data (client_id, data_json, row_count, summary_json)
                  VALUES (?, ?, ?, ?)""",
               (client_id, json.dumps(data), len(data), json.dumps(summary)))
    db.execute("UPDATE clients SET status = 'Data Uploaded' WHERE id = ?", (client_id,))
    client_row = db.execute(
        "SELECT company_name FROM clients WHERE id = ?", (client_id,)).fetchone()
    company = client_row["company_name"] if client_row else "Unknown"
    db.execute("""INSERT INTO notifications (type, message, client_id) VALUES (?, ?, ?)""",
               ("upload_received",
                f"{company} uploaded {len(data)} shipments — awaiting client confirmation",
                client_id))
    db.commit()
    return {"message": "Shipping data uploaded", "summary": summary}


@app.get("/api/clients/{client_id}/shipping-data")
def get_shipping_data(client_id: int, token: Optional[str] = Query(None)):
    db = get_persistent_db()
    sd = db.execute(
        "SELECT * FROM shipping_data WHERE client_id = ? ORDER BY id DESC LIMIT 1",
        (client_id,)).fetchone()
    if not sd:
        return {"data": [], "summary": {}, "confirmed_at": None}
    return {
        "data":         json.loads(sd["data_json"]),
        "summary":      json.loads(sd["summary_json"]),
        "row_count":    sd["row_count"],
        "uploaded_at":  sd["uploaded_at"],
        "confirmed_at": sd["confirmed_at"] if "confirmed_at" in sd.keys() else None
    }


@app.delete("/api/clients/{client_id}/shipping-data")
def delete_shipping_data(client_id: int, token: Optional[str] = Query(None)):
    db = get_persistent_db()
    # Get company name for notification
    client_row = db.execute(
        "SELECT company_name FROM clients WHERE id = ?", (client_id,)).fetchone()
    company = client_row["company_name"] if client_row else "Unknown"
    db.execute("DELETE FROM shipping_data WHERE client_id = ?", (client_id,))
    db.execute("DELETE FROM analyses WHERE client_id = ?", (client_id,))
    db.execute("UPDATE clients SET status = 'Invited' WHERE id = ?", (client_id,))
    # Notify admin that client cleared data for re-upload
    db.execute(
        "INSERT INTO notifications (type, message, client_id) VALUES (?, ?, ?)",
        ("data_cleared",
         f"{company} cleared their shipping data and will upload new data for re-analysis",
         client_id))
    db.commit()
    return {"message": "Shipping data removed"}


@app.post("/api/clients/{client_id}/confirm-data")
async def confirm_shipping_data(client_id: int, request: Request, token: Optional[str] = Query(None)):
    """Client confirms their data looks correct and submits for analysis."""
    db = get_persistent_db()
    sd = db.execute(
        "SELECT id FROM shipping_data WHERE client_id = ? ORDER BY id DESC LIMIT 1",
        (client_id,)).fetchone()
    if not sd:
        return JSONResponse({"error": "No shipping data to confirm"}, status_code=400)
    db.execute(
        "UPDATE shipping_data SET confirmed_at = datetime('now') WHERE id = ?",
        (sd["id"],))
    db.execute(
        "UPDATE clients SET status = 'Analysis Pending' WHERE id = ?",
        (client_id,))
    client_row = db.execute(
        "SELECT company_name FROM clients WHERE id = ?", (client_id,)).fetchone()
    company = client_row["company_name"] if client_row else "Unknown"
    db.execute(
        "INSERT INTO notifications (type, message, client_id) VALUES (?, ?, ?)",
        ("data_confirmed",
         f"{company} confirmed their shipping data — ready for analysis",
         client_id))
    db.commit()
    return {"message": "Data confirmed and submitted for analysis"}


@app.post("/api/clients/{client_id}/analysis", status_code=201)
async def run_analysis(client_id: int, request: Request, token: Optional[str] = Query(None)):
    db = get_persistent_db()
    body = await request.json()
    sd = db.execute(
        "SELECT data_json, summary_json FROM shipping_data WHERE client_id = ? ORDER BY id DESC LIMIT 1",
        (client_id,)).fetchone()
    if not sd:
        return JSONResponse({"error": "No shipping data available"}, status_code=400)
    shipments   = json.loads(sd["data_json"])
    sd_summary  = json.loads(sd["summary_json"]) if sd["summary_json"] else {}
    unit_system = sd_summary.get("unit_system", {"weight": "lbs", "dimensions": "in"})
    currency    = sd_summary.get("currency", "USD")
    results     = run_rate_analysis(shipments, body, db, unit_system=unit_system)
    results["currency"] = currency
    # Always insert a new analysis version (preserve history)
    db.execute("""INSERT INTO analyses (client_id, config_json, results_json, status)
                  VALUES (?, ?, ?, 'draft')""",
               (client_id, json.dumps(body), json.dumps(results)))
    db.commit()
    analysis_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    return {"message": "Analysis complete", "results": results, "analysis_id": analysis_id}


@app.post("/api/clients/{client_id}/analysis/publish")
def publish_analysis(client_id: int, request: Request = None, token: Optional[str] = Query(None)):
    db = get_persistent_db()
    # Publish only the most recent analysis for this client
    latest = db.execute(
        "SELECT id FROM analyses WHERE client_id = ? ORDER BY id DESC LIMIT 1",
        (client_id,)).fetchone()
    if not latest:
        return JSONResponse({"error": "No analysis found"}, status_code=404)
    db.execute("""UPDATE analyses SET status = 'published', published_at = datetime('now')
                  WHERE id = ?""", (latest["id"],))
    db.execute("UPDATE clients SET status = 'Analysis Complete' WHERE id = ?", (client_id,))
    client_row = db.execute(
        "SELECT company_name, email, contact_name FROM clients WHERE id = ?", (client_id,)).fetchone()
    company = client_row["company_name"] if client_row else "Unknown"
    client_email = client_row["email"] if client_row else None
    contact_name = client_row["contact_name"] if client_row else ""
    first_name = contact_name.split()[0] if contact_name else "there"
    db.execute("""INSERT INTO client_notifications (client_id, type, message)
                  VALUES (?, ?, ?)""",
               (client_id, "analysis_ready",
                "Your savings analysis is ready! Log in to view your personalized pricing package."))
    # Queue email notification to client
    if client_email:
        email_subject = f"Your Shipping Savings Analysis is Ready — {company}"
        email_body = f"""Hi {first_name},

Great news! Your personalized shipping savings analysis is complete and ready for you to review.

Our team has analyzed your shipping data against our carrier network and put together a custom pricing package for {company}.


━━━  WHAT'S INSIDE  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

   ✓  Side-by-side cost comparison
   ✓  Savings breakdown by carrier & service
   ✓  Your personalized rate card
   ✓  Estimated annual savings

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


Log in to your portal to see the full analysis:

   Portal:  (use the same link from your invitation email)
   Email:   {client_email}

Just sign in and head to the "Your Analysis" step to see everything.

If you have any questions about the analysis or want to discuss next steps, just reply to this email. I'm happy to walk you through it.

Best,
Craig
Broad Reach Logistics
"""
        db.execute("""INSERT INTO pending_emails (client_id, to_email, to_name, subject, body, email_type)
                      VALUES (?, ?, ?, ?, ?, 'analysis_ready')""",
                   (client_id, client_email, contact_name or company, email_subject, email_body))
    db.commit()
    return {"message": "Analysis published", "send_email": True, "company_name": company}


@app.get("/api/clients/{client_id}/analysis-history")
def get_analysis_history(client_id: int, token: Optional[str] = Query(None)):
    """Return list of all analysis versions for a client (metadata only, no full results)."""
    db = get_persistent_db()
    rows = db.execute(
        """SELECT id, status, created_at, published_at,
                  json_extract(config_json, '$.rate_card_ids') as rc_ids,
                  json_extract(results_json, '$.summary.total_sell') as total_sell,
                  json_extract(results_json, '$.summary.total_client_spend') as total_spend,
                  json_extract(results_json, '$.summary.total_savings') as total_savings,
                  json_extract(results_json, '$.summary.savings_pct') as savings_pct
           FROM analyses WHERE client_id = ? ORDER BY id DESC""",
        (client_id,)).fetchall()
    history = []
    for r in rows:
        entry = dict(r)
        try:
            entry["rc_ids"] = json.loads(entry["rc_ids"]) if entry["rc_ids"] else []
        except Exception:
            entry["rc_ids"] = []
        history.append(entry)
    return history


@app.get("/api/clients/{client_id}/analysis/{analysis_id}")
def get_specific_analysis(client_id: int, analysis_id: int, token: Optional[str] = Query(None),
                          role: Optional[str] = Query(None)):
    """Get a specific analysis version by ID."""
    db = get_persistent_db()
    an = db.execute(
        "SELECT * FROM analyses WHERE id = ? AND client_id = ?",
        (analysis_id, client_id)).fetchone()
    if not an:
        return JSONResponse({"error": "Analysis not found"}, status_code=404)
    analysis_results = json.loads(an["results_json"])
    if role == "client":
        analysis_results = _strip_internal_fields(analysis_results)
    return {
        "id":          an["id"],
        "config":      json.loads(an["config_json"]),
        "results":     analysis_results,
        "status":      an["status"],
        "created_at":  an["created_at"],
        "published_at": an["published_at"]
    }


@app.post("/api/clients/{client_id}/setup")
async def save_setup(client_id: int, request: Request, token: Optional[str] = Query(None)):
    db = get_persistent_db()
    body = await request.json()
    db.execute("UPDATE clients SET setup_info_json = ? WHERE id = ?",
               (json.dumps(body), client_id))
    db.commit()
    return {"message": "Setup info saved"}


@app.get("/api/clients/{client_id}/setup")
def get_setup(client_id: int, token: Optional[str] = Query(None)):
    db = get_persistent_db()
    c = db.execute("SELECT setup_info_json FROM clients WHERE id = ?", (client_id,)).fetchone()
    if c:
        return json.loads(c["setup_info_json"])
    return {}


@app.get("/api/clients/{client_id}/notifications")
def get_client_notifications(client_id: int, token: Optional[str] = Query(None)):
    db = get_persistent_db()
    rows = db.execute("""
        SELECT * FROM client_notifications WHERE client_id = ?
        ORDER BY created_at DESC LIMIT 20
    """, (client_id,)).fetchall()
    notifs      = [dict(r) for r in rows]
    unread_count = db.execute(
        "SELECT COUNT(*) FROM client_notifications WHERE client_id = ? AND read = 0",
        (client_id,)
    ).fetchone()[0]
    return {"notifications": notifs, "unread_count": unread_count}


@app.post("/api/clients/{client_id}/notifications/read")
def mark_client_notifications_read(client_id: int, token: Optional[str] = Query(None)):
    db = get_persistent_db()
    db.execute("UPDATE client_notifications SET read = 1 WHERE client_id = ?", (client_id,))
    db.commit()
    return {"message": "Marked as read"}


# ─── Rate Cards ───────────────────────────────────────────────────────────────

@app.get("/api/rate-cards")
def list_rate_cards(token: Optional[str] = Query(None)):
    db = get_persistent_db()
    rows = db.execute("SELECT * FROM rate_cards ORDER BY created_at DESC").fetchall()
    cards = []
    for r in rows:
        c = dict(r)
        grid = json.loads(c["rate_grid_json"])
        c["zone_count"]   = len(next(iter(grid.values()), {})) if grid else 0
        c["weight_count"] = len(grid)
        c["pricing_type"] = c.get("pricing_type", "WEIGHT_POUNDS")
        c["dim_divisor"]  = c.get("dim_divisor", 166)
        c["zone_key"]     = c.get("zone_key", "")
        c["fuel_rate"]    = c.get("fuel_rate", 0) or 0
        c["fuel_type"]    = c.get("fuel_type", "percentage") or "percentage"
        c["fuel_discount"] = c.get("fuel_discount", 0) or 0
        c["dim_threshold_cu_in"] = c.get("dim_threshold_cu_in", 0) or 0
        c["dim_divisor_alt"] = c.get("dim_divisor_alt", 0) or 0
        c["service_class"] = c.get("service_class", "economy") or "economy"
        c["card_type"]    = c.get("card_type", "sell_current") or "sell_current"
        c["fuel_rate_buy"] = c.get("fuel_rate_buy", 0) or 0
        c["fuel_rate_sell"] = c.get("fuel_rate_sell", 0) or 0
        c["dim_divisor_buy"] = c.get("dim_divisor_buy", 166) or 166
        cards.append(c)
    return cards


@app.post("/api/rate-cards", status_code=201)
async def create_rate_card(request: Request, token: Optional[str] = Query(None)):
    db = get_persistent_db()
    body = await request.json()
    csv_data     = body.get("csv_data", "")
    rate_grid    = body.get("rate_grid", {})
    pricing_type = body.get("pricing_type", "WEIGHT_POUNDS")
    name         = body.get("name", "")
    service_type = body.get("service_type", "")
    if csv_data and csv_data.strip():
        if is_wizmo_format(csv_data):
            parsed_grid, svc_name, min_days, max_days, parsed_ptype, zones = parse_wizmo_csv(csv_data)
            if parsed_grid:
                rate_grid = parsed_grid
                if not name and svc_name:
                    name = svc_name
                if not service_type and min_days and max_days:
                    service_type = f"{min_days}-{max_days} day"
                pricing_type = parsed_ptype or pricing_type
        else:
            lines = csv_data.strip().replace('\r\n', '\n').replace('\r', '\n').split('\n')
            rate_grid = {}
            for i, line in enumerate(lines):
                if not line.strip():
                    continue
                parts_csv = line.split(',')
                weight = parts_csv[0].strip()
                if i == 0 and (weight.lower() == 'weight' or not weight.replace('.','').replace('-','').isdigit()):
                    continue
                rate_grid[weight] = {}
                for z in range(1, len(parts_csv)):
                    val = parts_csv[z].strip()
                    try:
                        rate_grid[weight][str(z)] = float(val) if val else 0
                    except ValueError:
                        rate_grid[weight][str(z)] = 0
    dim_divisor = float(body.get("dim_divisor", 166))
    currency    = body.get("currency", "USD")
    country     = body.get("country",  "US")
    version     = body.get("version",  "v1")
    zone_key    = body.get("zone_key", "")
    fuel_rate   = float(body.get("fuel_rate", 0) or 0)
    fuel_type   = body.get("fuel_type", "percentage") or "percentage"
    fuel_discount = float(body.get("fuel_discount", 0) or 0)
    dim_threshold_cu_in = float(body.get("dim_threshold_cu_in", 0) or 0)
    dim_divisor_alt     = float(body.get("dim_divisor_alt", 0) or 0)
    transit_days_json   = json.dumps(body.get("transit_days_json", {}) or {})
    accessorials_json   = json.dumps(body.get("accessorials_json", {}) or {})
    service_class = body.get("service_class", "economy") or "economy"
    card_type   = body.get("card_type", "sell_current") or "sell_current"
    fuel_rate_buy  = float(body.get("fuel_rate_buy", 0) or 0)
    fuel_rate_sell = float(body.get("fuel_rate_sell", 0) or 0)
    dim_divisor_buy = float(body.get("dim_divisor_buy", 166) or 166)
    db.execute("""INSERT INTO rate_cards
        (name, service_type, carrier, pricing_type, description, rate_grid_json,
         zone_mapping_json, zone_key, dim_divisor, currency, country, version, status,
         fuel_rate, fuel_type, fuel_discount, dim_threshold_cu_in, dim_divisor_alt,
         transit_days_json, accessorials_json, service_class, card_type,
         fuel_rate_buy, fuel_rate_sell, dim_divisor_buy)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,'active',?,?,?,?,?,?,?,?,?,?,?,?)""",
        (name, service_type, body.get("carrier", ""), pricing_type,
         body.get("description", ""), json.dumps(rate_grid),
         json.dumps(body.get("zone_mapping", {})), zone_key,
         dim_divisor, currency, country, version,
         fuel_rate, fuel_type, fuel_discount, dim_threshold_cu_in, dim_divisor_alt,
         transit_days_json, accessorials_json, service_class, card_type,
         fuel_rate_buy, fuel_rate_sell, dim_divisor_buy))
    db.commit()
    rc_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    return {"id": rc_id, "message": "Rate card created"}


@app.get("/api/rate-cards/{rc_id}")
def get_rate_card(rc_id: str, token: Optional[str] = Query(None)):
    db = get_persistent_db()
    # Handle compare sub-route
    if rc_id == "compare":
        return JSONResponse({"error": "Use POST /api/rate-cards/compare"}, status_code=405)
    r = db.execute("SELECT * FROM rate_cards WHERE id = ?", (rc_id,)).fetchone()
    if not r:
        return JSONResponse({"error": "Rate card not found"}, status_code=404)
    result = dict(r)
    result["rate_grid_json"]   = json.loads(result["rate_grid_json"])
    result["zone_mapping_json"] = json.loads(result["zone_mapping_json"])
    result["dim_divisor"]      = result.get("dim_divisor", 166)
    result["zone_key"]         = result.get("zone_key", "")
    result["fuel_rate"]        = result.get("fuel_rate", 0) or 0
    result["fuel_type"]        = result.get("fuel_type", "percentage") or "percentage"
    result["fuel_discount"]    = result.get("fuel_discount", 0) or 0
    result["dim_threshold_cu_in"] = result.get("dim_threshold_cu_in", 0) or 0
    result["dim_divisor_alt"]  = result.get("dim_divisor_alt", 0) or 0
    result["service_class"]    = result.get("service_class", "economy") or "economy"
    result["card_type"]        = result.get("card_type", "sell_current") or "sell_current"
    result["fuel_rate_buy"]    = result.get("fuel_rate_buy", 0) or 0
    result["fuel_rate_sell"]   = result.get("fuel_rate_sell", 0) or 0
    result["dim_divisor_buy"]  = result.get("dim_divisor_buy", 166) or 166
    try:
        result["transit_days_json"] = json.loads(result["transit_days_json"]) if result.get("transit_days_json") else {}
    except Exception:
        result["transit_days_json"] = {}
    try:
        result["accessorials_json"] = json.loads(result["accessorials_json"]) if result.get("accessorials_json") else {}
    except Exception:
        result["accessorials_json"] = {}
    return result


@app.put("/api/rate-cards/{rc_id}")
async def update_rate_card(rc_id: int, request: Request, token: Optional[str] = Query(None)):
    db = get_persistent_db()
    body = await request.json()
    fields = []
    vals   = []
    for f in ["name", "service_type", "carrier", "description", "pricing_type",
              "currency", "country", "version", "status", "effective_date",
              "expiration_date", "zone_key", "fuel_type", "service_class", "card_type"]:
        if f in body:
            fields.append(f"{f} = ?")
            vals.append(body[f])
    if "dim_divisor" in body:
        fields.append("dim_divisor = ?")
        vals.append(float(body["dim_divisor"]))
    if "fuel_rate" in body:
        fields.append("fuel_rate = ?")
        vals.append(float(body["fuel_rate"] or 0))
    if "fuel_discount" in body:
        fields.append("fuel_discount = ?")
        vals.append(float(body["fuel_discount"] or 0))
    if "dim_threshold_cu_in" in body:
        fields.append("dim_threshold_cu_in = ?")
        vals.append(float(body["dim_threshold_cu_in"] or 0))
    if "dim_divisor_alt" in body:
        fields.append("dim_divisor_alt = ?")
        vals.append(float(body["dim_divisor_alt"] or 0))
    if "fuel_rate_buy" in body:
        fields.append("fuel_rate_buy = ?")
        vals.append(float(body["fuel_rate_buy"] or 0))
    if "fuel_rate_sell" in body:
        fields.append("fuel_rate_sell = ?")
        vals.append(float(body["fuel_rate_sell"] or 0))
    if "dim_divisor_buy" in body:
        fields.append("dim_divisor_buy = ?")
        vals.append(float(body["dim_divisor_buy"] or 166))
    if "transit_days_json" in body:
        fields.append("transit_days_json = ?")
        vals.append(json.dumps(body["transit_days_json"]) if isinstance(body["transit_days_json"], dict) else body["transit_days_json"])
    if "accessorials_json" in body:
        fields.append("accessorials_json = ?")
        vals.append(json.dumps(body["accessorials_json"]) if isinstance(body["accessorials_json"], dict) else body["accessorials_json"])
    if "rate_grid" in body:
        fields.append("rate_grid_json = ?")
        vals.append(json.dumps(body["rate_grid"]))
    if "zone_mapping" in body:
        fields.append("zone_mapping_json = ?")
        vals.append(json.dumps(body["zone_mapping"]))
    fields.append("updated_at = datetime('now')")
    vals.append(rc_id)
    db.execute(f"UPDATE rate_cards SET {', '.join(fields)} WHERE id = ?", vals)
    db.commit()
    return {"message": "Rate card updated"}


@app.delete("/api/rate-cards/{rc_id}")
def delete_rate_card(rc_id: int, token: Optional[str] = Query(None)):
    db = get_persistent_db()
    db.execute("DELETE FROM rate_cards WHERE id = ?", (rc_id,))
    db.commit()
    return {"message": "Rate card deleted"}


@app.post("/api/rate-cards/{rc_id}/clone")
def clone_rate_card(rc_id: int, token: Optional[str] = Query(None)):
    """Clone an existing rate card with a new name."""
    db = get_persistent_db()
    r = db.execute("SELECT * FROM rate_cards WHERE id = ?", (rc_id,)).fetchone()
    if not r:
        return JSONResponse({"error": "Rate card not found"}, status_code=404)
    src = dict(r)
    new_name = src["name"] + " (Copy)"
    # Avoid duplicate names
    counter = 1
    while db.execute("SELECT id FROM rate_cards WHERE name = ?", (new_name,)).fetchone():
        counter += 1
        new_name = src["name"] + f" (Copy {counter})"
    db.execute("""INSERT INTO rate_cards
        (name, service_type, carrier, pricing_type, description, rate_grid_json,
         zone_mapping_json, zone_key, dim_divisor, currency, country, version, status,
         fuel_rate, fuel_type, fuel_discount, dim_threshold_cu_in, dim_divisor_alt,
         transit_days_json, accessorials_json, service_class, card_type,
         fuel_rate_buy, fuel_rate_sell, dim_divisor_buy)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,'active',?,?,?,?,?,?,?,?,?,?,?,?)""",
        (new_name, src["service_type"], src["carrier"], src.get("pricing_type", "WEIGHT_POUNDS"),
         src["description"], src["rate_grid_json"], src["zone_mapping_json"],
         src.get("zone_key", ""), src.get("dim_divisor", 166),
         src.get("currency", "USD"), src.get("country", "US"),
         src.get("version", "v1"),
         src.get("fuel_rate", 0) or 0, src.get("fuel_type", "percentage") or "percentage",
         src.get("fuel_discount", 0) or 0, src.get("dim_threshold_cu_in", 0) or 0,
         src.get("dim_divisor_alt", 0) or 0,
         src.get("transit_days_json", "{}"), src.get("accessorials_json", "{}"),
         src.get("service_class", "economy") or "economy",
         src.get("card_type", "sell_current") or "sell_current",
         src.get("fuel_rate_buy", 0) or 0, src.get("fuel_rate_sell", 0) or 0,
         src.get("dim_divisor_buy", 166) or 166))
    db.commit()
    new_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    return {"id": new_id, "name": new_name, "message": f"Cloned as '{new_name}'"}


@app.get("/api/rate-cards/{rc_id}/export-csv")
def export_rate_card_csv(rc_id: int, token: Optional[str] = Query(None)):
    """Export a rate card as a CSV file."""
    import io, csv
    db = get_persistent_db()
    r = db.execute("SELECT * FROM rate_cards WHERE id = ?", (rc_id,)).fetchone()
    if not r:
        raise HTTPException(status_code=404, detail="Rate card not found")
    grid = json.loads(r["rate_grid_json"])
    weights = sorted(grid.keys(), key=lambda x: float(x) if x.replace('.','').replace('-','').isdigit() else 0)
    zones = sorted(set(z for w in weights for z in grid[w].keys()),
                   key=lambda x: int(x) if x.isdigit() else x)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Weight"] + [f"Zone {z}" for z in zones])
    for w in weights:
        row = [w] + [grid[w].get(z, "") for z in zones]
        writer.writerow(row)
    content = output.getvalue()
    safe_name = re.sub(r'[^\w\s-]', '', r["name"]).strip().replace(' ', '_')
    return StreamingResponse(
        iter([content]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}.csv"'}
    )


@app.post("/api/rate-cards/{rc_id}/import-csv")
async def import_rate_card_csv(rc_id: int, request: Request, token: Optional[str] = Query(None)):
    """Import CSV data to overwrite the rate grid of an existing rate card."""
    db = get_persistent_db()
    r = db.execute("SELECT id FROM rate_cards WHERE id = ?", (rc_id,)).fetchone()
    if not r:
        return JSONResponse({"error": "Rate card not found"}, status_code=404)
    body = await request.json()
    csv_data = body.get("csv_data", "")
    if not csv_data.strip():
        return JSONResponse({"error": "No CSV data provided"}, status_code=400)
    lines = csv_data.strip().replace('\r\n', '\n').replace('\r', '\n').split('\n')
    rate_grid = {}
    header_zones = []
    for i, line in enumerate(lines):
        if not line.strip():
            continue
        parts = [p.strip() for p in line.split(',')]
        if i == 0:
            # Header row — extract zone labels
            for h in parts[1:]:
                zone_num = re.sub(r'[^\d]', '', h)
                header_zones.append(zone_num if zone_num else str(len(header_zones) + 1))
            continue
        weight = parts[0]
        if not weight:
            continue
        rate_grid[weight] = {}
        for zi, z in enumerate(header_zones):
            val_str = parts[zi + 1] if zi + 1 < len(parts) else ""
            val_str = val_str.replace('$', '').replace(',', '').strip()
            try:
                rate_grid[weight][z] = float(val_str) if val_str else 0
            except ValueError:
                rate_grid[weight][z] = 0
    weight_count = len(rate_grid)
    zone_count = len(header_zones)
    db.execute("UPDATE rate_cards SET rate_grid_json = ?, updated_at = datetime('now') WHERE id = ?",
               (json.dumps(rate_grid), rc_id))
    db.commit()
    return {"message": f"Imported {weight_count} weight breaks × {zone_count} zones",
            "weight_count": weight_count, "zone_count": zone_count}


@app.post("/api/rate-cards/bulk-import-csv")
async def bulk_import_rate_card_csv(request: Request, token: Optional[str] = Query(None)):
    """Create a new rate card from uploaded CSV data."""
    db = get_persistent_db()
    body = await request.json()
    csv_data = body.get("csv_data", "")
    name = body.get("name", "Imported Rate Card")
    carrier = body.get("carrier", "")
    service_type = body.get("service_type", "")
    if not csv_data.strip():
        return JSONResponse({"error": "No CSV data provided"}, status_code=400)
    lines = csv_data.strip().replace('\r\n', '\n').replace('\r', '\n').split('\n')
    rate_grid = {}
    header_zones = []
    for i, line in enumerate(lines):
        if not line.strip():
            continue
        parts = [p.strip() for p in line.split(',')]
        if i == 0:
            for h in parts[1:]:
                zone_num = re.sub(r'[^\d]', '', h)
                header_zones.append(zone_num if zone_num else str(len(header_zones) + 1))
            continue
        weight = parts[0]
        if not weight:
            continue
        rate_grid[weight] = {}
        for zi, z in enumerate(header_zones):
            val_str = parts[zi + 1] if zi + 1 < len(parts) else ""
            val_str = val_str.replace('$', '').replace(',', '').strip()
            try:
                rate_grid[weight][z] = float(val_str) if val_str else 0
            except ValueError:
                rate_grid[weight][z] = 0
    db.execute("""INSERT INTO rate_cards
        (name, service_type, carrier, pricing_type, description, rate_grid_json,
         zone_mapping_json, zone_key, dim_divisor, currency, country, version, status)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,'active')""",
        (name, service_type, carrier, "WEIGHT_POUNDS", "",
         json.dumps(rate_grid), "{}", "", 166, "USD", "US", "v1"))
    db.commit()
    new_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    return {"id": new_id, "message": f"Created rate card '{name}' with {len(rate_grid)} weight breaks"}


@app.post("/api/rate-cards/compare")
async def compare_rate_cards(request: Request, token: Optional[str] = Query(None)):
    db = get_persistent_db()
    body = await request.json()
    card_id_1 = body.get("card_id_1")
    card_id_2 = body.get("card_id_2")
    if not card_id_1 or not card_id_2:
        return JSONResponse({"error": "card_id_1 and card_id_2 required"}, status_code=400)
    r1 = db.execute("SELECT * FROM rate_cards WHERE id = ?", (card_id_1,)).fetchone()
    r2 = db.execute("SELECT * FROM rate_cards WHERE id = ?", (card_id_2,)).fetchone()
    if not r1 or not r2:
        return JSONResponse({"error": "One or both rate cards not found"}, status_code=404)
    grid1 = json.loads(r1["rate_grid_json"])
    grid2 = json.loads(r2["rate_grid_json"])
    weights1 = set(grid1.keys())
    weights2 = set(grid2.keys())
    common_weights = sorted(weights1 & weights2, key=lambda x: float(x) if str(x).replace('.','').isdigit() else 0)
    zones_set = set()
    for w in common_weights:
        zones_set.update(grid1[w].keys())
        zones_set.update(grid2[w].keys())
    common_zones = sorted(zones_set, key=lambda x: int(x) if str(x).isdigit() else 0)
    matrix_arr    = []
    card1_cheaper = 0
    card2_cheaper = 0
    total_cells   = 0
    pct_diffs     = []
    for w in common_weights:
        zone_arr = []
        for z in common_zones:
            r1_rate = grid1[w].get(z)
            r2_rate = grid2[w].get(z)
            if r1_rate is not None and r2_rate is not None and r2_rate != 0:
                pct_diff = round((r1_rate - r2_rate) / r2_rate * 100, 2)
                total_cells += 1
                pct_diffs.append(pct_diff)
                if pct_diff < -0.01:   card1_cheaper += 1
                elif pct_diff > 0.01:  card2_cheaper += 1
                zone_arr.append({"zone": z, "pct_diff": pct_diff,
                                 "card1_rate": r1_rate, "card2_rate": r2_rate})
            else:
                zone_arr.append({"zone": z, "pct_diff": None,
                                 "card1_rate": r1_rate, "card2_rate": r2_rate})
        matrix_arr.append({"weight": w, "zones": zone_arr})
    avg_pct = round(sum(pct_diffs) / len(pct_diffs), 2) if pct_diffs else None
    return {
        "weights":    common_weights,
        "zones":      common_zones,
        "matrix":     matrix_arr,
        "card1_name": r1["name"],
        "card2_name": r2["name"],
        "card1_id":   int(card_id_1),
        "card2_id":   int(card_id_2),
        "summary": {
            "card1_cheaper_count": card1_cheaper,
            "card2_cheaper_count": card2_cheaper,
            "total_cells":         total_cells,
            "avg_pct_diff":        avg_pct
        }
    }


# ─── Zone Charts ──────────────────────────────────────────────────────────────

@app.get("/api/zone-charts")
def list_zone_charts(token: Optional[str] = Query(None)):
    db = get_persistent_db()
    rows = db.execute(
        "SELECT id, name, carrier, origin_zip, description, row_count, created_at "
        "FROM zone_charts ORDER BY created_at DESC"
    ).fetchall()
    return [dict(r) for r in rows]


@app.post("/api/zone-charts", status_code=201)
async def create_zone_chart(request: Request, token: Optional[str] = Query(None)):
    db = get_persistent_db()
    body = await request.json()
    name = body.get("name", "")
    if not name:
        return JSONResponse({"error": "Name required"}, status_code=400)
    carrier    = body.get("carrier", "")
    origin_zip = body.get("origin_zip", "")
    description = body.get("description", "")
    csv_data   = body.get("csv_data", "")
    data       = []
    if csv_data and csv_data.strip():
        lines  = csv_data.strip().replace('\r\n', '\n').replace('\r', '\n').split('\n')
        header = None
        for i, line in enumerate(lines):
            if not line.strip():
                continue
            parts_csv = [p.strip().strip('"') for p in line.split(',')]
            if i == 0:
                header = [h.lower().replace(' ', '_') for h in parts_csv]
                continue
            if header:
                row_dict = {}
                for j, col in enumerate(header):
                    row_dict[col] = parts_csv[j] if j < len(parts_csv) else ''
                dz = row_dict.get('dest_zip', row_dict.get('destination_zip', row_dict.get('zip', '')))
                zo = row_dict.get('zone', '')
                if dz or zo:
                    entry = {"dest_zip": dz[:5] if dz else '',
                             "zone":     zo,
                             "dest_zip_prefix": dz[:3] if dz else ''}
                    if 'origin_zip' in row_dict:
                        entry['origin_zip'] = row_dict['origin_zip']
                    if 'carrier' in row_dict:
                        entry['carrier'] = row_dict['carrier']
                    data.append(entry)
    else:
        data = body.get("data", [])
    db.execute("""INSERT INTO zone_charts (name, carrier, origin_zip, description, data_json, row_count)
                  VALUES (?, ?, ?, ?, ?, ?)""",
               (name, carrier, origin_zip, description, json.dumps(data), len(data)))
    db.commit()
    zc_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    return {"id": zc_id, "message": "Zone chart created", "row_count": len(data)}


@app.get("/api/zone-charts/{zc_id}")
def get_zone_chart(zc_id: int, token: Optional[str] = Query(None)):
    db = get_persistent_db()
    r = db.execute("SELECT * FROM zone_charts WHERE id = ?", (zc_id,)).fetchone()
    if not r:
        return JSONResponse({"error": "Zone chart not found"}, status_code=404)
    result = dict(r)
    result["data_json"] = json.loads(result["data_json"])
    return result


@app.delete("/api/zone-charts/{zc_id}")
def delete_zone_chart(zc_id: int, token: Optional[str] = Query(None)):
    db = get_persistent_db()
    db.execute("DELETE FROM zone_charts WHERE id = ?", (zc_id,))
    db.commit()
    return {"message": "Zone chart deleted"}


# ─── Documents ────────────────────────────────────────────────────────────────

@app.get("/api/documents")
def list_documents(token: Optional[str] = Query(None)):
    db = get_persistent_db()
    rows = db.execute("SELECT * FROM documents ORDER BY created_at DESC").fetchall()
    docs = []
    for r in rows:
        d = dict(r)
        all_clients = db.execute("SELECT documents_json FROM clients").fetchall()
        count = 0
        for c in all_clients:
            if r["id"] in json.loads(c["documents_json"]):
                count += 1
        d["client_count"] = count
        d["has_file"] = bool(d.get("file_path", ""))
        d["file_size"] = d.get("file_size", 0) or 0
        docs.append(d)
    return docs


@app.post("/api/documents", status_code=201)
async def create_document(
    file: UploadFile = File(None),
    name: str = Form(""),
    category: str = Form("Other"),
    token: Optional[str] = Query(None)
):
    db = get_persistent_db()
    auth = check_auth(db, token, "admin")
    if not auth:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    file_path_str = ""
    file_size = 0
    orig_filename = ""
    if file and file.filename:
        orig_filename = file.filename
        safe_name = re.sub(r'[^a-zA-Z0-9._-]', '_', file.filename)
        ts = datetime.now().strftime('%Y%m%d%H%M%S')
        stored_name = f"{ts}_{safe_name}"
        full_path = os.path.join(UPLOADS_DIR, stored_name)
        contents = await file.read()
        file_size = len(contents)
        with open(full_path, 'wb') as f:
            f.write(contents)
        file_path_str = stored_name
    doc_name = name or orig_filename or "Untitled"
    db.execute("INSERT INTO documents (name, category, filename, file_path, file_size) VALUES (?, ?, ?, ?, ?)",
               (doc_name, category, orig_filename, file_path_str, file_size))
    db.commit()
    doc_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    return {"id": doc_id, "message": "Document uploaded"}


@app.get("/api/documents/{doc_id}/download")
async def download_document(doc_id: int, token: Optional[str] = Query(None)):
    db = get_persistent_db()
    # Allow both admin and client access
    auth = check_auth(db, token)
    if not auth:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    doc = db.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    fp = doc["file_path"] if "file_path" in doc.keys() else ""
    if not fp:
        raise HTTPException(status_code=404, detail="No file attached to this document")
    full_path = os.path.join(UPLOADS_DIR, fp)
    if not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail="File not found on disk")
    orig_name = doc["filename"] or fp
    import mimetypes
    mime, _ = mimetypes.guess_type(orig_name)
    mime = mime or "application/octet-stream"
    return StreamingResponse(
        open(full_path, 'rb'),
        media_type=mime,
        headers={"Content-Disposition": f'attachment; filename="{orig_name}"'}
    )


@app.delete("/api/documents/{doc_id}")
async def delete_document(doc_id: int, token: Optional[str] = Query(None)):
    db = get_persistent_db()
    auth = check_auth(db, token, "admin")
    if not auth:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    doc = db.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    # Delete file from disk
    fp = doc["file_path"] if "file_path" in doc.keys() else ""
    if fp:
        full_path = os.path.join(UPLOADS_DIR, fp)
        if os.path.exists(full_path):
            os.remove(full_path)
    # Remove from all client assignments
    clients = db.execute("SELECT id, documents_json FROM clients").fetchall()
    for c in clients:
        doc_ids = json.loads(c["documents_json"])
        if doc_id in doc_ids:
            doc_ids.remove(doc_id)
            db.execute("UPDATE clients SET documents_json = ? WHERE id = ?",
                       (json.dumps(doc_ids), c["id"]))
    db.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
    db.commit()
    return {"message": "Document deleted"}


# ─── Settings ─────────────────────────────────────────────────────────────────

@app.get("/api/settings")
def get_settings(token: Optional[str] = Query(None)):
    db = get_persistent_db()
    auth = check_auth(db, token, "admin")
    if auth:
        admin = db.execute("SELECT * FROM admins WHERE id = ?", (auth["user_id"],)).fetchone()
    else:
        admin = db.execute("SELECT * FROM admins WHERE id = 1").fetchone()
    return {"name": admin["name"], "email": admin["email"]} if admin else {}


@app.post("/api/settings")
async def save_settings(request: Request, token: Optional[str] = Query(None)):
    db = get_persistent_db()
    body = await request.json()
    if "name" in body:
        db.execute("UPDATE admins SET name = ? WHERE id = 1", (body["name"],))
    if "password" in body and body["password"]:
        pw_hash = hashlib.sha256(body["password"].encode()).hexdigest()
        db.execute("UPDATE admins SET password_hash = ? WHERE id = 1", (pw_hash,))
    db.commit()
    return {"message": "Settings updated"}


@app.put("/api/settings")
async def update_settings(request: Request, token: Optional[str] = Query(None)):
    db = get_persistent_db()
    auth = check_auth(db, token, "admin")
    if not auth:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    body = await request.json()
    admin_id = auth["user_id"]
    if "name" in body and body["name"]:
        db.execute("UPDATE admins SET name = ? WHERE id = ?", (body["name"], admin_id))
    if "password" in body and body["password"]:
        pw_hash = hashlib.sha256(body["password"].encode()).hexdigest()
        db.execute("UPDATE admins SET password_hash = ? WHERE id = ?", (pw_hash, admin_id))
    db.commit()
    return {"message": "Settings updated"}


# ─── Admin Users Management ───────────────────────────────────────────────────

@app.get("/api/admin-users")
def list_admin_users(token: Optional[str] = Query(None)):
    db = get_persistent_db()
    auth = check_auth(db, token, "admin")
    if not auth:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    rows = db.execute("SELECT id, email, name FROM admins ORDER BY id").fetchall()
    return [{"id": r["id"], "email": r["email"], "name": r["name"]} for r in rows]


@app.post("/api/admin-users")
async def add_admin_user(request: Request, token: Optional[str] = Query(None)):
    db = get_persistent_db()
    auth = check_auth(db, token, "admin")
    if not auth:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    body = await request.json()
    email = (body.get("email") or "").strip().lower()
    name = (body.get("name") or "").strip()
    if not email:
        return JSONResponse({"error": "Email is required"}, status_code=400)
    if not name:
        return JSONResponse({"error": "Name is required"}, status_code=400)
    # Check for duplicate
    existing = db.execute("SELECT id FROM admins WHERE LOWER(email) = ?", (email,)).fetchone()
    if existing:
        return JSONResponse({"error": "An admin with this email already exists"}, status_code=409)
    # Generate a random password hash (admin will use Google SSO to sign in)
    random_pw = hashlib.sha256(str(uuid.uuid4()).encode()).hexdigest()
    db.execute("INSERT INTO admins (email, password_hash, name) VALUES (?, ?, ?)",
               (email, random_pw, name))
    db.commit()
    new_id = db.execute("SELECT id FROM admins WHERE LOWER(email) = ?", (email,)).fetchone()["id"]
    return {"id": new_id, "email": email, "name": name}


@app.delete("/api/admin-users/{admin_id}")
def remove_admin_user(admin_id: int, token: Optional[str] = Query(None)):
    db = get_persistent_db()
    auth = check_auth(db, token, "admin")
    if not auth:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    # Can't remove yourself
    if auth["user_id"] == admin_id:
        return JSONResponse({"error": "You cannot remove yourself"}, status_code=400)
    # Can't remove if only one admin left
    count = db.execute("SELECT COUNT(*) FROM admins").fetchone()[0]
    if count <= 1:
        return JSONResponse({"error": "Cannot remove the last admin"}, status_code=400)
    admin = db.execute("SELECT id FROM admins WHERE id = ?", (admin_id,)).fetchone()
    if not admin:
        return JSONResponse({"error": "Admin not found"}, status_code=404)
    # Remove their sessions too
    db.execute("DELETE FROM sessions WHERE user_type = 'admin' AND user_id = ?", (admin_id,))
    db.execute("DELETE FROM admins WHERE id = ?", (admin_id,))
    db.commit()
    return {"message": "Admin removed"}


# ─── Access Requests ──────────────────────────────────────────────────────────

@app.post("/api/access-requests")
async def submit_access_request(request: Request):
    """Public endpoint — no auth required. Someone requests admin access."""
    db = get_persistent_db()
    body = await request.json()
    email = (body.get("email") or "").strip().lower()
    name = (body.get("name") or "").strip()
    if not email:
        return JSONResponse({"error": "Email is required"}, status_code=400)
    # Check if already an admin
    existing_admin = db.execute("SELECT id FROM admins WHERE LOWER(email) = ?", (email,)).fetchone()
    if existing_admin:
        return JSONResponse({"error": "This email already has admin access"}, status_code=409)
    # Check for existing pending request
    existing_req = db.execute("SELECT id FROM access_requests WHERE LOWER(email) = ? AND status = 'pending'", (email,)).fetchone()
    if existing_req:
        return JSONResponse({"error": "A request from this email is already pending"}, status_code=409)
    db.execute("INSERT INTO access_requests (email, name, status) VALUES (?, ?, 'pending')",
               (email, name or email.split('@')[0].title()))
    # Create a notification for admins
    db.execute("INSERT INTO notifications (type, message) VALUES (?, ?)",
               ("access_request", f"{name or email} has requested admin access"))
    db.commit()
    return {"message": "Access request submitted"}


@app.get("/api/access-requests")
def list_access_requests(token: Optional[str] = Query(None)):
    db = get_persistent_db()
    auth = check_auth(db, token, "admin")
    if not auth:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    rows = db.execute("SELECT * FROM access_requests ORDER BY created_at DESC").fetchall()
    return [dict(r) for r in rows]


@app.get("/api/access-requests/pending-count")
def pending_access_request_count(token: Optional[str] = Query(None)):
    db = get_persistent_db()
    count = db.execute("SELECT COUNT(*) FROM access_requests WHERE status = 'pending'").fetchone()[0]
    return {"count": count}


@app.post("/api/access-requests/{req_id}/approve")
async def approve_access_request(req_id: int, request: Request, token: Optional[str] = Query(None)):
    db = get_persistent_db()
    auth = check_auth(db, token, "admin")
    if not auth:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    req_row = db.execute("SELECT * FROM access_requests WHERE id = ?", (req_id,)).fetchone()
    if not req_row:
        return JSONResponse({"error": "Request not found"}, status_code=404)
    if req_row["status"] != "pending":
        return JSONResponse({"error": "Request already processed"}, status_code=400)
    email = req_row["email"].strip().lower()
    name = req_row["name"] or email.split('@')[0].title()
    # Check if already an admin (shouldn't happen, but safety)
    existing = db.execute("SELECT id FROM admins WHERE LOWER(email) = ?", (email,)).fetchone()
    if existing:
        db.execute("UPDATE access_requests SET status = 'approved', reviewed_at = datetime('now'), reviewed_by = ? WHERE id = ?",
                   (auth["user_id"], req_id))
        db.commit()
        return {"message": "Already an admin", "email": email}
    # Create admin account
    random_pw = hashlib.sha256(str(uuid.uuid4()).encode()).hexdigest()
    db.execute("INSERT INTO admins (email, password_hash, name) VALUES (?, ?, ?)",
               (email, random_pw, name))
    db.execute("UPDATE access_requests SET status = 'approved', reviewed_at = datetime('now'), reviewed_by = ? WHERE id = ?",
               (auth["user_id"], req_id))
    # Queue an approval notification email
    approver = db.execute("SELECT name FROM admins WHERE id = ?", (auth["user_id"],)).fetchone()
    approver_name = approver["name"] if approver else "An administrator"
    db.execute("""
        INSERT INTO pending_emails (client_id, to_email, to_name, subject, body, email_type, status)
        VALUES (NULL, ?, ?, ?, ?, 'access_approved', 'pending')
    """, (
        email, name,
        "Your Broad Reach Admin Access Has Been Approved",
        f"Hi {name},\n\n"
        f"Great news! {approver_name} has approved your request for admin access to the Broad Reach portal.\n\n"
        f"You can now sign in using your Google account ({email}) at the admin login page.\n\n"
        f"Welcome aboard!\n\nBroad Reach Team"
    ))
    db.commit()
    return {"message": f"{name} approved and added as admin", "email": email, "name": name}


@app.post("/api/access-requests/{req_id}/deny")
async def deny_access_request(req_id: int, request: Request, token: Optional[str] = Query(None)):
    db = get_persistent_db()
    auth = check_auth(db, token, "admin")
    if not auth:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    req_row = db.execute("SELECT * FROM access_requests WHERE id = ?", (req_id,)).fetchone()
    if not req_row:
        return JSONResponse({"error": "Request not found"}, status_code=404)
    if req_row["status"] != "pending":
        return JSONResponse({"error": "Request already processed"}, status_code=400)
    db.execute("UPDATE access_requests SET status = 'denied', reviewed_at = datetime('now'), reviewed_by = ? WHERE id = ?",
               (auth["user_id"], req_id))
    db.commit()
    return {"message": "Request denied"}


# ─── Notifications ────────────────────────────────────────────────────────────

@app.get("/api/notifications")
def list_notifications(token: Optional[str] = Query(None)):
    db = get_persistent_db()
    rows = db.execute("""
        SELECT n.*, c.company_name FROM notifications n
        LEFT JOIN clients c ON c.id = n.client_id
        ORDER BY n.created_at DESC LIMIT 50
    """).fetchall()
    notifs = [dict(r) for r in rows]
    unread_count = db.execute("SELECT COUNT(*) FROM notifications WHERE read = 0").fetchone()[0]
    return {"notifications": notifs, "unread_count": unread_count}


@app.post("/api/notifications/read")
def mark_all_notifications_read(token: Optional[str] = Query(None)):
    db = get_persistent_db()
    db.execute("UPDATE notifications SET read = 1")
    db.commit()
    return {"message": "All marked as read"}


# ─── Dashboard ────────────────────────────────────────────────────────────────

@app.get("/api/dashboard")
def dashboard(token: Optional[str] = Query(None)):
    db = get_persistent_db()
    total_clients = db.execute("SELECT COUNT(*) FROM clients").fetchone()[0]
    active        = db.execute("SELECT COUNT(*) FROM analyses WHERE status = 'published'").fetchone()[0]
    pending       = db.execute("SELECT COUNT(*) FROM clients WHERE status = 'Analysis Pending'").fetchone()[0]
    completed     = db.execute("SELECT COUNT(*) FROM analyses WHERE status = 'published'").fetchone()[0]
    total_rcs     = db.execute("SELECT COUNT(*) FROM rate_cards").fetchone()[0]
    carriers      = db.execute("SELECT COUNT(DISTINCT carrier) FROM rate_cards").fetchone()[0]
    return {
        "total_clients":      total_clients,
        "active_analyses":    active,
        "pending_uploads":    pending,
        "completed_analyses": completed,
        "total_rate_cards":   total_rcs,
        "active_carriers":    carriers,
    }


@app.get("/api/analyses/export")
def export_all_analyses(token: Optional[str] = Query(None)):
    """Export all published client analyses as JSON for bulk download."""
    db = get_persistent_db()
    rows = db.execute("""
        SELECT a.*, c.company_name, c.email, c.contact_name
        FROM analyses a
        JOIN clients c ON a.client_id = c.id
        WHERE a.status = 'published'
        ORDER BY a.published_at DESC
    """).fetchall()
    results = []
    for r in rows:
        results.append({
            "client_id": r["client_id"],
            "company_name": r["company_name"],
            "email": r["email"],
            "contact_name": r["contact_name"],
            "status": r["status"],
            "created_at": r["created_at"],
            "published_at": r["published_at"],
            "config": json.loads(r["config_json"]),
            "results": json.loads(r["results_json"])
        })
    return results


# ─── Zone Lookup ──────────────────────────────────────────────────────────────

@app.get("/api/zones/lookup")
def zones_lookup(
    zip: Optional[str] = Query(None),
    carrier: Optional[str] = Query(None),
    token: Optional[str] = Query(None)
):
    if not zip:
        return JSONResponse({"error": "zip parameter required"}, status_code=400)
    zip_code = zip.strip()
    carrier  = (carrier or "").strip()

    is_canadian = len(zip_code) >= 1 and zip_code[0].isalpha()

    if is_canadian:
        fsa = zip_code[:3].upper()
        if not carrier:
            fsa_data, province = lookup_ca_zone(zip_code)
            if not fsa_data or not isinstance(fsa_data, dict):
                return {"zip": zip_code, "country": "CA", "zones": {}, "note": "FSA not found"}
            zones_out = {}
            for ck, cv in fsa_data.items():
                if ck == "p":
                    continue
                zones_out[ck] = cv
            return {
                "zip":      zip_code,
                "fsa":      fsa,
                "province": province,
                "country":  "CA",
                "zones":    zones_out
            }
        else:
            zone_val, province = lookup_ca_zone(zip_code, carrier)
            return {
                "zip":      zip_code,
                "fsa":      fsa,
                "province": province,
                "country":  "CA",
                "carrier":  carrier,
                "zone":     zone_val
            }
    else:
        zip5 = zip_code.zfill(5)
        zip3 = zip5[:3]
        if not carrier:
            zone_val, state, _ = lookup_us_zone(zip5)
            if zone_val is None or not isinstance(zone_val, dict):
                return {"zip": zip5, "state": None, "zones": {}, "note": "ZIP not found"}
            zones_out = {}
            das_flags = {}
            for ck, cv in zone_val.items():
                if ck == "s":
                    continue
                if ck.endswith("_DAS"):
                    base_k = ck[:-4]
                    if cv == "DAS":
                        das_flags[base_k] = True
                    continue
                display = CARRIER_DISPLAY.get(ck, ck)
                zones_out[display] = cv
            return {
                "zip":       zip5,
                "state":     state,
                "country":   "US",
                "zones":     zones_out,
                "das_flags": das_flags
            }
        else:
            carrier_key = carrier
            for ck, disp in CARRIER_DISPLAY.items():
                if disp.lower() == carrier.lower() or ck.lower() == carrier.lower():
                    carrier_key = ck
                    break
            zone_val, state, das = lookup_us_zone(zip5, carrier_key)
            return {
                "zip":     zip5,
                "state":   state,
                "country": "US",
                "carrier": carrier,
                "zone":    zone_val,
                "das":     "DAS" if das else None
            }


# ─── Service Catalog ──────────────────────────────────────────────────────────

@app.get("/api/service-catalog")
def service_catalog(token: Optional[str] = Query(None)):
    path = os.path.join(DATA_DIR, "wizmo_service_catalog.json")
    try:
        with open(path) as f:
            catalog = json.load(f)
        return catalog
    except Exception as e:
        return JSONResponse({"error": f"Could not load service catalog: {e}"}, status_code=400)


# ─── Transit Times ────────────────────────────────────────────────────────────

@app.get("/api/transit-times")
def transit_times(
    state: Optional[str] = Query(None),
    origin_zip: Optional[str] = Query(None),
    dest_zip: Optional[str] = Query(None),
    token: Optional[str] = Query(None)
):
    path = os.path.join(DATA_DIR, "ups_transit_times.json")
    try:
        with open(path) as f:
            tt = json.load(f)
    except Exception as e:
        return JSONResponse({"error": f"Could not load transit times: {e}"}, status_code=400)

    state_val = (state or "").strip().upper()
    if state_val:
        by_state = tt.get("by_state", {})
        state_data = by_state.get(state_val)
        if state_data is None:
            return {"state": state_val, "hubs": {}, "note": "State not found"}
        return {"state": state_val, "transit_days": state_data}
    else:
        return tt


# ─── Peak Surcharges ──────────────────────────────────────────────────────────

@app.get("/api/peak-surcharges")
def peak_surcharges(token: Optional[str] = Query(None)):
    path = os.path.join(DATA_DIR, "peak_surcharges.json")
    try:
        with open(path) as f:
            ps = json.load(f)
        return ps
    except Exception as e:
        return JSONResponse({"error": f"Could not load peak surcharges: {e}"}, status_code=400)


# ─── Accessorial Rules (CRUD) ────────────────────────────────────────────────

@app.get("/api/accessorial-rules")
def list_accessorial_rules(token: Optional[str] = Query(None)):
    db = get_persistent_db()
    rows = db.execute("SELECT * FROM accessorial_rules ORDER BY id ASC").fetchall()
    rules = []
    for r in rows:
        d = dict(r)
        try:
            d["condition_json"] = json.loads(d["condition_json"]) if d.get("condition_json") else {}
        except Exception:
            d["condition_json"] = {}
        try:
            d["zone_rates_json"] = json.loads(d["zone_rates_json"]) if d.get("zone_rates_json") else {}
        except Exception:
            d["zone_rates_json"] = {}
        rules.append(d)
    return rules


@app.post("/api/accessorial-rules", status_code=201)
async def create_accessorial_rule(request: Request, token: Optional[str] = Query(None)):
    db = get_persistent_db()
    body = await request.json()
    name = body.get("name", "")
    if not name:
        return JSONResponse({"error": "Name required"}, status_code=400)
    fee_type = body.get("fee_type", "")
    if not fee_type:
        return JSONResponse({"error": "fee_type required"}, status_code=400)
    cond = body.get("condition_json", {})
    if isinstance(cond, dict):
        cond = json.dumps(cond)
    zone_rates = body.get("zone_rates_json", {})
    if isinstance(zone_rates, dict):
        zone_rates = json.dumps(zone_rates)
    cur = db.execute("""
        INSERT INTO accessorial_rules
            (name, carrier, fee_type, condition_json, amount, amount_type,
             zone_rates_json, apply_to_carriers, active, start_date, end_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        name,
        body.get("carrier", ""),
        fee_type,
        cond,
        float(body.get("amount", 0) or 0),
        body.get("amount_type", "flat") or "flat",
        zone_rates,
        body.get("apply_to_carriers", "") or "",
        1 if body.get("active", True) else 0,
        body.get("start_date", "") or "",
        body.get("end_date", "") or "",
    ))
    db.commit()
    return {"id": cur.lastrowid, "message": "Accessorial rule created"}


@app.put("/api/accessorial-rules/{rule_id}")
async def update_accessorial_rule(rule_id: int, request: Request, token: Optional[str] = Query(None)):
    db = get_persistent_db()
    body = await request.json()
    fields = []
    vals   = []
    for f in ["name", "carrier", "fee_type", "amount_type", "apply_to_carriers", "start_date", "end_date"]:
        if f in body:
            fields.append(f"{f} = ?")
            vals.append(body[f])
    if "amount" in body:
        fields.append("amount = ?")
        vals.append(float(body["amount"] or 0))
    if "active" in body:
        fields.append("active = ?")
        vals.append(1 if body["active"] else 0)
    if "condition_json" in body:
        cond = body["condition_json"]
        fields.append("condition_json = ?")
        vals.append(json.dumps(cond) if isinstance(cond, dict) else cond)
    if "zone_rates_json" in body:
        zr = body["zone_rates_json"]
        fields.append("zone_rates_json = ?")
        vals.append(json.dumps(zr) if isinstance(zr, dict) else zr)
    if not fields:
        return JSONResponse({"error": "No fields to update"}, status_code=400)
    vals.append(rule_id)
    db.execute(f"UPDATE accessorial_rules SET {', '.join(fields)} WHERE id = ?", vals)
    db.commit()
    return {"message": "Accessorial rule updated"}


@app.delete("/api/accessorial-rules/{rule_id}")
def delete_accessorial_rule(rule_id: int, token: Optional[str] = Query(None)):
    db = get_persistent_db()
    db.execute("DELETE FROM accessorial_rules WHERE id = ?", (rule_id,))
    db.commit()
    return {"message": "Accessorial rule deleted"}


# ─── Service Cost Config ───────────────────────────────────────────────────────

@app.get("/api/service-cost-config")
def get_service_cost_config(token: Optional[str] = Query(None)):
    db = get_persistent_db()
    row = db.execute("SELECT * FROM service_cost_config LIMIT 1").fetchone()
    if not row:
        return {"line_haul_cost": 0.11, "daily_pickup_cost": 100.0, "pickup_days": 1, "sort_cost": 0.06}
    return dict(row)


@app.put("/api/service-cost-config")
async def update_service_cost_config(request: Request, token: Optional[str] = Query(None)):
    db = get_persistent_db()
    body = await request.json()
    fields = []
    vals   = []
    if "line_haul_cost" in body:
        fields.append("line_haul_cost = ?")
        vals.append(float(body["line_haul_cost"] or 0))
    if "daily_pickup_cost" in body:
        fields.append("daily_pickup_cost = ?")
        vals.append(float(body["daily_pickup_cost"] or 0))
    if "pickup_days" in body:
        fields.append("pickup_days = ?")
        vals.append(int(body["pickup_days"] or 1))
    if "sort_cost" in body:
        fields.append("sort_cost = ?")
        vals.append(float(body["sort_cost"] or 0))
    fields.append("updated_at = datetime('now')")
    # Upsert: update row 1 or insert
    row = db.execute("SELECT id FROM service_cost_config LIMIT 1").fetchone()
    if row:
        db.execute(f"UPDATE service_cost_config SET {', '.join(fields)} WHERE id = ?",
                   vals + [row["id"]])
    else:
        db.execute("""
            INSERT INTO service_cost_config (line_haul_cost, daily_pickup_cost, pickup_days, sort_cost)
            VALUES (?, ?, ?, ?)
        """, (
            float(body.get("line_haul_cost", 0.11) or 0.11),
            float(body.get("daily_pickup_cost", 100.0) or 100.0),
            int(body.get("pickup_days", 1) or 1),
            float(body.get("sort_cost", 0.06) or 0.06),
        ))
    db.commit()
    return {"message": "Service cost config updated"}


# ─── Accessorials ────────────────────────────────────────────────────────────

@app.get("/api/accessorials")
def accessorials(
    carrier: Optional[str] = Query(None),
    token: Optional[str] = Query(None)
):
    carrier_val = (carrier or "").strip()
    results = {}

    fedex_path = os.path.join(DATA_DIR, "fedex_accessorials.json")
    try:
        with open(fedex_path) as f:
            fa = json.load(f)
        if not carrier_val or carrier_val.lower() in ("fedex", "all"):
            results["FedEx"] = fa
    except Exception:
        pass

    ups_ca_path = os.path.join(DATA_DIR, "ups_canada_accessorials.json")
    try:
        with open(ups_ca_path) as f:
            ua = json.load(f)
        if not carrier_val or carrier_val.lower() in ("ups canada", "ups_canada", "all"):
            results["UPS Canada"] = ua
    except Exception:
        pass

    if carrier_val and carrier_val.lower() not in ("fedex", "ups canada", "ups_canada", "all"):
        return {"carrier": carrier_val, "accessorials": [], "note": "No accessorials data for this carrier"}

    return {"carrier": carrier_val or "all", "accessorials": results}


# ─── Induction Locations ─────────────────────────────────────────────────────────────────────

@app.get("/api/induction-locations")
def list_induction_locations(token: Optional[str] = Query(None)):
    db = get_persistent_db()
    try:
        rows = db.execute(
            "SELECT * FROM induction_locations ORDER BY country, is_primary DESC, name"
        ).fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        return []


@app.post("/api/induction-locations", status_code=201)
async def create_induction_location(request: Request, token: Optional[str] = Query(None)):
    db = get_persistent_db()
    body = await request.json()
    name         = body.get("name", "")
    display_name = body.get("display_name", "")
    country      = body.get("country", "US")
    zip_or_postal = body.get("zip_or_postal", "")
    is_primary   = int(body.get("is_primary", 0))
    active       = int(body.get("active", 1))
    if not name:
        return JSONResponse({"error": "name is required"}, status_code=400)
    db.execute(
        "INSERT INTO induction_locations (name, display_name, country, zip_or_postal, is_primary, active) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (name, display_name, country, zip_or_postal, is_primary, active)
    )
    db.commit()
    loc_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    return {"id": loc_id, "message": "Induction location created"}


@app.put("/api/induction-locations/{loc_id}")
async def update_induction_location(loc_id: int, request: Request, token: Optional[str] = Query(None)):
    db = get_persistent_db()
    body = await request.json()
    fields = []
    vals   = []
    for f in ["name", "display_name", "country", "zip_or_postal"]:
        if f in body:
            fields.append(f"{f} = ?")
            vals.append(body[f])
    for f in ["is_primary", "active"]:
        if f in body:
            fields.append(f"{f} = ?")
            vals.append(int(body[f]))
    if not fields:
        return {"message": "No fields to update"}
    vals.append(loc_id)
    db.execute(f"UPDATE induction_locations SET {', '.join(fields)} WHERE id = ?", vals)
    db.commit()
    return {"message": "Induction location updated"}


@app.delete("/api/induction-locations/{loc_id}")
def delete_induction_location(loc_id: int, token: Optional[str] = Query(None)):
    db = get_persistent_db()
    db.execute("DELETE FROM induction_locations WHERE id = ?", (loc_id,))
    db.commit()
    return {"message": "Induction location deleted"}


# ─── Zone Skip Config ─────────────────────────────────────────────────────────────────────

@app.get("/api/zone-skip-config")
def get_zone_skip_config(
    induction_location_id: Optional[int] = Query(None),
    token: Optional[str] = Query(None)
):
    db = get_persistent_db()
    try:
        if induction_location_id:
            rows = db.execute(
                "SELECT * FROM zone_skip_config WHERE induction_location_id = ? ORDER BY carrier, service_name",
                (induction_location_id,)
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT * FROM zone_skip_config ORDER BY induction_location_id, carrier, service_name"
            ).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


@app.put("/api/zone-skip-config")
async def update_zone_skip_config(request: Request, token: Optional[str] = Query(None)):
    """Bulk update zone_skip_config. Body: {records: [{induction_location_id, carrier, service_name, ...}]}"""
    db = get_persistent_db()
    body = await request.json()
    records = body.get("records", [])
    updated = 0
    for rec in records:
        loc_id  = rec.get("induction_location_id")
        carrier = rec.get("carrier", "")
        svc     = rec.get("service_name", "")
        if not loc_id:
            continue
        # Upsert: check if record exists
        existing = db.execute(
            "SELECT id FROM zone_skip_config WHERE induction_location_id = ? AND carrier = ? AND service_name = ?",
            (loc_id, carrier, svc)
        ).fetchone()
        zone_skip_allowed = int(rec.get("zone_skip_allowed", 1))
        zone_skip_fixed   = float(rec.get("zone_skip_fixed", 0) or 0)
        zone_skip_per_lb  = float(rec.get("zone_skip_per_lb", 0) or 0)
        service_available = int(rec.get("service_available", 1))
        if existing:
            db.execute(
                "UPDATE zone_skip_config SET zone_skip_allowed=?, zone_skip_fixed=?, zone_skip_per_lb=?, service_available=? WHERE id=?",
                (zone_skip_allowed, zone_skip_fixed, zone_skip_per_lb, service_available, existing["id"])
            )
        else:
            db.execute(
                "INSERT INTO zone_skip_config (induction_location_id, carrier, service_name, zone_skip_allowed, zone_skip_fixed, zone_skip_per_lb, service_available) VALUES (?,?,?,?,?,?,?)",
                (loc_id, carrier, svc, zone_skip_allowed, zone_skip_fixed, zone_skip_per_lb, service_available)
            )
        updated += 1
    db.commit()
    return {"message": f"{updated} zone skip config records updated"}


# ─── Zone File Versions ──────────────────────────────────────────────────────

@app.get("/api/zone-files")
def list_zone_files(token: Optional[str] = Query(None)):
    db = get_persistent_db()
    try:
        rows = db.execute(
            "SELECT id, carrier, country, file_name, effective_date, is_active, uploaded_at FROM zone_file_versions ORDER BY uploaded_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


@app.post("/api/zone-files/upload", status_code=201)
async def upload_zone_file(request: Request, token: Optional[str] = Query(None)):
    db = get_persistent_db()
    body = await request.json()
    carrier = body.get("carrier", "")
    country = body.get("country", "US")
    file_name = body.get("file_name", "")
    effective_date = body.get("effective_date", "")
    data = body.get("data", {})
    if not carrier:
        return JSONResponse({"error": "carrier is required"}, status_code=400)
    # Deactivate previous versions for same carrier+country
    db.execute(
        "UPDATE zone_file_versions SET is_active = 0 WHERE carrier = ? AND country = ?",
        (carrier, country)
    )
    db.execute(
        "INSERT INTO zone_file_versions (carrier, country, file_name, effective_date, data_json, is_active) VALUES (?,?,?,?,?,1)",
        (carrier, country, file_name, effective_date, json.dumps(data))
    )
    db.commit()
    zf_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    return {"id": zf_id, "message": "Zone file uploaded"}


@app.delete("/api/zone-files/{zf_id}")
def delete_zone_file(zf_id: int, token: Optional[str] = Query(None)):
    db = get_persistent_db()
    db.execute("DELETE FROM zone_file_versions WHERE id = ?", (zf_id,))
    db.commit()
    return {"message": "Zone file version deleted"}


# ─── DAS File Versions ────────────────────────────────────────────────────────

@app.get("/api/das-files")
def list_das_files(token: Optional[str] = Query(None)):
    db = get_persistent_db()
    try:
        rows = db.execute(
            "SELECT id, carrier, file_name, effective_date, is_active, uploaded_at FROM das_versions ORDER BY uploaded_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


@app.post("/api/das-files/upload", status_code=201)
async def upload_das_file(request: Request, token: Optional[str] = Query(None)):
    db = get_persistent_db()
    body = await request.json()
    carrier = body.get("carrier", "")
    file_name = body.get("file_name", "")
    effective_date = body.get("effective_date", "")
    data = body.get("data", {})
    if not carrier:
        return JSONResponse({"error": "carrier is required"}, status_code=400)
    # Deactivate previous versions for same carrier
    db.execute(
        "UPDATE das_versions SET is_active = 0 WHERE carrier = ?",
        (carrier,)
    )
    db.execute(
        "INSERT INTO das_versions (carrier, file_name, effective_date, data_json, is_active) VALUES (?,?,?,?,1)",
        (carrier, file_name, effective_date, json.dumps(data))
    )
    db.commit()
    das_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    return {"id": das_id, "message": "DAS file uploaded"}


@app.delete("/api/das-files/{das_id}")
def delete_das_file(das_id: int, token: Optional[str] = Query(None)):
    db = get_persistent_db()
    db.execute("DELETE FROM das_versions WHERE id = ?", (das_id,))
    db.commit()
    return {"message": "DAS file version deleted"}


# ─── Service Cost Overrides (per rate card) ──────────────────────────────────

@app.get("/api/service-cost-overrides")
def list_service_cost_overrides(rate_card_id: Optional[int] = Query(None), token: Optional[str] = Query(None)):
    db = get_persistent_db()
    try:
        if rate_card_id:
            rows = db.execute(
                "SELECT * FROM service_cost_overrides WHERE rate_card_id = ?",
                (rate_card_id,)
            ).fetchall()
        else:
            rows = db.execute("SELECT * FROM service_cost_overrides").fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


@app.put("/api/service-cost-overrides")
async def upsert_service_cost_override(request: Request, token: Optional[str] = Query(None)):
    db = get_persistent_db()
    body = await request.json()
    rc_id = body.get("rate_card_id")
    if not rc_id:
        return JSONResponse({"error": "rate_card_id is required"}, status_code=400)
    existing = db.execute(
        "SELECT id FROM service_cost_overrides WHERE rate_card_id = ?", (rc_id,)
    ).fetchone()
    line_haul_cost = float(body.get("line_haul_cost", 0) or 0)
    line_haul_type = body.get("line_haul_type", "per_piece")
    pickup_cost = float(body.get("pickup_cost", 0) or 0)
    sort_cost = float(body.get("sort_cost", 0) or 0)
    if existing:
        db.execute(
            "UPDATE service_cost_overrides SET line_haul_cost=?, line_haul_type=?, pickup_cost=?, sort_cost=? WHERE id=?",
            (line_haul_cost, line_haul_type, pickup_cost, sort_cost, existing["id"])
        )
    else:
        db.execute(
            "INSERT INTO service_cost_overrides (rate_card_id, line_haul_cost, line_haul_type, pickup_cost, sort_cost) VALUES (?,?,?,?,?)",
            (rc_id, line_haul_cost, line_haul_type, pickup_cost, sort_cost)
        )
    db.commit()
    return {"message": "Service cost override saved"}


@app.delete("/api/service-cost-overrides/{override_id}")
def delete_service_cost_override(override_id: int, token: Optional[str] = Query(None)):
    db = get_persistent_db()
    db.execute("DELETE FROM service_cost_overrides WHERE id = ?", (override_id,))
    db.commit()
    return {"message": "Service cost override deleted"}


# ─── Static Files (must be last to avoid catching /api/* routes) ─────────────
app.mount("/", StaticFiles(directory=BASE_DIR, html=True), name="static")

# ─── Entry Point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
