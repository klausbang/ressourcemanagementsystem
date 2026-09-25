# `database` module

A reusable SQLite connection lifecycle for a Flask app, plus a way for several
independent modules (e.g. `basic_app`'s `users` table, `proposals`'s `proposals` table,
and your own app's own tables) to each contribute their own schema without any of them
needing to know about the others.

Extracted from the RMS project's `app/db.py` (connection lifecycle) and its
rebuild-and-rename migration pattern (documented in RMS's own `CLAUDE.md`).

## Install

No packaging yet - copy (or symlink) the `reusable_modules/database/` folder into your
project and import it as `from reusable_modules.database import ...` (add the parent
folder to `sys.path` if `reusable_modules/` isn't already a sibling of your app code -
see `SimpleVisualPlanner/app/__init__.py` for the pattern).

## Usage

```python
from flask import Flask
from reusable_modules.database import init_db_extension, init_db, register_schema, get_db

# 1. Any module that owns a table registers its schema - a plain SQL string is enough
#    for a brand-new table:
register_schema("""
    CREATE TABLE IF NOT EXISTS widgets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL
    );
""")

app = Flask(__name__)
app.config["DATABASE"] = "myapp.db"   # relative to the process CWD, or pass an absolute path

# 2. Wire the per-request connection lifecycle into the app (once):
init_db_extension(app)

# 3. Run every registered schema fragment (call after every module that owns a table has
#    had a chance to register_schema() - inside an app context, since it needs a live
#    connection):
with app.app_context():
    init_db()

# 4. Use get_db() from a route/view, same as you would sqlite3.connect() directly:
@app.route("/widgets")
def list_widgets():
    db = get_db()
    return str([dict(r) for r in db.execute("SELECT * FROM widgets").fetchall()])
```

`register_schema()` also accepts a callable `fn(db: sqlite3.Connection) -> None` instead
of a plain SQL string, for anything beyond a bare `CREATE TABLE` - a migration (see
below), or seeding a lookup table's rows.

## Connection lifecycle

`get_db()` opens (or reuses) one SQLite connection per request, stored on Flask's
request-local `g`, with `PRAGMA foreign_keys = ON` and `row_factory = sqlite3.Row` set.
`init_db_extension(app)` registers `close_db` as a `teardown_appcontext` handler so that
connection is closed automatically at the end of every request. This mirrors RMS's own
`app/db.py:get_db()`/`close_db()` exactly.

**Test isolation warning**: if you call `init_db()`/mutate data from a test script,
always override `app.config["DATABASE"]` to a scratch/temp path *before* the first
`get_db()` call in that app context - otherwise you'll be reading/writing whatever real
database file `DATABASE` was already pointed at.

## The rebuild-and-rename migration pattern (`migrations.py`)

SQLite cannot `ALTER TABLE` to widen a `CHECK` constraint or change a column's foreign
key - the only way is to build a new table with the target schema, copy the data across,
drop the old table, and rename the new one into place. `migrations.py` provides this as
two small, reusable pieces so you don't have to hand-write the boilerplate (or the
`PRAGMA foreign_keys = OFF/ON` wrapping) every time:

```python
from reusable_modules.database.migrations import is_migration_needed, rebuild_table

def _migrate_widgets_table(db):
    # Detect via the table's own CREATE TABLE text (sqlite_master.sql) - PRAGMA
    # table_info does NOT expose CHECK constraints, only column names/types.
    if not is_migration_needed(
        db, "widgets",
        required_sql_fragments=("'archived'",),   # a new CHECK-allowed status value
        required_columns=("archived_at",),         # a new column added alongside it
    ):
        return  # already current - correct no-op on every later init_db() call

    rebuild_table(
        db, "widgets",
        create_new_sql="""
            CREATE TABLE widgets_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('active', 'archived')),
                archived_at TEXT
            )
        """,
        copy_columns="id, name, status, archived_at",
        select_columns="id, name, status, NULL",  # archived_at didn't exist on old rows
    )

register_schema(_migrate_widgets_table)  # a callable fragment, run by init_db()
```

Register the migration function itself via `register_schema()` (as a callable, not a
SQL string) so it runs every time `init_db()` does, right alongside the plain
`CREATE TABLE IF NOT EXISTS` fragments - `is_migration_needed`'s check makes every call
after the first a correct no-op.

**Always test a real migration against a copy of your live database first** (row-count
preservation, new-value insertability, idempotency on a second `init_db()` call) before
trusting it against production data - this pattern is mechanical, but a hand-written
`create_new_sql`/`copy_columns` mismatch will silently drop or corrupt data.

## `table_utils.rows_with_meta()`

A small, pure display helper (no domain logic, no database calls) - converts
`sqlite3.Row` results to plain dicts, flags rows whose `dup_keys` values collide with
another row's (`_dup: True`, useful for an amber "duplicate-looking row" highlight in a
list UI), and optionally sorts by a column whitelisted in `sortable_keys`. Copied
verbatim from RMS's `app/table_utils.py`.

## Multiple apps in one process

`register_schema()`'s fragment list is process-global, not per-Flask-app-instance - if
your test suite calls your `create_app()` factory more than once in the same process,
each module's schema fragment gets registered again, but re-registering the exact same
string or function object is a no-op (deduplicated by `register_schema()` itself), and
running the same `CREATE TABLE IF NOT EXISTS`/idempotent migration twice is harmless.
This is simplest for a first version of the library; a future version could move the
registry onto the Flask `app` object itself if genuinely running two *different* apps
with *different* schemas in one process ever comes up.
