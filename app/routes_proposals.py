"""Enhancement/bug proposal submission (any signed-in role). Admin review of
submitted proposals lives in routes_admin.py / admin_manage.html instead, next
to the rest of the admin-managed lists.
"""

from datetime import datetime
from urllib.parse import urlparse

from flask import Blueprint, flash, redirect, request, session, url_for

from .db import get_db, init_db
from .routes_common import render_ui, require_any_role

bp = Blueprint("proposals", __name__, url_prefix="/proposals")


def _safe_redirect_target(path: str | None) -> str:
    """Only ever redirect back to a same-site relative path, never an external URL."""
    if path and path.startswith("/") and not path.startswith("//"):
        return path
    return url_for("common.home")


@bp.route("/new", methods=["GET", "POST"])
@require_any_role("admin", "planner", "technician")
def new_proposal():
    init_db()
    db = get_db()

    if request.method == "POST":
        path = request.form.get("path", "").strip()
        proposal_type = request.form.get("proposal_type", "").strip()
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip() or None

        if proposal_type not in ("enhancement", "bug"):
            flash("Please choose whether this is an enhancement or a bug report.", "error")
            return render_ui("proposal_new.html", path=path, form_values=request.form)
        if not title:
            flash("A short title is required.", "error")
            return render_ui("proposal_new.html", path=path, form_values=request.form)

        db.execute(
            """
            INSERT INTO proposals
                (path, proposal_type, title, description, submitted_by_user_id, submitted_by_username, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                path or "/",
                proposal_type,
                title,
                description,
                session.get("user_id"),
                session.get("username"),
                datetime.now().strftime("%Y-%m-%d %H:%M"),
            ),
        )
        db.commit()
        flash("Thanks - your proposal was submitted for review.", "info")
        return redirect(_safe_redirect_target(path))

    path = request.args.get("path", "")
    if not path and request.referrer:
        path = urlparse(request.referrer).path or "/"
    return render_ui("proposal_new.html", path=path or "/", form_values={})
