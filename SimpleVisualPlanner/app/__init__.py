import os
import sys
from pathlib import Path

# reusable_modules/ is normally a sibling of this project's own folder in the repo (the
# monorepo checkout), not an installed package - make it importable without a pip
# install, per the plan's "plain folders, reused by copying/adding to PYTHONPATH"
# decision. A standalone deployment (Vercel: "Root Directory" = SimpleVisualPlanner)
# only ships this one folder, though - the sibling doesn't exist there - so this project
# also carries its own vendored copy at SimpleVisualPlanner/reusable_modules/ as a
# fallback. Prefer the sibling (the "live" copy) whenever it's present, so local
# development keeps editing one copy; only fall back to the vendored one when it isn't -
# i.e. exactly the standalone/Vercel case. Keep the vendored copy in sync by hand after
# any change to the real reusable_modules/ - see README.md "Deploying to Vercel".
REPO_ROOT = Path(__file__).resolve().parents[2]
VENDORED_ROOT = Path(__file__).resolve().parents[1]
if (REPO_ROOT / "reusable_modules").is_dir():
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
elif (VENDORED_ROOT / "reusable_modules").is_dir():
    if str(VENDORED_ROOT) not in sys.path:
        sys.path.insert(0, str(VENDORED_ROOT))

from flask import Flask

from reusable_modules import basic_app
from reusable_modules.database import get_db, init_db, init_db_extension
from reusable_modules.proposals import count_pending, init_proposals


def create_app(config_overrides: dict | None = None) -> Flask:
    """Build the app. `config_overrides` is applied *before* init_db()/seeding run below
    - critically, before DATABASE is ever touched - specifically so the test suite
    (tests/conftest.py) can redirect DATABASE to an isolated scratch file and never once
    read or write the real simplevisualplanner.db. Calling create_app() with no argument
    behaves exactly as before."""
    app = basic_app.create_app(
        {
            # Overridable via env var (proposal id 8: sharing this dev instance beyond
            # this machine) - the checked-in default is public the moment this repo is,
            # so anyone who knows it can forge session cookies for a reachable instance.
            # See README.md "Sharing this app during development" before setting HOST
            # to anything but 127.0.0.1.
            "SECRET_KEY": os.environ.get("SECRET_KEY", "dev-secret-change-me"),
            # Postgres in production (Vercel: DATABASE_URL, or Vercel Postgres's own
            # auto-injected POSTGRES_URL - see README.md "Deploying to Vercel"), a local
            # SQLite file otherwise. get_db() (reusable_modules/database) picks the
            # backend from this value alone - a postgres:// or postgresql:// URL means
            # Postgres, anything else is treated as a SQLite file path.
            "DATABASE": os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL") or "simplevisualplanner.db",
            "brand": "SimpleVisualPlanner",
            "roles": ["admin", "user", "planner"],
            "role_home_endpoints": {
                "admin": "core.dashboard",
                "user": "core.dashboard",
                # A planner's own tool is the point of their account - land there
                # directly rather than on the generic dashboard.
                "planner": "planner.visual_planner",
            },
            "nav_items": [
                {"label": "Dashboard", "endpoint": "core.dashboard"},
                {"label": "Visual Planner", "endpoint": "planner.visual_planner", "roles": ["planner", "admin"]},
                {
                    "label": "Review Proposals",
                    "endpoint": "proposals.admin_review",
                    "roles": ["admin"],
                    "badge": count_pending,
                },
                {"label": "User Admin", "endpoint": "user_admin", "roles": ["admin"]},
            ],
        },
        # Must be this app's own __name__ (not basic_app's default), so Flask resolves
        # its template root_path to SimpleVisualPlanner/app/ - see create_app()'s
        # docstring in reusable_modules/basic_app/__init__.py for why.
        import_name=__name__,
    )

    if config_overrides:
        app.config.update(config_overrides)

    init_db_extension(app)
    init_proposals(app, allowed_roles=("admin", "user", "planner"), reviewer_role="admin")
    basic_app.enable_user_admin(app, manager_role="admin")

    from .routes_core import bp as core_bp
    from .routes_planner import bp as planner_bp
    app.register_blueprint(core_bp)
    app.register_blueprint(planner_bp)

    with app.app_context():
        init_db()
        _seed_demo_users()

    return app


def _seed_demo_users() -> None:
    """One demo user per role, so there's something to log in as on a first run - same
    passwordless-by-username demonstrator login basic_app itself uses."""
    db = get_db()
    db.execute("INSERT OR IGNORE INTO users (username, role) VALUES ('admin.demo', 'admin')")
    db.execute("INSERT OR IGNORE INTO users (username, role) VALUES ('user.demo', 'user')")
    db.execute("INSERT OR IGNORE INTO users (username, role) VALUES ('planner.demo', 'planner')")
    db.commit()
