import sqlite3
from pathlib import Path
from typing import Any

from flask import current_app, g

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    role TEXT NOT NULL CHECK(role IN ('admin', 'planner', 'technician')),
    linked_resource_id INTEGER,
    FOREIGN KEY (linked_resource_id) REFERENCES resources(id)
);

CREATE TABLE IF NOT EXISTS capabilities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    discipline TEXT
);

CREATE TABLE IF NOT EXISTS resources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'available',
    site TEXT
);

CREATE TABLE IF NOT EXISTS exclusion_groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS exclusion_group_resources (
    group_id INTEGER NOT NULL,
    resource_id INTEGER NOT NULL,
    PRIMARY KEY (group_id, resource_id),
    FOREIGN KEY (group_id) REFERENCES exclusion_groups(id) ON DELETE CASCADE,
    FOREIGN KEY (resource_id) REFERENCES resources(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS resource_capabilities (
    resource_id INTEGER NOT NULL,
    capability_id INTEGER NOT NULL,
    PRIMARY KEY (resource_id, capability_id),
    FOREIGN KEY (resource_id) REFERENCES resources(id) ON DELETE CASCADE,
    FOREIGN KEY (capability_id) REFERENCES capabilities(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    contact_name TEXT,
    contact_email TEXT,
    contact_phone TEXT,
    address TEXT,
    created_at TEXT NOT NULL,
    created_by_user_id INTEGER,
    FOREIGN KEY (created_by_user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS customer_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_code TEXT NOT NULL UNIQUE,
    customer_name TEXT NOT NULL,
    product_name TEXT NOT NULL,
    weekly_note TEXT,
    waiting_for_customer INTEGER NOT NULL DEFAULT 0,
    customer_id INTEGER -- no declared FK, same reasoning as ordered_tests.template_application_id:
        -- an existing table, so a plain ADD COLUMN is the only safe way to add this without
        -- risking silently dropping an ON DELETE action (Phase 8's eut_id lesson); deleting a
        -- customer clears this application-side (see delete_customer) rather than via a
        -- DB-level ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS milestones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    target_date TEXT,
    notes TEXT,
    FOREIGN KEY (order_id) REFERENCES customer_orders(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS staff_absences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    resource_id INTEGER NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    reason TEXT,
    FOREIGN KEY (resource_id) REFERENCES resources(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS customer_visits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    notes TEXT,
    FOREIGN KEY (order_id) REFERENCES customer_orders(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS euts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    serial_number TEXT,
    notes TEXT,
    FOREIGN KEY (order_id) REFERENCES customer_orders(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS ordered_tests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    eut_id INTEGER,
    test_name TEXT NOT NULL,
    required_capability_id INTEGER,
    sequence INTEGER,
    planned_start_date TEXT,
    planned_end_date TEXT,
    template_application_id INTEGER, -- no declared FK: deleting the whole group is an
        -- application-level cascade (delete matching ordered_tests, then the
        -- template_applications row), not a DB-enforced one, so a later ADD COLUMN
        -- migration on this table can't silently drop an ON DELETE action (the exact
        -- bug hit adding eut_id in Phase 8)
    FOREIGN KEY (order_id) REFERENCES customer_orders(id) ON DELETE CASCADE,
    FOREIGN KEY (eut_id) REFERENCES euts(id) ON DELETE SET NULL,
    FOREIGN KEY (required_capability_id) REFERENCES capabilities(id)
);

CREATE TABLE IF NOT EXISTS activity_dependencies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ordered_test_id INTEGER NOT NULL,
    depends_on_ordered_test_id INTEGER NOT NULL,
    FOREIGN KEY (ordered_test_id) REFERENCES ordered_tests(id) ON DELETE CASCADE,
    FOREIGN KEY (depends_on_ordered_test_id) REFERENCES ordered_tests(id) ON DELETE CASCADE,
    UNIQUE (ordered_test_id, depends_on_ordered_test_id)
);

CREATE TABLE IF NOT EXISTS reschedule_dismissals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ordered_test_id INTEGER NOT NULL,
    depends_on_ordered_test_id INTEGER NOT NULL,
    dismissed_at TEXT NOT NULL,
    FOREIGN KEY (ordered_test_id) REFERENCES ordered_tests(id) ON DELETE CASCADE,
    FOREIGN KEY (depends_on_ordered_test_id) REFERENCES ordered_tests(id) ON DELETE CASCADE,
    UNIQUE (ordered_test_id, depends_on_ordered_test_id)
);

CREATE TABLE IF NOT EXISTS activity_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ordered_test_id INTEGER NOT NULL,
    changed_at TEXT NOT NULL,
    user_id INTEGER,
    username TEXT,
    action TEXT NOT NULL,
    detail TEXT NOT NULL,
    reason TEXT,
    FOREIGN KEY (ordered_test_id) REFERENCES ordered_tests(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS proposals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT NOT NULL,
    proposal_type TEXT NOT NULL CHECK(proposal_type IN ('enhancement', 'bug')),
    title TEXT NOT NULL,
    description TEXT,
    submitted_by_user_id INTEGER,
    submitted_by_username TEXT,
    created_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'new' CHECK(status IN ('new', 'accepted', 'in_progress', 'done', 'rejected')),
    admin_comment TEXT,
    admin_user_id INTEGER,
    updated_at TEXT,
    FOREIGN KEY (submitted_by_user_id) REFERENCES users(id),
    FOREIGN KEY (admin_user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS activity_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    notes TEXT,
    version INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS template_applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    template_id INTEGER,
    template_name TEXT NOT NULL,
    order_id INTEGER NOT NULL,
    eut_id INTEGER,
    applied_at TEXT NOT NULL,
    applied_template_version INTEGER,
    modified INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (template_id) REFERENCES activity_templates(id) ON DELETE SET NULL,
    FOREIGN KEY (order_id) REFERENCES customer_orders(id) ON DELETE CASCADE,
    FOREIGN KEY (eut_id) REFERENCES euts(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS activity_template_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    template_id INTEGER NOT NULL,
    step_number INTEGER NOT NULL,
    activity_name TEXT NOT NULL,
    required_capability_id INTEGER,
    notes TEXT,
    FOREIGN KEY (template_id) REFERENCES activity_templates(id) ON DELETE CASCADE,
    FOREIGN KEY (required_capability_id) REFERENCES capabilities(id)
);

CREATE TABLE IF NOT EXISTS allocations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ordered_test_id INTEGER NOT NULL,
    resource_id INTEGER NOT NULL,
    planner_user_id INTEGER NOT NULL,
    notes TEXT,
    UNIQUE (ordered_test_id, resource_id),
    FOREIGN KEY (ordered_test_id) REFERENCES ordered_tests(id) ON DELETE CASCADE,
    FOREIGN KEY (resource_id) REFERENCES resources(id),
    FOREIGN KEY (planner_user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS test_procedures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    capability_id INTEGER,
    title TEXT NOT NULL,
    summary TEXT,
    steps TEXT NOT NULL,
    equipment_needed TEXT,
    facility_needed TEXT,
    safety_notes TEXT,
    FOREIGN KEY (capability_id) REFERENCES capabilities(id)
);

CREATE TABLE IF NOT EXISTS work_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    work_order_code TEXT NOT NULL UNIQUE,
    ordered_test_id INTEGER NOT NULL UNIQUE,
    technician_user_id INTEGER NOT NULL,
    procedure_id INTEGER,
    status TEXT NOT NULL DEFAULT 'planned' CHECK(status IN ('planned', 'in_progress', 'on_hold', 'completed')),
    scheduled_date TEXT,
    started_at TEXT,
    completed_at TEXT,
    result TEXT CHECK(result IN ('pass', 'fail', 'n_a') OR result IS NULL),
    notes TEXT,
    FOREIGN KEY (ordered_test_id) REFERENCES ordered_tests(id) ON DELETE CASCADE,
    FOREIGN KEY (technician_user_id) REFERENCES users(id),
    FOREIGN KEY (procedure_id) REFERENCES test_procedures(id)
);

CREATE TABLE IF NOT EXISTS procedure_checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    procedure_id INTEGER NOT NULL,
    step_number INTEGER NOT NULL,
    description TEXT NOT NULL,
    expected_value TEXT,
    FOREIGN KEY (procedure_id) REFERENCES test_procedures(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS test_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_code TEXT NOT NULL UNIQUE,
    work_order_id INTEGER NOT NULL UNIQUE,
    ordered_test_id INTEGER NOT NULL,
    procedure_id INTEGER,
    uut_name TEXT,
    uut_serial_number TEXT,
    technician_user_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft', 'submitted', 'approved', 'rejected')),
    technician_signed_at TEXT,
    overall_result TEXT CHECK(overall_result IN ('pass', 'fail', 'n_a') OR overall_result IS NULL),
    notes TEXT,
    reviewer_user_id INTEGER,
    reviewer_decision TEXT CHECK(reviewer_decision IN ('approved', 'rejected') OR reviewer_decision IS NULL),
    reviewer_comment TEXT,
    reviewer_signed_at TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (work_order_id) REFERENCES work_orders(id) ON DELETE CASCADE,
    FOREIGN KEY (ordered_test_id) REFERENCES ordered_tests(id) ON DELETE CASCADE,
    FOREIGN KEY (procedure_id) REFERENCES test_procedures(id),
    FOREIGN KEY (technician_user_id) REFERENCES users(id),
    FOREIGN KEY (reviewer_user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS report_steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id INTEGER NOT NULL,
    step_number INTEGER NOT NULL,
    description TEXT NOT NULL,
    expected_value TEXT,
    actual_value TEXT,
    result TEXT CHECK(result IN ('pass', 'fail', 'n_a') OR result IS NULL),
    FOREIGN KEY (report_id) REFERENCES test_reports(id) ON DELETE CASCADE
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


def _table_exists(db: sqlite3.Connection, name: str) -> bool:
    return (
        db.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)
        ).fetchone()
        is not None
    )


def _migrate_users_table(db: sqlite3.Connection) -> None:
    """Upgrade a users table created before the technician role/linked_resource_id existed."""
    if not _table_exists(db, "users"):
        return

    columns = {row["name"] for row in db.execute("PRAGMA table_info(users)").fetchall()}
    if "linked_resource_id" in columns:
        return

    # Build the replacement under a temporary name, then drop the old table and
    # rename the replacement into place. Renaming the *old* table directly would
    # make SQLite rewrite other tables' FK text (e.g. allocations' "REFERENCES
    # users(...)") to point at the temporary name, leaving it dangling for good.
    # Doing it this way, other tables' FK text keeps saying "users" throughout,
    # and it resolves correctly again once the replacement is renamed into place.
    db.execute("PRAGMA foreign_keys = OFF")
    try:
        db.execute(
            """
            CREATE TABLE users_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                role TEXT NOT NULL CHECK(role IN ('admin', 'planner', 'technician')),
                linked_resource_id INTEGER,
                FOREIGN KEY (linked_resource_id) REFERENCES resources(id)
            )
            """
        )
        db.execute("INSERT INTO users_new (id, username, role) SELECT id, username, role FROM users")
        db.execute("DROP TABLE users")
        db.execute("ALTER TABLE users_new RENAME TO users")
        db.commit()
    finally:
        db.execute("PRAGMA foreign_keys = ON")


def _migrate_ordered_tests_table(db: sqlite3.Connection) -> None:
    """Upgrade an ordered_tests table created before the optional eut_id column existed.

    Needs a full table rebuild (not a plain ADD COLUMN) because eut_id must carry an
    ON DELETE SET NULL action, and SQLite cannot attach a delete action to a column
    added later via ALTER TABLE ADD COLUMN.
    """
    if not _table_exists(db, "ordered_tests"):
        return

    columns = {row["name"] for row in db.execute("PRAGMA table_info(ordered_tests)").fetchall()}
    has_eut_id = "eut_id" in columns
    has_correct_fk = any(
        fk["table"] == "euts" and fk["from"] == "eut_id" and fk["on_delete"] == "SET NULL"
        for fk in db.execute("PRAGMA foreign_key_list(ordered_tests)").fetchall()
    )
    if has_eut_id and has_correct_fk:
        return

    # Same rename-the-replacement approach as _migrate_users_table, for the same reason:
    # other tables' FK text (allocations/work_orders/test_reports -> "ordered_tests") must
    # keep resolving correctly once the replacement is renamed into place.
    db.execute("PRAGMA foreign_keys = OFF")
    try:
        db.execute(
            """
            CREATE TABLE ordered_tests_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                eut_id INTEGER,
                test_name TEXT NOT NULL,
                required_capability_id INTEGER,
                FOREIGN KEY (order_id) REFERENCES customer_orders(id) ON DELETE CASCADE,
                FOREIGN KEY (eut_id) REFERENCES euts(id) ON DELETE SET NULL,
                FOREIGN KEY (required_capability_id) REFERENCES capabilities(id)
            )
            """
        )
        if has_eut_id:
            db.execute(
                """
                INSERT INTO ordered_tests_new (id, order_id, eut_id, test_name, required_capability_id)
                SELECT id, order_id, eut_id, test_name, required_capability_id FROM ordered_tests
                """
            )
        else:
            db.execute(
                """
                INSERT INTO ordered_tests_new (id, order_id, test_name, required_capability_id)
                SELECT id, order_id, test_name, required_capability_id FROM ordered_tests
                """
            )
        db.execute("DROP TABLE ordered_tests")
        db.execute("ALTER TABLE ordered_tests_new RENAME TO ordered_tests")
        db.commit()
    finally:
        db.execute("PRAGMA foreign_keys = ON")


def _migrate_resources_table(db: sqlite3.Connection) -> None:
    """Upgrade a resources table created before the optional site column existed."""
    if not _table_exists(db, "resources"):
        return

    columns = {row["name"] for row in db.execute("PRAGMA table_info(resources)").fetchall()}
    if "site" in columns:
        return

    # A plain ADD COLUMN is enough here: site is nullable with no CHECK/FK/default,
    # so SQLite can add it in place without a table rebuild.
    db.execute("ALTER TABLE resources ADD COLUMN site TEXT")
    db.commit()


def _migrate_ordered_tests_sequence(db: sqlite3.Connection) -> None:
    """Upgrade an ordered_tests table created before the optional sequence column existed."""
    if not _table_exists(db, "ordered_tests"):
        return

    columns = {row["name"] for row in db.execute("PRAGMA table_info(ordered_tests)").fetchall()}
    if "sequence" in columns:
        return

    # A plain ADD COLUMN is enough here: sequence is nullable with no CHECK/FK/default,
    # so SQLite can add it in place without a table rebuild.
    db.execute("ALTER TABLE ordered_tests ADD COLUMN sequence INTEGER")

    # Backfill existing rows with a stable 1..N order per (order_id, eut_id) group,
    # based on current id order, so reordering has a real starting point instead of
    # every pre-existing row sharing NULL.
    rows = db.execute("SELECT id, order_id, eut_id FROM ordered_tests ORDER BY order_id, eut_id, id").fetchall()
    counters: dict[tuple, int] = {}
    for row in rows:
        key = (row["order_id"], row["eut_id"])
        counters[key] = counters.get(key, 0) + 1
        db.execute("UPDATE ordered_tests SET sequence = ? WHERE id = ?", (counters[key], row["id"]))
    db.commit()


def _migrate_capabilities_table(db: sqlite3.Connection) -> None:
    """Upgrade a capabilities table created before the optional discipline column existed."""
    if not _table_exists(db, "capabilities"):
        return

    columns = {row["name"] for row in db.execute("PRAGMA table_info(capabilities)").fetchall()}
    if "discipline" in columns:
        return

    # A plain ADD COLUMN is enough here: discipline is nullable with no CHECK/FK/default,
    # so SQLite can add it in place without a table rebuild.
    db.execute("ALTER TABLE capabilities ADD COLUMN discipline TEXT")
    db.commit()


def _migrate_customer_orders_table(db: sqlite3.Connection) -> None:
    """Upgrade a customer_orders table created before the weekly_note/waiting_for_customer columns existed."""
    if not _table_exists(db, "customer_orders"):
        return

    columns = {row["name"] for row in db.execute("PRAGMA table_info(customer_orders)").fetchall()}
    # Both new columns have only constant defaults (NULL / 0) and no FK/CHECK,
    # so a plain ADD COLUMN is enough for either, without a table rebuild.
    if "weekly_note" not in columns:
        db.execute("ALTER TABLE customer_orders ADD COLUMN weekly_note TEXT")
    if "waiting_for_customer" not in columns:
        db.execute("ALTER TABLE customer_orders ADD COLUMN waiting_for_customer INTEGER NOT NULL DEFAULT 0")
    if "customer_id" not in columns:
        db.execute("ALTER TABLE customer_orders ADD COLUMN customer_id INTEGER")
    db.commit()


def _migrate_ordered_tests_planned_dates(db: sqlite3.Connection) -> None:
    """Upgrade an ordered_tests table created before the optional planned date columns existed."""
    if not _table_exists(db, "ordered_tests"):
        return

    columns = {row["name"] for row in db.execute("PRAGMA table_info(ordered_tests)").fetchall()}
    # Both new columns are nullable with no CHECK/FK/default, so a plain ADD COLUMN
    # is enough for either, without a table rebuild.
    if "planned_start_date" not in columns:
        db.execute("ALTER TABLE ordered_tests ADD COLUMN planned_start_date TEXT")
    if "planned_end_date" not in columns:
        db.execute("ALTER TABLE ordered_tests ADD COLUMN planned_end_date TEXT")
    db.commit()


def _migrate_ordered_tests_template_application(db: sqlite3.Connection) -> None:
    """Upgrade an ordered_tests table created before the optional template_application_id
    column existed. No FK is declared on this column (see the schema comment), so a plain
    ADD COLUMN is enough - nothing to lose in a later rebuild."""
    if not _table_exists(db, "ordered_tests"):
        return
    columns = {row["name"] for row in db.execute("PRAGMA table_info(ordered_tests)").fetchall()}
    if "template_application_id" not in columns:
        db.execute("ALTER TABLE ordered_tests ADD COLUMN template_application_id INTEGER")
        db.commit()


def _migrate_template_applications_table(db: sqlite3.Connection) -> None:
    """Upgrade a template_applications table created before applied_template_version/modified
    existed. Both are nullable-or-defaulted with no CHECK/FK, so a plain ADD COLUMN is enough."""
    if not _table_exists(db, "template_applications"):
        return
    columns = {row["name"] for row in db.execute("PRAGMA table_info(template_applications)").fetchall()}
    if "applied_template_version" not in columns:
        db.execute("ALTER TABLE template_applications ADD COLUMN applied_template_version INTEGER")
    if "modified" not in columns:
        db.execute("ALTER TABLE template_applications ADD COLUMN modified INTEGER NOT NULL DEFAULT 0")
    db.commit()


def _migrate_activity_templates_version(db: sqlite3.Connection) -> None:
    """Upgrade an activity_templates table created before the optional version column
    existed. An integer counter (bumped on every item add/edit/delete/reorder) rather than
    a last-modified timestamp, so a template_applications batch's staleness check is exact
    even if both changes land within the same minute-resolution timestamp used elsewhere
    in this app."""
    if not _table_exists(db, "activity_templates"):
        return
    columns = {row["name"] for row in db.execute("PRAGMA table_info(activity_templates)").fetchall()}
    if "version" not in columns:
        db.execute("ALTER TABLE activity_templates ADD COLUMN version INTEGER NOT NULL DEFAULT 1")
        db.commit()


def init_db() -> None:
    db = get_db()
    _migrate_users_table(db)
    db.executescript(SCHEMA_SQL)
    _migrate_ordered_tests_table(db)
    _migrate_resources_table(db)
    _migrate_ordered_tests_sequence(db)
    _migrate_capabilities_table(db)
    _migrate_customer_orders_table(db)
    _migrate_ordered_tests_planned_dates(db)
    _migrate_ordered_tests_template_application(db)
    _migrate_template_applications_table(db)
    _migrate_activity_templates_version(db)
    db.commit()


def init_demo_seed() -> None:
    db = get_db()

    db.execute("INSERT OR IGNORE INTO users (username, role) VALUES ('admin.demo', 'admin')")
    db.execute("INSERT OR IGNORE INTO users (username, role) VALUES ('planner.demo', 'planner')")
    db.execute("INSERT OR IGNORE INTO users (username, role) VALUES ('technician.demo', 'technician')")
    db.execute("INSERT OR IGNORE INTO users (username, role) VALUES ('technician2.demo', 'technician')")

    db.execute("INSERT OR IGNORE INTO capabilities (name, description, discipline) VALUES (?, ?, ?)", ("Multimeter Calibration", "Ability to calibrate multimeters", "Calibration"))
    db.execute("INSERT OR IGNORE INTO capabilities (name, description, discipline) VALUES (?, ?, ?)", ("Vibration Test", "Ability to run vibration tests", "Environmental"))
    db.execute("INSERT OR IGNORE INTO capabilities (name, description, discipline) VALUES (?, ?, ?)", ("Humidity Test", "Ability to run humidity tests", "Environmental"))
    db.execute("INSERT OR IGNORE INTO capabilities (name, description, discipline) VALUES (?, ?, ?)", ("CE", "Conducted Emissions", "EMC"))
    db.execute("INSERT OR IGNORE INTO capabilities (name, description, discipline) VALUES (?, ?, ?)", ("CI", "Conducted Immunity", "EMC"))
    db.execute("INSERT OR IGNORE INTO capabilities (name, description, discipline) VALUES (?, ?, ?)", ("RE", "Radiated Emissions", "EMC"))
    db.execute("INSERT OR IGNORE INTO capabilities (name, description, discipline) VALUES (?, ?, ?)", ("RI", "Radiated Immunity", "EMC"))

    # Backfill: assign a discipline to capabilities that already existed on a
    # dev database from before Phase 11 (their INSERT OR IGNORE above was a no-op).
    _DISCIPLINE_BY_CAPABILITY = {
        "Multimeter Calibration": "Calibration",
        "Vibration Test": "Environmental",
        "Humidity Test": "Environmental",
        "CE": "EMC",
        "CI": "EMC",
        "RE": "EMC",
        "RI": "EMC",
    }
    for capability_name, discipline in _DISCIPLINE_BY_CAPABILITY.items():
        db.execute(
            "UPDATE capabilities SET discipline = ? WHERE name = ? AND discipline IS NULL",
            (discipline, capability_name),
        )

    db.execute("INSERT OR IGNORE INTO resources (code, name, resource_type, status) VALUES (?, ?, ?, ?)", ("EQ-001", "Multimeter Calibrator A", "equipment", "available"))
    db.execute("INSERT OR IGNORE INTO resources (code, name, resource_type, status) VALUES (?, ?, ?, ?)", ("EQ-020", "Vibration Tester V-9", "equipment", "available"))
    db.execute("INSERT OR IGNORE INTO resources (code, name, resource_type, status) VALUES (?, ?, ?, ?)", ("FAC-004", "Humidity Chamber Room B", "facility", "available"))
    db.execute("INSERT OR IGNORE INTO resources (code, name, resource_type, status) VALUES (?, ?, ?, ?)", ("TECH-102", "Maya Jensen", "technician", "available"))
    db.execute("INSERT OR IGNORE INTO resources (code, name, resource_type, status) VALUES (?, ?, ?, ?)", ("TECH-103", "Sam Ibrahim", "technician", "available"))
    db.execute("INSERT OR IGNORE INTO resources (code, name, resource_type, status, site) VALUES (?, ?, ?, ?, ?)", ("FAC-010", "CON Chamber - CE Setup", "facility", "available", "TLC"))
    db.execute("INSERT OR IGNORE INTO resources (code, name, resource_type, status, site) VALUES (?, ?, ?, ?, ?)", ("FAC-011", "CON Chamber - CI Setup", "facility", "available", "TLC"))
    db.execute("INSERT OR IGNORE INTO resources (code, name, resource_type, status, site) VALUES (?, ?, ?, ?, ?)", ("FAC-012", "SAC Chamber - RE Setup", "facility", "available", "TLS"))
    db.execute("INSERT OR IGNORE INTO resources (code, name, resource_type, status, site) VALUES (?, ?, ?, ?, ?)", ("FAC-013", "SAC Chamber - RI Setup", "facility", "available", "TLS"))

    db.execute("INSERT OR IGNORE INTO customer_orders (order_code, customer_name, product_name) VALUES (?, ?, ?)", ("ORD-2026-001", "Acme Instruments", "Multimeter"))
    db.execute("INSERT OR IGNORE INTO customer_orders (order_code, customer_name, product_name) VALUES (?, ?, ?)", ("ORD-2026-002", "Nova Mobile", "Mobile Phone Prototype"))
    db.execute("INSERT OR IGNORE INTO customer_orders (order_code, customer_name, product_name) VALUES (?, ?, ?)", ("ORD-2026-003", "Contoso Labs", "IoT Gateway"))

    db.execute("""
        UPDATE customer_orders SET weekly_note = ?
        WHERE order_code = 'ORD-2026-002' AND weekly_note IS NULL
    """, ("Vibration test passed on Prototype Unit A; humidity test in progress. Unit B still queued.",))
    db.execute("""
        UPDATE customer_orders SET waiting_for_customer = 1, weekly_note = ?
        WHERE order_code = 'ORD-2026-003' AND weekly_note IS NULL
    """, ("Blocked: waiting on customer to confirm which CE/CI limit class applies before we sign off the report.",))

    _seed_milestone(db, "ORD-2026-002", "Draft report to customer", "2026-08-10")
    _seed_milestone(db, "ORD-2026-003", "Final report due", "2026-08-05")

    _seed_staff_absence(db, "TECH-102", "2026-08-04", "2026-08-06", "Summer vacation")
    _seed_customer_visit(db, "ORD-2026-003", "2026-08-03", "2026-08-03", "Customer on-site to observe CE/CI testing.")

    _seed_eut(db, "ORD-2026-002", "Prototype Unit A", "SN-88213-004")
    _seed_eut(db, "ORD-2026-002", "Prototype Unit B", "SN-88213-005")

    db.execute("""
        INSERT INTO ordered_tests (order_id, test_name, required_capability_id)
        SELECT o.id, ?, c.id
        FROM customer_orders o
        JOIN capabilities c ON c.name = ?
        WHERE o.order_code = ?
          AND NOT EXISTS (
              SELECT 1 FROM ordered_tests ot
              WHERE ot.order_id = o.id AND ot.test_name = ? AND ot.required_capability_id = c.id
          )
    """, ("Multimeter Calibration", "Multimeter Calibration", "ORD-2026-001", "Multimeter Calibration"))

    db.execute("""
        INSERT INTO ordered_tests (order_id, eut_id, test_name, required_capability_id)
        SELECT o.id, e.id, ?, c.id
        FROM customer_orders o
        JOIN capabilities c ON c.name = ?
        LEFT JOIN euts e ON e.order_id = o.id AND e.name = 'Prototype Unit A'
        WHERE o.order_code = ?
          AND NOT EXISTS (
              SELECT 1 FROM ordered_tests ot
              WHERE ot.order_id = o.id AND ot.test_name = ? AND ot.required_capability_id = c.id
          )
    """, ("Vibration Test", "Vibration Test", "ORD-2026-002", "Vibration Test"))

    db.execute("""
        INSERT INTO ordered_tests (order_id, eut_id, test_name, required_capability_id)
        SELECT o.id, e.id, ?, c.id
        FROM customer_orders o
        JOIN capabilities c ON c.name = ?
        LEFT JOIN euts e ON e.order_id = o.id AND e.name = 'Prototype Unit A'
        WHERE o.order_code = ?
          AND NOT EXISTS (
              SELECT 1 FROM ordered_tests ot
              WHERE ot.order_id = o.id AND ot.test_name = ? AND ot.required_capability_id = c.id
          )
    """, ("Humidity Test", "Humidity Test", "ORD-2026-002", "Humidity Test"))

    # Backfill: on a dev database that already had ORD-2026-002's Vibration/Humidity Test
    # rows from before Phase 8 (EUTs didn't exist yet, so the two INSERTs above were
    # skipped by their own NOT EXISTS guard), link those pre-existing rows to Prototype
    # Unit A now that it exists, instead of leaving them EUT-less.
    db.execute("""
        UPDATE ordered_tests
        SET eut_id = (
            SELECT e.id FROM euts e
            JOIN customer_orders o ON o.id = e.order_id
            WHERE o.order_code = 'ORD-2026-002' AND e.name = 'Prototype Unit A'
        )
        WHERE eut_id IS NULL
          AND test_name IN ('Vibration Test', 'Humidity Test')
          AND order_id = (SELECT id FROM customer_orders WHERE order_code = 'ORD-2026-002')
    """)

    db.execute("""
        INSERT INTO ordered_tests (order_id, eut_id, test_name, required_capability_id)
        SELECT o.id, e.id, ?, c.id
        FROM customer_orders o
        JOIN capabilities c ON c.name = ?
        LEFT JOIN euts e ON e.order_id = o.id AND e.name = 'Prototype Unit B'
        WHERE o.order_code = ?
          AND NOT EXISTS (
              SELECT 1 FROM ordered_tests ot
              WHERE ot.order_id = o.id AND ot.eut_id = e.id AND ot.test_name = ? AND ot.required_capability_id = c.id
          )
    """, ("Vibration Test", "Vibration Test", "ORD-2026-002", "Vibration Test"))

    db.execute("""
        INSERT INTO ordered_tests (order_id, test_name, required_capability_id)
        SELECT o.id, ?, c.id
        FROM customer_orders o
        JOIN capabilities c ON c.name = ?
        WHERE o.order_code = ?
          AND NOT EXISTS (
              SELECT 1 FROM ordered_tests ot
              WHERE ot.order_id = o.id AND ot.test_name = ? AND ot.required_capability_id = c.id
          )
    """, ("CE", "CE", "ORD-2026-003", "CE"))

    db.execute("""
        INSERT INTO ordered_tests (order_id, test_name, required_capability_id)
        SELECT o.id, ?, c.id
        FROM customer_orders o
        JOIN capabilities c ON c.name = ?
        WHERE o.order_code = ?
          AND NOT EXISTS (
              SELECT 1 FROM ordered_tests ot
              WHERE ot.order_id = o.id AND ot.test_name = ? AND ot.required_capability_id = c.id
          )
    """, ("CI", "CI", "ORD-2026-003", "CI"))

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
        JOIN capabilities c ON c.name = ?
        WHERE r.code = ?
    """, ("CE", "FAC-010"))

    db.execute("""
        INSERT OR IGNORE INTO resource_capabilities (resource_id, capability_id)
        SELECT r.id, c.id
        FROM resources r
        JOIN capabilities c ON c.name = ?
        WHERE r.code = ?
    """, ("CI", "FAC-011"))

    db.execute("""
        INSERT OR IGNORE INTO resource_capabilities (resource_id, capability_id)
        SELECT r.id, c.id
        FROM resources r
        JOIN capabilities c ON c.name = ?
        WHERE r.code = ?
    """, ("RE", "FAC-012"))

    db.execute("""
        INSERT OR IGNORE INTO resource_capabilities (resource_id, capability_id)
        SELECT r.id, c.id
        FROM resources r
        JOIN capabilities c ON c.name = ?
        WHERE r.code = ?
    """, ("RI", "FAC-013"))

    db.execute("""
        INSERT OR IGNORE INTO resource_capabilities (resource_id, capability_id)
        SELECT r.id, c.id
        FROM resources r
        JOIN capabilities c ON c.name IN ('Vibration Test', 'Humidity Test', 'CE', 'CI')
        WHERE r.code = 'TECH-102'
    """)

    db.execute("""
        INSERT OR IGNORE INTO resource_capabilities (resource_id, capability_id)
        SELECT r.id, c.id
        FROM resources r
        JOIN capabilities c ON c.name IN ('Multimeter Calibration', 'Vibration Test', 'Humidity Test', 'CE', 'CI', 'RE', 'RI')
        WHERE r.code = 'TECH-103'
    """)

    _seed_exclusion_group(db, "CON Chamber (TLC)", "Shared conducted-emissions/immunity test chamber; only one setup can run at a time.", ["FAC-010", "FAC-011"])
    _seed_exclusion_group(db, "SAC Chamber (TLS)", "Shared radiated-emissions/immunity semi-anechoic chamber; only one setup can run at a time.", ["FAC-012", "FAC-013"])

    _seed_allocation(db, "ORD-2026-003", "CE", "FAC-010")
    _seed_allocation(db, "ORD-2026-003", "CE", "TECH-103")
    _seed_allocation(db, "ORD-2026-003", "CI", "FAC-011")
    _seed_allocation(db, "ORD-2026-003", "CI", "TECH-103")

    # Deliberately overlapping work orders in the same exclusion group (CON Chamber),
    # seeded directly rather than through the app's own conflict-checked routes, to
    # demonstrate the inline conflict flag on the planner's Schedule tab: a schedule
    # can still drift into conflict after the fact (e.g. a test overruns), not just
    # at the moment a technician schedules it.
    db.execute("""
        INSERT INTO work_orders
            (work_order_code, ordered_test_id, technician_user_id, status,
             scheduled_date, started_at, completed_at, notes)
        SELECT
            'WO-0005', ot.id, u.id, 'in_progress',
            '2026-08-03', '2026-08-03 09:00', NULL, 'CE scan running long.'
        FROM ordered_tests ot
        JOIN customer_orders o ON o.id = ot.order_id
        JOIN users u ON u.username = 'technician2.demo'
        WHERE o.order_code = 'ORD-2026-003' AND ot.test_name = 'CE'
          AND NOT EXISTS (SELECT 1 FROM work_orders wo WHERE wo.ordered_test_id = ot.id)
    """)

    db.execute("""
        INSERT INTO work_orders
            (work_order_code, ordered_test_id, technician_user_id, status,
             scheduled_date, started_at, completed_at, notes)
        SELECT
            'WO-0006', ot.id, u.id, 'in_progress',
            '2026-08-03', '2026-08-03 09:30', NULL, 'CI setup started before checking the CON chamber was free.'
        FROM ordered_tests ot
        JOIN customer_orders o ON o.id = ot.order_id
        JOIN users u ON u.username = 'technician2.demo'
        WHERE o.order_code = 'ORD-2026-003' AND ot.test_name = 'CI'
          AND NOT EXISTS (SELECT 1 FROM work_orders wo WHERE wo.ordered_test_id = ot.id)
    """)

    # Phase 15 demo (FR-CON-3, cross-site equipment warning): a shared spectrum analyzer
    # used at TLC in the morning and TLS in the afternoon of the same day, on ORD-2026-003
    # alongside its existing CE/CI hard-conflict demo, so the Schedule tab shows both a
    # blocking conflict and a non-blocking cross-site warning as distinct signals.
    db.execute(
        "INSERT OR IGNORE INTO resources (code, name, resource_type, status) VALUES (?, ?, ?, ?)",
        ("EQ-030", "Shared Spectrum Analyzer", "equipment", "available"),
    )
    db.execute("""
        INSERT INTO ordered_tests (order_id, test_name, required_capability_id)
        SELECT o.id, ?, c.id
        FROM customer_orders o
        JOIN capabilities c ON c.name = ?
        WHERE o.order_code = ?
          AND NOT EXISTS (
              SELECT 1 FROM ordered_tests ot
              WHERE ot.order_id = o.id AND ot.test_name = ? AND ot.required_capability_id = c.id
          )
    """, ("RE", "RE", "ORD-2026-003", "RE"))
    db.execute("""
        INSERT INTO ordered_tests (order_id, test_name)
        SELECT o.id, ?
        FROM customer_orders o
        WHERE o.order_code = ?
          AND NOT EXISTS (SELECT 1 FROM ordered_tests ot WHERE ot.order_id = o.id AND ot.test_name = ?)
    """, ("Spectrum Sweep", "ORD-2026-003", "Spectrum Sweep"))

    _seed_allocation(db, "ORD-2026-003", "RE", "FAC-012")
    _seed_allocation(db, "ORD-2026-003", "RE", "EQ-030")
    _seed_allocation(db, "ORD-2026-003", "Spectrum Sweep", "FAC-010")
    _seed_allocation(db, "ORD-2026-003", "Spectrum Sweep", "EQ-030")

    db.execute("""
        INSERT INTO work_orders
            (work_order_code, ordered_test_id, technician_user_id, status,
             scheduled_date, started_at, completed_at, result)
        SELECT
            'WO-0009', ot.id, u.id, 'completed',
            '2026-08-03', '2026-08-03 09:00', '2026-08-03 10:00', 'pass'
        FROM ordered_tests ot
        JOIN customer_orders o ON o.id = ot.order_id
        JOIN users u ON u.username = 'technician2.demo'
        WHERE o.order_code = 'ORD-2026-003' AND ot.test_name = 'Spectrum Sweep'
          AND NOT EXISTS (SELECT 1 FROM work_orders wo WHERE wo.ordered_test_id = ot.id)
    """)
    db.execute("""
        INSERT INTO work_orders
            (work_order_code, ordered_test_id, technician_user_id, status,
             scheduled_date, started_at, completed_at, result)
        SELECT
            'WO-0010', ot.id, u.id, 'completed',
            '2026-08-03', '2026-08-03 13:00', '2026-08-03 14:00', 'pass'
        FROM ordered_tests ot
        JOIN customer_orders o ON o.id = ot.order_id
        JOIN users u ON u.username = 'technician2.demo'
        WHERE o.order_code = 'ORD-2026-003' AND ot.test_name = 'RE'
          AND NOT EXISTS (SELECT 1 FROM work_orders wo WHERE wo.ordered_test_id = ot.id)
    """)

    db.execute("""
        UPDATE users SET linked_resource_id = (SELECT id FROM resources WHERE code = 'TECH-102')
        WHERE username = 'technician.demo' AND linked_resource_id IS NULL
    """)

    db.execute("""
        UPDATE users SET linked_resource_id = (SELECT id FROM resources WHERE code = 'TECH-103')
        WHERE username = 'technician2.demo' AND linked_resource_id IS NULL
    """)

    _seed_activity_template(
        db,
        "Standard EMC Test Sequence",
        "Kick-off through EUT return, per the customer's standard project workflow. Order can be freely changed per project after applying.",
        [
            ("Kick-off", None),
            ("Testplan", None),
            ("EUT delivery", None),
            ("RE", "RE"),
            ("RI", "RI"),
            ("CI", "CI"),
            ("CE", "CE"),
            ("Burst", None),
            ("Surge", None),
            ("Voltage Dips", None),
            ("Power Frequency Magnetic Field", None),
            ("Other tests", None),
            ("ESD", None),
            ("Report writing", None),
            ("Report review", None),
            ("Report to customer", None),
            ("EUT return", None),
        ],
    )

    db.execute("INSERT OR IGNORE INTO customer_orders (order_code, customer_name, product_name) VALUES (?, ?, ?)", ("ORD-2026-004", "Helios Devices", "Smart Thermostat"))
    _seed_milestone(db, "ORD-2026-004", "EUT delivery expected", "2026-08-01")
    _seed_eut(db, "ORD-2026-004", "Rev A", "SN-71100-001")
    _seed_eut(db, "ORD-2026-004", "Rev B", "SN-71100-002")

    # Rev A: bulk-created directly from the template items, mirroring what the planner's
    # "Apply Template" action produces, so the demo shows an already-applied EUT. Rev B is
    # left with no activities on purpose, so the same action can be demonstrated live.
    db.execute("""
        INSERT INTO ordered_tests (order_id, eut_id, test_name, required_capability_id, sequence)
        SELECT o.id, e.id, ati.activity_name, ati.required_capability_id, ati.step_number
        FROM activity_templates at
        JOIN activity_template_items ati ON ati.template_id = at.id
        JOIN customer_orders o ON o.order_code = 'ORD-2026-004'
        JOIN euts e ON e.order_id = o.id AND e.name = 'Rev A'
        WHERE at.name = 'Standard EMC Test Sequence'
          AND NOT EXISTS (SELECT 1 FROM ordered_tests ot2 WHERE ot2.order_id = o.id AND ot2.eut_id = e.id)
    """)

    # Phase 14 demo: "Report writing" depends on "CE" being completed first (the
    # customer's own literal rule), and CE carries a planned window already in the
    # past (relative to the seeded "today") with no work order yet, so the demo shows
    # both a blocked activity and the dashboard's overdue flag together.
    db.execute("""
        UPDATE ordered_tests
        SET planned_start_date = '2026-07-20', planned_end_date = '2026-07-24'
        WHERE planned_start_date IS NULL
          AND id = (
              SELECT ot.id FROM ordered_tests ot
              JOIN customer_orders o ON o.id = ot.order_id
              JOIN euts e ON e.id = ot.eut_id
              WHERE o.order_code = 'ORD-2026-004' AND e.name = 'Rev A' AND ot.test_name = 'CE'
          )
    """)
    db.execute("""
        INSERT INTO activity_dependencies (ordered_test_id, depends_on_ordered_test_id)
        SELECT report.id, ce.id
        FROM ordered_tests report
        JOIN ordered_tests ce ON ce.order_id = report.order_id AND ce.eut_id = report.eut_id
        JOIN customer_orders o ON o.id = report.order_id
        JOIN euts e ON e.id = report.eut_id
        WHERE o.order_code = 'ORD-2026-004' AND e.name = 'Rev A'
          AND report.test_name = 'Report writing' AND ce.test_name = 'CE'
          AND NOT EXISTS (
              SELECT 1 FROM activity_dependencies ad
              WHERE ad.ordered_test_id = report.id AND ad.depends_on_ordered_test_id = ce.id
          )
    """)

    _seed_procedure(
        db,
        capability_name="Multimeter Calibration",
        title="Multimeter Calibration Procedure (Cal-DMM-01)",
        summary="Verify and calibrate a digital multimeter's DC/AC voltage, resistance, and current ranges against a certified reference standard.",
        steps="\n".join([
            "1. Allow the multimeter and reference calibrator to stabilize at ambient temperature (20-25 C) for at least 30 minutes.",
            "2. Visually inspect the unit for physical damage, loose terminals, or worn test leads.",
            "3. Connect the multimeter to the calibrator via low-thermal test leads.",
            "4. Zero/null the multimeter on each range before taking readings.",
            "5. Apply reference DC voltage at 10%, 50%, and 90% of each range; record readings.",
            "6. Apply reference AC voltage at 1 kHz on each voltage range; record readings.",
            "7. Apply reference resistance values on each ohms range; record readings.",
            "8. Apply reference DC/AC current on each current range; record readings.",
            "9. Compare all recorded readings against manufacturer tolerance specifications.",
            "10. Adjust internal calibration trimmers/firmware offsets if any reading exceeds tolerance, then repeat the affected range.",
            "11. Affix a calibration sticker with date and due date, and archive the certificate.",
        ]),
        equipment_needed="Certified multimeter calibrator (EQ-001), low-thermal test lead set",
        facility_needed="ESD-safe calibration bench, 20-25 C controlled environment",
        safety_notes="Discharge any stored energy in the unit under test before connecting leads. Do not exceed the calibrator's rated output on any range.",
    )
    _seed_procedure_checks(db, "Multimeter Calibration Procedure (Cal-DMM-01)", [
        ("DC Voltage - 2V range @ 1.000 V applied", "1.000 V +/- 0.002 V"),
        ("DC Voltage - 20V range @ 10.00 V applied", "10.00 V +/- 0.02 V"),
        ("AC Voltage - 2V range @ 1.000 V, 1 kHz applied", "1.000 V +/- 0.005 V"),
        ("Resistance - 200 Ohm range @ 100.0 Ohm applied", "100.0 Ohm +/- 0.3 Ohm"),
        ("DC Current - 200 mA range @ 100.0 mA applied", "100.0 mA +/- 0.3 mA"),
        ("Visual/mechanical inspection", "No physical damage, leads and terminals intact"),
    ])

    _seed_procedure(
        db,
        capability_name="Vibration Test",
        title="Random Vibration Test Procedure (Test Method 514.7)",
        summary="Subject the product to a random vibration profile to verify it survives transportation and field vibration without mechanical or functional failure.",
        steps="\n".join([
            "1. Inspect the unit under test (UUT) for pre-existing damage and record baseline photos.",
            "2. Perform a functional check of the UUT and record baseline performance.",
            "3. Mount the UUT to the vibration table fixture using the specified torque pattern.",
            "4. Attach control and monitoring accelerometers at the defined reference points.",
            "5. Program the shaker controller with the specified random vibration spectrum (PSD profile) and duration.",
            "6. Run a low-level resonance survey sine sweep to identify resonant frequencies.",
            "7. Execute the full-level random vibration test in each of the three orthogonal axes (X, Y, Z).",
            "8. Monitor the UUT continuously during test for intermittent failures using the functional monitoring harness.",
            "9. Perform a post-test visual inspection and functional check.",
            "10. Compare pre- and post-test functional results; document any deviation.",
        ]),
        equipment_needed="Electrodynamic shaker system, Vibration Tester V-9 (EQ-020), control/monitoring accelerometers, test fixture",
        facility_needed="Vibration test lab with adequate power and ventilation",
        safety_notes="Verify fixture torque and accelerometer cabling before energizing the shaker. Keep clear of the moving fixture during operation; E-stop training required.",
    )
    _seed_procedure_checks(db, "Random Vibration Test Procedure (Test Method 514.7)", [
        ("Pre-test visual inspection", "No visible damage"),
        ("Pre-test functional check", "Unit powers on and passes self-test"),
        ("Resonance survey sine sweep", "No resonance shift greater than 5% vs. baseline"),
        ("Random vibration - X axis", "No functional dropout during run"),
        ("Random vibration - Y axis", "No functional dropout during run"),
        ("Random vibration - Z axis", "No functional dropout during run"),
        ("Post-test visual inspection", "No new visible damage"),
        ("Post-test functional check", "Matches pre-test baseline, unit passes self-test"),
    ])

    _seed_procedure(
        db,
        capability_name="Humidity Test",
        title="Damp Heat / Humidity Test Procedure (IEC 60068-2-78)",
        summary="Expose the product to elevated temperature and humidity to verify resistance to moisture ingress, corrosion, and performance degradation.",
        steps="\n".join([
            "1. Perform and record a baseline functional check of the unit under test at ambient conditions.",
            "2. Place the unit in the humidity chamber without packaging, ensuring adequate airflow around all surfaces.",
            "3. Set chamber conditions to 40 C +/-2 C and 93% RH +/-3%, per the test specification.",
            "4. Ramp the chamber to target conditions and begin the soak duration (standard: 96 hours).",
            "5. Log chamber temperature and humidity at regular intervals throughout the test.",
            "6. Perform interim functional checks at 24-hour intervals if the unit can be safely accessed.",
            "7. At completion, remove the unit and allow it to stabilize at ambient conditions for 1-2 hours before handling.",
            "8. Perform a final visual inspection for corrosion, condensation damage, or material degradation.",
            "9. Perform a final functional check and compare against baseline results.",
        ]),
        equipment_needed="Data logger, functional test jig",
        facility_needed="Humidity Chamber Room B (FAC-004)",
        safety_notes="Allow condensation to evaporate before reconnecting power. Use insulated gloves when handling chamber racks during unloading.",
    )
    _seed_procedure_checks(db, "Damp Heat / Humidity Test Procedure (IEC 60068-2-78)", [
        ("Pre-test functional check", "Unit powers on and passes self-test"),
        ("Chamber conditions reached", "40 +/-2 C / 93 +/-3% RH within 1 hour of ramp"),
        ("96-hour soak completed", "Continuous exposure, no interruption greater than 15 min"),
        ("Post-test visual inspection", "No corrosion or condensation damage"),
        ("Post-test functional check", "Matches pre-test baseline, unit passes self-test"),
    ])

    _seed_allocation(db, "ORD-2026-002", "Vibration Test", "EQ-020", eut_name="Prototype Unit A")
    _seed_allocation(db, "ORD-2026-002", "Vibration Test", "TECH-102", eut_name="Prototype Unit A")
    _seed_allocation(db, "ORD-2026-002", "Humidity Test", "FAC-004", eut_name="Prototype Unit A")
    _seed_allocation(db, "ORD-2026-002", "Humidity Test", "TECH-102", eut_name="Prototype Unit A")

    db.execute("""
        INSERT INTO work_orders
            (work_order_code, ordered_test_id, technician_user_id, procedure_id, status,
             scheduled_date, started_at, completed_at, result, notes)
        SELECT
            'WO-0001', ot.id, u.id, p.id, 'completed',
            '2026-07-20', '2026-07-20 09:00', '2026-07-20 11:30', 'pass',
            'Unit passed the random vibration profile per Test Method 514.7. No anomalies observed on functional monitoring; no visible damage on post-test inspection.'
        FROM ordered_tests ot
        JOIN customer_orders o ON o.id = ot.order_id
        JOIN euts e ON e.id = ot.eut_id AND e.name = 'Prototype Unit A'
        JOIN users u ON u.username = 'technician.demo'
        JOIN test_procedures p ON p.title = 'Random Vibration Test Procedure (Test Method 514.7)'
        WHERE o.order_code = 'ORD-2026-002' AND ot.test_name = 'Vibration Test'
          AND NOT EXISTS (SELECT 1 FROM work_orders wo WHERE wo.ordered_test_id = ot.id)
    """)

    db.execute("""
        INSERT INTO test_reports
            (report_code, work_order_id, ordered_test_id, procedure_id, uut_name, uut_serial_number,
             technician_user_id, status, technician_signed_at, overall_result, notes,
             reviewer_user_id, reviewer_decision, reviewer_comment, reviewer_signed_at, created_at)
        SELECT
            'RPT-0001', wo.id, wo.ordered_test_id, wo.procedure_id, o.product_name, 'SN-88213-004',
            wo.technician_user_id, 'approved', '2026-07-20 11:25', 'pass',
            'Unit passed the random vibration profile per Test Method 514.7. No anomalies observed.',
            u2.id, 'approved', 'Reviewed traces and photos, agree with pass result.', '2026-07-20 15:40', '2026-07-20 09:00'
        FROM work_orders wo
        JOIN ordered_tests ot ON ot.id = wo.ordered_test_id
        JOIN customer_orders o ON o.id = ot.order_id
        JOIN users u2 ON u2.username = 'technician2.demo'
        WHERE wo.work_order_code = 'WO-0001'
          AND NOT EXISTS (SELECT 1 FROM test_reports tr WHERE tr.work_order_id = wo.id)
    """)

    _seed_history_entry(db, "ORD-2026-002", "Vibration Test", "Prototype Unit A", "2026-07-19 14:00", "planner.demo", "resource_assigned", "Resource EQ-020 (Vibration Tester V-9) assigned.")
    _seed_history_entry(db, "ORD-2026-002", "Vibration Test", "Prototype Unit A", "2026-07-19 14:01", "planner.demo", "resource_assigned", "Resource TECH-102 (Maya Jensen) assigned.")
    _seed_history_entry(db, "ORD-2026-002", "Vibration Test", "Prototype Unit A", "2026-07-20 09:00", "technician.demo", "work_order_created", "Work order WO-0001 created.")
    _seed_history_entry(db, "ORD-2026-002", "Vibration Test", "Prototype Unit A", "2026-07-20 09:00", "technician.demo", "work_order_started", "Work order WO-0001 started.")
    _seed_history_entry(db, "ORD-2026-002", "Vibration Test", "Prototype Unit A", "2026-07-20 11:30", "technician.demo", "work_order_completed", "Work order WO-0001 completed with result: pass.", reason="No anomalies observed on functional monitoring; no visible damage on post-test inspection.")

    db.execute("""
        INSERT INTO report_steps (report_id, step_number, description, expected_value, actual_value, result)
        SELECT tr.id, pc.step_number, pc.description, pc.expected_value, pc.expected_value, 'pass'
        FROM test_reports tr
        JOIN procedure_checks pc ON pc.procedure_id = tr.procedure_id
        WHERE tr.report_code = 'RPT-0001'
          AND NOT EXISTS (SELECT 1 FROM report_steps rs WHERE rs.report_id = tr.id)
    """)

    db.commit()


def _seed_activity_template(
    db: sqlite3.Connection, name: str, notes: str, items: list[tuple[str, str | None]]
) -> None:
    db.execute("INSERT OR IGNORE INTO activity_templates (name, notes) VALUES (?, ?)", (name, notes))
    template_id = db.execute("SELECT id FROM activity_templates WHERE name = ?", (name,)).fetchone()["id"]
    if db.execute("SELECT 1 FROM activity_template_items WHERE template_id = ?", (template_id,)).fetchone():
        return
    for step_number, (activity_name, capability_name) in enumerate(items, start=1):
        capability_id = None
        if capability_name:
            row = db.execute("SELECT id FROM capabilities WHERE name = ?", (capability_name,)).fetchone()
            capability_id = row["id"] if row else None
        db.execute(
            """
            INSERT INTO activity_template_items (template_id, step_number, activity_name, required_capability_id)
            VALUES (?, ?, ?, ?)
            """,
            (template_id, step_number, activity_name, capability_id),
        )


def _seed_exclusion_group(db: sqlite3.Connection, name: str, notes: str, resource_codes: list[str]) -> None:
    db.execute("INSERT OR IGNORE INTO exclusion_groups (name, notes) VALUES (?, ?)", (name, notes))
    group_id = db.execute("SELECT id FROM exclusion_groups WHERE name = ?", (name,)).fetchone()["id"]
    for code in resource_codes:
        db.execute(
            """
            INSERT OR IGNORE INTO exclusion_group_resources (group_id, resource_id)
            SELECT ?, r.id FROM resources r WHERE r.code = ?
            """,
            (group_id, code),
        )


def _seed_history_entry(
    db: sqlite3.Connection,
    order_code: str,
    test_name: str,
    eut_name: str,
    changed_at: str,
    username: str,
    action: str,
    detail: str,
    reason: str | None = None,
) -> None:
    db.execute(
        """
        INSERT INTO activity_history (ordered_test_id, changed_at, user_id, username, action, detail, reason)
        SELECT ot.id, ?, u.id, u.username, ?, ?, ?
        FROM ordered_tests ot
        JOIN customer_orders o ON o.id = ot.order_id
        JOIN euts e ON e.id = ot.eut_id AND e.name = ?
        JOIN users u ON u.username = ?
        WHERE o.order_code = ? AND ot.test_name = ?
          AND NOT EXISTS (
              SELECT 1 FROM activity_history h WHERE h.ordered_test_id = ot.id AND h.action = ? AND h.changed_at = ?
          )
        """,
        (changed_at, action, detail, reason, eut_name, username, order_code, test_name, action, changed_at),
    )


def _seed_milestone(db: sqlite3.Connection, order_code: str, title: str, target_date: str) -> None:
    db.execute(
        """
        INSERT INTO milestones (order_id, title, target_date)
        SELECT o.id, ?, ?
        FROM customer_orders o
        WHERE o.order_code = ?
          AND NOT EXISTS (SELECT 1 FROM milestones m WHERE m.order_id = o.id AND m.title = ?)
        """,
        (title, target_date, order_code, title),
    )


def _seed_staff_absence(
    db: sqlite3.Connection, resource_code: str, start_date: str, end_date: str, reason: str
) -> None:
    db.execute(
        """
        INSERT INTO staff_absences (resource_id, start_date, end_date, reason)
        SELECT r.id, ?, ?, ?
        FROM resources r
        WHERE r.code = ?
          AND NOT EXISTS (
              SELECT 1 FROM staff_absences a
              WHERE a.resource_id = r.id AND a.start_date = ? AND a.end_date = ?
          )
        """,
        (start_date, end_date, reason, resource_code, start_date, end_date),
    )


def _seed_customer_visit(
    db: sqlite3.Connection, order_code: str, start_date: str, end_date: str, notes: str
) -> None:
    db.execute(
        """
        INSERT INTO customer_visits (order_id, start_date, end_date, notes)
        SELECT o.id, ?, ?, ?
        FROM customer_orders o
        WHERE o.order_code = ?
          AND NOT EXISTS (
              SELECT 1 FROM customer_visits v
              WHERE v.order_id = o.id AND v.start_date = ? AND v.end_date = ?
          )
        """,
        (start_date, end_date, notes, order_code, start_date, end_date),
    )


def _seed_eut(db: sqlite3.Connection, order_code: str, name: str, serial_number: str) -> None:
    db.execute(
        """
        INSERT INTO euts (order_id, name, serial_number)
        SELECT o.id, ?, ?
        FROM customer_orders o
        WHERE o.order_code = ?
          AND NOT EXISTS (SELECT 1 FROM euts e WHERE e.order_id = o.id AND e.name = ?)
        """,
        (name, serial_number, order_code, name),
    )


def _seed_procedure(
    db: sqlite3.Connection,
    capability_name: str,
    title: str,
    summary: str,
    steps: str,
    equipment_needed: str,
    facility_needed: str,
    safety_notes: str,
) -> None:
    db.execute(
        """
        INSERT INTO test_procedures (capability_id, title, summary, steps, equipment_needed, facility_needed, safety_notes)
        SELECT c.id, ?, ?, ?, ?, ?, ?
        FROM capabilities c
        WHERE c.name = ?
          AND NOT EXISTS (SELECT 1 FROM test_procedures p WHERE p.title = ?)
        """,
        (title, summary, steps, equipment_needed, facility_needed, safety_notes, capability_name, title),
    )


def _seed_procedure_checks(db: sqlite3.Connection, procedure_title: str, checks: list[tuple[str, str]]) -> None:
    proc = db.execute("SELECT id FROM test_procedures WHERE title = ?", (procedure_title,)).fetchone()
    if proc is None:
        return
    existing = db.execute(
        "SELECT 1 FROM procedure_checks WHERE procedure_id = ?", (proc["id"],)
    ).fetchone()
    if existing:
        return
    for step_number, (description, expected_value) in enumerate(checks, start=1):
        db.execute(
            "INSERT INTO procedure_checks (procedure_id, step_number, description, expected_value) VALUES (?, ?, ?, ?)",
            (proc["id"], step_number, description, expected_value),
        )


def _seed_allocation(
    db: sqlite3.Connection, order_code: str, test_name: str, resource_code: str, eut_name: str | None = None
) -> None:
    """Seed one allocation. When an order has more than one ordered_test with the same
    test_name (e.g. the same test repeated per EUT), pass eut_name to target the right one."""
    db.execute(
        """
        INSERT OR IGNORE INTO allocations (ordered_test_id, resource_id, planner_user_id, notes)
        SELECT ot.id, r.id, u.id, 'Seeded demo allocation'
        FROM ordered_tests ot
        JOIN customer_orders o ON o.id = ot.order_id
        LEFT JOIN euts e ON e.id = ot.eut_id
        JOIN resources r ON r.code = ?
        JOIN users u ON u.username = 'planner.demo'
        WHERE o.order_code = ? AND ot.test_name = ?
          AND (? IS NULL OR e.name = ?)
        """,
        (resource_code, order_code, test_name, eut_name, eut_name),
    )
