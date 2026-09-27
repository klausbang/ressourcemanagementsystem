"""A thin wrapper making a psycopg (Postgres) connection behave enough like a
sqlite3.Connection that every existing query in basic_app/proposals/user_admin - written
once, against SQLite - runs unchanged against Postgres too. Specifically translates:

- "?" positional placeholders -> "%s" (psycopg/Postgres style). Safe here because none
  of this codebase's own SQL ever contains a literal "?" outside of a placeholder
  position - if you add a query that does, this blanket replace would corrupt it.
- SQLite's "INSERT OR IGNORE INTO ..." -> "INSERT INTO ... ON CONFLICT DO NOTHING",
  Postgres's equivalent "ignore on any constraint violation" - used by
  SimpleVisualPlanner's demo-user seeding.
- .executescript() (SQLite-only; psycopg has no equivalent) -> a plain .execute() of the
  whole multi-statement string, which Postgres's simple query protocol accepts directly
  as long as there are no bind parameters, which is true for every schema fragment this
  library registers.

Row access is made to look like sqlite3.Row too: psycopg's dict_row row factory returns
plain dicts, so `row["col"]` and `dict(row)` both already work with no changes needed at
the call sites either.

Only reached when app.config["DATABASE"] is a postgres:// or postgresql:// URL - see
reusable_modules/database/__init__.py:get_db(). Plain local-file SQLite (the default)
never imports this module at all, so a project that never sets a Postgres URL has no new
dependency on psycopg.
"""
import re

import psycopg
from psycopg.rows import dict_row

_INSERT_OR_IGNORE_RE = re.compile(r"(?is)^\s*INSERT\s+OR\s+IGNORE\s+INTO")


def _translate(sql: str) -> str:
    is_insert_ignore = bool(_INSERT_OR_IGNORE_RE.match(sql))
    if is_insert_ignore:
        sql = _INSERT_OR_IGNORE_RE.sub("INSERT INTO", sql, count=1)
    sql = sql.replace("?", "%s")
    if is_insert_ignore:
        sql = sql.rstrip().rstrip(";") + " ON CONFLICT DO NOTHING"
    return sql


class PostgresConnection:
    """Drop-in-enough replacement for sqlite3.Connection, backed by a real psycopg
    connection. See module docstring for exactly what's translated and why."""

    backend = "postgres"

    def __init__(self, dsn: str):
        self._conn = psycopg.connect(dsn, autocommit=False, row_factory=dict_row)

    def execute(self, sql: str, params=()):
        cur = self._conn.cursor()
        cur.execute(_translate(sql), params if params else None)
        return cur

    def executescript(self, sql: str):
        # No params, so Postgres's simple query protocol runs every ";"-separated
        # statement in the string in one round trip - psycopg's own .execute() already
        # supports this for a parameter-free multi-statement string.
        cur = self._conn.cursor()
        cur.execute(sql)
        return cur

    def commit(self) -> None:
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()


def connect(dsn: str) -> PostgresConnection:
    return PostgresConnection(dsn)
