from flask import Blueprint, flash, redirect, request, session, url_for

from .db import get_db, init_db
from .routes_common import render_ui, require_role
from .table_utils import rows_with_meta

bp = Blueprint("planner", __name__, url_prefix="/planner")

ORDER_SORTABLE_KEYS = {"order_code", "customer_name", "product_name"}
ORDER_DUP_KEYS = ["order_code", "customer_name", "product_name"]

TEST_SORTABLE_KEYS = {"order_code", "test_name", "capability_name"}
TEST_DUP_KEYS = ["order_code", "test_name", "capability_name"]

ALLOC_SORTABLE_KEYS = {"order_code", "customer_name", "test_name", "capability_name", "allocated_summary"}
ALLOC_DUP_KEYS = ["order_code", "customer_name", "test_name", "capability_name", "allocated_summary"]


def _load_planner_context(db) -> dict:
    raw_tests = db.execute(
        """
        SELECT
            ot.id AS ordered_test_id,
            o.order_code,
            o.customer_name,
            ot.test_name,
            c.id AS capability_id,
            c.name AS capability_name
        FROM ordered_tests ot
        JOIN customer_orders o ON o.id = ot.order_id
        LEFT JOIN capabilities c ON c.id = ot.required_capability_id
        ORDER BY o.order_code, ot.id
        """
    ).fetchall()

    ordered_tests_rows = rows_with_meta(
        raw_tests,
        dup_keys=TEST_DUP_KEYS,
        sort_key=request.args.get("tests_sort"),
        sort_dir=request.args.get("tests_dir", "asc"),
        sortable_keys=TEST_SORTABLE_KEYS,
    )

    allocation_rows = db.execute(
        """
        SELECT
            a.id AS allocation_id,
            a.ordered_test_id,
            r.id AS resource_id,
            r.code AS resource_code,
            r.name AS resource_name,
            r.resource_type AS resource_type
        FROM allocations a
        JOIN resources r ON r.id = a.resource_id
        ORDER BY a.ordered_test_id, r.code
        """
    ).fetchall()

    allocations_by_test: dict[int, list] = {}
    for row in allocation_rows:
        allocations_by_test.setdefault(row["ordered_test_id"], []).append(dict(row))

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

    tests_for_alloc = []
    for row in raw_tests:
        item = dict(row)
        allocated = allocations_by_test.get(item["ordered_test_id"], [])
        item["allocated_resources"] = allocated
        item["allocated_summary"] = ", ".join(r["resource_code"] for r in allocated)
        assigned_ids = {r["resource_id"] for r in allocated}
        item["available_candidates"] = [
            c for c in by_capability.get(item["capability_id"], []) if c["resource_id"] not in assigned_ids
        ]
        tests_for_alloc.append(item)

    tests = rows_with_meta(
        tests_for_alloc,
        dup_keys=ALLOC_DUP_KEYS,
        sort_key=request.args.get("alloc_sort"),
        sort_dir=request.args.get("alloc_dir", "asc"),
        sortable_keys=ALLOC_SORTABLE_KEYS,
    )

    orders = rows_with_meta(
        db.execute(
            "SELECT id, order_code, customer_name, product_name FROM customer_orders ORDER BY order_code"
        ).fetchall(),
        dup_keys=ORDER_DUP_KEYS,
        sort_key=request.args.get("orders_sort"),
        sort_dir=request.args.get("orders_dir", "asc"),
        sortable_keys=ORDER_SORTABLE_KEYS,
    )

    capabilities = db.execute("SELECT id, name FROM capabilities ORDER BY name").fetchall()

    return {
        "tests": tests,
        "ordered_tests_rows": ordered_tests_rows,
        "by_capability": by_capability,
        "orders": orders,
        "capabilities": capabilities,
    }


def _render_planner_orders(db, order_form_values=None, order_form_errors=None):
    context = _load_planner_context(db)
    context["order_form_values"] = order_form_values or {}
    context["order_form_errors"] = order_form_errors or {}
    return render_ui("planner_orders.html", **context)


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

        if action == "update_order":
            order_id = request.form.get("order_id", "").strip()
            order_code = request.form.get("order_code", "").strip()
            customer_name = request.form.get("customer_name", "").strip()
            product_name = request.form.get("product_name", "").strip()

            if not (order_id and order_code and customer_name and product_name):
                flash("Order code, customer name, and product name are required.", "error")
            elif db.execute(
                "SELECT 1 FROM customer_orders WHERE order_code = ? AND id != ?", (order_code, order_id)
            ).fetchone():
                flash(f"Order code {order_code} already exists.", "error")
            else:
                db.execute(
                    "UPDATE customer_orders SET order_code = ?, customer_name = ?, product_name = ? WHERE id = ?",
                    (order_code, customer_name, product_name, order_id),
                )
                db.commit()
                flash(f"Order {order_code} updated.", "info")

            return redirect(url_for("planner.planner_orders"))

        if action == "delete_order":
            order_id = request.form.get("order_id", "").strip()
            db.execute("DELETE FROM customer_orders WHERE id = ?", (order_id,))
            db.commit()
            flash("Order deleted, along with its ordered tests and allocations.", "info")
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

        if action == "update_test":
            ordered_test_id = request.form.get("ordered_test_id", "").strip()
            test_name = request.form.get("test_name", "").strip()
            required_capability_id = request.form.get("required_capability_id", "").strip() or None

            if not (ordered_test_id and test_name):
                flash("Test name is required.", "error")
            else:
                db.execute(
                    "UPDATE ordered_tests SET test_name = ?, required_capability_id = ? WHERE id = ?",
                    (test_name, required_capability_id, ordered_test_id),
                )
                db.commit()
                flash(f"Test '{test_name}' updated.", "info")

            return redirect(url_for("planner.planner_orders"))

        if action == "delete_test":
            ordered_test_id = request.form.get("ordered_test_id", "").strip()
            db.execute("DELETE FROM ordered_tests WHERE id = ?", (ordered_test_id,))
            db.commit()
            flash("Ordered test deleted, along with its allocation (if any).", "info")
            return redirect(url_for("planner.planner_orders"))

        if action == "delete_allocation":
            allocation_id = request.form.get("allocation_id", "").strip()
            db.execute("DELETE FROM allocations WHERE id = ?", (allocation_id,))
            db.commit()
            flash("Resource unassigned from test.", "info")
            return redirect(url_for("planner.planner_orders"))

        if action == "assign_resource":
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
            elif db.execute(
                "SELECT 1 FROM allocations WHERE ordered_test_id = ? AND resource_id = ?",
                (ordered_test_id, resource_id),
            ).fetchone():
                flash("That resource is already assigned to this test.", "error")
            else:
                db.execute(
                    """
                    INSERT INTO allocations (ordered_test_id, resource_id, planner_user_id, notes)
                    VALUES (?, ?, ?, ?)
                    """,
                    (ordered_test_id, resource_id, session.get("user_id"), "Assigned by planner"),
                )
                db.commit()
                flash("Resource assigned to test.", "info")

            return redirect(url_for("planner.planner_orders"))

    return _render_planner_orders(db)
