from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from .db import get_db, init_db
from .routes_common import require_role

bp = Blueprint("planner", __name__, url_prefix="/planner")


@bp.route("/", methods=["GET", "POST"])
@require_role("planner")
def planner_orders():
    init_db()
    db = get_db()

    if request.method == "POST":
        ordered_test_id = request.form.get("ordered_test_id", "").strip()
        resource_id = request.form.get("resource_id", "").strip()

        if not (ordered_test_id and resource_id):
            flash("Ordered test and resource are required.", "error")
            return redirect(url_for("planner.planner_orders"))

        valid = db.execute(
            """
            SELECT 1
            FROM ordered_tests ot
            JOIN resource_capabilities rc
              ON rc.resource_id = ?
             AND rc.capability_id = ot.required_capability_id
            WHERE ot.id = ?
            """,
            (resource_id, ordered_test_id),
        ).fetchone()

        if valid is None:
            flash("Selected resource does not match required capability.", "error")
            return redirect(url_for("planner.planner_orders"))

        db.execute(
            """
            INSERT INTO allocations (ordered_test_id, resource_id, planner_user_id, notes)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(ordered_test_id)
            DO UPDATE SET
                resource_id = excluded.resource_id,
                planner_user_id = excluded.planner_user_id,
                notes = excluded.notes
            """,
            (ordered_test_id, resource_id, session.get("user_id"), "Assigned by planner"),
        )
        db.commit()
        flash("Allocation saved.", "info")
        return redirect(url_for("planner.planner_orders"))

    tests = db.execute(
        """
        SELECT
            ot.id AS ordered_test_id,
            o.order_code,
            o.customer_name,
            ot.test_name,
            c.id AS capability_id,
            c.name AS capability_name,
            a.resource_id AS allocated_resource_id,
            r.code AS allocated_resource_code,
            r.name AS allocated_resource_name
        FROM ordered_tests ot
        JOIN customer_orders o ON o.id = ot.order_id
        LEFT JOIN capabilities c ON c.id = ot.required_capability_id
        LEFT JOIN allocations a ON a.ordered_test_id = ot.id
        LEFT JOIN resources r ON r.id = a.resource_id
        ORDER BY o.order_code, ot.id
        """
    ).fetchall()

    candidates = db.execute(
        """
        SELECT
            rc.capability_id,
            r.id AS resource_id,
            r.code,
            r.name,
            r.status
        FROM resource_capabilities rc
        JOIN resources r ON r.id = rc.resource_id
        ORDER BY rc.capability_id, r.code
        """
    ).fetchall()

    by_capability: dict[int, list] = {}
    for row in candidates:
        by_capability.setdefault(row["capability_id"], []).append(row)

    return render_template("planner_orders.html", tests=tests, by_capability=by_capability)