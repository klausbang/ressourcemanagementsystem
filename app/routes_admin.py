import sqlite3

from flask import Blueprint, flash, redirect, request, url_for

from .db import get_db, init_db
from .routes_common import render_ui, require_role
from .table_utils import rows_with_meta

bp = Blueprint("admin", __name__, url_prefix="/admin")

VALID_ROLES = ("admin", "planner")

USER_SORTABLE_KEYS = {"username", "role"}
USER_DUP_KEYS = ["username", "role"]

CAPABILITY_SORTABLE_KEYS = {"name", "description"}
CAPABILITY_DUP_KEYS = ["name", "description"]

RESOURCE_SORTABLE_KEYS = {"code", "name", "resource_type", "status"}
RESOURCE_DUP_KEYS = ["code", "name", "resource_type", "status"]

MAPPING_SORTABLE_KEYS = {"code", "resource_name", "capability_name"}
MAPPING_DUP_KEYS = ["code", "resource_name", "capability_name"]


def _load_admin_context(db) -> dict:
    users = rows_with_meta(
        db.execute("SELECT id, username, role FROM users ORDER BY username").fetchall(),
        dup_keys=USER_DUP_KEYS,
        sort_key=request.args.get("users_sort"),
        sort_dir=request.args.get("users_dir", "asc"),
        sortable_keys=USER_SORTABLE_KEYS,
    )
    resources = rows_with_meta(
        db.execute("SELECT id, code, name, resource_type, status FROM resources ORDER BY code").fetchall(),
        dup_keys=RESOURCE_DUP_KEYS,
        sort_key=request.args.get("resources_sort"),
        sort_dir=request.args.get("resources_dir", "asc"),
        sortable_keys=RESOURCE_SORTABLE_KEYS,
    )
    capabilities = rows_with_meta(
        db.execute("SELECT id, name, description FROM capabilities ORDER BY name").fetchall(),
        dup_keys=CAPABILITY_DUP_KEYS,
        sort_key=request.args.get("capabilities_sort"),
        sort_dir=request.args.get("capabilities_dir", "asc"),
        sortable_keys=CAPABILITY_SORTABLE_KEYS,
    )
    mappings = rows_with_meta(
        db.execute(
            """
            SELECT rc.resource_id, rc.capability_id, r.code, r.name AS resource_name, c.name AS capability_name
            FROM resource_capabilities rc
            JOIN resources r ON r.id = rc.resource_id
            JOIN capabilities c ON c.id = rc.capability_id
            ORDER BY r.code, c.name
            """
        ).fetchall(),
        dup_keys=MAPPING_DUP_KEYS,
        sort_key=request.args.get("mappings_sort"),
        sort_dir=request.args.get("mappings_dir", "asc"),
        sortable_keys=MAPPING_SORTABLE_KEYS,
    )
    return {
        "users": users,
        "resources": resources,
        "capabilities": capabilities,
        "mappings": mappings,
    }


def _render_admin(db):
    return render_ui("admin_manage.html", **_load_admin_context(db))


@bp.route("/", methods=["GET", "POST"])
@require_role("admin")
def admin_manage():
    init_db()
    db = get_db()

    if request.method == "POST":
        action = request.form.get("action", "")

        if action == "create_user":
            username = request.form.get("username", "").strip()
            role = request.form.get("role", "").strip()

            if not (username and role):
                flash("Username and role are required.", "error")
            elif role not in VALID_ROLES:
                flash("Role must be admin or planner.", "error")
            elif db.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone():
                flash(f"Username {username} already exists.", "error")
            else:
                db.execute("INSERT INTO users (username, role) VALUES (?, ?)", (username, role))
                db.commit()
                flash(f"User {username} created.", "info")

        elif action == "update_user":
            user_id = request.form.get("user_id", "").strip()
            username = request.form.get("username", "").strip()
            role = request.form.get("role", "").strip()

            if not (user_id and username and role):
                flash("Username and role are required.", "error")
            elif role not in VALID_ROLES:
                flash("Role must be admin or planner.", "error")
            elif db.execute("SELECT 1 FROM users WHERE username = ? AND id != ?", (username, user_id)).fetchone():
                flash(f"Username {username} already exists.", "error")
            else:
                db.execute("UPDATE users SET username = ?, role = ? WHERE id = ?", (username, role, user_id))
                db.commit()
                flash(f"User {username} updated.", "info")

        elif action == "delete_user":
            user_id = request.form.get("user_id", "").strip()
            try:
                db.execute("DELETE FROM users WHERE id = ?", (user_id,))
                db.commit()
                flash("User deleted.", "info")
            except sqlite3.IntegrityError:
                db.rollback()
                flash("Cannot delete user: allocations exist that were assigned by this planner.", "error")

        elif action == "create_capability":
            name = request.form.get("name", "").strip()
            description = request.form.get("description", "").strip()

            if not name:
                flash("Capability name is required.", "error")
            elif db.execute("SELECT 1 FROM capabilities WHERE name = ?", (name,)).fetchone():
                flash(f"Capability {name} already exists.", "error")
            else:
                db.execute(
                    "INSERT INTO capabilities (name, description) VALUES (?, ?)",
                    (name, description),
                )
                db.commit()
                flash("Capability saved.", "info")

        elif action == "update_capability":
            capability_id = request.form.get("capability_id", "").strip()
            name = request.form.get("name", "").strip()
            description = request.form.get("description", "").strip()

            if not (capability_id and name):
                flash("Capability name is required.", "error")
            elif db.execute(
                "SELECT 1 FROM capabilities WHERE name = ? AND id != ?", (name, capability_id)
            ).fetchone():
                flash(f"Capability {name} already exists.", "error")
            else:
                db.execute(
                    "UPDATE capabilities SET name = ?, description = ? WHERE id = ?",
                    (name, description, capability_id),
                )
                db.commit()
                flash("Capability updated.", "info")

        elif action == "delete_capability":
            capability_id = request.form.get("capability_id", "").strip()
            try:
                db.execute("DELETE FROM capabilities WHERE id = ?", (capability_id,))
                db.commit()
                flash("Capability deleted.", "info")
            except sqlite3.IntegrityError:
                db.rollback()
                flash("Cannot delete capability: it is required by existing ordered tests.", "error")

        elif action == "create_resource":
            code = request.form.get("code", "").strip()
            name = request.form.get("name", "").strip()
            resource_type = request.form.get("resource_type", "").strip()
            status = request.form.get("status", "").strip() or "available"

            if not (code and name and resource_type):
                flash("Resource code, name, and type are required.", "error")
            elif db.execute("SELECT 1 FROM resources WHERE code = ?", (code,)).fetchone():
                flash(f"Resource code {code} already exists.", "error")
            else:
                db.execute(
                    "INSERT INTO resources (code, name, resource_type, status) VALUES (?, ?, ?, ?)",
                    (code, name, resource_type, status),
                )
                db.commit()
                flash("Resource saved.", "info")

        elif action == "update_resource":
            resource_id = request.form.get("resource_id", "").strip()
            code = request.form.get("code", "").strip()
            name = request.form.get("name", "").strip()
            resource_type = request.form.get("resource_type", "").strip()
            status = request.form.get("status", "").strip()

            if not (resource_id and code and name and resource_type and status):
                flash("Resource code, name, type, and status are required.", "error")
            elif db.execute(
                "SELECT 1 FROM resources WHERE code = ? AND id != ?", (code, resource_id)
            ).fetchone():
                flash(f"Resource code {code} already exists.", "error")
            else:
                db.execute(
                    "UPDATE resources SET code = ?, name = ?, resource_type = ?, status = ? WHERE id = ?",
                    (code, name, resource_type, status, resource_id),
                )
                db.commit()
                flash("Resource updated.", "info")

        elif action == "delete_resource":
            resource_id = request.form.get("resource_id", "").strip()
            try:
                db.execute("DELETE FROM resources WHERE id = ?", (resource_id,))
                db.commit()
                flash("Resource deleted.", "info")
            except sqlite3.IntegrityError:
                db.rollback()
                flash("Cannot delete resource: it has existing allocations.", "error")

        elif action == "assign_capability":
            resource_id = request.form.get("resource_id", "").strip()
            capability_id = request.form.get("capability_id", "").strip()

            if not (resource_id and capability_id):
                flash("Resource and capability are required for assignment.", "error")
            else:
                db.execute(
                    "INSERT OR IGNORE INTO resource_capabilities (resource_id, capability_id) VALUES (?, ?)",
                    (resource_id, capability_id),
                )
                db.commit()
                flash("Capability assigned to resource.", "info")

        elif action == "remove_capability":
            resource_id = request.form.get("resource_id", "").strip()
            capability_id = request.form.get("capability_id", "").strip()

            db.execute(
                "DELETE FROM resource_capabilities WHERE resource_id = ? AND capability_id = ?",
                (resource_id, capability_id),
            )
            db.commit()
            flash("Capability unassigned from resource.", "info")

        return redirect(url_for("admin.admin_manage"))

    return _render_admin(db)
