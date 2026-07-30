from functools import wraps
from urllib.parse import urlparse

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from .db import init_db, get_db
from .table_utils import rows_with_meta

bp = Blueprint("common", __name__)

UI_MODES = ("simple", "modern")

RESOURCE_SORTABLE_KEYS = {"code", "name", "resource_type", "status", "capabilities"}
RESOURCE_DUP_KEYS = ["code", "name", "resource_type", "status", "capabilities"]

ROLE_HOME_ENDPOINT = {
    "admin": "admin.admin_manage",
    "planner": "planner.planner_orders",
    "technician": "technician.technician_dashboard",
}


def current_role() -> str | None:
    return session.get("role")


def role_home_url() -> str:
    """Where a signed-in user lands: their role's own workspace, not the (hidden) catalog."""
    endpoint = ROLE_HOME_ENDPOINT.get(current_role())
    return url_for(endpoint) if endpoint else url_for("common.login")


def current_ui_mode() -> str:
    return session.get("ui_mode", "simple")


def render_ui(template_name: str, **context):
    mode = current_ui_mode()
    context.setdefault("ui_mode", mode)
    return render_template(f"{mode}/{template_name}", **context)


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


def require_any_role(*expected_roles: str):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            role = current_role()
            if role not in expected_roles:
                flash(f"Access denied. Required role: {' or '.join(expected_roles)}.", "error")
                return redirect(url_for("common.login"))
            return view(*args, **kwargs)

        return wrapped

    return decorator


@bp.route("/ui-mode/<mode>")
def set_ui_mode(mode):
    if mode not in UI_MODES:
        flash("Unknown interface mode.", "error")
        return redirect(role_home_url())

    session["ui_mode"] = mode

    referrer = request.referrer
    if referrer:
        parsed = urlparse(referrer)
        if parsed.netloc == request.host:
            target = parsed.path or role_home_url()
            if parsed.query:
                target = f"{target}?{parsed.query}"
            return redirect(target)

    return redirect(role_home_url())


@bp.route("/help")
def help_page():
    return render_ui("help.html")


@bp.route("/")
def home():
    if session.get("username"):
        return redirect(role_home_url())
    return render_ui("landing.html")


@bp.route("/catalog")
@require_any_role("admin", "planner", "technician")
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

    stats = db.execute(
        """
        SELECT
            COUNT(*) AS total_resources,
            SUM(CASE WHEN status = 'available' THEN 1 ELSE 0 END) AS available_resources,
            COUNT(DISTINCT resource_type) AS resource_types
        FROM resources
        """
    ).fetchone()

    return render_ui(
        "resource_catalog.html",
        resources=resources,
        capabilities=capabilities,
        selected_type=resource_type,
        selected_capability=capability_id,
        role=current_role(),
        stats=stats,
    )


@bp.route("/login", methods=["GET", "POST"])
def login():
    init_db()
    db = get_db()

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        if not username:
            flash("Username is required.", "error")
            return render_ui("login.html")

        user = db.execute("SELECT id, username, role FROM users WHERE username = ?", (username,)).fetchone()
        if user is None:
            flash("Unknown user.", "error")
            return render_ui("login.html")

        session["user_id"] = user["id"]
        session["username"] = user["username"]
        session["role"] = user["role"]
        if user["role"] == "technician":
            # The technician workspace only exists in the modern UI.
            session["ui_mode"] = "modern"
        flash(f"Signed in as {user['username']} ({user['role']}).", "info")
        return redirect(role_home_url())

    return render_ui("login.html")


@bp.route("/logout")
def logout():
    ui_mode = session.get("ui_mode")
    session.clear()
    if ui_mode:
        session["ui_mode"] = ui_mode
    flash("Signed out.", "info")
    return redirect(url_for("common.home"))
