from flask import Blueprint, redirect, session, url_for

from reusable_modules.basic_app.auth import require_role
from reusable_modules.basic_app.ui import render_ui

bp = Blueprint("core", __name__)


@bp.route("/")
def index():
    if session.get("username"):
        return redirect(url_for("core.dashboard"))
    return redirect(url_for("auth.login"))


@bp.route("/dashboard")
@require_role("admin", "user")
def dashboard():
    return render_ui("basic_app/dashboard.html")
