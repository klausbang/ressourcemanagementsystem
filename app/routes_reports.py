from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from .db import get_db, init_db
from .routes_common import current_role, require_any_role, require_role

bp = Blueprint("reports", __name__, url_prefix="/reports")


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def _next_report_code(db) -> str:
    row = db.execute("SELECT MAX(id) AS max_id FROM test_reports").fetchone()
    next_id = (row["max_id"] or 0) + 1
    return f"RPT-{next_id:04d}"


def _fetch_report(db, report_id: int) -> dict | None:
    row = db.execute(
        """
        SELECT tr.*,
               wo.work_order_code, wo.scheduled_date, wo.started_at AS wo_started_at, wo.completed_at AS wo_completed_at,
               ot.id AS ordered_test_id, ot.test_name,
               o.order_code, o.customer_name, o.product_name,
               p.title AS procedure_title, p.summary AS procedure_summary, p.safety_notes AS procedure_safety_notes,
               tech.username AS technician_username,
               rev.username AS reviewer_username
        FROM test_reports tr
        JOIN work_orders wo ON wo.id = tr.work_order_id
        JOIN ordered_tests ot ON ot.id = tr.ordered_test_id
        JOIN customer_orders o ON o.id = ot.order_id
        LEFT JOIN test_procedures p ON p.id = tr.procedure_id
        JOIN users tech ON tech.id = tr.technician_user_id
        LEFT JOIN users rev ON rev.id = tr.reviewer_user_id
        WHERE tr.id = ?
        """,
        (report_id,),
    ).fetchone()
    if row is None:
        return None

    report = dict(row)

    steps = db.execute(
        "SELECT * FROM report_steps WHERE report_id = ? ORDER BY step_number", (report_id,)
    ).fetchall()
    report["steps"] = [dict(s) for s in steps]

    resources = db.execute(
        """
        SELECT r.code, r.name, r.resource_type
        FROM allocations a
        JOIN resources r ON r.id = a.resource_id
        WHERE a.ordered_test_id = ?
        ORDER BY r.resource_type, r.code
        """,
        (report["ordered_test_id"],),
    ).fetchall()
    report["assigned_resources"] = [dict(r) for r in resources]

    return report


def _apply_report_edits(db, report_id: int, form) -> None:
    uut_name = form.get("uut_name", "").strip() or None
    uut_serial_number = form.get("uut_serial_number", "").strip() or None
    notes = form.get("notes", "").strip() or None
    db.execute(
        "UPDATE test_reports SET uut_name = ?, uut_serial_number = ?, notes = ? WHERE id = ?",
        (uut_name, uut_serial_number, notes, report_id),
    )

    for step_id in form.getlist("step_id"):
        actual_value = form.get(f"actual_value_{step_id}", "").strip() or None
        result = form.get(f"result_{step_id}", "").strip() or None
        db.execute(
            "UPDATE report_steps SET actual_value = ?, result = ? WHERE id = ? AND report_id = ?",
            (actual_value, result, step_id, report_id),
        )


@bp.route("/create", methods=["POST"])
@require_role("technician")
def create_report():
    init_db()
    db = get_db()

    work_order_id = request.form.get("work_order_id", "").strip()
    wo = db.execute("SELECT * FROM work_orders WHERE id = ?", (work_order_id,)).fetchone() if work_order_id else None

    if wo is None:
        flash("Work order not found.", "error")
        return redirect(url_for("technician.technician_dashboard"))
    if wo["technician_user_id"] != session.get("user_id"):
        flash("You can only create a report for your own work order.", "error")
        return redirect(url_for("technician.technician_dashboard"))
    if not wo["procedure_id"]:
        flash("Assign a test procedure to this work order before creating a report.", "error")
        return redirect(url_for("technician.technician_dashboard"))
    if db.execute("SELECT 1 FROM test_reports WHERE work_order_id = ?", (wo["id"],)).fetchone():
        flash("A test report already exists for this work order.", "error")
        return redirect(url_for("technician.technician_dashboard"))

    ordered_test = db.execute(
        """
        SELECT o.product_name FROM ordered_tests ot
        JOIN customer_orders o ON o.id = ot.order_id
        WHERE ot.id = ?
        """,
        (wo["ordered_test_id"],),
    ).fetchone()

    code = _next_report_code(db)
    cur = db.execute(
        """
        INSERT INTO test_reports
            (report_code, work_order_id, ordered_test_id, procedure_id, uut_name, technician_user_id, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, 'draft', ?)
        """,
        (code, wo["id"], wo["ordered_test_id"], wo["procedure_id"], ordered_test["product_name"], wo["technician_user_id"], _now()),
    )
    report_id = cur.lastrowid

    checks = db.execute(
        "SELECT step_number, description, expected_value FROM procedure_checks WHERE procedure_id = ? ORDER BY step_number",
        (wo["procedure_id"],),
    ).fetchall()
    for c in checks:
        db.execute(
            "INSERT INTO report_steps (report_id, step_number, description, expected_value) VALUES (?, ?, ?, ?)",
            (report_id, c["step_number"], c["description"], c["expected_value"]),
        )

    db.commit()
    flash(f"Test report {code} created.", "info")
    return redirect(url_for("reports.report_detail", report_id=report_id))


@bp.route("/")
@require_any_role("technician", "planner")
def reports_list():
    init_db()
    db = get_db()
    user_id = session.get("user_id")
    role = current_role()

    pending_query = """
        SELECT tr.id, tr.report_code, tr.status, tr.overall_result, tr.created_at,
               ot.test_name, o.order_code, o.customer_name, tech.username AS technician_username
        FROM test_reports tr
        JOIN ordered_tests ot ON ot.id = tr.ordered_test_id
        JOIN customer_orders o ON o.id = ot.order_id
        JOIN users tech ON tech.id = tr.technician_user_id
        WHERE tr.status = 'submitted'
    """
    params: list = []
    if role == "technician":
        pending_query += " AND tr.technician_user_id != ?"
        params.append(user_id)
    pending_query += " ORDER BY tr.created_at"
    pending_reviews = db.execute(pending_query, params).fetchall()

    all_reports = db.execute(
        """
        SELECT tr.id, tr.report_code, tr.status, tr.overall_result, tr.created_at,
               ot.test_name, o.order_code, o.customer_name,
               tech.username AS technician_username, rev.username AS reviewer_username
        FROM test_reports tr
        JOIN ordered_tests ot ON ot.id = tr.ordered_test_id
        JOIN customer_orders o ON o.id = ot.order_id
        JOIN users tech ON tech.id = tr.technician_user_id
        LEFT JOIN users rev ON rev.id = tr.reviewer_user_id
        ORDER BY tr.created_at DESC
        """
    ).fetchall()

    return render_template(
        "modern/reports_list.html",
        pending_reviews=pending_reviews,
        all_reports=all_reports,
    )


@bp.route("/<int:report_id>", methods=["GET", "POST"])
@require_any_role("technician", "planner")
def report_detail(report_id: int):
    init_db()
    db = get_db()

    report = _fetch_report(db, report_id)
    if report is None:
        flash("Test report not found.", "error")
        return redirect(url_for("reports.reports_list"))

    user_id = session.get("user_id")
    is_author = report["technician_user_id"] == user_id
    is_eligible_reviewer = current_role() in ("technician", "planner") and user_id != report["technician_user_id"]

    if request.method == "POST":
        action = request.form.get("action", "")

        if action == "save_report":
            if not is_author or report["status"] != "draft":
                flash("This report can't be edited.", "error")
            else:
                _apply_report_edits(db, report_id, request.form)
                db.commit()
                flash("Report saved.", "info")
            return redirect(url_for("reports.report_detail", report_id=report_id))

        if action == "submit_report":
            if not is_author or report["status"] != "draft":
                flash("This report can't be submitted.", "error")
                return redirect(url_for("reports.report_detail", report_id=report_id))

            _apply_report_edits(db, report_id, request.form)
            overall_result = request.form.get("overall_result", "").strip() or None
            steps = db.execute("SELECT result FROM report_steps WHERE report_id = ?", (report_id,)).fetchall()

            if any(s["result"] is None for s in steps):
                db.commit()
                flash("Every test step needs a pass/fail/n-a result before submitting.", "error")
            elif not overall_result:
                db.commit()
                flash("Select an overall result before submitting.", "error")
            else:
                db.execute(
                    "UPDATE test_reports SET status = 'submitted', technician_signed_at = ?, overall_result = ? WHERE id = ?",
                    (_now(), overall_result, report_id),
                )
                db.commit()
                flash("Report submitted for review.", "info")
            return redirect(url_for("reports.report_detail", report_id=report_id))

        if action == "review_report":
            decision = request.form.get("decision", "").strip()
            comment = request.form.get("comment", "").strip() or None

            if not is_eligible_reviewer or report["status"] != "submitted":
                flash("You can't review this report.", "error")
            elif decision not in ("approved", "rejected"):
                flash("Select approve or reject.", "error")
            elif decision == "rejected" and not comment:
                flash("A comment is required when rejecting a report.", "error")
            else:
                db.execute(
                    """
                    UPDATE test_reports
                    SET status = ?, reviewer_user_id = ?, reviewer_decision = ?, reviewer_comment = ?, reviewer_signed_at = ?
                    WHERE id = ?
                    """,
                    (decision, user_id, decision, comment, _now(), report_id),
                )
                db.commit()
                flash(f"Report {decision}.", "info")
            return redirect(url_for("reports.report_detail", report_id=report_id))

        if action == "reopen_report":
            if not is_author or report["status"] != "rejected":
                flash("Only a rejected report can be reopened.", "error")
            else:
                db.execute("UPDATE test_reports SET status = 'draft' WHERE id = ?", (report_id,))
                db.commit()
                flash("Report reopened for editing.", "info")
            return redirect(url_for("reports.report_detail", report_id=report_id))

    return render_template(
        "modern/report_detail.html",
        report=report,
        is_author=is_author,
        is_eligible_reviewer=is_eligible_reviewer,
    )
