from datetime import datetime
from urllib.parse import urlparse

from flask import Blueprint, current_app, flash, redirect, request, session, url_for

from reusable_modules.basic_app.auth import current_role
from reusable_modules.basic_app.ui import render_ui
from reusable_modules.database import get_db

bp = Blueprint("proposals", __name__, url_prefix="/proposals", template_folder="templates")


def _safe_redirect_target(path: str | None) -> str:
    """Only ever redirect back to a same-site relative path, never an external URL."""
    if path and path.startswith("/") and not path.startswith("//"):
        return path
    return url_for("auth.login")


def _deny(required_role_desc: str):
    flash(f"Access denied. Required role: {required_role_desc}.", "error")
    return redirect(url_for("auth.login"))


@bp.route("/new", methods=["GET", "POST"])
def new_proposal():
    allowed_roles = current_app.config.get("PROPOSALS_ALLOWED_ROLES", ())
    if allowed_roles and current_role() not in allowed_roles:
        return _deny(" or ".join(allowed_roles))

    db = get_db()
    types = current_app.config.get("PROPOSALS_TYPES", ())

    if request.method == "POST":
        path = request.form.get("path", "").strip()
        proposal_type = request.form.get("proposal_type", "").strip()
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip() or None
        is_general = 1 if request.form.get("is_general") else 0

        if proposal_type not in types:
            flash("Please choose a valid proposal type.", "error")
            return render_ui("proposals/new.html", path=path, form_values=request.form)
        if not title:
            flash("A short title is required.", "error")
            return render_ui("proposals/new.html", path=path, form_values=request.form)

        db.execute(
            """
            INSERT INTO proposals
                (path, proposal_type, title, description, submitted_by_user_id,
                 submitted_by_username, created_at, is_general)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                path or "/",
                proposal_type,
                title,
                description,
                session.get("user_id"),
                session.get("username"),
                datetime.now().strftime("%Y-%m-%d %H:%M"),
                is_general,
            ),
        )
        db.commit()
        flash("Thanks - your proposal was submitted for review.", "info")
        return redirect(_safe_redirect_target(path))

    path = request.args.get("path", "")
    if not path and request.referrer:
        path = urlparse(request.referrer).path or "/"
    return render_ui("proposals/new.html", path=path or "/", form_values={})


@bp.route("/admin", methods=["GET", "POST"])
def admin_review():
    reviewer_role = current_app.config.get("PROPOSALS_REVIEWER_ROLE", "admin")
    if current_role() != reviewer_role:
        return _deny(reviewer_role)

    db = get_db()
    types = current_app.config.get("PROPOSALS_TYPES", ())
    statuses = current_app.config.get("PROPOSALS_STATUSES", ())

    if request.method == "POST":
        action = request.form.get("action", "")

        if action == "update_proposal":
            proposal_id = request.form.get("proposal_id", "").strip()
            title = request.form.get("title", "").strip()
            description = request.form.get("description", "").strip() or None
            proposal_type = request.form.get("proposal_type", "").strip()
            status = request.form.get("status", "").strip()
            admin_comment = request.form.get("admin_comment", "").strip() or None
            is_general = 1 if request.form.get("is_general") else 0

            if not (proposal_id and title and proposal_type in types and status in statuses):
                flash("A valid proposal, title, type, and status are required.", "error")
            else:
                db.execute(
                    """
                    UPDATE proposals
                    SET title = ?, description = ?, proposal_type = ?, status = ?,
                        admin_comment = ?, is_general = ?, admin_user_id = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        title, description, proposal_type, status, admin_comment, is_general,
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

        return redirect(url_for("proposals.admin_review"))

    proposals = [dict(r) for r in db.execute("SELECT * FROM proposals ORDER BY created_at DESC").fetchall()]
    return render_ui("proposals/admin_review.html", proposals=proposals, proposal_types=types, statuses=statuses)
