import math
from datetime import date, datetime, time, timedelta

from flask import Blueprint, flash, redirect, request, session, url_for

from . import history
from .db import get_db, init_db
from .routes_common import render_ui, require_role
from .scheduling import (
    find_all_running_conflicts,
    find_planned_facility_overlaps,
    find_reschedule_suggestions,
    would_create_dependency_cycle,
)
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
        SELECT a.ordered_test_id, r.id AS resource_id, r.code, r.name, r.resource_type, r.site
        FROM allocations a
        JOIN resources r ON r.id = a.resource_id
        ORDER BY a.ordered_test_id, r.code
        """
    ).fetchall()
    resources_by_test: dict[int, list] = {}
    for row in allocation_rows:
        resources_by_test.setdefault(row["ordered_test_id"], []).append(dict(row))

    def _activity_site(resources: list) -> str | None:
        for r in resources:
            if r["resource_type"] == "facility" and r["site"]:
                return r["site"]
        return None

    groups_by_resource: dict[int, set] = {}
    for row in db.execute("SELECT group_id, resource_id FROM exclusion_group_resources").fetchall():
        groups_by_resource.setdefault(row["resource_id"], set()).add(row["group_id"])

    def _resources_conflict(res_ids_a: set, res_ids_b: set) -> bool:
        if res_ids_a & res_ids_b:
            return True
        groups_a = set().union(*(groups_by_resource.get(rid, set()) for rid in res_ids_a)) if res_ids_a else set()
        groups_b = set().union(*(groups_by_resource.get(rid, set()) for rid in res_ids_b)) if res_ids_b else set()
        return bool(groups_a & groups_b)

    visible_rows = []
    unscheduled = []

    for row in raw:
        item = dict(row)
        item["assigned_resources"] = resources_by_test.get(item["ordered_test_id"], [])
        item["activity_site"] = _activity_site(item["assigned_resources"])

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
        item["_bar_start"] = bar_start
        item["_bar_end"] = bar_end
        visible_rows.append(item)

    visible_rows.sort(key=lambda r: (r["col_offset"], r["order_code"]))

    # Flag lab/equipment mutual-exclusion conflicts (Phase 9): two different ordered
    # tests, both visible today, whose resources collide (same resource, or two
    # resources in the same admin-defined exclusion group) and whose actual/inferred
    # time windows overlap. This is a passive safety net on top of the hard block at
    # work-order start/resume time (app/scheduling.py) - it also catches conflicts
    # that only appear later, e.g. a test overrunning into the next one's slot.
    for a in visible_rows:
        a_res_ids = {r["resource_id"] for r in a["assigned_resources"]}
        conflicts = []
        for b in visible_rows:
            if b["ordered_test_id"] == a["ordered_test_id"]:
                continue
            b_res_ids = {r["resource_id"] for r in b["assigned_resources"]}
            if not _resources_conflict(a_res_ids, b_res_ids):
                continue
            if a["_bar_start"] < b["_bar_end"] and b["_bar_start"] < a["_bar_end"]:
                conflicts.append(b)
        a["conflicts_with"] = conflicts

    # Flag cross-site equipment use (Phase 15, FR-CON-3): the same shared equipment
    # resource used by two different activities visible today whose facility puts them
    # at different sites, with no transit time modeled between them. This only warns
    # (doesn't block) and is skipped when the pair is already flagged as a hard
    # resource conflict above, since same-equipment + overlapping time is already
    # covered there - this is about the non-overlapping, back-to-back case instead.
    for a in visible_rows:
        if not a["activity_site"]:
            continue
        a_equipment_ids = {r["resource_id"] for r in a["assigned_resources"] if r["resource_type"] == "equipment"}
        if not a_equipment_ids:
            a["cross_site_with"] = []
            continue
        cross_site = []
        for b in visible_rows:
            if b["ordered_test_id"] == a["ordered_test_id"] or b in a["conflicts_with"]:
                continue
            if not b["activity_site"] or b["activity_site"] == a["activity_site"]:
                continue
            b_equipment_ids = {r["resource_id"] for r in b["assigned_resources"] if r["resource_type"] == "equipment"}
            if a_equipment_ids & b_equipment_ids:
                cross_site.append(b)
        a["cross_site_with"] = cross_site

    view_day_iso = view_day.isoformat()
    absences_today = [
        dict(row)
        for row in db.execute(
            """
            SELECT r.code AS resource_code, r.name AS resource_name, a.reason
            FROM staff_absences a
            JOIN resources r ON r.id = a.resource_id
            WHERE a.start_date <= ? AND a.end_date >= ?
            ORDER BY r.code
            """,
            (view_day_iso, view_day_iso),
        ).fetchall()
    ]
    visits_today = [
        dict(row)
        for row in db.execute(
            """
            SELECT o.order_code, o.customer_name, v.notes
            FROM customer_visits v
            JOIN customer_orders o ON o.id = v.order_id
            WHERE v.start_date <= ? AND v.end_date >= ?
            ORDER BY o.order_code
            """,
            (view_day_iso, view_day_iso),
        ).fetchall()
    ]

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
        "absences_today": absences_today,
        "visits_today": visits_today,
    }


def _next_sequence(db, order_id, eut_id) -> int:
    """Next free sequence number for ordered_tests within one (order_id, eut_id) scope."""
    if eut_id:
        row = db.execute(
            "SELECT COALESCE(MAX(sequence), 0) + 1 AS n FROM ordered_tests WHERE order_id = ? AND eut_id = ?",
            (order_id, eut_id),
        ).fetchone()
    else:
        row = db.execute(
            "SELECT COALESCE(MAX(sequence), 0) + 1 AS n FROM ordered_tests WHERE order_id = ? AND eut_id IS NULL",
            (order_id,),
        ).fetchone()
    return row["n"]


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
            o.id AS order_id,
            o.order_code,
            o.customer_name,
            ot.eut_id,
            e.name AS eut_name,
            ot.test_name,
            ot.sequence,
            ot.planned_start_date,
            ot.planned_end_date,
            c.id AS capability_id,
            c.name AS capability_name,
            EXISTS(SELECT 1 FROM activity_history h WHERE h.ordered_test_id = ot.id) AS has_history
        FROM ordered_tests ot
        JOIN customer_orders o ON o.id = ot.order_id
        LEFT JOIN euts e ON e.id = ot.eut_id
        LEFT JOIN capabilities c ON c.id = ot.required_capability_id
        ORDER BY o.order_code, ot.eut_id, ot.sequence, ot.id
        """
    ).fetchall()

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

    dependency_rows = db.execute(
        """
        SELECT
            ad.id AS dependency_id,
            ad.ordered_test_id,
            ad.depends_on_ordered_test_id,
            dep.test_name AS depends_on_test_name,
            dep_o.order_code AS depends_on_order_code,
            dep_wo.status AS depends_on_wo_status
        FROM activity_dependencies ad
        JOIN ordered_tests dep ON dep.id = ad.depends_on_ordered_test_id
        JOIN customer_orders dep_o ON dep_o.id = dep.order_id
        LEFT JOIN work_orders dep_wo ON dep_wo.ordered_test_id = dep.id
        ORDER BY dep_o.order_code, dep.sequence, dep.id
        """
    ).fetchall()

    dependencies_by_test: dict[int, list] = {}
    dependency_ids_by_test: dict[int, set] = {}
    for row in dependency_rows:
        dependencies_by_test.setdefault(row["ordered_test_id"], []).append(
            {
                "dependency_id": row["dependency_id"],
                "depends_on_ordered_test_id": row["depends_on_ordered_test_id"],
                "test_name": row["depends_on_test_name"],
                "order_code": row["depends_on_order_code"],
                "is_met": row["depends_on_wo_status"] == "completed",
            }
        )
        dependency_ids_by_test.setdefault(row["ordered_test_id"], set()).add(row["depends_on_ordered_test_id"])

    tests_by_order: dict[int, list] = {}
    for row in raw_tests:
        tests_by_order.setdefault(row["order_id"], []).append(dict(row))

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

        item["dependencies"] = dependencies_by_test.get(item["ordered_test_id"], [])
        item["is_blocked"] = any(not d["is_met"] for d in item["dependencies"])
        already = dependency_ids_by_test.get(item["ordered_test_id"], set())
        item["dependency_candidates"] = [
            other
            for other in tests_by_order.get(item["order_id"], [])
            if other["ordered_test_id"] != item["ordered_test_id"]
            and other["ordered_test_id"] not in already
            and not would_create_dependency_cycle(db, item["ordered_test_id"], other["ordered_test_id"])
        ]

        tests_for_alloc.append(item)

    tests = rows_with_meta(
        tests_for_alloc,
        dup_keys=ALLOC_DUP_KEYS,
        sort_key=request.args.get("alloc_sort"),
        sort_dir=request.args.get("alloc_dir", "asc"),
        sortable_keys=ALLOC_SORTABLE_KEYS,
    )

    ordered_tests_rows = rows_with_meta(
        tests_for_alloc,
        dup_keys=TEST_DUP_KEYS,
        sort_key=request.args.get("tests_sort"),
        sort_dir=request.args.get("tests_dir", "asc"),
        sortable_keys=TEST_SORTABLE_KEYS,
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
    templates = db.execute("SELECT id, name FROM activity_templates ORDER BY name").fetchall()

    context = {
        "tests": tests,
        "ordered_tests_rows": ordered_tests_rows,
        "by_capability": by_capability,
        "orders": orders,
        "euts": euts_rows,
        "capabilities": capabilities,
        "templates": templates,
    }
    context.update(_load_schedule_context(db))
    context.update(_load_orders_overview_context(db, orders, tests_for_alloc, euts_rows))

    if context["is_schedule_tab"]:
        active_tab = "schedule"
    elif context["is_overview_tab"]:
        active_tab = "overview"
    elif request.args.get("tab") in ("orders", "tests", "assign"):
        active_tab = request.args.get("tab")
    else:
        active_tab = "orders"
    context["active_tab"] = active_tab

    return context


def _test_status_label(wo_status: str | None, result: str | None) -> str:
    if wo_status is None:
        return "Not yet actioned"
    label = {
        "planned": "Planned",
        "in_progress": "In Progress",
        "on_hold": "On hold",
        "completed": "Completed",
    }.get(wo_status, wo_status)
    if wo_status == "completed" and result:
        return f"{label} — {result}"
    return label


def _load_orders_overview_context(db, orders, tests_for_alloc, euts_rows) -> dict:
    """Build the data for the three alternate 'Orders Overview' presentations
    (expandable list, status-grouped Kanban board, master-detail), reusing
    the same underlying data as the Ordered Tests / Dashboard views so this
    stays a read-oriented lens on one source of truth, not a second one."""
    status_rows = db.execute(
        """
        SELECT ot.id AS ordered_test_id, wo.status AS wo_status, wo.result AS result
        FROM ordered_tests ot
        LEFT JOIN work_orders wo ON wo.ordered_test_id = ot.id
        """
    ).fetchall()
    status_by_test = {
        row["ordered_test_id"]: _test_status_label(row["wo_status"], row["result"]) for row in status_rows
    }

    dashboard_ctx = _load_dashboard_context(db)
    projects_by_id = {p["order_id"]: p for p in dashboard_ctx["active_projects"] + dashboard_ctx["completed_projects"]}

    overview_orders = []
    for o in orders:
        proj = projects_by_id.get(o["id"])
        if proj is None:
            continue
        order_tests = [dict(t) for t in tests_for_alloc if t.get("order_id") == o["id"]]
        for t in order_tests:
            t["status_label"] = status_by_test.get(t["ordered_test_id"], "Not yet actioned")

        eut_groups = []
        for e in euts_rows:
            if e["order_id"] != o["id"]:
                continue
            eut_groups.append({"eut": e, "tests": [t for t in order_tests if t["eut_id"] == e["id"]]})

        overview_orders.append(
            {
                **proj,
                "eut_groups": eut_groups,
                "direct_tests": [t for t in order_tests if t["eut_id"] is None],
            }
        )

    overview_orders.sort(key=lambda p: p["order_code"])

    kanban_columns = ["Planned", "In Progress", "Reporting", "Waiting for Customer", "Completed"]
    kanban_board = {col: [] for col in kanban_columns}
    for p in overview_orders:
        kanban_board.setdefault(p["display_status"], []).append(p)

    selected_id = request.args.get("overview_order_id", type=int)
    selected_order = None
    if overview_orders:
        selected_order = next((p for p in overview_orders if p["order_id"] == selected_id), overview_orders[0])

    return {
        "overview_orders": overview_orders,
        "kanban_columns": kanban_columns,
        "kanban_board": kanban_board,
        "overview_selected_order": selected_order,
        "overview_default_view": "detail" if request.args.get("overview_order_id") is not None else "list",
        "is_overview_tab": request.args.get("overview_order_id") is not None,
    }


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
            return redirect(url_for("planner.planner_orders", tab="orders"))

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

            return redirect(url_for("planner.planner_orders", tab="orders"))

        if action == "delete_order":
            order_id = request.form.get("order_id", "").strip()
            db.execute("DELETE FROM customer_orders WHERE id = ?", (order_id,))
            db.commit()
            flash("Order deleted, along with its ordered tests and allocations.", "info")
            return redirect(url_for("planner.planner_orders", tab="orders"))

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
            return redirect(url_for("planner.planner_orders", tab="orders"))

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

            return redirect(url_for("planner.planner_orders", tab="orders"))

        if action == "delete_eut":
            eut_id = request.form.get("eut_id", "").strip()
            db.execute("DELETE FROM euts WHERE id = ?", (eut_id,))
            db.commit()
            flash("EUT deleted. Its test activities remain, now unlinked from an EUT.", "info")
            return redirect(url_for("planner.planner_orders", tab="orders"))

        if action == "add_test":
            order_id = request.form.get("order_id", "").strip()
            eut_id = request.form.get("eut_id", "").strip() or None
            test_name = request.form.get("test_name", "").strip()
            required_capability_id = request.form.get("required_capability_id", "").strip() or None
            planned_start_date = request.form.get("planned_start_date", "").strip() or None
            planned_end_date = request.form.get("planned_end_date", "").strip() or None

            if not (order_id and test_name):
                flash("Order and test name are required.", "error")
            elif db.execute("SELECT 1 FROM customer_orders WHERE id = ?", (order_id,)).fetchone() is None:
                flash("Selected order does not exist.", "error")
            elif eut_id and db.execute(
                "SELECT 1 FROM euts WHERE id = ? AND order_id = ?", (eut_id, order_id)
            ).fetchone() is None:
                flash("Selected EUT does not belong to this order.", "error")
            elif planned_start_date and planned_end_date and planned_end_date < planned_start_date:
                flash("Planned end date cannot be before the planned start date.", "error")
            else:
                db.execute(
                    """
                    INSERT INTO ordered_tests
                        (order_id, eut_id, test_name, required_capability_id, sequence, planned_start_date, planned_end_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        order_id, eut_id, test_name, required_capability_id,
                        _next_sequence(db, order_id, eut_id), planned_start_date, planned_end_date,
                    ),
                )
                db.commit()
                flash(f"Test '{test_name}' added.", "info")

            return redirect(url_for("planner.planner_orders", tab="tests"))

        if action == "apply_template":
            order_id = request.form.get("order_id", "").strip()
            eut_id = request.form.get("eut_id", "").strip() or None
            template_id = request.form.get("template_id", "").strip()

            if not (order_id and template_id):
                flash("Order and template are required.", "error")
            elif db.execute("SELECT 1 FROM customer_orders WHERE id = ?", (order_id,)).fetchone() is None:
                flash("Selected order does not exist.", "error")
            elif eut_id and db.execute(
                "SELECT 1 FROM euts WHERE id = ? AND order_id = ?", (eut_id, order_id)
            ).fetchone() is None:
                flash("Selected EUT does not belong to this order.", "error")
            else:
                items = db.execute(
                    "SELECT activity_name, required_capability_id FROM activity_template_items WHERE template_id = ? ORDER BY step_number",
                    (template_id,),
                ).fetchall()
                if not items:
                    flash("That template has no activities yet.", "error")
                else:
                    next_seq = _next_sequence(db, order_id, eut_id)
                    for offset, item in enumerate(items):
                        db.execute(
                            "INSERT INTO ordered_tests (order_id, eut_id, test_name, required_capability_id, sequence) VALUES (?, ?, ?, ?, ?)",
                            (order_id, eut_id, item["activity_name"], item["required_capability_id"], next_seq + offset),
                        )
                    db.commit()
                    flash(f"Applied template: {len(items)} activities added.", "info")

            return redirect(url_for("planner.planner_orders", tab="tests"))

        if action == "move_test":
            ordered_test_id = request.form.get("ordered_test_id", "").strip()
            direction = request.form.get("direction", "").strip()
            item = db.execute(
                "SELECT id, order_id, eut_id, sequence FROM ordered_tests WHERE id = ?", (ordered_test_id,)
            ).fetchone()

            if item is None or direction not in ("up", "down"):
                flash("Cannot move that test.", "error")
            else:
                eut_clause = "eut_id = ?" if item["eut_id"] is not None else "eut_id IS NULL"
                eut_params = [item["eut_id"]] if item["eut_id"] is not None else []
                neighbor = db.execute(
                    f"""
                    SELECT id, sequence FROM ordered_tests
                    WHERE order_id = ? AND {eut_clause}
                      AND sequence {'<' if direction == 'up' else '>'} ?
                    ORDER BY sequence {'DESC' if direction == 'up' else 'ASC'}
                    LIMIT 1
                    """,
                    [item["order_id"], *eut_params, item["sequence"]],
                ).fetchone()
                if neighbor is None:
                    flash("Already at that end of the list.", "info")
                else:
                    db.execute("UPDATE ordered_tests SET sequence = ? WHERE id = ?", (neighbor["sequence"], item["id"]))
                    db.execute("UPDATE ordered_tests SET sequence = ? WHERE id = ?", (item["sequence"], neighbor["id"]))
                    history.record(
                        db, item["id"], session.get("user_id"), session.get("username"),
                        "reordered", f"Moved {direction} (sequence {item['sequence']} -> {neighbor['sequence']}).",
                    )
                    db.commit()
                    flash("Test reordered.", "info")

            return redirect(url_for("planner.planner_orders", tab="tests"))

        if action == "update_test":
            ordered_test_id = request.form.get("ordered_test_id", "").strip()
            eut_id = request.form.get("eut_id", "").strip() or None
            test_name = request.form.get("test_name", "").strip()
            required_capability_id = request.form.get("required_capability_id", "").strip() or None
            planned_start_date = request.form.get("planned_start_date", "").strip() or None
            planned_end_date = request.form.get("planned_end_date", "").strip() or None

            existing = db.execute(
                "SELECT order_id, eut_id, sequence, planned_start_date, planned_end_date FROM ordered_tests WHERE id = ?",
                (ordered_test_id,),
            ).fetchone()

            if not (ordered_test_id and test_name) or existing is None:
                flash("Test name is required.", "error")
            elif eut_id and db.execute(
                "SELECT 1 FROM euts WHERE id = ? AND order_id = ?", (eut_id, existing["order_id"])
            ).fetchone() is None:
                flash("Selected EUT does not belong to this test's order.", "error")
            elif planned_start_date and planned_end_date and planned_end_date < planned_start_date:
                flash("Planned end date cannot be before the planned start date.", "error")
            else:
                # Moving a test to a different EUT (or out of one) puts it at the end of
                # its new scope's order, rather than keeping a sequence number that was
                # only meaningful in the old scope.
                sequence = existing["sequence"]
                eut_changed = eut_id != existing["eut_id"]
                if eut_changed:
                    sequence = _next_sequence(db, existing["order_id"], eut_id)
                db.execute(
                    """
                    UPDATE ordered_tests
                    SET eut_id = ?, test_name = ?, required_capability_id = ?, sequence = ?,
                        planned_start_date = ?, planned_end_date = ?
                    WHERE id = ?
                    """,
                    (eut_id, test_name, required_capability_id, sequence, planned_start_date, planned_end_date, ordered_test_id),
                )
                if eut_changed:
                    def _eut_label(eid):
                        if not eid:
                            return "no EUT"
                        row = db.execute("SELECT name FROM euts WHERE id = ?", (eid,)).fetchone()
                        return row["name"] if row else "no EUT"
                    history.record(
                        db, ordered_test_id, session.get("user_id"), session.get("username"),
                        "eut_changed",
                        f"Moved from {_eut_label(existing['eut_id'])} to {_eut_label(eut_id)}.",
                    )
                if (planned_start_date, planned_end_date) != (existing["planned_start_date"], existing["planned_end_date"]):
                    history.record(
                        db, ordered_test_id, session.get("user_id"), session.get("username"),
                        "planned_dates_changed",
                        f"Planned dates set to {planned_start_date or '(none)'} - {planned_end_date or '(none)'}.",
                    )
                db.commit()
                flash(f"Test '{test_name}' updated.", "info")

            return redirect(url_for("planner.planner_orders", tab="tests"))

        if action == "delete_test":
            ordered_test_id = request.form.get("ordered_test_id", "").strip()
            db.execute("DELETE FROM ordered_tests WHERE id = ?", (ordered_test_id,))
            db.commit()
            flash("Ordered test deleted, along with its allocation (if any).", "info")
            return redirect(url_for("planner.planner_orders", tab="tests"))

        if action == "add_dependency":
            ordered_test_id = request.form.get("ordered_test_id", "").strip()
            depends_on_id = request.form.get("depends_on_ordered_test_id", "").strip()

            test = db.execute("SELECT order_id FROM ordered_tests WHERE id = ?", (ordered_test_id,)).fetchone()
            dep = db.execute("SELECT order_id, test_name FROM ordered_tests WHERE id = ?", (depends_on_id,)).fetchone()

            if not (ordered_test_id and depends_on_id) or test is None or dep is None:
                flash("A valid test and prerequisite are required.", "error")
            elif ordered_test_id == depends_on_id:
                flash("A test cannot depend on itself.", "error")
            elif test["order_id"] != dep["order_id"]:
                flash("A dependency must be within the same order.", "error")
            elif db.execute(
                "SELECT 1 FROM activity_dependencies WHERE ordered_test_id = ? AND depends_on_ordered_test_id = ?",
                (ordered_test_id, depends_on_id),
            ).fetchone():
                flash("That dependency already exists.", "error")
            elif would_create_dependency_cycle(db, int(ordered_test_id), int(depends_on_id)):
                flash("That would create a circular dependency.", "error")
            else:
                db.execute(
                    "INSERT INTO activity_dependencies (ordered_test_id, depends_on_ordered_test_id) VALUES (?, ?)",
                    (ordered_test_id, depends_on_id),
                )
                history.record(
                    db, ordered_test_id, session.get("user_id"), session.get("username"),
                    "dependency_added", f"Now depends on: {dep['test_name']}.",
                )
                db.commit()
                flash("Dependency added.", "info")

            return redirect(url_for("planner.planner_orders", tab="tests"))

        if action == "remove_dependency":
            dependency_id = request.form.get("dependency_id", "").strip()
            row = db.execute(
                """
                SELECT ad.ordered_test_id, dep.test_name
                FROM activity_dependencies ad
                JOIN ordered_tests dep ON dep.id = ad.depends_on_ordered_test_id
                WHERE ad.id = ?
                """,
                (dependency_id,),
            ).fetchone()
            db.execute("DELETE FROM activity_dependencies WHERE id = ?", (dependency_id,))
            if row:
                history.record(
                    db, row["ordered_test_id"], session.get("user_id"), session.get("username"),
                    "dependency_removed", f"No longer depends on: {row['test_name']}.",
                )
            db.commit()
            flash("Dependency removed.", "info")
            return redirect(url_for("planner.planner_orders", tab="tests"))

        if action == "delete_allocation":
            allocation_id = request.form.get("allocation_id", "").strip()
            alloc = db.execute(
                """
                SELECT a.ordered_test_id, r.code, r.name
                FROM allocations a
                JOIN resources r ON r.id = a.resource_id
                WHERE a.id = ?
                """,
                (allocation_id,),
            ).fetchone()
            db.execute("DELETE FROM allocations WHERE id = ?", (allocation_id,))
            if alloc:
                history.record(
                    db, alloc["ordered_test_id"], session.get("user_id"), session.get("username"),
                    "resource_removed", f"Resource {alloc['code']} ({alloc['name']}) unassigned.",
                )
            db.commit()
            flash("Resource unassigned from test.", "info")
            return redirect(url_for("planner.planner_orders", tab="assign"))

        if action == "assign_resource":
            ordered_test_id = request.form.get("ordered_test_id", "").strip()
            resource_id = request.form.get("resource_id", "").strip()

            if not (ordered_test_id and resource_id):
                flash("Ordered test and resource are required.", "error")
                return redirect(url_for("planner.planner_orders", tab="assign"))

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
                resource = db.execute("SELECT code, name FROM resources WHERE id = ?", (resource_id,)).fetchone()
                history.record(
                    db, ordered_test_id, session.get("user_id"), session.get("username"),
                    "resource_assigned",
                    f"Resource {resource['code']} ({resource['name']}) assigned." if resource else "Resource assigned.",
                )
                db.commit()
                flash("Resource assigned to test.", "info")

            return redirect(url_for("planner.planner_orders", tab="assign"))

    return _render_planner_orders(db)


# ---------------------------------------------------------------------------
# Phase 11: project/discipline dashboard.
#
# Project and discipline status are *derived* from underlying test activity /
# work order status (BR-001 Single Source of Truth), not separately entered -
# unlike the customer's current Sprint.xls, where the same fact gets typed in
# by hand a second time. The only genuinely manual fields are weekly_note and
# waiting_for_customer, since neither has any other source in the system.
# ---------------------------------------------------------------------------

REPORT_DISCIPLINE = "Report"
DEFAULT_DISCIPLINE = "Project Management"


def _activity_discipline(test_name: str, capability_discipline: str | None) -> str:
    if capability_discipline:
        return capability_discipline
    if "report" in test_name.lower():
        return REPORT_DISCIPLINE
    return DEFAULT_DISCIPLINE


def _rollup_status(total: int, completed: int, active: int) -> str:
    if total == 0:
        return "Planned"
    if completed == total:
        return "Completed"
    if active > 0 or completed > 0:
        return "In Progress"
    return "Planned"


def _load_dashboard_context(db) -> dict:
    rows = db.execute(
        """
        SELECT
            o.id AS order_id, o.order_code, o.customer_name, o.product_name,
            o.weekly_note, o.waiting_for_customer,
            ot.id AS ordered_test_id, ot.test_name, ot.planned_end_date,
            c.discipline AS capability_discipline,
            wo.id AS work_order_id, wo.procedure_id, wo.status AS wo_status
        FROM customer_orders o
        LEFT JOIN ordered_tests ot ON ot.order_id = o.id
        LEFT JOIN capabilities c ON c.id = ot.required_capability_id
        LEFT JOIN work_orders wo ON wo.ordered_test_id = ot.id
        ORDER BY o.order_code
        """
    ).fetchall()

    today_iso = date.today().isoformat()
    projects: dict[int, dict] = {}
    for row in rows:
        proj = projects.setdefault(
            row["order_id"],
            {
                "order_id": row["order_id"],
                "order_code": row["order_code"],
                "customer_name": row["customer_name"],
                "product_name": row["product_name"],
                "weekly_note": row["weekly_note"],
                "waiting_for_customer": bool(row["waiting_for_customer"]),
                "activities": [],
                "unscheduled_count": 0,
                "missing_procedure_count": 0,
                "overdue_count": 0,
            },
        )
        if row["ordered_test_id"] is None:
            continue
        discipline = _activity_discipline(row["test_name"], row["capability_discipline"])
        proj["activities"].append({"discipline": discipline, "status": row["wo_status"]})
        if row["work_order_id"] is None:
            proj["unscheduled_count"] += 1
        elif row["procedure_id"] is None:
            proj["missing_procedure_count"] += 1
        if row["planned_end_date"] and row["planned_end_date"] < today_iso and row["wo_status"] != "completed":
            proj["overdue_count"] += 1

    conflicted_order_ids = set()
    for a, b in find_all_running_conflicts(db):
        conflicted_order_ids.add(a["order_id"])
        conflicted_order_ids.add(b["order_id"])

    planned_overlaps_by_order: dict[int, list] = {}
    for a, b in find_planned_facility_overlaps(db):
        planned_overlaps_by_order.setdefault(a["order_id"], []).append(b)
        planned_overlaps_by_order.setdefault(b["order_id"], []).append(a)

    milestone_rows = db.execute(
        """
        SELECT m.id, m.order_id, m.title, m.target_date, m.notes, o.order_code
        FROM milestones m
        JOIN customer_orders o ON o.id = m.order_id
        ORDER BY m.target_date IS NULL, m.target_date
        """
    ).fetchall()
    milestones_by_order: dict[int, list] = {}
    for row in milestone_rows:
        milestones_by_order.setdefault(row["order_id"], []).append(dict(row))

    visit_rows = db.execute(
        """
        SELECT v.id, v.order_id, v.start_date, v.end_date, v.notes, o.order_code
        FROM customer_visits v
        JOIN customer_orders o ON o.id = v.order_id
        ORDER BY v.start_date
        """
    ).fetchall()
    visits_by_order: dict[int, list] = {}
    for row in visit_rows:
        visits_by_order.setdefault(row["order_id"], []).append(dict(row))

    today = date.today().isoformat()
    horizon = (date.today() + timedelta(days=14)).isoformat()
    upcoming_absences = [
        dict(row)
        for row in db.execute(
            """
            SELECT a.id, r.code AS resource_code, r.name AS resource_name,
                   a.start_date, a.end_date, a.reason
            FROM staff_absences a
            JOIN resources r ON r.id = a.resource_id
            WHERE a.end_date >= ? AND a.start_date <= ?
            ORDER BY a.start_date
            """,
            (today, horizon),
        ).fetchall()
    ]

    result_projects = []
    for order_id, proj in projects.items():
        activities = proj.pop("activities")
        total = len(activities)
        completed = sum(1 for a in activities if a["status"] == "completed")
        active = sum(1 for a in activities if a["status"] in ("in_progress", "on_hold"))

        report_total = sum(1 for a in activities if a["discipline"] == REPORT_DISCIPLINE)
        report_completed = sum(
            1 for a in activities if a["discipline"] == REPORT_DISCIPLINE and a["status"] == "completed"
        )
        non_report_total = total - report_total
        non_report_completed = completed - report_completed

        if total == 0:
            computed_status = "Planned"
        elif completed == total:
            computed_status = "Completed"
        elif active > 0:
            computed_status = "In Progress"
        elif (
            non_report_total > 0
            and non_report_completed == non_report_total
            and report_total > 0
            and report_completed < report_total
        ):
            computed_status = "Reporting"
        elif completed > 0:
            computed_status = "In Progress"
        else:
            computed_status = "Planned"

        disciplines: dict[str, dict] = {}
        for a in activities:
            d = disciplines.setdefault(a["discipline"], {"total": 0, "completed": 0, "active": 0})
            d["total"] += 1
            if a["status"] == "completed":
                d["completed"] += 1
            elif a["status"] in ("in_progress", "on_hold"):
                d["active"] += 1

        proj["computed_status"] = computed_status
        proj["display_status"] = "Waiting for Customer" if proj["waiting_for_customer"] else computed_status
        proj["discipline_status"] = {
            name: _rollup_status(d["total"], d["completed"], d["active"]) for name, d in disciplines.items()
        }
        proj["total_activities"] = total
        proj["has_conflict"] = order_id in conflicted_order_ids
        proj["has_overdue"] = proj["overdue_count"] > 0
        proj["planned_overlaps"] = planned_overlaps_by_order.get(order_id, [])
        proj["has_planned_overlap"] = bool(proj["planned_overlaps"])
        proj["milestones"] = milestones_by_order.get(order_id, [])
        proj["visits"] = visits_by_order.get(order_id, [])
        result_projects.append(proj)

    result_projects.sort(key=lambda p: p["order_code"])
    active_projects = [p for p in result_projects if p["computed_status"] != "Completed"]
    completed_projects = [p for p in result_projects if p["computed_status"] == "Completed"]

    return {
        "active_projects": active_projects,
        "completed_projects": completed_projects,
        "upcoming_absences": upcoming_absences,
        "reschedule_suggestions": find_reschedule_suggestions(db),
    }


@bp.route("/dashboard", methods=["GET", "POST"])
@require_role("planner")
def dashboard():
    init_db()
    db = get_db()

    if request.method == "POST":
        action = request.form.get("action", "")

        if action == "update_project_status":
            order_id = request.form.get("order_id", "").strip()
            weekly_note = request.form.get("weekly_note", "").strip() or None
            waiting_for_customer = 1 if request.form.get("waiting_for_customer") else 0
            db.execute(
                "UPDATE customer_orders SET weekly_note = ?, waiting_for_customer = ? WHERE id = ?",
                (weekly_note, waiting_for_customer, order_id),
            )
            db.commit()
            flash("Project status updated.", "info")
            return redirect(url_for("planner.dashboard"))

        if action == "create_milestone":
            order_id = request.form.get("order_id", "").strip()
            title = request.form.get("title", "").strip()
            target_date = request.form.get("target_date", "").strip() or None
            notes = request.form.get("notes", "").strip() or None

            if not (order_id and title):
                flash("Order and milestone title are required.", "error")
            else:
                db.execute(
                    "INSERT INTO milestones (order_id, title, target_date, notes) VALUES (?, ?, ?, ?)",
                    (order_id, title, target_date, notes),
                )
                db.commit()
                flash(f"Milestone '{title}' added.", "info")
            return redirect(url_for("planner.dashboard"))

        if action == "delete_milestone":
            milestone_id = request.form.get("milestone_id", "").strip()
            db.execute("DELETE FROM milestones WHERE id = ?", (milestone_id,))
            db.commit()
            flash("Milestone deleted.", "info")
            return redirect(url_for("planner.dashboard"))

        if action == "create_visit":
            order_id = request.form.get("order_id", "").strip()
            start_date = request.form.get("start_date", "").strip()
            end_date = request.form.get("end_date", "").strip() or start_date
            notes = request.form.get("notes", "").strip() or None

            if not (order_id and start_date):
                flash("Order and start date are required.", "error")
            elif end_date < start_date:
                flash("End date cannot be before start date.", "error")
            else:
                db.execute(
                    "INSERT INTO customer_visits (order_id, start_date, end_date, notes) VALUES (?, ?, ?, ?)",
                    (order_id, start_date, end_date, notes),
                )
                db.commit()
                flash("Customer visit recorded.", "info")
            return redirect(url_for("planner.dashboard"))

        if action == "delete_visit":
            visit_id = request.form.get("visit_id", "").strip()
            db.execute("DELETE FROM customer_visits WHERE id = ?", (visit_id,))
            db.commit()
            flash("Customer visit deleted.", "info")
            return redirect(url_for("planner.dashboard"))

        if action == "accept_reschedule_suggestion":
            dependency_id = request.form.get("dependency_id", "").strip()
            new_start = request.form.get("suggested_planned_start", "").strip()
            new_end = request.form.get("suggested_planned_end", "").strip()
            dep = db.execute(
                "SELECT ordered_test_id, depends_on_ordered_test_id FROM activity_dependencies WHERE id = ?",
                (dependency_id,),
            ).fetchone()
            if not (dep and new_start and new_end):
                flash("Cannot apply that suggestion.", "error")
            else:
                db.execute(
                    "UPDATE ordered_tests SET planned_start_date = ?, planned_end_date = ? WHERE id = ?",
                    (new_start, new_end, dep["ordered_test_id"]),
                )
                # The prerequisite's delay is a fixed fact once suggested; without this,
                # the same delay would immediately generate a fresh suggestion shifting
                # the just-applied dates again, since the pair would still qualify.
                db.execute(
                    """
                    INSERT OR IGNORE INTO reschedule_dismissals
                        (ordered_test_id, depends_on_ordered_test_id, dismissed_at)
                    VALUES (?, ?, ?)
                    """,
                    (dep["ordered_test_id"], dep["depends_on_ordered_test_id"], datetime.now().strftime("%Y-%m-%d %H:%M")),
                )
                history.record(
                    db, dep["ordered_test_id"], session.get("user_id"), session.get("username"),
                    "planned_dates_changed",
                    f"Planned dates shifted to {new_start} - {new_end} (accepted reschedule suggestion).",
                )
                db.commit()
                flash("Reschedule suggestion applied.", "info")
            return redirect(url_for("planner.dashboard"))

        if action == "ignore_reschedule_suggestion":
            dependency_id = request.form.get("dependency_id", "").strip()
            dep = db.execute(
                "SELECT ordered_test_id, depends_on_ordered_test_id FROM activity_dependencies WHERE id = ?",
                (dependency_id,),
            ).fetchone()
            if dep and not db.execute(
                "SELECT 1 FROM reschedule_dismissals WHERE ordered_test_id = ? AND depends_on_ordered_test_id = ?",
                (dep["ordered_test_id"], dep["depends_on_ordered_test_id"]),
            ).fetchone():
                db.execute(
                    "INSERT INTO reschedule_dismissals (ordered_test_id, depends_on_ordered_test_id, dismissed_at) VALUES (?, ?, ?)",
                    (dep["ordered_test_id"], dep["depends_on_ordered_test_id"], datetime.now().strftime("%Y-%m-%d %H:%M")),
                )
                db.commit()
            flash("Suggestion dismissed.", "info")
            return redirect(url_for("planner.dashboard"))

    context = _load_dashboard_context(db)
    orders = db.execute("SELECT id, order_code FROM customer_orders ORDER BY order_code").fetchall()
    context["orders"] = orders
    return render_ui("dashboard.html", **context)


@bp.route("/activity/<int:ordered_test_id>/history")
@require_role("planner")
def activity_history(ordered_test_id):
    init_db()
    db = get_db()

    activity = db.execute(
        """
        SELECT ot.id, ot.test_name, o.order_code, o.customer_name, e.name AS eut_name
        FROM ordered_tests ot
        JOIN customer_orders o ON o.id = ot.order_id
        LEFT JOIN euts e ON e.id = ot.eut_id
        WHERE ot.id = ?
        """,
        (ordered_test_id,),
    ).fetchone()

    if activity is None:
        flash("That test activity no longer exists.", "error")
        return redirect(url_for("planner.planner_orders"))

    entries = db.execute(
        """
        SELECT changed_at, username, action, detail, reason
        FROM activity_history
        WHERE ordered_test_id = ?
        ORDER BY changed_at DESC, id DESC
        """,
        (ordered_test_id,),
    ).fetchall()

    return render_ui("activity_history.html", activity=activity, entries=entries)
