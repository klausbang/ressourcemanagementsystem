"""Shared pytest fixtures for the whole suite. See ../README.md ("Running the tests")
for how to run these, and app/__init__.py:create_app()'s config_overrides parameter for
why fixtures here never touch the real simplevisualplanner.db.
"""
import os
import socket
import sys
import threading
import time
import urllib.request
from pathlib import Path

import pytest
from werkzeug.serving import make_server

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from app import create_app, _seed_demo_users  # noqa: E402

# Set TEST_POSTGRES_URL to also run the whole suite against a real Postgres server -
# proves reusable_modules/database's SQLite/Postgres abstraction actually holds, not
# just that it reads correctly. Unset (the default): every test runs against SQLite
# only, exactly as before - nothing here changes unless you opt in.
POSTGRES_TEST_URL = os.environ.get("TEST_POSTGRES_URL")
_BACKENDS = ["sqlite"] + (["postgres"] if POSTGRES_TEST_URL else [])


def _reset_postgres(database_url: str) -> None:
    """Wipe both tables between tests. DELETE (not TRUNCATE) is enough - no test relies
    on specific row ids, only on looking them up dynamically after insert."""
    import psycopg

    with psycopg.connect(database_url, autocommit=True) as conn:
        conn.execute("DELETE FROM proposals")
        conn.execute("DELETE FROM users")


@pytest.fixture(params=_BACKENDS)
def app(request, tmp_path):
    """A fresh SimpleVisualPlanner app per test. Parametrized over every backend in
    _BACKENDS - by default just "sqlite" (an isolated scratch file, never the real
    database); with TEST_POSTGRES_URL set, every test also runs a second time against
    that Postgres server, reset to empty first. Either way, comes pre-seeded with the
    three demo users (admin.demo/user.demo/planner.demo) exactly like a real run."""
    if request.param == "postgres":
        database = POSTGRES_TEST_URL
    else:
        database = str(tmp_path / "test.db")

    application = create_app({"DATABASE": database, "TESTING": True})

    if request.param == "postgres":
        _reset_postgres(database)
        with application.app_context():
            _seed_demo_users()

    yield application


@pytest.fixture
def client(app):
    return app.test_client()


def login(client, username):
    """POST /login as `username` (passwordless), following the redirect to wherever
    that role lands."""
    return client.post("/login", data={"username": username}, follow_redirects=True)


class _ServerThread(threading.Thread):
    def __init__(self, application, port):
        super().__init__(daemon=True)
        self.server = make_server("127.0.0.1", port, application)

    def run(self):
        self.server.serve_forever()

    def shutdown(self):
        self.server.shutdown()


def _free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.fixture
def live_server(tmp_path):
    """A real SimpleVisualPlanner instance served over actual HTTP on an ephemeral local
    port, backed by an isolated scratch database - for tests that need a real browser
    (Playwright's `page` fixture) rather than Flask's test client. Yields the base URL.
    """
    application = create_app({"DATABASE": str(tmp_path / "test.db"), "TESTING": True})
    port = _free_port()
    thread = _ServerThread(application, port)
    thread.start()

    base_url = f"http://127.0.0.1:{port}"
    for _ in range(50):
        try:
            urllib.request.urlopen(base_url + "/login", timeout=0.2)
            break
        except Exception:
            time.sleep(0.1)
    else:
        thread.shutdown()
        raise RuntimeError(f"live_server never became responsive at {base_url}")

    yield base_url

    thread.shutdown()
