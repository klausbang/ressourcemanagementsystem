import sqlite3
from datetime import datetime

from flask import Blueprint, flash, redirect, request, session, url_for

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
RESOURCE_TYPES = ["equipment", "facility", "technician", "procedure"]

MAPPING_SORTABLE_KEYS = {"code", "resource_name", "capability_name"}
MAPPING_DUP_KEYS = ["code", "resource_name", "capability_name"]

EXCLUSION_GROUP_SORTABLE_KEYS = {"name", "notes"}
EXCLUSION_GROUP_DUP_KEYS = ["name", "notes"]

TEMPLATE_SORTABLE_KEYS = {"name", "notes"}
TEMPLATE_DUP_KEYS = ["name", "notes"]

PROPOSAL_SORTABLE_KEYS = {"path", "proposal_type", "title", "submitted_by_username", "created_at", "status"}
PROPOSAL_DUP_KEYS = ["path", "title", "submitted_by_username"]

ABSENCE_SORTABLE_KEYS = {"resource_code", "resource_name", "start_date", "end_date", "reason"}
ABSENCE_DUP_KEYS = ["resource_code", "start_date", "end_date"]

CUSTOMER_SORTABLE_KEYS = {"name", "contact_name", "contact_email", "contact_phone"}
CUSTOMER_DUP_KEYS = ["name"]

# Which tab an action's result belongs on, so a POST redirect lands back where it was
# submitted from instead of always resetting to the first ("Users") tab - the same fix
# already applied to the Planner page's tabs.
ACTION_TAB = {
    "create_user": "users", "update_user": "users", "delete_user": "users",
    "create_capability": "capabilities", "update_capability": "capabilities", "delete_capability": "capabilities",
    "create_resource": "resources", "update_resource": "resources", "delete_resource": "resources",
    "assign_capability": "mappings", "remove_capability": "mappings",
    "create_exclusion_group": "exclusion", "update_exclusion_group": "exclusion", "delete_exclusion_group": "exclusion",
    "assign_exclusion_resource": "exclusion", "remove_exclusion_resource": "exclusion",
    "create_template": "templates", "update_template": "templates", "delete_template": "templates",
    "add_template_item": "templates", "update_template_item": "templates",
    "delete_template_item": "templates", "move_template_item": "templates",
    "create_absence": "absences", "delete_absence": "absences",
    "update_proposal": "proposals", "delete_proposal": "proposals",
    "create_customer": "customers", "update_customer": "customers", "delete_customer": "customers",
}


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

    templates = rows_with_meta(
        db.execute("SELECT id, name, notes FROM activity_templates ORDER BY name").fetchall(),
        dup_keys=TEMPLATE_DUP_KEYS,
        sort_key=request.args.get("templates_sort"),
        sort_dir=request.args.get("templates_dir", "asc"),
        sortable_keys=TEMPLATE_SORTABLE_KEYS,
    )
    item_rows = db.execute(
        """
        SELECT ati.id, ati.template_id, ati.step_number, ati.activity_name, ati.required_capability_id,
               c.name AS capability_name
        FROM activity_template_items ati
        LEFT JOIN capabilities c ON c.id = ati.required_capability_id
        ORDER BY ati.template_id, ati.step_number
        """
    ).fetchall()
    items_by_template: dict[int, list] = {}
    for row in item_rows:
        items_by_template.setdefault(row["template_id"], []).append(dict(row))
    for template in templates:
        template["items"] = items_by_template.get(template["id"], [])

    absences = rows_with_meta(
        db.execute(
            """
            SELECT a.id, a.resource_id, r.code AS resource_code, r.name AS resource_name,
                   a.start_date, a.end_date, a.reason
            FROM staff_absences a
            JOIN resources r ON r.id = a.resource_id
            ORDER BY a.start_date
            """
        ).fetchall(),
        dup_keys=ABSENCE_DUP_KEYS,
        sort_key=request.args.get("absences_sort"),
        sort_dir=request.args.get("absences_dir", "asc"),
        sortable_keys=ABSENCE_SORTABLE_KEYS,
    )

    proposals = rows_with_meta(
        db.execute(
            """
            SELECT id, path, proposal_type, title, description, submitted_by_username,
                   created_at, status, admin_comment, updated_at
            FROM proposals
            ORDER BY created_at DESC
            """
        ).fetchall(),
        dup_keys=PROPOSAL_DUP_KEYS,
        sort_key=request.args.get("proposals_sort"),
        sort_dir=request.args.get("proposals_dir", "asc"),
        sortable_keys=PROPOSAL_SORTABLE_KEYS,
    )

    customers = rows_with_meta(
        db.execute(
            """
            SELECT id, name, contact_name, contact_email, contact_phone, address, created_at
            FROM customers
            ORDER BY name
            """
        ).fetchall(),
        dup_keys=CUSTOMER_DUP_KEYS,
        sort_key=request.args.get("customers_sort"),
        sort_dir=request.args.get("customers_dir", "asc"),
        sortable_keys=CUSTOMER_SORTABLE_KEYS,
    )
    # A customer's "complete" profile is derived at read time (BR-001), not a stored flag:
    # it just needs a contact name, email, and address to be considered fully filled in.
    for c in customers:
        c["is_complete"] = bool(c["contact_name"] and c["contact_email"] and c["address"])
    incomplete_customers = [c for c in customers if not c["is_complete"]]

    valid_tabs = {"users", "capabilities", "resources", "mappings", "exclusion", "templates", "absences", "proposals", "customers"}
    active_tab = request.args.get("tab", "users")
    if active_tab not in valid_tabs:
        active_tab = "users"

    return {
        "active_tab": active_tab,
        "users": users,
        "resource_types": RESOURCE_TYPES,
        "resources": resources,
        "capabilities": capabilities,
        "mappings": mappings,
        "technician_resources": technician_resources,
        "exclusion_groups": exclusion_groups,
        "templates": templates,
        "absences": absences,
        "proposals": proposals,
        "customers": customers,
        "incomplete_customers": incomplete_customers,
    }


def _resequence_template_items(db, template_id) -> None:
    """Renumber a template's items 1..N in their current relative order (after a delete)."""
    rows = db.execute(
        "SELECT id FROM activity_template_items WHERE template_id = ? ORDER BY step_number", (template_id,)
    ).fetchall()
    for step_number, row in enumerate(rows, start=1):
        db.execute(
            "UPDATE activity_template_items SET step_number = ? WHERE id = ?", (step_number, row["id"])
        )


def _touch_template(db, template_id) -> None:
    """Mark a template's activity sequence as changed, so any already-applied
    template_applications batch can be flagged as out of date with what the template now
    contains. Only bumped for changes to the template's *items* (add/edit/delete/reorder),
    not a plain name/notes edit, since only the item sequence is what a batch would need
    re-syncing against."""
    db.execute("UPDATE activity_templates SET version = version + 1 WHERE id = ?", (template_id,))


def _render_admin(db, active_tab_override: str | None = None, **extra):
    context = _load_admin_context(db)
    if active_tab_override:
        context["active_tab"] = active_tab_override
    context.update(extra)
    return render_ui("admin_manage.html", **context)


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

            resource_form_error = None
            if not (code and name and resource_type):
                resource_form_error = "Resource code, name, and type are required."
            elif resource_type not in RESOURCE_TYPES:
                resource_form_error = f"Resource type must be one of: {', '.join(RESOURCE_TYPES)}."
            elif db.execute("SELECT 1 FROM resources WHERE code = ?", (code,)).fetchone():
                resource_form_error = f"Resource code '{code}' is already in use. Choose a different code."

            if resource_form_error:
                # Re-render in place (rather than the shared redirect below) so the admin's
                # typed values aren't silently lost - a duplicate code otherwise looked like
                # "the save did nothing", since the create-resource form reset to blank with
                # only an easy-to-miss flash message as feedback.
                flash(resource_form_error, "error")
                return _render_admin(
                    db,
                    active_tab_override="resources",
                    resource_form_values={
                        "code": code, "name": name, "resource_type": resource_type,
                        "status": status, "site": site or "",
                    },
                )

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
            elif resource_type not in RESOURCE_TYPES:
                flash(f"Resource type must be one of: {', '.join(RESOURCE_TYPES)}.", "error")
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

        elif action == "create_template":
            name = request.form.get("name", "").strip()
            notes = request.form.get("notes", "").strip()

            if not name:
                flash("Template name is required.", "error")
            elif db.execute("SELECT 1 FROM activity_templates WHERE name = ?", (name,)).fetchone():
                flash(f"Template {name} already exists.", "error")
            else:
                db.execute(
                    "INSERT INTO activity_templates (name, notes) VALUES (?, ?)",
                    (name, notes),
                )
                db.commit()
                flash(f"Template '{name}' created.", "info")

        elif action == "update_template":
            template_id = request.form.get("template_id", "").strip()
            name = request.form.get("name", "").strip()
            notes = request.form.get("notes", "").strip()

            if not (template_id and name):
                flash("Template name is required.", "error")
            elif db.execute(
                "SELECT 1 FROM activity_templates WHERE name = ? AND id != ?", (name, template_id)
            ).fetchone():
                flash(f"Template {name} already exists.", "error")
            else:
                db.execute(
                    "UPDATE activity_templates SET name = ?, notes = ? WHERE id = ?",
                    (name, notes, template_id),
                )
                db.commit()
                flash(f"Template '{name}' updated.", "info")

        elif action == "delete_template":
            template_id = request.form.get("template_id", "").strip()
            db.execute("DELETE FROM activity_templates WHERE id = ?", (template_id,))
            db.commit()
            flash("Template deleted.", "info")

        elif action == "add_template_item":
            template_id = request.form.get("template_id", "").strip()
            activity_name = request.form.get("activity_name", "").strip()
            required_capability_id = request.form.get("required_capability_id", "").strip() or None

            if not (template_id and activity_name):
                flash("Template and activity name are required.", "error")
            else:
                next_step = db.execute(
                    "SELECT COALESCE(MAX(step_number), 0) + 1 AS n FROM activity_template_items WHERE template_id = ?",
                    (template_id,),
                ).fetchone()["n"]
                db.execute(
                    """
                    INSERT INTO activity_template_items (template_id, step_number, activity_name, required_capability_id)
                    VALUES (?, ?, ?, ?)
                    """,
                    (template_id, next_step, activity_name, required_capability_id),
                )
                _touch_template(db, template_id)
                db.commit()
                flash(f"Activity '{activity_name}' added to template.", "info")

        elif action == "update_template_item":
            item_id = request.form.get("item_id", "").strip()
            activity_name = request.form.get("activity_name", "").strip()
            required_capability_id = request.form.get("required_capability_id", "").strip() or None

            if not (item_id and activity_name):
                flash("Activity name is required.", "error")
            else:
                row = db.execute("SELECT template_id FROM activity_template_items WHERE id = ?", (item_id,)).fetchone()
                db.execute(
                    "UPDATE activity_template_items SET activity_name = ?, required_capability_id = ? WHERE id = ?",
                    (activity_name, required_capability_id, item_id),
                )
                if row:
                    _touch_template(db, row["template_id"])
                db.commit()
                flash(f"Activity '{activity_name}' updated.", "info")

        elif action == "delete_template_item":
            item_id = request.form.get("item_id", "").strip()
            row = db.execute("SELECT template_id FROM activity_template_items WHERE id = ?", (item_id,)).fetchone()
            db.execute("DELETE FROM activity_template_items WHERE id = ?", (item_id,))
            if row:
                _resequence_template_items(db, row["template_id"])
                _touch_template(db, row["template_id"])
            db.commit()
            flash("Activity removed from template.", "info")

        elif action == "move_template_item":
            item_id = request.form.get("item_id", "").strip()
            direction = request.form.get("direction", "").strip()
            item = db.execute(
                "SELECT id, template_id, step_number FROM activity_template_items WHERE id = ?", (item_id,)
            ).fetchone()

            if item is None or direction not in ("up", "down"):
                flash("Cannot move that activity.", "error")
            else:
                neighbor = db.execute(
                    f"""
                    SELECT id, step_number FROM activity_template_items
                    WHERE template_id = ? AND step_number {'<' if direction == 'up' else '>'} ?
                    ORDER BY step_number {'DESC' if direction == 'up' else 'ASC'}
                    LIMIT 1
                    """,
                    (item["template_id"], item["step_number"]),
                ).fetchone()
                if neighbor is None:
                    flash("Already at that end of the template.", "info")
                else:
                    db.execute(
                        "UPDATE activity_template_items SET step_number = ? WHERE id = ?",
                        (neighbor["step_number"], item["id"]),
                    )
                    db.execute(
                        "UPDATE activity_template_items SET step_number = ? WHERE id = ?",
                        (item["step_number"], neighbor["id"]),
                    )
                    _touch_template(db, item["template_id"])
                    db.commit()
                    flash("Activity reordered.", "info")

        elif action == "create_absence":
            resource_id = request.form.get("resource_id", "").strip()
            start_date = request.form.get("start_date", "").strip()
            end_date = request.form.get("end_date", "").strip()
            reason = request.form.get("reason", "").strip() or None

            if not (resource_id and start_date and end_date):
                flash("Technician, start date, and end date are required.", "error")
            elif end_date < start_date:
                flash("End date cannot be before start date.", "error")
            else:
                db.execute(
                    "INSERT INTO staff_absences (resource_id, start_date, end_date, reason) VALUES (?, ?, ?, ?)",
                    (resource_id, start_date, end_date, reason),
                )
                db.commit()
                flash("Absence recorded.", "info")

        elif action == "delete_absence":
            absence_id = request.form.get("absence_id", "").strip()
            db.execute("DELETE FROM staff_absences WHERE id = ?", (absence_id,))
            db.commit()
            flash("Absence deleted.", "info")

        elif action == "update_proposal":
            proposal_id = request.form.get("proposal_id", "").strip()
            title = request.form.get("title", "").strip()
            description = request.form.get("description", "").strip() or None
            proposal_type = request.form.get("proposal_type", "").strip()
            status = request.form.get("status", "").strip()
            admin_comment = request.form.get("admin_comment", "").strip() or None
            valid_statuses = ("new", "accepted", "in_progress", "done", "rejected")

            if not (proposal_id and title and proposal_type in ("enhancement", "bug") and status in valid_statuses):
                flash("A valid proposal, title, type, and status are required.", "error")
            else:
                db.execute(
                    """
                    UPDATE proposals
                    SET title = ?, description = ?, proposal_type = ?, status = ?, admin_comment = ?,
                        admin_user_id = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        title, description, proposal_type, status, admin_comment,
                        session.get("user_id"), datetime.now().strftime("%Y-%m-%d %H:%M"), proposal_id,
                    ),
                )
                db.commit()
                flash("Proposal updated.", "info")

        elif action == "delete_proposal":
            proposal_id = request.form.get("proposal_id", "").strip()
            db.execute("DELETE FROM proposals WHERE id = ?", (proposal_id,))
            db.commit()
            flash("Proposal deleted.", "info")

        elif action == "create_customer":
            name = request.form.get("name", "").strip()
            contact_name = request.form.get("contact_name", "").strip() or None
            contact_email = request.form.get("contact_email", "").strip() or None
            contact_phone = request.form.get("contact_phone", "").strip() or None
            address = request.form.get("address", "").strip() or None

            if not name:
                flash("Customer name is required.", "error")
            elif db.execute("SELECT 1 FROM customers WHERE name = ?", (name,)).fetchone():
                flash(f"Customer '{name}' already exists.", "error")
            else:
                db.execute(
                    """
                    INSERT INTO customers (name, contact_name, contact_email, contact_phone, address, created_at, created_by_user_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (name, contact_name, contact_email, contact_phone, address, datetime.now().strftime("%Y-%m-%d %H:%M"), session.get("user_id")),
                )
                db.commit()
                flash(f"Customer '{name}' added.", "info")

        elif action == "update_customer":
            customer_id = request.form.get("customer_id", "").strip()
            name = request.form.get("name", "").strip()
            contact_name = request.form.get("contact_name", "").strip() or None
            contact_email = request.form.get("contact_email", "").strip() or None
            contact_phone = request.form.get("contact_phone", "").strip() or None
            address = request.form.get("address", "").strip() or None

            if not (customer_id and name):
                flash("Customer name is required.", "error")
            elif db.execute(
                "SELECT 1 FROM customers WHERE name = ? AND id != ?", (name, customer_id)
            ).fetchone():
                flash(f"Customer '{name}' already exists.", "error")
            else:
                db.execute(
                    """
                    UPDATE customers
                    SET name = ?, contact_name = ?, contact_email = ?, contact_phone = ?, address = ?
                    WHERE id = ?
                    """,
                    (name, contact_name, contact_email, contact_phone, address, customer_id),
                )
                # customer_orders.customer_name is a denormalized snapshot (kept so every
                # existing order display/report continues to work unchanged) - refresh it
                # for any order pointing at this customer so a rename doesn't leave orders
                # showing the old name.
                db.execute(
                    "UPDATE customer_orders SET customer_name = ? WHERE customer_id = ?", (name, customer_id)
                )
                db.commit()
                flash(f"Customer '{name}' updated.", "info")

        elif action == "delete_customer":
            customer_id = request.form.get("customer_id", "").strip()
            if db.execute("SELECT 1 FROM customer_orders WHERE customer_id = ?", (customer_id,)).fetchone():
                flash("Cannot delete a customer still referenced by an order.", "error")
            else:
                db.execute("DELETE FROM customers WHERE id = ?", (customer_id,))
                db.commit()
                flash("Customer deleted.", "info")

        return redirect(url_for("admin.admin_manage", tab=ACTION_TAB.get(action, "users")))

    return _render_admin(db)
