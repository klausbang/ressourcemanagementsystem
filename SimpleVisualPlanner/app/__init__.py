import sys
from pathlib import Path

# reusable_modules/ is a sibling of this project's own folder in the repo, not an
# installed package - make it importable without a pip install, per the plan's "plain
# folders, reused by copying/adding to PYTHONPATH" decision.
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from flask import Flask

from reusable_modules import basic_app
from reusable_modules.database import get_db, init_db, init_db_extension
from reusable_modules.proposals import count_pending, init_proposals


def create_app() -> Flask:
    app = basic_app.create_app(
        {
            "SECRET_KEY": "dev-secret-change-me",
            "DATABASE": "simplevisualplanner.db",
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
