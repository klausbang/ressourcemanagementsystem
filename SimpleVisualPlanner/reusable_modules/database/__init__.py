"""Reusable SQLite/Postgres connection lifecycle + schema-composition module.

Owns nothing domain-specific itself - other modules (basic_app, proposals, or an app's
own code) each contribute a schema fragment via register_schema(), and this module runs
them all together inside one generic init_db(). See README.md for usage.

Backend (SQLite vs Postgres) is a runtime choice, not a build-time one - see
get_db()/_is_postgres_url() below - so a schema fragment whose SQL differs between the
two (anything with an auto-incrementing primary key, most commonly) should register a
callable that branches on the connection's own `.backend` attribute ("sqlite" or
"postgres") rather than a single hardcoded SQL string - see basic_app/auth.py's
USERS_SCHEMA_SQLITE/USERS_SCHEMA_POSTGRES for the pattern.
"""
import sqlite3
from pathlib import Path
from typing import Callable, Union

from flask import Flask, current_app, g

SchemaFragment = Union[str, Callable[[object], None]]

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


def _database_setting() -> str:
    return str(current_app.config["DATABASE"])


def _is_postgres_url(value: str) -> bool:
    return value.startswith("postgres://") or value.startswith("postgresql://")


class _SQLiteConnection(sqlite3.Connection):
    """Plain sqlite3.Connection instances don't support arbitrary attribute assignment
    (no __dict__) - this subclass exists purely to carry a `.backend` class attribute so
    schema-fragment callables can branch on `db.backend` the same way they do for the
    Postgres wrapper, without a hasattr/getattr dance at every call site."""

    backend = "sqlite"


def get_db():
    """A per-request database connection, stored on Flask's `g` and reused for the rest
    of the request. Call close_db (wired up automatically by init_db_extension) to close
    it on teardown.

    Backend is chosen from app.config["DATABASE"]: a "postgres://" or "postgresql://"
    URL connects to Postgres (see postgres.py); anything else is treated as a local
    SQLite file path (relative paths are relative to the process's current working
    directory, matching plain sqlite3 behavior) - the default, and everything this
    module supported before Postgres was added. Both are returned with dict-like row
    access (`row["col"]`, `dict(row)`), so calling code never needs to know which one
    it's talking to.
    """
    if "db" not in g:
        setting = _database_setting()
        if _is_postgres_url(setting):
            from .postgres import connect as _connect_postgres

            g.db = _connect_postgres(setting)
        else:
            db = sqlite3.connect(Path(setting), factory=_SQLiteConnection)
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
