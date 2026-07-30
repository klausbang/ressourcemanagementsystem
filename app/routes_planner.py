import math
from datetime import date, datetime, time, timedelta

from flask import Blueprint, flash, redirect, request, session, url_for

from .db import get_db, init_db
from .routes_common import render_ui, require_role
from .table_utils import rows_with_meta

bp = Blueprint("planner", __name__, url_prefix="/planner")

ORDER_SORTABLE_KEYS = {"order_code", "customer_name", "product_name"}
ORDER_DUP_KEYS = ["order_code", "customer_name", "product_name"]

EUT_SORTABLE_KEYS = {"order_code", "name", "serial_number"}
EUT_DUP_KEYS = ["order_code", "name", "serial_number"]

TEST_SORTABLE_KEYS = {"order_code", "eut_name", "test_name", "capability_name"}
TEST_DUP_KEYS = ["order_code", "eut_name", "test_name", "capability_name"]

ALLOC_SORTABLE_KEYS = {"order_code", "customer_name", "eut_name", "test_name", "capability_name", "allocated_summary"}
ALLOC_DUP_KEYS = ["order_code", "customer_name", "eut_name", "test_name", "capability_name", "allocated_summary"]

SCHEDULE_WINDOW_HOURS = 24
SCHEDULE_DEFAULT_HOUR = 8  # assumed start-of-shift time when only a scheduled_date (no time) is known


def _parse_date_only(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value.split(" ")[0], "%Y-%m-%d").date()
    except ValueError:
        return None


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(value.strip(), fmt)
        except ValueError:
            continue
    return None


def _schedule_view_day() -> date:
    """The day being viewed, from the ?sched_start=YYYY-MM-DD query param."""
    return _parse_date_only(request.args.get("sched_start")) or date.today()


def _load_schedule_context(db) -> dict:
    view_day = _schedule_view_day()
    window_start = datetime.combine(view_day, time.min)
    window_end = window_start + timedelta(hours=SCHEDULE_WINDOW_HOURS)
    now = datetime.now()

    hours = []
    for i in range(SCHEDULE_WINDOW_HOURS):
        slot_start = window_start + timedelta(hours=i)
        hours.append(
            {
                "hour": slot_start.hour,
                "label": f"{slot_start.hour:02d}",
                "is_current": view_day == now.date() and slot_start.hour == now.hour,
            }
        )

    raw = db.execute(
        """
        SELECT
            ot.id AS ordered_test_id,
            o.order_code, o.customer_name, o.product_name,
            ot.test_name,
            c.name AS capability_name,
            wo.id AS work_order_id, wo.work_order_code, wo.status AS wo_status,
            wo.scheduled_date, wo.started_at, wo.completed_at, wo.result,
            tech.username AS technician_username
        FROM ordered_tests ot
        JOIN customer_orders o ON o.id = ot.order_id
        LEFT JOIN capabilities c ON c.id = ot.required_capability_id
        LEFT JOIN work_orders wo ON wo.ordered_test_id = ot.id
        LEFT JOIN users tech ON tech.id = wo.technician_user_id
        ORDER BY o.order_code, ot.id
        """
    ).fetchall()

    allocation_rows = db.execute(
        """
        SELECT a.ordered_test_id, r.code, r.name, r.resource_type
        FROM allocations a
        JOIN resources r ON r.id = a.resource_id
        ORDER BY a.ordered_test_id, r.code
        """
    ).fetchall()
    resources_by_test: dict[int, list] = {}
    for row in allocation_rows:
        resources_by_test.setdefault(row["ordered_test_id"], []).append(dict(row))

    visible_rows = []
    unscheduled = []

    for row in raw:
        item = dict(row)
        item["assigned_resources"] = resources_by_test.get(item["ordered_test_id"], [])

        if not item["work_order_id"]:
            unscheduled.append(item)
            continue

        bar_start = _parse_datetime(item["started_at"])
        if bar_start is None:
            sd = _parse_date_only(item["scheduled_date"])
            if sd:
                bar_start = datetime.combine(sd, time(SCHEDULE_DEFAULT_HOUR, 0))

        if bar_start is None:
            unscheduled.append(item)
            continue

        bar_end = _parse_datetime(item["completed_at"])
        if bar_end is None:
            if item["wo_status"] in ("in_progress", "on_hold"):
                bar_end = now
            else:
                bar_end = bar_start + timedelta(hours=1)
        if bar_end <= bar_start:
            bar_end = bar_start + timedelta(hours=1)

        if bar_end <= window_start or bar_start >= window_end:
            continue  # entirely outside the visible day; reachable via prev/next

        clipped_start = max(bar_start, window_start)
        clipped_end = min(bar_end, window_end)

        start_offset = int((clipped_start - window_start).total_seconds() // 3600)
        end_offset = math.ceil((clipped_end - window_start).total_seconds() / 3600)
        start_offset = max(0, min(start_offset, SCHEDULE_WINDOW_HOURS - 1))
        end_offset = max(start_offset + 1, min(end_offset, SCHEDULE_WINDOW_HOURS))

        item["col_offset"] = start_offset
        item["col_span"] = end_offset - start_offset
        item["clipped_before"] = clipped_start > bar_start
        item["clipped_after"] = clipped_end < bar_end
        visible_rows.append(item)

    visible_rows.sort(key=lambda r: (r["col_offset"], r["order_code"]))

    return {
        "view_day": view_day,
        "window_slot_count": SCHEDULE_WINDOW_HOURS,
        "schedule_hours": hours,
        "schedule_rows": visible_rows,
        "unscheduled_tests": unscheduled,
        "sched_prev": (view_day - timedelta(days=1)).isoformat(),
        "sched_next": (view_day + timedelta(days=1)).isoformat(),
        "sched_today": date.today().isoformat(),
        "is_schedule_tab": bool(request.args.get("sched_start")),
    }


def _load_planner_context(db) -> dict:
    raw_euts = db.execute(
        """
        SELECT
            e.id, e.order_id, e.name, e.serial_number, e.notes,
            o.order_code
        FROM euts e
        JOIN customer_orders o ON o.id = e.order_id
        ORDER BY o.order_code, e.name
        """
    ).fetchall()

    euts_rows = rows_with_meta(
        raw_euts,
        dup_keys=EUT_DUP_KEYS,
        sort_key=request.args.get("euts_sort"),
        sort_dir=request.args.get("euts_dir", "asc"),
        sortable_keys=EUT_SORTABLE_KEYS,
    )

    raw_tests = db.execute(
        """
        SELECT
            ot.id AS ordered_test_id,
            o.order_code,
            o.customer_name,
            ot.eut_id,
            e.name AS eut_name,
            ot.test_name,
            c.id AS capability_id,
            c.name AS capability_name
        FROM ordered_tests ot
        JOIN customer_orders o ON o.id = ot.order_id
        LEFT JOIN euts e ON e.id = ot.eut_id
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

    context = {
        "tests": tests,
        "ordered_tests_rows": ordered_tests_rows,
        "by_capability": by_capability,
        "orders": orders,
        "euts": euts_rows,
        "capabilities": capabilities,
    }
    context.update(_load_schedule_context(db))
    return context


def _render_planner_orders(db, order_form_values=None, order_form_errors=None, eut_form_values=None, eut_form_errors=None):
    context = _load_planner_context(db)
    context["order_form_values"] = order_form_values or {}
    context["order_form_errors"] = order_form_errors or {}
    context["eut_form_values"] = eut_form_values or {}
    context["eut_form_errors"] = eut_form_errors or {}
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

        if action == "create_eut":
            order_id = request.form.get("order_id", "").strip()
            name = request.form.get("name", "").strip()
            serial_number = request.form.get("serial_number", "").strip() or None

            eut_form_errors = {}
            if not order_id:
                eut_form_errors["order_id"] = "Order is required."
            elif db.execute("SELECT 1 FROM customer_orders WHERE id = ?", (order_id,)).fetchone() is None:
                eut_form_errors["order_id"] = "Selected order does not exist."
            if not name:
                eut_form_errors["name"] = "EUT name is required."

            if eut_form_errors:
                return _render_planner_orders(
                    db,
                    eut_form_values={"order_id": order_id, "name": name, "serial_number": serial_number or ""},
                    eut_form_errors=eut_form_errors,
                )

            db.execute(
                "INSERT INTO euts (order_id, name, serial_number) VALUES (?, ?, ?)",
                (order_id, name, serial_number),
            )
            db.commit()
            flash(f"EUT '{name}' added.", "info")
            return redirect(url_for("planner.planner_orders"))

        if action == "update_eut":
            eut_id = request.form.get("eut_id", "").strip()
            name = request.form.get("name", "").strip()
            serial_number = request.form.get("serial_number", "").strip() or None

            if not (eut_id and name):
                flash("EUT name is required.", "error")
            else:
                db.execute(
                    "UPDATE euts SET name = ?, serial_number = ? WHERE id = ?",
                    (name, serial_number, eut_id),
                )
                db.commit()
                flash(f"EUT '{name}' updated.", "info")

            return redirect(url_for("planner.planner_orders"))

        if action == "delete_eut":
            eut_id = request.form.get("eut_id", "").strip()
            db.execute("DELETE FROM euts WHERE id = ?", (eut_id,))
            db.commit()
            flash("EUT deleted. Its test activities remain, now unlinked from an EUT.", "info")
            return redirect(url_for("planner.planner_orders"))

        if action == "add_test":
            order_id = request.form.get("order_id", "").strip()
            eut_id = request.form.get("eut_id", "").strip() or None
            test_name = request.form.get("test_name", "").strip()
            required_capability_id = request.form.get("required_capability_id", "").strip() or None

            if not (order_id and test_name):
                flash("Order and test name are required.", "error")
            elif db.execute("SELECT 1 FROM customer_orders WHERE id = ?", (order_id,)).fetchone() is None:
                flash("Selected order does not exist.", "error")
            elif eut_id and db.execute(
                "SELECT 1 FROM euts WHERE id = ? AND order_id = ?", (eut_id, order_id)
            ).fetchone() is None:
                flash("Selected EUT does not belong to this order.", "error")
            else:
                db.execute(
                    "INSERT INTO ordered_tests (order_id, eut_id, test_name, required_capability_id) VALUES (?, ?, ?, ?)",
                    (order_id, eut_id, test_name, required_capability_id),
                )
                db.commit()
                flash(f"Test '{test_name}' added.", "info")

            return redirect(url_for("planner.planner_orders"))

        if action == "update_test":
            ordered_test_id = request.form.get("ordered_test_id", "").strip()
            eut_id = request.form.get("eut_id", "").strip() or None
            test_name = request.form.get("test_name", "").strip()
            required_capability_id = request.form.get("required_capability_id", "").strip() or None

            existing = db.execute(
                "SELECT order_id FROM ordered_tests WHERE id = ?", (ordered_test_id,)
            ).fetchone()

            if not (ordered_test_id and test_name) or existing is None:
                flash("Test name is required.", "error")
            elif eut_id and db.execute(
                "SELECT 1 FROM euts WHERE id = ? AND order_id = ?", (eut_id, existing["order_id"])
            ).fetchone() is None:
                flash("Selected EUT does not belong to this test's order.", "error")
            else:
                db.execute(
                    "UPDATE ordered_tests SET eut_id = ?, test_name = ?, required_capability_id = ? WHERE id = ?",
                    (eut_id, test_name, required_capability_id, ordered_test_id),
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
