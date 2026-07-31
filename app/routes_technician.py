from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from . import history
from .db import get_db, init_db
from .routes_common import require_role
from .scheduling import conflict_message, find_running_conflict
from .table_utils import rows_with_meta

bp = Blueprint("technician", __name__, url_prefix="/technician")

TEST_SORTABLE_KEYS = {"order_code", "customer_name", "product_name", "test_name", "capability_name", "wo_status"}
TEST_DUP_KEYS = ["order_code", "test_name", "capability_name"]


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def _linked_resource_id(db) -> int | None:
    user_id = session.get("user_id")
    if not user_id:
        return None
    row = db.execute("SELECT linked_resource_id FROM users WHERE id = ?", (user_id,)).fetchone()
    return row["linked_resource_id"] if row else None


def _next_work_order_code(db) -> str:
    row = db.execute("SELECT MAX(id) AS max_id FROM work_orders").fetchone()
    next_id = (row["max_id"] or 0) + 1
    return f"WO-{next_id:04d}"


def _load_technician_context(db) -> dict:
    resource_id = _linked_resource_id(db)

    assigned_rows = (
        db.execute(
            """
            SELECT
                ot.id AS ordered_test_id,
                o.order_code,
                o.customer_name,
                o.product_name,
                ot.test_name,
                c.id AS capability_id,
                c.name AS capability_name
            FROM allocations a
            JOIN ordered_tests ot ON ot.id = a.ordered_test_id
            JOIN customer_orders o ON o.id = ot.order_id
            LEFT JOIN capabilities c ON c.id = ot.required_capability_id
            WHERE a.resource_id = ?
            ORDER BY o.order_code, ot.id
            """,
            (resource_id,),
        ).fetchall()
        if resource_id
        else []
    )

    test_ids = [row["ordered_test_id"] for row in assigned_rows]

    resources_by_test: dict[int, list] = {}
    work_orders_by_test: dict[int, dict] = {}
    reports_by_wo: dict[int, dict] = {}
    if test_ids:
        placeholders = ",".join("?" for _ in test_ids)

        resource_rows = db.execute(
            f"""
            SELECT a.ordered_test_id, r.code, r.name, r.resource_type
            FROM allocations a
            JOIN resources r ON r.id = a.resource_id
            WHERE a.ordered_test_id IN ({placeholders})
            ORDER BY r.resource_type, r.code
            """,
            test_ids,
        ).fetchall()
        for row in resource_rows:
            resources_by_test.setdefault(row["ordered_test_id"], []).append(dict(row))

        wo_rows = db.execute(
            f"""
            SELECT wo.*, p.title AS procedure_title
            FROM work_orders wo
            LEFT JOIN test_procedures p ON p.id = wo.procedure_id
            WHERE wo.ordered_test_id IN ({placeholders})
            """,
            test_ids,
        ).fetchall()
        for row in wo_rows:
            work_orders_by_test[row["ordered_test_id"]] = dict(row)

        wo_ids = [row["id"] for row in wo_rows]
        if wo_ids:
            wo_placeholders = ",".join("?" for _ in wo_ids)
            report_rows = db.execute(
                f"""
                SELECT id, work_order_id, report_code, status, overall_result
                FROM test_reports
                WHERE work_order_id IN ({wo_placeholders})
                """,
                wo_ids,
            ).fetchall()
            for row in report_rows:
                reports_by_wo[row["work_order_id"]] = dict(row)

    procedures_by_capability: dict[int, list] = {}
    all_procedures = db.execute(
        """
        SELECT p.id, p.capability_id, p.title, p.summary, p.steps, p.equipment_needed, p.facility_needed, p.safety_notes,
               c.name AS capability_name
        FROM test_procedures p
        LEFT JOIN capabilities c ON c.id = p.capability_id
        ORDER BY p.title
        """
    ).fetchall()
    for row in all_procedures:
        procedures_by_capability.setdefault(row["capability_id"], []).append(row)

    tests = []
    for row in assigned_rows:
        item = dict(row)
        item["assigned_resources"] = resources_by_test.get(item["ordered_test_id"], [])
        work_order = work_orders_by_test.get(item["ordered_test_id"])
        item["work_order"] = work_order
        item["wo_status"] = work_order["status"] if work_order else "unassigned"
        item["report"] = reports_by_wo.get(work_order["id"]) if work_order else None
        item["available_procedures"] = procedures_by_capability.get(item["capability_id"], [])
        tests.append(item)

    tests = rows_with_meta(
        tests,
        dup_keys=TEST_DUP_KEYS,
        sort_key=request.args.get("tests_sort"),
        sort_dir=request.args.get("tests_dir", "asc"),
        sortable_keys=TEST_SORTABLE_KEYS,
    )

    open_count = sum(1 for t in tests if t["wo_status"] in ("planned", "in_progress", "on_hold"))
    completed_count = sum(1 for t in tests if t["wo_status"] == "completed")

    return {
        "tests": tests,
        "all_procedures": all_procedures,
        "resource_id": resource_id,
        "open_count": open_count,
        "completed_count": completed_count,
    }


@bp.route("/", methods=["GET", "POST"])
@require_role("technician")
def technician_dashboard():
    init_db()
    db = get_db()

    if request.method == "POST":
        action = request.form.get("action", "")

        if action == "create_work_order":
            ordered_test_id = request.form.get("ordered_test_id", "").strip()
            procedure_id = request.form.get("procedure_id", "").strip() or None
            scheduled_date = request.form.get("scheduled_date", "").strip() or None
            notes = request.form.get("notes", "").strip() or None

            if not ordered_test_id:
                flash("Ordered test is required.", "error")
            elif db.execute(
                "SELECT 1 FROM work_orders WHERE ordered_test_id = ?", (ordered_test_id,)
            ).fetchone():
                flash("A work order already exists for this test.", "error")
            else:
                code = _next_work_order_code(db)
                db.execute(
                    """
                    INSERT INTO work_orders
                        (work_order_code, ordered_test_id, technician_user_id, procedure_id, status, scheduled_date, notes)
                    VALUES (?, ?, ?, ?, 'planned', ?, ?)
                    """,
                    (code, ordered_test_id, session.get("user_id"), procedure_id, scheduled_date, notes),
                )
                history.record(
                    db, ordered_test_id, session.get("user_id"), session.get("username"),
                    "work_order_created", f"Work order {code} created.",
                )
                db.commit()
                flash(f"Work order {code} created.", "info")

            return redirect(url_for("technician.technician_dashboard"))

        if action == "start_work_order":
            work_order_id = request.form.get("work_order_id", "").strip()
            wo = db.execute("SELECT ordered_test_id, work_order_code FROM work_orders WHERE id = ?", (work_order_id,)).fetchone()
            conflict = find_running_conflict(db, wo["ordered_test_id"], exclude_work_order_id=work_order_id) if wo else None
            if conflict:
                flash(conflict_message(conflict), "error")
            else:
                db.execute(
                    "UPDATE work_orders SET status = 'in_progress', started_at = ? WHERE id = ?",
                    (_now(), work_order_id),
                )
                history.record(
                    db, wo["ordered_test_id"], session.get("user_id"), session.get("username"),
                    "work_order_started", f"Work order {wo['work_order_code']} started.",
                )
                db.commit()
                flash("Work order started.", "info")
            return redirect(url_for("technician.technician_dashboard"))

        if action == "hold_work_order":
            work_order_id = request.form.get("work_order_id", "").strip()
            wo = db.execute("SELECT ordered_test_id, work_order_code FROM work_orders WHERE id = ?", (work_order_id,)).fetchone()
            db.execute("UPDATE work_orders SET status = 'on_hold' WHERE id = ?", (work_order_id,))
            if wo:
                history.record(
                    db, wo["ordered_test_id"], session.get("user_id"), session.get("username"),
                    "work_order_held", f"Work order {wo['work_order_code']} put on hold.",
                )
            db.commit()
            flash("Work order put on hold.", "info")
            return redirect(url_for("technician.technician_dashboard"))

        if action == "resume_work_order":
            work_order_id = request.form.get("work_order_id", "").strip()
            wo = db.execute("SELECT ordered_test_id, work_order_code FROM work_orders WHERE id = ?", (work_order_id,)).fetchone()
            conflict = find_running_conflict(db, wo["ordered_test_id"], exclude_work_order_id=work_order_id) if wo else None
            if conflict:
                flash(conflict_message(conflict), "error")
            else:
                db.execute("UPDATE work_orders SET status = 'in_progress' WHERE id = ?", (work_order_id,))
                history.record(
                    db, wo["ordered_test_id"], session.get("user_id"), session.get("username"),
                    "work_order_resumed", f"Work order {wo['work_order_code']} resumed.",
                )
                db.commit()
                flash("Work order resumed.", "info")
            return redirect(url_for("technician.technician_dashboard"))

        if action == "complete_work_order":
            work_order_id = request.form.get("work_order_id", "").strip()
            result = request.form.get("result", "").strip() or None
            notes = request.form.get("notes", "").strip() or None

            if not result:
                flash("A pass/fail/n-a result is required to complete a work order.", "error")
            else:
                wo = db.execute("SELECT ordered_test_id, work_order_code FROM work_orders WHERE id = ?", (work_order_id,)).fetchone()
                db.execute(
                    "UPDATE work_orders SET status = 'completed', completed_at = ?, result = ?, notes = ? WHERE id = ?",
                    (_now(), result, notes, work_order_id),
                )
                if wo:
                    history.record(
                        db, wo["ordered_test_id"], session.get("user_id"), session.get("username"),
                        "work_order_completed",
                        f"Work order {wo['work_order_code']} completed with result: {result}.",
                        reason=notes,
                    )
                db.commit()
                flash("Work order completed.", "info")

            return redirect(url_for("technician.technician_dashboard"))

        if action == "update_procedure":
            work_order_id = request.form.get("work_order_id", "").strip()
            procedure_id = request.form.get("procedure_id", "").strip() or None
            wo = db.execute("SELECT ordered_test_id, work_order_code FROM work_orders WHERE id = ?", (work_order_id,)).fetchone()
            db.execute("UPDATE work_orders SET procedure_id = ? WHERE id = ?", (procedure_id, work_order_id))
            if wo:
                proc = db.execute("SELECT title FROM test_procedures WHERE id = ?", (procedure_id,)).fetchone() if procedure_id else None
                history.record(
                    db, wo["ordered_test_id"], session.get("user_id"), session.get("username"),
                    "procedure_changed",
                    f"Test procedure changed to: {proc['title']}." if proc else "Test procedure cleared.",
                )
            db.commit()
            flash("Test procedure updated.", "info")
            return redirect(url_for("technician.technician_dashboard"))

        if action == "update_notes":
            work_order_id = request.form.get("work_order_id", "").strip()
            notes = request.form.get("notes", "").strip() or None
            db.execute("UPDATE work_orders SET notes = ? WHERE id = ?", (notes, work_order_id))
            db.commit()
            flash("Notes updated.", "info")
            return redirect(url_for("technician.technician_dashboard"))

    context = _load_technician_context(db)
    # The technician workspace only exists in the modern UI, so it always renders
    # from there regardless of the session's simple/modern toggle.
    return render_template("modern/technician_dashboard.html", **context)
