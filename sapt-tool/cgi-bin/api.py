#!/usr/bin/env python3
"""Broad Reach Customer Portal — CGI-bin API Backend
Enhanced Analysis Engine v3 with real zone data and full rate card integration."""
import json, os, sys, sqlite3, hashlib, uuid, math, re
from datetime import datetime, timedelta

# ─── Path Constants ────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
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
    db = sqlite3.connect(DB_PATH)
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
        setup_info_json TEXT DEFAULT '{}'
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
    """)
    # Add zone_key column if it doesn't exist (migration)
    try:
        db.execute("ALTER TABLE rate_cards ADD COLUMN zone_key TEXT DEFAULT ''")
    except Exception:
        pass
    db.commit()
    return db


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
            }

    results         = []
    total_original  = 0
    total_br        = 0
    total_base_cost = 0
    total_weight_lbs = 0
    total_cubic_ft  = 0
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

    for ship in shipments:
        raw_actual = float(ship.get("weight",       1) or 1)
        raw_billed = float(ship.get("billed_weight",0) or 0)

        dim_wt   = calc_dim_weight(
            ship.get("length", 0), ship.get("width", 0), ship.get("height", 0),
            dim_factor, dim_divisor=effective_dim_divisor)
        cubic_ft = calc_cubic_feet(
            ship.get("length", 0), ship.get("width", 0), ship.get("height", 0), dim_factor)

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

        for rc_id, card in cards.items():
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

            # Per-card DIM weight
            card_dim_divisor = card.get("dim_divisor", 166) if use_per_card_dim else effective_dim_divisor
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

            final = (base_rate * (1 + pct)) + (card_billable_ceil * per_lb) + per_ship
            final = round(final, 2)
            all_card_prices[card["name"]] = {
                "base":        round(base_rate, 2),
                "final":       final,
                "id":          rc_id,
                "billable_wt": card_billable_ceil,
                "zone":        card_zone
            }

            if best_price is None or final < best_price:
                best_price = final
                best_card  = card

        has_savings = best_price is not None and best_price < original_price
        savings     = round(original_price - best_price, 2) if has_savings else 0
        if not has_savings and best_price is None:
            best_price = original_price

        effective_br = best_price if has_savings else original_price
        total_br    += effective_br

        if has_savings and best_card:
            best_base = all_card_prices.get(best_card["name"], {}).get("base", 0)
            total_base_cost += best_base
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
            br_service_mix.setdefault(best_card["name"], {"count": 0, "total": 0})
            br_service_mix[best_card["name"]]["count"] += 1
            br_service_mix[best_card["name"]]["total"] += best_price

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
            "savings":         savings,
            "savings_pct":     round((savings / original_price) * 100, 1)
                               if original_price > 0 and savings > 0 else 0,
            "all_rates":       all_card_prices
        })

    # Finalize breakdowns
    total_count = len(results)

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
        },
        "by_zone":         zone_breakdown,
        "by_service":      service_savings,
        "by_carrier":      carrier_savings,
        "by_weight_band":  weight_band_breakdown,
        "br_service_mix":  br_service_mix,
        "zone_weight_pivot": zone_weight_pivot,
    }


# ─── HTTP Helpers ──────────────────────────────────────────────────────────────
def respond(data, status=200):
    print(f"Status: {status}")
    print("Content-Type: application/json")
    print()
    print(json.dumps(data))
    sys.exit(0)

def error(msg, status=400):
    respond({"error": msg}, status)

def read_body():
    try:
        length = int(os.environ.get("CONTENT_LENGTH", 0))
        if length > 0:
            return json.loads(sys.stdin.read(length))
    except Exception:
        pass
    return {}

def parse_path(path_info):
    parts = [p for p in path_info.strip("/").split("/") if p]
    return parts

def get_query_params():
    qs = os.environ.get("QUERY_STRING", "")
    params = {}
    for pair in qs.split("&"):
        if "=" in pair:
            k, v = pair.split("=", 1)
            params[k] = v
    return params

def check_auth(db, required_type=None):
    params = get_query_params()
    token  = params.get("token", "")
    if not token:
        return None
    sess = db.execute("SELECT * FROM sessions WHERE token = ?", (token,)).fetchone()
    if not sess:
        return None
    if required_type and sess["user_type"] != required_type:
        return None
    return {"user_type": sess["user_type"], "user_id": sess["user_id"], "token": sess["token"]}


# ─── Route Handlers ────────────────────────────────────────────────────────────

def handle_auth_login(db, body):
    email      = body.get("email", "").strip().lower()
    password   = body.get("password", "")
    login_type = body.get("type", "client")

    if login_type == "admin":
        pw_hash = hashlib.sha256(password.encode()).hexdigest()
        admin = db.execute(
            "SELECT * FROM admins WHERE email = ? AND password_hash = ?",
            (email, pw_hash)).fetchone()
        if not admin:
            error("Invalid admin credentials", 401)
        token = str(uuid.uuid4())
        db.execute("INSERT INTO sessions (token, user_type, user_id) VALUES (?, ?, ?)",
                   (token, "admin", admin["id"]))
        db.commit()
        respond({"token": token, "user_type": "admin", "user_id": admin["id"],
                 "name": admin["name"], "email": admin["email"]})
    else:
        client = db.execute(
            "SELECT * FROM clients WHERE LOWER(email) = ?", (email,)).fetchone()
        if not client:
            error("No invitation found for this email. Please contact your Broad Reach representative.", 401)
        token = str(uuid.uuid4())
        db.execute("INSERT INTO sessions (token, user_type, user_id) VALUES (?, ?, ?)",
                   (token, "client", client["id"]))
        db.commit()
        respond({
            "token":        token,
            "user_type":    "client",
            "user_id":      client["id"],
            "company_name": client["company_name"],
            "email":        client["email"],
            "contact_name": client["contact_name"],
            "logo_url":     client["logo_url"],
            "status":       client["status"]
        })


def handle_zones_lookup(db, params):
    """GET /api/zones/lookup?zip=10001[&carrier=USPS]"""
    zip_code = params.get("zip", "").strip()
    carrier  = params.get("carrier", "").strip()
    if not zip_code:
        error("zip parameter required")

    is_canadian = len(zip_code) >= 1 and zip_code[0].isalpha()

    if is_canadian:
        fsa = zip_code[:3].upper()
        if not carrier:
            # Return all zones
            fsa_data, province = lookup_ca_zone(zip_code)
            if not fsa_data or not isinstance(fsa_data, dict):
                respond({"zip": zip_code, "country": "CA", "zones": {}, "note": "FSA not found"})
            # Build display-named zone map
            zones_out = {}
            for ck, cv in fsa_data.items():
                if ck == "p":
                    continue
                zones_out[ck] = cv
            respond({
                "zip":      zip_code,
                "fsa":      fsa,
                "province": province,
                "country":  "CA",
                "zones":    zones_out
            })
        else:
            zone_val, province = lookup_ca_zone(zip_code, carrier)
            respond({
                "zip":      zip_code,
                "fsa":      fsa,
                "province": province,
                "country":  "CA",
                "carrier":  carrier,
                "zone":     zone_val
            })
    else:
        zip5 = zip_code.zfill(5)
        zip3 = zip5[:3]
        if not carrier:
            # Return all carriers
            zone_val, state, _ = lookup_us_zone(zip5)
            if zone_val is None or not isinstance(zone_val, dict):
                respond({"zip": zip5, "state": None, "zones": {}, "note": "ZIP not found"})
            # Build nicely named zones object
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
            respond({
                "zip":       zip5,
                "state":     state,
                "country":   "US",
                "zones":     zones_out,
                "das_flags": das_flags
            })
        else:
            # Map display carrier name to zone key
            # Try exact key first, then map
            carrier_key = carrier
            for ck, disp in CARRIER_DISPLAY.items():
                if disp.lower() == carrier.lower() or ck.lower() == carrier.lower():
                    carrier_key = ck
                    break
            zone_val, state, das = lookup_us_zone(zip5, carrier_key)
            respond({
                "zip":     zip5,
                "state":   state,
                "country": "US",
                "carrier": carrier,
                "zone":    zone_val,
                "das":     "DAS" if das else None
            })


def handle_service_catalog(db):
    """GET /api/service-catalog"""
    path = os.path.join(DATA_DIR, "wizmo_service_catalog.json")
    try:
        with open(path) as f:
            catalog = json.load(f)
        respond(catalog)
    except Exception as e:
        error(f"Could not load service catalog: {e}")


def handle_transit_times(db, params):
    """GET /api/transit-times[?state=NY]"""
    path = os.path.join(DATA_DIR, "ups_transit_times.json")
    try:
        with open(path) as f:
            tt = json.load(f)
    except Exception as e:
        error(f"Could not load transit times: {e}")

    state = params.get("state", "").strip().upper()
    if state:
        by_state = tt.get("by_state", {})
        state_data = by_state.get(state)
        if state_data is None:
            respond({"state": state, "hubs": {}, "note": "State not found"})
        respond({"state": state, "transit_days": state_data})
    else:
        respond(tt)


def handle_peak_surcharges(db):
    """GET /api/peak-surcharges"""
    path = os.path.join(DATA_DIR, "peak_surcharges.json")
    try:
        with open(path) as f:
            ps = json.load(f)
        respond(ps)
    except Exception as e:
        error(f"Could not load peak surcharges: {e}")


def handle_accessorials(db, params):
    """GET /api/accessorials[?carrier=FedEx]"""
    carrier = params.get("carrier", "").strip()

    results = {}

    # FedEx accessorials
    fedex_path = os.path.join(DATA_DIR, "fedex_accessorials.json")
    try:
        with open(fedex_path) as f:
            fa = json.load(f)
        if not carrier or carrier.lower() in ("fedex", "all"):
            results["FedEx"] = fa
    except Exception:
        pass

    # UPS Canada accessorials
    ups_ca_path = os.path.join(DATA_DIR, "ups_canada_accessorials.json")
    try:
        with open(ups_ca_path) as f:
            ua = json.load(f)
        if not carrier or carrier.lower() in ("ups canada", "ups_canada", "all"):
            results["UPS Canada"] = ua
    except Exception:
        pass

    if carrier and carrier.lower() not in ("fedex", "ups canada", "ups_canada", "all"):
        respond({"carrier": carrier, "accessorials": [], "note": "No accessorials data for this carrier"})

    respond({"carrier": carrier or "all", "accessorials": results})


def handle_clients(db, method, parts, body, auth):
    if len(parts) == 1:
        if method == "GET":
            rows = db.execute("SELECT * FROM clients ORDER BY invited_at DESC").fetchall()
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
            respond(clients)
        elif method == "POST":
            name  = body.get("company_name", "")
            email = body.get("email", "")
            if not name or not email:
                error("Company name and email required")
            try:
                db.execute("""INSERT INTO clients (company_name, email, contact_name, logo_url, documents_json)
                              VALUES (?, ?, ?, ?, ?)""",
                           (name, email, body.get("contact_name", ""),
                            body.get("logo_url", ""), json.dumps(body.get("documents", []))))
                db.commit()
                client_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
                respond({"id": client_id, "message": "Client invited"}, 201)
            except sqlite3.IntegrityError:
                error("Client with this email already exists")

    elif len(parts) >= 2:
        client_id = parts[1]

        if len(parts) == 2:
            if method == "GET":
                c = db.execute("SELECT * FROM clients WHERE id = ?", (client_id,)).fetchone()
                if not c:
                    error("Client not found", 404)
                result = dict(c)
                result["documents_json"]  = json.loads(result["documents_json"])
                result["setup_info_json"] = json.loads(result["setup_info_json"])
                sd = db.execute(
                    "SELECT * FROM shipping_data WHERE client_id = ? ORDER BY id DESC LIMIT 1",
                    (client_id,)).fetchone()
                if sd:
                    result["shipping_data"] = {
                        "id":          sd["id"],
                        "data":        json.loads(sd["data_json"]),
                        "row_count":   sd["row_count"],
                        "summary":     json.loads(sd["summary_json"]),
                        "uploaded_at": sd["uploaded_at"]
                    }
                else:
                    result["shipping_data"] = None
                an = db.execute(
                    "SELECT * FROM analyses WHERE client_id = ? ORDER BY id DESC LIMIT 1",
                    (client_id,)).fetchone()
                if an:
                    result["analysis"] = {
                        "id":          an["id"],
                        "config":      json.loads(an["config_json"]),
                        "results":     json.loads(an["results_json"]),
                        "status":      an["status"],
                        "created_at":  an["created_at"],
                        "published_at": an["published_at"]
                    }
                else:
                    result["analysis"] = None
                respond(result)
            elif method == "PUT":
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
                respond({"message": "Client updated"})

        elif len(parts) == 3:
            sub = parts[2]
            if sub == "documents":
                if method == "POST":
                    doc_ids = body.get("document_ids", [])
                    db.execute("UPDATE clients SET documents_json = ? WHERE id = ?",
                               (json.dumps(doc_ids), client_id))
                    db.commit()
                    respond({"message": "Documents updated"})

            elif sub == "shipping-data":
                if method == "POST":
                    data = body.get("data", [])
                    if not data:
                        error("No shipping data provided")
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
                    db.execute("UPDATE clients SET status = 'Analysis Pending' WHERE id = ?", (client_id,))
                    client_row = db.execute(
                        "SELECT company_name FROM clients WHERE id = ?", (client_id,)).fetchone()
                    company = client_row["company_name"] if client_row else "Unknown"
                    db.execute("""INSERT INTO notifications (type, message, client_id) VALUES (?, ?, ?)""",
                               ("upload_received",
                                f"{company} uploaded {len(data)} shipments — ready for analysis",
                                client_id))
                    db.commit()
                    respond({"message": "Shipping data uploaded", "summary": summary}, 201)
                elif method == "GET":
                    sd = db.execute(
                        "SELECT * FROM shipping_data WHERE client_id = ? ORDER BY id DESC LIMIT 1",
                        (client_id,)).fetchone()
                    if not sd:
                        respond({"data": [], "summary": {}})
                    respond({
                        "data":        json.loads(sd["data_json"]),
                        "summary":     json.loads(sd["summary_json"]),
                        "row_count":   sd["row_count"],
                        "uploaded_at": sd["uploaded_at"]
                    })
                elif method == "DELETE":
                    db.execute("DELETE FROM shipping_data WHERE client_id = ?", (client_id,))
                    db.execute("DELETE FROM analyses WHERE client_id = ?", (client_id,))
                    db.execute("UPDATE clients SET status = 'Invited' WHERE id = ?", (client_id,))
                    db.commit()
                    respond({"message": "Shipping data removed"})

            elif sub == "analysis":
                if method == "POST":
                    sd = db.execute(
                        "SELECT data_json, summary_json FROM shipping_data WHERE client_id = ? ORDER BY id DESC LIMIT 1",
                        (client_id,)).fetchone()
                    if not sd:
                        error("No shipping data available")
                    shipments   = json.loads(sd["data_json"])
                    sd_summary  = json.loads(sd["summary_json"]) if sd["summary_json"] else {}
                    unit_system = sd_summary.get("unit_system", {"weight": "lbs", "dimensions": "in"})
                    currency    = sd_summary.get("currency", "USD")
                    results     = run_rate_analysis(shipments, body, db, unit_system=unit_system)
                    results["currency"] = currency
                    existing = db.execute("SELECT id FROM analyses WHERE client_id = ?", (client_id,)).fetchone()
                    if existing:
                        db.execute("""UPDATE analyses SET config_json = ?, results_json = ?, status = 'draft',
                                      created_at = datetime('now') WHERE client_id = ?""",
                                   (json.dumps(body), json.dumps(results), client_id))
                    else:
                        db.execute("""INSERT INTO analyses (client_id, config_json, results_json, status)
                                      VALUES (?, ?, ?, 'draft')""",
                                   (client_id, json.dumps(body), json.dumps(results)))
                    db.commit()
                    respond({"message": "Analysis complete", "results": results}, 201)

            elif sub == "setup":
                if method == "POST":
                    db.execute("UPDATE clients SET setup_info_json = ? WHERE id = ?",
                               (json.dumps(body), client_id))
                    db.commit()
                    respond({"message": "Setup info saved"})
                elif method == "GET":
                    c = db.execute("SELECT setup_info_json FROM clients WHERE id = ?", (client_id,)).fetchone()
                    if c:
                        respond(json.loads(c["setup_info_json"]))
                    else:
                        respond({})

        elif len(parts) == 4:
            sub    = parts[2]
            action = parts[3]
            if sub == "analysis" and action == "publish":
                if method == "POST":
                    db.execute("""UPDATE analyses SET status = 'published', published_at = datetime('now')
                                  WHERE client_id = ?""", (client_id,))
                    db.execute("UPDATE clients SET status = 'Analysis Complete' WHERE id = ?", (client_id,))
                    client_row = db.execute(
                        "SELECT company_name FROM clients WHERE id = ?", (client_id,)).fetchone()
                    company = client_row["company_name"] if client_row else "Unknown"
                    db.execute("""INSERT INTO client_notifications (client_id, type, message)
                                  VALUES (?, ?, ?)""",
                               (client_id, "analysis_ready",
                                "Your savings analysis is ready! Log in to view your personalized pricing package."))
                    db.commit()
                    respond({"message": "Analysis published", "send_email": True, "company_name": company})


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


def handle_rate_cards(db, method, parts, body):
    if len(parts) == 1:
        if method == "GET":
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
                cards.append(c)
            respond(cards)
        elif method == "POST":
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
            db.execute("""INSERT INTO rate_cards
                (name, service_type, carrier, pricing_type, description, rate_grid_json,
                 zone_mapping_json, zone_key, dim_divisor, currency, country, version, status)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,'active')""",
                (name, service_type, body.get("carrier", ""), pricing_type,
                 body.get("description", ""), json.dumps(rate_grid),
                 json.dumps(body.get("zone_mapping", {})), zone_key,
                 dim_divisor, currency, country, version))
            db.commit()
            rc_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
            respond({"id": rc_id, "message": "Rate card created"}, 201)

    elif len(parts) == 2:
        rc_id = parts[1]
        if rc_id == "compare" and method == "POST":
            card_id_1 = body.get("card_id_1")
            card_id_2 = body.get("card_id_2")
            if not card_id_1 or not card_id_2:
                error("card_id_1 and card_id_2 required")
            r1 = db.execute("SELECT * FROM rate_cards WHERE id = ?", (card_id_1,)).fetchone()
            r2 = db.execute("SELECT * FROM rate_cards WHERE id = ?", (card_id_2,)).fetchone()
            if not r1 or not r2:
                error("One or both rate cards not found", 404)
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
            respond({
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
            })
        elif method == "GET":
            r = db.execute("SELECT * FROM rate_cards WHERE id = ?", (rc_id,)).fetchone()
            if not r:
                error("Rate card not found", 404)
            result = dict(r)
            result["rate_grid_json"]   = json.loads(result["rate_grid_json"])
            result["zone_mapping_json"] = json.loads(result["zone_mapping_json"])
            result["dim_divisor"]      = result.get("dim_divisor", 166)
            result["zone_key"]         = result.get("zone_key", "")
            respond(result)
        elif method == "PUT":
            fields = []
            vals   = []
            for f in ["name", "service_type", "carrier", "description", "pricing_type",
                      "currency", "country", "version", "status", "effective_date",
                      "expiration_date", "zone_key"]:
                if f in body:
                    fields.append(f"{f} = ?")
                    vals.append(body[f])
            if "dim_divisor" in body:
                fields.append("dim_divisor = ?")
                vals.append(float(body["dim_divisor"]))
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
            respond({"message": "Rate card updated"})
        elif method == "DELETE":
            db.execute("DELETE FROM rate_cards WHERE id = ?", (rc_id,))
            db.commit()
            respond({"message": "Rate card deleted"})


def handle_documents(db, method, parts, body):
    if len(parts) == 1:
        if method == "GET":
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
                docs.append(d)
            respond(docs)
        elif method == "POST":
            db.execute("INSERT INTO documents (name, category, filename) VALUES (?, ?, ?)",
                       (body.get("name", ""), body.get("category", "Other"), body.get("filename", "")))
            db.commit()
            doc_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
            respond({"id": doc_id, "message": "Document created"}, 201)


def handle_zone_charts(db, method, parts, body):
    if len(parts) == 1:
        if method == "GET":
            rows = db.execute(
                "SELECT id, name, carrier, origin_zip, description, row_count, created_at "
                "FROM zone_charts ORDER BY created_at DESC"
            ).fetchall()
            respond([dict(r) for r in rows])
        elif method == "POST":
            name = body.get("name", "")
            if not name:
                error("Name required")
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
            respond({"id": zc_id, "message": "Zone chart created", "row_count": len(data)}, 201)

    elif len(parts) == 2:
        zc_id = parts[1]
        if method == "GET":
            r = db.execute("SELECT * FROM zone_charts WHERE id = ?", (zc_id,)).fetchone()
            if not r:
                error("Zone chart not found", 404)
            result = dict(r)
            result["data_json"] = json.loads(result["data_json"])
            respond(result)
        elif method == "DELETE":
            db.execute("DELETE FROM zone_charts WHERE id = ?", (zc_id,))
            db.commit()
            respond({"message": "Zone chart deleted"})


def handle_settings(db, method, body):
    if method == "GET":
        admin = db.execute("SELECT * FROM admins WHERE id = 1").fetchone()
        respond({"name": admin["name"], "email": admin["email"]} if admin else {})
    elif method == "PUT":
        if "name" in body:
            db.execute("UPDATE admins SET name = ? WHERE id = 1", (body["name"],))
        if "password" in body and body["password"]:
            pw_hash = hashlib.sha256(body["password"].encode()).hexdigest()
            db.execute("UPDATE admins SET password_hash = ? WHERE id = 1", (pw_hash,))
        db.commit()
        respond({"message": "Settings updated"})


def handle_notifications(db, method, parts, body):
    if len(parts) == 1 and method == "GET":
        rows = db.execute("""
            SELECT n.*, c.company_name FROM notifications n
            LEFT JOIN clients c ON c.id = n.client_id
            ORDER BY n.created_at DESC LIMIT 50
        """).fetchall()
        notifs = [dict(r) for r in rows]
        unread_count = db.execute("SELECT COUNT(*) FROM notifications WHERE read = 0").fetchone()[0]
        respond({"notifications": notifs, "unread_count": unread_count})
    elif len(parts) == 3 and parts[2] == "read" and method == "POST":
        notif_id = parts[1]
        db.execute("UPDATE notifications SET read = 1 WHERE id = ?", (notif_id,))
        db.commit()
        respond({"message": "Marked as read"})
    elif len(parts) == 2 and parts[1] == "read-all" and method == "POST":
        db.execute("UPDATE notifications SET read = 1")
        db.commit()
        respond({"message": "All marked as read"})
    else:
        error("Unknown notifications endpoint", 404)


def handle_client_notifications(db, method, parts, body, client_id):
    if len(parts) == 3 and parts[2] == "notifications" and method == "GET":
        rows = db.execute("""
            SELECT * FROM client_notifications WHERE client_id = ?
            ORDER BY created_at DESC LIMIT 20
        """, (client_id,)).fetchall()
        notifs      = [dict(r) for r in rows]
        unread_count = db.execute(
            "SELECT COUNT(*) FROM client_notifications WHERE client_id = ? AND read = 0",
            (client_id,)
        ).fetchone()[0]
        respond({"notifications": notifs, "unread_count": unread_count})
    elif len(parts) == 4 and parts[3] == "read" and method == "POST":
        db.execute("UPDATE client_notifications SET read = 1 WHERE client_id = ?", (client_id,))
        db.commit()
        respond({"message": "Marked as read"})
    else:
        error("Unknown client notifications endpoint", 404)


def handle_dashboard(db):
    total_clients = db.execute("SELECT COUNT(*) FROM clients").fetchone()[0]
    active        = db.execute("SELECT COUNT(*) FROM analyses WHERE status = 'published'").fetchone()[0]
    pending       = db.execute("SELECT COUNT(*) FROM clients WHERE status = 'Analysis Pending'").fetchone()[0]
    completed     = db.execute("SELECT COUNT(*) FROM analyses WHERE status = 'published'").fetchone()[0]
    total_rcs     = db.execute("SELECT COUNT(*) FROM rate_cards").fetchone()[0]
    respond({
        "total_clients":      total_clients,
        "active_analyses":    active,
        "pending_uploads":    pending,
        "completed_analyses": completed,
        "total_rate_cards":   total_rcs,
    })


# ─── Main Router ───────────────────────────────────────────────────────────────
def main():
    db = init_db()
    seed_demo_data(db)

    method    = os.environ.get("REQUEST_METHOD", "GET")
    path_info = os.environ.get("PATH_INFO", "")
    parts     = parse_path(path_info)
    params    = get_query_params()

    body = {}
    if method in ("POST", "PUT", "PATCH"):
        body = read_body()

    if not parts:
        respond({
            "status": "ok", "version": "3.0",
            "us_zones_loaded":  len(US_ZONES),
            "ca_zones_loaded":  len(CA_ZONES),
        })

    route = parts[0]

    if route == "auth" and len(parts) >= 2 and parts[1] == "login":
        handle_auth_login(db, body)

    elif route == "clients":
        if len(parts) >= 3 and parts[2] == "notifications":
            handle_client_notifications(db, method, parts, body, parts[1])
        else:
            handle_clients(db, method, parts, body, None)

    elif route == "notifications":
        handle_notifications(db, method, parts, body)

    elif route == "rate-cards":
        handle_rate_cards(db, method, parts, body)

    elif route == "zone-charts":
        handle_zone_charts(db, method, parts, body)

    elif route == "documents":
        handle_documents(db, method, parts, body)

    elif route == "settings":
        handle_settings(db, method, body)

    elif route == "dashboard":
        handle_dashboard(db)

    # ── New endpoints ──────────────────────────────────────────────────────────

    elif route == "zones" and len(parts) >= 2 and parts[1] == "lookup":
        handle_zones_lookup(db, params)

    elif route == "service-catalog":
        handle_service_catalog(db)

    elif route == "transit-times":
        handle_transit_times(db, params)

    elif route == "peak-surcharges":
        handle_peak_surcharges(db)

    elif route == "accessorials":
        handle_accessorials(db, params)

    else:
        error("Unknown route: " + "/".join(parts), 404)


if __name__ == "__main__":
    main()
