import sqlite3
from pathlib import Path
from typing import Any

from flask import current_app, g

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    role TEXT NOT NULL CHECK(role IN ('admin', 'planner'))
);

CREATE TABLE IF NOT EXISTS capabilities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT
);

CREATE TABLE IF NOT EXISTS resources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'available'
);

CREATE TABLE IF NOT EXISTS resource_capabilities (
    resource_id INTEGER NOT NULL,
    capability_id INTEGER NOT NULL,
    PRIMARY KEY (resource_id, capability_id),
    FOREIGN KEY (resource_id) REFERENCES resources(id) ON DELETE CASCADE,
    FOREIGN KEY (capability_id) REFERENCES capabilities(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS customer_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_code TEXT NOT NULL UNIQUE,
    customer_name TEXT NOT NULL,
    product_name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ordered_tests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    test_name TEXT NOT NULL,
    required_capability_id INTEGER,
    FOREIGN KEY (order_id) REFERENCES customer_orders(id) ON DELETE CASCADE,
    FOREIGN KEY (required_capability_id) REFERENCES capabilities(id)
);

CREATE TABLE IF NOT EXISTS allocations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ordered_test_id INTEGER NOT NULL UNIQUE,
    resource_id INTEGER NOT NULL,
    planner_user_id INTEGER NOT NULL,
    notes TEXT,
    FOREIGN KEY (ordered_test_id) REFERENCES ordered_tests(id) ON DELETE CASCADE,
    FOREIGN KEY (resource_id) REFERENCES resources(id),
    FOREIGN KEY (planner_user_id) REFERENCES users(id)
);
"""


def _db_path() -> Path:
    return Path(current_app.root_path).parent / current_app.config["DATABASE"]


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        db = sqlite3.connect(_db_path())
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON;")
        g.db = db
    return g.db


def close_db(_: Any = None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db() -> None:
    db = get_db()
    db.executescript(SCHEMA_SQL)
    db.commit()


def init_demo_seed() -> None:
    db = get_db()

    db.execute("INSERT OR IGNORE INTO users (username, role) VALUES ('admin.demo', 'admin')")
    db.execute("INSERT OR IGNORE INTO users (username, role) VALUES ('planner.demo', 'planner')")

    db.execute("INSERT OR IGNORE INTO capabilities (name, description) VALUES (?, ?)", ("Multimeter Calibration", "Ability to calibrate multimeters"))
    db.execute("INSERT OR IGNORE INTO capabilities (name, description) VALUES (?, ?)", ("Vibration Test", "Ability to run vibration tests"))
    db.execute("INSERT OR IGNORE INTO capabilities (name, description) VALUES (?, ?)", ("Humidity Test", "Ability to run humidity tests"))

    db.execute("INSERT OR IGNORE INTO resources (code, name, resource_type, status) VALUES (?, ?, ?, ?)", ("EQ-001", "Multimeter Calibrator A", "equipment", "available"))
    db.execute("INSERT OR IGNORE INTO resources (code, name, resource_type, status) VALUES (?, ?, ?, ?)", ("EQ-020", "Vibration Tester V-9", "equipment", "available"))
    db.execute("INSERT OR IGNORE INTO resources (code, name, resource_type, status) VALUES (?, ?, ?, ?)", ("FAC-004", "Humidity Chamber Room B", "facility", "available"))
    db.execute("INSERT OR IGNORE INTO resources (code, name, resource_type, status) VALUES (?, ?, ?, ?)", ("TECH-102", "Maya Jensen", "technician", "available"))

    db.execute("INSERT OR IGNORE INTO customer_orders (order_code, customer_name, product_name) VALUES (?, ?, ?)", ("ORD-2026-001", "Acme Instruments", "Multimeter"))
    db.execute("INSERT OR IGNORE INTO customer_orders (order_code, customer_name, product_name) VALUES (?, ?, ?)", ("ORD-2026-002", "Nova Mobile", "Mobile Phone Prototype"))

    db.execute("""
        INSERT OR IGNORE INTO ordered_tests (order_id, test_name, required_capability_id)
        SELECT o.id, ?, c.id
        FROM customer_orders o
        JOIN capabilities c ON c.name = ?
        WHERE o.order_code = ?
    """, ("Multimeter Calibration", "Multimeter Calibration", "ORD-2026-001"))

    db.execute("""
        INSERT OR IGNORE INTO ordered_tests (order_id, test_name, required_capability_id)
        SELECT o.id, ?, c.id
        FROM customer_orders o
        JOIN capabilities c ON c.name = ?
        WHERE o.order_code = ?
    """, ("Vibration Test", "Vibration Test", "ORD-2026-002"))

    db.execute("""
        INSERT OR IGNORE INTO ordered_tests (order_id, test_name, required_capability_id)
        SELECT o.id, ?, c.id
        FROM customer_orders o
        JOIN capabilities c ON c.name = ?
        WHERE o.order_code = ?
    """, ("Humidity Test", "Humidity Test", "ORD-2026-002"))

    db.execute("""
        INSERT OR IGNORE INTO resource_capabilities (resource_id, capability_id)
        SELECT r.id, c.id
        FROM resources r
        JOIN capabilities c ON c.name = ?
        WHERE r.code = ?
    """, ("Multimeter Calibration", "EQ-001"))

    db.execute("""
        INSERT OR IGNORE INTO resource_capabilities (resource_id, capability_id)
        SELECT r.id, c.id
        FROM resources r
        JOIN capabilities c ON c.name = ?
        WHERE r.code = ?
    """, ("Vibration Test", "EQ-020"))

    db.execute("""
        INSERT OR IGNORE INTO resource_capabilities (resource_id, capability_id)
        SELECT r.id, c.id
        FROM resources r
        JOIN capabilities c ON c.name = ?
        WHERE r.code = ?
    """, ("Humidity Test", "FAC-004"))

    db.execute("""
        INSERT OR IGNORE INTO resource_capabilities (resource_id, capability_id)
        SELECT r.id, c.id
        FROM resources r
        JOIN capabilities c ON c.name IN ('Vibration Test', 'Humidity Test')
        WHERE r.code = 'TECH-102'
    """)

    db.commit()
