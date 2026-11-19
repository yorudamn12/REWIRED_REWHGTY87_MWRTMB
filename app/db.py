"""SQLite helpers: open a connection, create tables, seed inventory, save chat messages."""

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from app.seed import HINDI, SEED_ITEMS

# The database file lives in the project folder (next to app/ and static/)
DB_PATH = Path(__file__).resolve().parent.parent / "listlens.db"

# The store owner's own ListLens chat (order alerts) is saved under this special name
STORE_CHAT = "__store__"

# Short codes used in SKU numbers, e.g. SKU-STP-007
CATEGORY_CODES = {
    "staples": "STP", "dairy": "DRY", "personal_care": "PCR", "cleaning": "CLN",
    "snacks": "SNK", "beverages": "BEV", "other": "OTH",
}


def get_conn():
    """Open a new connection. row_factory lets us read columns by name: row["price"]."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def now():
    """Current local time as text, e.g. 2026-11-19T10:30:00"""
    return datetime.now().isoformat(timespec="seconds")


def make_sku(category, item_id):
    """SKU code from category + id, e.g. ('staples', 7) -> 'SKU-STP-007'"""
    return f"SKU-{CATEGORY_CODES.get(category, 'OTH')}-{item_id:03d}"


def _add_missing_columns(conn, table, columns):
    """Older database files may miss newer columns: add them if needed."""
    existing = [r["name"] for r in conn.execute(f"PRAGMA table_info({table})")]
    for col in columns:
        if col not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} TEXT")


def init_db():
    """Create all tables (if missing) and fill inventory the first time."""
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY,
            name TEXT, brand TEXT, category TEXT, unit TEXT,
            price REAL, stock INTEGER,
            sku TEXT, hindi_name TEXT
        );
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY,
            buyer_name TEXT, flat TEXT, status TEXT, total REAL,
            image_path TEXT, created_at TEXT,
            society TEXT, block TEXT, delivery_date TEXT
        );
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY,
            order_id INT, raw_text TEXT, qty INT, item_id INT NULL,
            status TEXT, chosen_item_id INT NULL, line_price REAL,
            alternatives_json TEXT
        );
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY,
            buyer_name TEXT, sender TEXT, type TEXT,
            payload_json TEXT, created_at TEXT
        );
    """)
    _add_missing_columns(conn, "orders", ["society", "block", "delivery_date"])
    _add_missing_columns(conn, "inventory", ["sku", "hindi_name"])

    # Seed only if inventory is empty (so restarting the server keeps stock changes)
    count = conn.execute("SELECT COUNT(*) FROM inventory").fetchone()[0]
    if count == 0:
        for name, brand, category, unit, price, stock in SEED_ITEMS:
            cur = conn.execute(
                "INSERT INTO inventory (name, brand, category, unit, price, stock, hindi_name) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (name, brand, category, unit, price, stock, HINDI.get(name, "")),
            )
            conn.execute("UPDATE inventory SET sku = ? WHERE id = ?", (make_sku(category, cur.lastrowid), cur.lastrowid))

    # Fill SKU / Hindi name for rows from an older database
    for r in conn.execute("SELECT id, name, category FROM inventory WHERE sku IS NULL").fetchall():
        conn.execute("UPDATE inventory SET sku = ?, hindi_name = ? WHERE id = ?",
                     (make_sku(r["category"], r["id"]), HINDI.get(r["name"], ""), r["id"]))
    conn.commit()
    conn.close()


def get_inventory(conn):
    """All inventory rows as a list of plain dicts."""
    rows = conn.execute("SELECT * FROM inventory ORDER BY category, name").fetchall()
    return [dict(r) for r in rows]


def add_message(conn, buyer_name, sender, msg_type, payload):
    """Save one chat message. payload is a dict; we store it as JSON text.
    sender: "buyer", "bot" (ListLens assistant) or "vendor" (the shop owner stepping in)."""
    cur = conn.execute(
        "INSERT INTO messages (buyer_name, sender, type, payload_json, created_at) VALUES (?, ?, ?, ?, ?)",
        (buyer_name, sender, msg_type, json.dumps(payload), now()),
    )
    return cur.lastrowid


def bot_text(conn, buyer_name, text):
    """Shortcut: bot sends a plain text message."""
    return add_message(conn, buyer_name, "bot", "text", {"text": text})


def notify_store(conn, text, order_id=None):
    """ListLens sends an alert to the store owner's phone chat.
    order_id (optional) adds an 'Open order' button that jumps to the dashboard."""
    return add_message(conn, STORE_CHAT, "bot", "alert", {"text": text, "order_id": order_id})
