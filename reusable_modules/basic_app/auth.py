"""Login/logout blueprint, generalized from RMS's app/routes_common.py: passwordless
username lookup (same demonstrator-style login RMS uses), but decoupled from RMS's fixed
admin/planner/technician role enum - roles and where each one lands after login are
supplied via basic_app.create_app()'s config, and the lookup itself is pluggable.
"""
from functools import wraps

from flask import Blueprint, current_app, flash, redirect, request, session, url_for

from reusable_modules.database import get_db, register_schema

bp = Blueprint(
    "auth", __name__,
    template_folder="templates",
    static_folder="static",
    static_url_path="/basic-app-static",
)

# basic_app owns this table. No FK from here to anything another module adds (e.g.
# proposals.submitted_by_user_id) - cross-module references are enforced at the
# application level only, so proposals has no hard dependency on this exact schema.
USERS_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    role TEXT NOT NULL
);
"""
register_schema(USERS_SCHEMA)


def default_user_lookup(username: str) -> dict | None:
    """The default user_lookup: a plain SQLite lookup against the `users` table this
    module owns. Pass your own callable via create_app(config={"user_lookup": ...}) to
    back logins with something else entirely (a different table, an external directory,
    real password checking, ...) without touching this module's code."""
    db = get_db()
    row = db.execute(
        "SELECT id, username, role FROM users WHERE username = ?", (username,)
    ).fetchone()
    return dict(row) if row else None


def _user_lookup():
    return current_app.config.get("BASIC_APP_USER_LOOKUP") or default_user_lookup


def current_role() -> str | None:
    return session.get("role")


def current_user() -> dict | None:
    if not session.get("user_id"):
        return None
    return {"id": session["user_id"], "username": session.get("username"), "role": session.get("role")}


def role_home_url() -> str:
    """Where a signed-in user lands: their role's own configured endpoint, or "/" if
    none was configured for that role (or nobody's signed in)."""
    endpoints = current_app.config.get("BASIC_APP_ROLE_HOME_ENDPOINTS", {})
    endpoint = endpoints.get(current_role())
    return url_for(endpoint) if endpoint else "/"


def require_role(*expected_roles: str):
    """Decorator restricting a view to one or more roles. Usage:
    @require_role("admin") or @require_role("admin", "planner")."""

    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if current_role() not in expected_roles:
                flash(f"Access denied. Required role: {' or '.join(expected_roles)}.", "error")
                return redirect(url_for("auth.login"))
            return view(*args, **kwargs)

        return wrapped

    return decorator


@bp.route("/login", methods=["GET", "POST"])
def login():
    from .ui import render_ui

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        if not username:
            flash("Username is required.", "error")
            return render_ui("basic_app/login.html")

        user = _user_lookup()(username)
        if user is None:
            flash("Unknown user.", "error")
            return render_ui("basic_app/login.html")

        session["user_id"] = user["id"]
        session["username"] = user["username"]
        session["role"] = user["role"]
        flash(f"Signed in as {user['username']} ({user['role']}).", "info")
        return redirect(role_home_url())

    return render_ui("basic_app/login.html")


@bp.route("/logout")
def logout():
    session.clear()
    flash("Signed out.", "info")
    return redirect(url_for("auth.login"))
