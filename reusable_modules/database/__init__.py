"""Reusable SQLite connection lifecycle + schema-composition module.

Owns nothing domain-specific itself - other modules (basic_app, proposals, or an app's
own code) each contribute a schema fragment via register_schema(), and this module runs
them all together inside one generic init_db(). See README.md for usage.
"""
import sqlite3
from pathlib import Path
from typing import Callable, Union

from flask import Flask, current_app, g

SchemaFragment = Union[str, Callable[[sqlite3.Connection], None]]

# Process-global on purpose (see README "Multiple apps in one process" note): every
# module that calls register_schema() during import/init contributes here, and init_db()
# runs the accumulated list against whichever app's database is active in the current
# app context. A fragment is only ever added once, even if register_schema() is called
# again with an identical string or the same function object.
_schema_fragments: list[SchemaFragment] = []


def register_schema(fragment: SchemaFragment) -> None:
    """Register a schema contribution: either a `CREATE TABLE IF NOT EXISTS ...` SQL
    string, or a callable taking a sqlite3.Connection (for anything that needs more than
    a plain CREATE TABLE - e.g. a migration, or seeding a lookup row). Call this once,
    typically at import time or inside a module's own init_xxx(app) function, before the
    consuming app calls init_db().
    """
    if fragment not in _schema_fragments:
        _schema_fragments.append(fragment)


def _db_path() -> Path:
    """Resolve the configured DATABASE path. Relative paths are relative to whatever the
    process's current working directory is when the app runs (matching plain sqlite3
    behavior) - pass an absolute path in app.config["DATABASE"] if that's not what you
    want."""
    return Path(current_app.config["DATABASE"])


def get_db() -> sqlite3.Connection:
    """A per-request SQLite connection, stored on Flask's `g` and reused for the rest of
    the request. Call close_db (wired up automatically by init_db_extension) to close it
    on teardown."""
    if "db" not in g:
        db = sqlite3.connect(_db_path())
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON;")
        g.db = db
    return g.db


def close_db(_: object = None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db_extension(app: Flask) -> None:
    """Wire this module's connection lifecycle into `app`: closes the per-request
    connection on teardown. Call once per app, any time before the first request (or
    before your own init_db() call, which also needs an app context)."""
    app.teardown_appcontext(close_db)


def init_db() -> None:
    """Run every registered schema fragment against the current app's database, inside
    an active app/request context. Safe to call repeatedly - each fragment should itself
    be idempotent (a plain `CREATE TABLE IF NOT EXISTS`, or a migration function that
    detects it already ran - see migrations.py for that pattern)."""
    db = get_db()
    for fragment in _schema_fragments:
        if callable(fragment):
            fragment(db)
        else:
            db.executescript(fragment)
    db.commit()
