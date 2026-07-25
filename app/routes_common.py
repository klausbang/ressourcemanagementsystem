from functools import wraps

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from .db import init_db, get_db
from .table_utils import rows_with_meta

bp = Blueprint("common", __name__)

RESOURCE_SORTABLE_KEYS = {"code", "name", "resource_type", "status", "capabilities"}
RESOURCE_DUP_KEYS = ["code", "name", "resource_type", "status", "capabilities"]


def current_role() -> str | None:
    return session.get("role")


def require_role(expected_role: str):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            role = current_role()
            if role != expected_role:
                flash(f"Access denied. Required role: {expected_role}.", "error")
                return redirect(url_for("common.login"))
            return view(*args, **kwargs)

        return wrapped

    return decorator


@bp.route("/")
def resource_catalog():
    init_db()
    db = get_db()

    resource_type = request.args.get("resource_type", "")
    capability_id = request.args.get("capability_id", "")

    query = """
        SELECT r.id, r.code, r.name, r.resource_type, r.status,
               GROUP_CONCAT(c.name, ', ') AS capabilities
        FROM resources r
        LEFT JOIN resource_capabilities rc ON rc.resource_id = r.id
        LEFT JOIN capabilities c ON c.id = rc.capability_id
    """
    params: list[str] = []

    where = []
    if resource_type:
        where.append("r.resource_type = ?")
        params.append(resource_type)
    if capability_id:
        where.append("r.id IN (SELECT resource_id FROM resource_capabilities WHERE capability_id = ?)")
        params.append(capability_id)

    if where:
        query += " WHERE " + " AND ".join(where)

    query += " GROUP BY r.id ORDER BY r.code"

    resources = rows_with_meta(
        db.execute(query, params).fetchall(),
        dup_keys=RESOURCE_DUP_KEYS,
        sort_key=request.args.get("resources_sort"),
        sort_dir=request.args.get("resources_dir", "asc"),
        sortable_keys=RESOURCE_SORTABLE_KEYS,
    )
    capabilities = db.execute("SELECT id, name FROM capabilities ORDER BY name").fetchall()

    return render_template(
        "resource_catalog.html",
        resources=resources,
        capabilities=capabilities,
        selected_type=resource_type,
        selected_capability=capability_id,
        role=current_role(),
    )


@bp.route("/login", methods=["GET", "POST"])
def login():
    init_db()
    db = get_db()

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        if not username:
            flash("Username is required.", "error")
            return render_template("login.html")

        user = db.execute("SELECT id, username, role FROM users WHERE username = ?", (username,)).fetchone()
        if user is None:
            flash("Unknown user.", "error")
            return render_template("login.html")

        session["user_id"] = user["id"]
        session["username"] = user["username"]
        session["role"] = user["role"]
        flash(f"Signed in as {user['username']} ({user['role']}).", "info")
        return redirect(url_for("common.resource_catalog"))

    return render_template("login.html")


@bp.route("/logout")
def logout():
    session.clear()
    flash("Signed out.", "info")
    return redirect(url_for("common.resource_catalog"))
