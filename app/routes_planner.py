from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from .db import get_db, init_db
from .routes_common import require_role

bp = Blueprint("planner", __name__, url_prefix="/planner")


def _load_planner_context(db) -> dict:
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

    orders = db.execute(
        "SELECT id, order_code, customer_name, product_name FROM customer_orders ORDER BY order_code"
    ).fetchall()

    capabilities = db.execute("SELECT id, name FROM capabilities ORDER BY name").fetchall()

    return {
        "tests": tests,
        "by_capability": by_capability,
        "orders": orders,
        "capabilities": capabilities,
    }


def _render_planner_orders(db, order_form_values=None, order_form_errors=None):
    context = _load_planner_context(db)
    context["order_form_values"] = order_form_values or {}
    context["order_form_errors"] = order_form_errors or {}
    return render_template("planner_orders.html", **context)


@bp.route("/", methods=["GET", "POST"])
@require_role("planner")
def planner_orders():
    init_db()
    db = get_db()

    if request.method == "POST":
        action = request.form.get("action", "assign_resource")

        if action == "create_order":
            order_code = request.form.get("order_code", "").strip()
            customer_name = request.form.get("customer_name", "").strip()
            product_name = request.form.get("product_name", "").strip()

            order_form_errors = {}
            if not order_code:
                order_form_errors["order_code"] = "Order code is required."
            elif db.execute("SELECT 1 FROM customer_orders WHERE order_code = ?", (order_code,)).fetchone():
                order_form_errors["order_code"] = f"Order code {order_code} already exists."
            if not customer_name:
                order_form_errors["customer_name"] = "Customer name is required."
            if not product_name:
                order_form_errors["product_name"] = "Product name is required."

            if order_form_errors:
                return _render_planner_orders(
                    db,
                    order_form_values={
                        "order_code": order_code,
                        "customer_name": customer_name,
                        "product_name": product_name,
                    },
                    order_form_errors=order_form_errors,
                )

            db.execute(
                "INSERT INTO customer_orders (order_code, customer_name, product_name) VALUES (?, ?, ?)",
                (order_code, customer_name, product_name),
            )
            db.commit()
            flash(f"Order {order_code} created.", "info")
            return redirect(url_for("planner.planner_orders"))

        if action == "add_test":
            order_id = request.form.get("order_id", "").strip()
            test_name = request.form.get("test_name", "").strip()
            required_capability_id = request.form.get("required_capability_id", "").strip() or None

            if not (order_id and test_name):
                flash("Order and test name are required.", "error")
            elif db.execute("SELECT 1 FROM customer_orders WHERE id = ?", (order_id,)).fetchone() is None:
                flash("Selected order does not exist.", "error")
            else:
                db.execute(
                    "INSERT INTO ordered_tests (order_id, test_name, required_capability_id) VALUES (?, ?, ?)",
                    (order_id, test_name, required_capability_id),
                )
                db.commit()
                flash(f"Test '{test_name}' added.", "info")

            return redirect(url_for("planner.planner_orders"))

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

    return _render_planner_orders(db)