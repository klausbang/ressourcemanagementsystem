"""Proposal submission (the "P" button) + reviewer management, generalized from RMS's
app/routes_proposals.py (submission) and the proposals tab of app/routes_admin.py /
templates/modern/admin_manage.html (review). Depends on basic_app (role/session helpers,
render_ui) and database (schema registration, get_db) - see each module's own README.
"""
from flask import Flask

from reusable_modules.database import get_db, register_schema

from .schema import PROPOSALS_SCHEMA

DEFAULT_TYPES = ("enhancement", "bug", "new_feature")
DEFAULT_STATUSES = ("new", "accepted", "in_progress", "done", "rejected")

# "new" is the one status that means "nobody with reviewer authority has looked at this
# yet" - the sensible default definition of "needs action" for count_pending() below.
NEEDS_ACTION_STATUSES = ("new",)


def init_proposals(
    app: Flask,
    allowed_roles: tuple[str, ...] = (),
    reviewer_role: str = "admin",
    proposal_types: tuple[str, ...] = DEFAULT_TYPES,
    statuses: tuple[str, ...] = DEFAULT_STATUSES,
) -> None:
    """Wire the proposals module into `app`. Call once, after basic_app.create_app() and
    before the app starts serving requests (init_db() still needs to run afterward, same
    as any other module's schema fragment).

    - allowed_roles: which roles may submit a proposal (default: every role in
      app.config["BASIC_APP_ROLES"], i.e. every signed-in user, if basic_app.create_app()
      already ran; pass an explicit tuple to restrict submission to fewer roles).
    - reviewer_role: which single role may see/act on the review screen (default: "admin").
    - proposal_types / statuses: the allowed values for each field, validated in
      routes.py - not enforced by a database CHECK constraint (see schema.py), so this
      list can change later without a migration.
    """
    register_schema(PROPOSALS_SCHEMA)
    app.config["PROPOSALS_ALLOWED_ROLES"] = tuple(allowed_roles) or tuple(
        app.config.get("BASIC_APP_ROLES", ())
    )
    app.config["PROPOSALS_REVIEWER_ROLE"] = reviewer_role
    app.config["PROPOSALS_TYPES"] = tuple(proposal_types)
    app.config["PROPOSALS_STATUSES"] = tuple(statuses)

    from .routes import bp as proposals_bp
    app.register_blueprint(proposals_bp)

    @app.context_processor
    def _inject_proposals_defaults():
        # So proposals/floating_button.html - included from base.html on every page,
        # not just ones that explicitly pass proposal_types in their own render_ui()
        # call - always has a proposal_types list to build its Type dropdown from.
        return {"proposal_types": app.config["PROPOSALS_TYPES"]}


def count_pending(statuses: tuple[str, ...] = NEEDS_ACTION_STATUSES) -> int:
    """How many proposals still need reviewer attention (default: status "new", i.e. not
    yet looked at). A zero-argument-callable-shaped default (call it directly, don't
    wrap it) - drop it straight into basic_app's nav_items as a "badge" callable to show
    a live pending-count badge on whichever nav link points at the review screen:

        "nav_items": [
            {"label": "Review Proposals", "endpoint": "proposals.admin_review",
             "roles": ["admin"], "badge": proposals.count_pending},
        ]

    Needs an active app/request context (it calls the database module's get_db()), which
    a nav_items "badge" callable always has - it's only ever invoked while rendering a
    page.
    """
    db = get_db()
    placeholders = ",".join("?" for _ in statuses)
    row = db.execute(
        f"SELECT COUNT(*) AS n FROM proposals WHERE status IN ({placeholders})", statuses
    ).fetchone()
    return row["n"] if row else 0
