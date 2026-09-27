"""Generic helpers for the "rebuild-and-rename" SQLite migration pattern: needed whenever
a table's CHECK constraint must be widened (e.g. adding a new allowed status/type value)
or a column's foreign key must change, since SQLite cannot ALTER either in place. Not
tied to any specific table - callers describe the target schema and column mapping,
these helpers do the mechanical rebuild/detection work.
"""
import sqlite3


def table_exists(db: sqlite3.Connection, name: str) -> bool:
    return (
        db.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)
        ).fetchone()
        is not None
    )


def get_table_sql(db: sqlite3.Connection, name: str) -> str | None:
    """The table's own CREATE TABLE text, needed to detect CHECK constraints - PRAGMA
    table_info does not expose them."""
    row = db.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)
    ).fetchone()
    return row["sql"] if row else None


def get_columns(db: sqlite3.Connection, name: str) -> set[str]:
    return {r["name"] for r in db.execute(f"PRAGMA table_info({name})").fetchall()}


def is_migration_needed(
    db: sqlite3.Connection,
    table: str,
    required_sql_fragments: tuple[str, ...] = (),
    required_columns: tuple[str, ...] = (),
) -> bool:
    """Whether `table` still needs a rebuild: False if the table doesn't exist yet (a
    fresh CREATE TABLE will already be current, nothing to migrate), or if every one of
    `required_sql_fragments` already appears in the table's own CREATE TABLE text and
    every one of `required_columns` already exists. True otherwise - the table exists
    but is missing something the current schema needs.
    """
    if not table_exists(db, table):
        return False
    sql = get_table_sql(db, table) or ""
    if any(fragment not in sql for fragment in required_sql_fragments):
        return True
    columns = get_columns(db, table)
    return any(col not in columns for col in required_columns)


def rebuild_table(
    db: sqlite3.Connection,
    table: str,
    create_new_sql: str,
    copy_columns: str,
    select_columns: str | None = None,
) -> None:
    """Rebuild `table` to a new schema: create `<table>_new` from `create_new_sql`
    (which must literally create a table named `f"{table}_new"`), copy every row across
    with `INSERT INTO <table>_new (copy_columns) SELECT select_columns FROM <table>`,
    drop the old table, and rename the new one into place - all wrapped in
    `PRAGMA foreign_keys = OFF/ON` so the transient duplicate-named table doesn't trip
    any FK checks mid-rebuild.

    `select_columns` lets a caller supply a literal/expression for a brand-new column a
    migration is introducing (e.g. `"1"` or `"'waiting'"` as a default) instead of a
    plain column name; when omitted it defaults to `copy_columns` (a straight copy).

    This function always performs the rebuild unconditionally - call is_migration_needed
    first to decide whether it's needed, so a second run of your init_db() is a correct
    no-op instead of rebuilding every time.
    """
    select_columns = select_columns or copy_columns
    db.execute("PRAGMA foreign_keys = OFF")
    try:
        db.execute(create_new_sql)
        db.execute(
            f"INSERT INTO {table}_new ({copy_columns}) SELECT {select_columns} FROM {table}"
        )
        db.execute(f"DROP TABLE {table}")
        db.execute(f"ALTER TABLE {table}_new RENAME TO {table}")
        db.commit()
    finally:
        db.execute("PRAGMA foreign_keys = ON")
