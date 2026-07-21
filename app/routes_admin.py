from flask import Blueprint, flash, redirect, render_template, request, url_for

from .db import get_db, init_db
from .routes_common import require_role

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.route("/", methods=["GET", "POST"])
@require_role("admin")
def admin_manage():
    init_db()
    db = get_db()

    action = request.form.get("action", "")
    if request.method == "POST":
        if action == "create_capability":
            name = request.form.get("name", "").strip()
            description = request.form.get("description", "").strip()
            if not name:
                flash("Capability name is required.", "error")
            else:
                db.execute(
                    "INSERT OR IGNORE INTO capabilities (name, description) VALUES (?, ?)",
                    (name, description),
                )
                db.commit()
                flash("Capability saved.", "info")

        elif action == "create_resource":
            code = request.form.get("code", "").strip()
            name = request.form.get("name", "").strip()
            resource_type = request.form.get("resource_type", "").strip()
            if not (code and name and resource_type):
                flash("Resource code, name, and type are required.", "error")
            else:
                db.execute(
                    "INSERT OR IGNORE INTO resources (code, name, resource_type, status) VALUES (?, ?, ?, 'available')",
                    (code, name, resource_type),
                )
                db.commit()
                flash("Resource saved.", "info")

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

        return redirect(url_for("admin.admin_manage"))

    resources = db.execute("SELECT id, code, name, resource_type, status FROM resources ORDER BY code").fetchall()
    capabilities = db.execute("SELECT id, name, description FROM capabilities ORDER BY name").fetchall()
    mappings = db.execute(
        """
        SELECT r.code, r.name AS resource_name, c.name AS capability_name
        FROM resource_capabilities rc
        JOIN resources r ON r.id = rc.resource_id
        JOIN capabilities c ON c.id = rc.capability_id
        ORDER BY r.code, c.name
        """
    ).fetchall()

    return render_template(
        "admin_manage.html",
        resources=resources,
        capabilities=capabilities,
        mappings=mappings,
    )