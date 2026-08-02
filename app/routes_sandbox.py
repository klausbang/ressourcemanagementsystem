"""Editable-table-view prototypes (Phase 22, proposal id 23): three different UI
approaches for pasting/inserting/exporting table rows in bulk (from Excel, CSV, or
JSON), all operating on the same throwaway sandbox_items table so a trial genuinely
persists without touching any real Admin/Planner data. Admin-only, Modern UI only -
this is an internal try-it-and-decide area, not a role-facing feature.
"""

import csv
import io
import json

from flask import Blueprint, Response, flash, redirect, render_template, request, url_for

from .db import _seed_sandbox_items, get_db, init_db
from .routes_common import require_role

bp = Blueprint("sandbox", __name__, url_prefix="/sandbox")

FIELDS = ["code", "name", "category", "quantity", "notes"]


def _rows(db) -> list[dict]:
    return [dict(row) for row in db.execute("SELECT * FROM sandbox_items ORDER BY id").fetchall()]


def _redirect_to(page: str):
    endpoint = {"a": "sandbox.page_a", "b": "sandbox.page_b", "c": "sandbox.page_c"}.get(page, "sandbox.index")
    return redirect(url_for(endpoint))


@bp.route("/")
@require_role("admin")
def index():
    init_db()
    return render_template("modern/sandbox_index.html")


@bp.route("/a")
@require_role("admin")
def page_a():
    init_db()
    db = get_db()
    return render_template("modern/sandbox_a.html", rows=_rows(db))


@bp.route("/b")
@require_role("admin")
def page_b():
    init_db()
    db = get_db()
    return render_template("modern/sandbox_b.html", rows=_rows(db))


@bp.route("/c")
@require_role("admin")
def page_c():
    init_db()
    db = get_db()
    return render_template("modern/sandbox_c.html", rows=_rows(db))


def _clean_row(raw: dict) -> dict:
    quantity = raw.get("quantity")
    try:
        quantity = int(quantity) if quantity not in (None, "") else None
    except (TypeError, ValueError):
        quantity = None
    return {
        "code": (raw.get("code") or "").strip() or None,
        "name": (raw.get("name") or "").strip() or None,
        "category": (raw.get("category") or "").strip() or None,
        "quantity": quantity,
        "notes": (raw.get("notes") or "").strip() or None,
    }


@bp.route("/action", methods=["POST"])
@require_role("admin")
def action():
    init_db()
    db = get_db()
    action_name = request.form.get("action", "")
    return_to = request.form.get("return_to", "a")

    if action_name == "reset_sample_data":
        _seed_sandbox_items(db, only_if_empty=False)
        db.commit()
        flash("Sandbox reset to its 8 sample rows.", "info")

    elif action_name == "replace_all":
        # Options A and C: the whole grid's current state, collected client-side into one
        # JSON blob, replaces every sandbox row in one transaction - the "spreadsheet" model
        # where there's no meaningful difference between an edited, pasted, or newly typed row.
        try:
            raw_rows = json.loads(request.form.get("rows_json", "[]"))
        except (TypeError, ValueError):
            raw_rows = None
        if raw_rows is None or not isinstance(raw_rows, list):
            flash("Could not read the submitted table data.", "error")
        else:
            db.execute("DELETE FROM sandbox_items")
            db.execute("DELETE FROM sqlite_sequence WHERE name = 'sandbox_items'")
            for raw in raw_rows:
                if not isinstance(raw, dict):
                    continue
                row = _clean_row(raw)
                if not any(row.values()):
                    continue  # skip fully-blank trailing rows
                db.execute(
                    "INSERT INTO sandbox_items (code, name, category, quantity, notes) VALUES (?, ?, ?, ?, ?)",
                    (row["code"], row["name"], row["category"], row["quantity"], row["notes"]),
                )
            db.commit()
            flash(f"Saved {len(raw_rows)} row(s).", "info")

    elif action_name == "create_row":
        row = _clean_row(request.form)
        db.execute(
            "INSERT INTO sandbox_items (code, name, category, quantity, notes) VALUES (?, ?, ?, ?, ?)",
            (row["code"], row["name"], row["category"], row["quantity"], row["notes"]),
        )
        db.commit()
        flash("Row added.", "info")

    elif action_name == "update_row":
        item_id = request.form.get("item_id", "").strip()
        row = _clean_row(request.form)
        db.execute(
            "UPDATE sandbox_items SET code = ?, name = ?, category = ?, quantity = ?, notes = ? WHERE id = ?",
            (row["code"], row["name"], row["category"], row["quantity"], row["notes"], item_id),
        )
        db.commit()
        flash("Row saved.", "info")

    elif action_name == "delete_row":
        item_id = request.form.get("item_id", "").strip()
        db.execute("DELETE FROM sandbox_items WHERE id = ?", (item_id,))
        db.commit()
        flash("Row deleted.", "info")

    elif action_name == "batch_insert":
        # Option B: rows already parsed and previewed client-side (from a pasted
        # Excel/CSV block or an uploaded CSV/JSON file), appended rather than replacing
        # anything already in the table - the "traditional form" model treats this as
        # adding N new rows, not re-stating the whole table.
        try:
            raw_rows = json.loads(request.form.get("rows_json", "[]"))
        except (TypeError, ValueError):
            raw_rows = None
        if not raw_rows or not isinstance(raw_rows, list):
            flash("No rows to insert - paste or choose a file first, then Preview.", "error")
        else:
            inserted = 0
            for raw in raw_rows:
                if not isinstance(raw, dict):
                    continue
                row = _clean_row(raw)
                if not any(row.values()):
                    continue
                db.execute(
                    "INSERT INTO sandbox_items (code, name, category, quantity, notes) VALUES (?, ?, ?, ?, ?)",
                    (row["code"], row["name"], row["category"], row["quantity"], row["notes"]),
                )
                inserted += 1
            db.commit()
            flash(f"Inserted {inserted} new row(s).", "info")

    return _redirect_to(return_to)


@bp.route("/export.json")
@require_role("admin")
def export_json():
    init_db()
    db = get_db()
    rows = [{k: r[k] for k in FIELDS} for r in _rows(db)]
    body = json.dumps(rows, indent=2)
    return Response(
        body,
        mimetype="application/json",
        headers={"Content-Disposition": "attachment; filename=sandbox-items.json"},
    )


@bp.route("/export.csv")
@require_role("admin")
def export_csv():
    init_db()
    db = get_db()
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=FIELDS)
    writer.writeheader()
    for r in _rows(db):
        writer.writerow({k: r[k] for k in FIELDS})
    return Response(
        buf.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=sandbox-items.csv"},
    )
