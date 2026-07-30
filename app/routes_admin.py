import sqlite3

from flask import Blueprint, flash, redirect, request, url_for

from .db import get_db, init_db
from .routes_common import render_ui, require_role
from .table_utils import rows_with_meta

bp = Blueprint("admin", __name__, url_prefix="/admin")

VALID_ROLES = ("admin", "planner", "technician")

USER_SORTABLE_KEYS = {"username", "role"}
USER_DUP_KEYS = ["username", "role"]

CAPABILITY_SORTABLE_KEYS = {"name", "description"}
CAPABILITY_DUP_KEYS = ["name", "description"]

RESOURCE_SORTABLE_KEYS = {"code", "name", "resource_type", "status", "site"}
RESOURCE_DUP_KEYS = ["code", "name", "resource_type", "status", "site"]

MAPPING_SORTABLE_KEYS = {"code", "resource_name", "capability_name"}
MAPPING_DUP_KEYS = ["code", "resource_name", "capability_name"]

EXCLUSION_GROUP_SORTABLE_KEYS = {"name", "notes"}
EXCLUSION_GROUP_DUP_KEYS = ["name", "notes"]


def _load_admin_context(db) -> dict:
    users = rows_with_meta(
        db.execute(
            """
            SELECT u.id, u.username, u.role, u.linked_resource_id, r.code AS linked_resource_code
            FROM users u
            LEFT JOIN resources r ON r.id = u.linked_resource_id
            ORDER BY u.username
            """
        ).fetchall(),
        dup_keys=USER_DUP_KEYS,
        sort_key=request.args.get("users_sort"),
        sort_dir=request.args.get("users_dir", "asc"),
        sortable_keys=USER_SORTABLE_KEYS,
    )
    technician_resources = db.execute(
        "SELECT id, code, name FROM resources WHERE resource_type = 'technician' ORDER BY code"
    ).fetchall()
    resources = rows_with_meta(
        db.execute("SELECT id, code, name, resource_type, status, site FROM resources ORDER BY code").fetchall(),
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
    exclusion_groups = rows_with_meta(
        db.execute("SELECT id, name, notes FROM exclusion_groups ORDER BY name").fetchall(),
        dup_keys=EXCLUSION_GROUP_DUP_KEYS,
        sort_key=request.args.get("exclusion_groups_sort"),
        sort_dir=request.args.get("exclusion_groups_dir", "asc"),
        sortable_keys=EXCLUSION_GROUP_SORTABLE_KEYS,
    )
    member_rows = db.execute(
        """
        SELECT egr.group_id, r.id AS resource_id, r.code, r.name, r.site
        FROM exclusion_group_resources egr
        JOIN resources r ON r.id = egr.resource_id
        ORDER BY egr.group_id, r.code
        """
    ).fetchall()
    members_by_group: dict[int, list] = {}
    for row in member_rows:
        members_by_group.setdefault(row["group_id"], []).append(dict(row))
    for group in exclusion_groups:
        group["members"] = members_by_group.get(group["id"], [])
        member_ids = {m["resource_id"] for m in group["members"]}
        group["available_facilities"] = [
            r for r in resources if r["resource_type"] == "facility" and r["id"] not in member_ids
        ]

    return {
        "users": users,
        "resources": resources,
        "capabilities": capabilities,
        "mappings": mappings,
        "technician_resources": technician_resources,
        "exclusion_groups": exclusion_groups,
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
            linked_resource_id = request.form.get("linked_resource_id", "").strip() or None
            if role != "technician":
                linked_resource_id = None

            if not (username and role):
                flash("Username and role are required.", "error")
            elif role not in VALID_ROLES:
                flash("Role must be admin, planner, or technician.", "error")
            elif db.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone():
                flash(f"Username {username} already exists.", "error")
            else:
                db.execute(
                    "INSERT INTO users (username, role, linked_resource_id) VALUES (?, ?, ?)",
                    (username, role, linked_resource_id),
                )
                db.commit()
                flash(f"User {username} created.", "info")

        elif action == "update_user":
            user_id = request.form.get("user_id", "").strip()
            username = request.form.get("username", "").strip()
            role = request.form.get("role", "").strip()
            linked_resource_id = request.form.get("linked_resource_id", "").strip() or None
            if role != "technician":
                linked_resource_id = None

            if not (user_id and username and role):
                flash("Username and role are required.", "error")
            elif role not in VALID_ROLES:
                flash("Role must be admin, planner, or technician.", "error")
            elif db.execute("SELECT 1 FROM users WHERE username = ? AND id != ?", (username, user_id)).fetchone():
                flash(f"Username {username} already exists.", "error")
            else:
                db.execute(
                    "UPDATE users SET username = ?, role = ?, linked_resource_id = ? WHERE id = ?",
                    (username, role, linked_resource_id, user_id),
                )
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
            site = request.form.get("site", "").strip() or None

            if not (code and name and resource_type):
                flash("Resource code, name, and type are required.", "error")
            elif db.execute("SELECT 1 FROM resources WHERE code = ?", (code,)).fetchone():
                flash(f"Resource code {code} already exists.", "error")
            else:
                db.execute(
                    "INSERT INTO resources (code, name, resource_type, status, site) VALUES (?, ?, ?, ?, ?)",
                    (code, name, resource_type, status, site),
                )
                db.commit()
                flash("Resource saved.", "info")

        elif action == "update_resource":
            resource_id = request.form.get("resource_id", "").strip()
            code = request.form.get("code", "").strip()
            name = request.form.get("name", "").strip()
            resource_type = request.form.get("resource_type", "").strip()
            status = request.form.get("status", "").strip()
            site = request.form.get("site", "").strip() or None

            if not (resource_id and code and name and resource_type and status):
                flash("Resource code, name, type, and status are required.", "error")
            elif db.execute(
                "SELECT 1 FROM resources WHERE code = ? AND id != ?", (code, resource_id)
            ).fetchone():
                flash(f"Resource code {code} already exists.", "error")
            else:
                db.execute(
                    "UPDATE resources SET code = ?, name = ?, resource_type = ?, status = ?, site = ? WHERE id = ?",
                    (code, name, resource_type, status, site, resource_id),
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

        elif action == "create_exclusion_group":
            name = request.form.get("name", "").strip()
            notes = request.form.get("notes", "").strip()

            if not name:
                flash("Exclusion group name is required.", "error")
            elif db.execute("SELECT 1 FROM exclusion_groups WHERE name = ?", (name,)).fetchone():
                flash(f"Exclusion group {name} already exists.", "error")
            else:
                db.execute(
                    "INSERT INTO exclusion_groups (name, notes) VALUES (?, ?)",
                    (name, notes),
                )
                db.commit()
                flash(f"Exclusion group '{name}' created.", "info")

        elif action == "update_exclusion_group":
            group_id = request.form.get("group_id", "").strip()
            name = request.form.get("name", "").strip()
            notes = request.form.get("notes", "").strip()

            if not (group_id and name):
                flash("Exclusion group name is required.", "error")
            elif db.execute(
                "SELECT 1 FROM exclusion_groups WHERE name = ? AND id != ?", (name, group_id)
            ).fetchone():
                flash(f"Exclusion group {name} already exists.", "error")
            else:
                db.execute(
                    "UPDATE exclusion_groups SET name = ?, notes = ? WHERE id = ?",
                    (name, notes, group_id),
                )
                db.commit()
                flash(f"Exclusion group '{name}' updated.", "info")

        elif action == "delete_exclusion_group":
            group_id = request.form.get("group_id", "").strip()
            db.execute("DELETE FROM exclusion_groups WHERE id = ?", (group_id,))
            db.commit()
            flash("Exclusion group deleted.", "info")

        elif action == "assign_exclusion_resource":
            group_id = request.form.get("group_id", "").strip()
            resource_id = request.form.get("resource_id", "").strip()

            if not (group_id and resource_id):
                flash("Exclusion group and resource are required.", "error")
            else:
                db.execute(
                    "INSERT OR IGNORE INTO exclusion_group_resources (group_id, resource_id) VALUES (?, ?)",
                    (group_id, resource_id),
                )
                db.commit()
                flash("Resource added to exclusion group.", "info")

        elif action == "remove_exclusion_resource":
            group_id = request.form.get("group_id", "").strip()
            resource_id = request.form.get("resource_id", "").strip()

            db.execute(
                "DELETE FROM exclusion_group_resources WHERE group_id = ? AND resource_id = ?",
                (group_id, resource_id),
            )
            db.commit()
            flash("Resource removed from exclusion group.", "info")

        return redirect(url_for("admin.admin_manage"))

    return _render_admin(db)
