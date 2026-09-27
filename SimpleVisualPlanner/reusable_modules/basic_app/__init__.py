"""Reusable Flask app factory + login/logout + nav shell, generalized from RMS's
app/__init__.py and app/routes_common.py. See README.md for usage.
"""
from flask import Flask

from .user_admin import enable_user_admin

__all__ = ["create_app", "enable_user_admin"]


def create_app(config: dict | None = None, import_name: str = __name__) -> Flask:
    """Create a Flask app wired up with basic_app's login/logout blueprint and a Modern-
    styled page shell (topbar, nav, flash messages). `config` (all keys optional) may
    set:
      - Any plain Flask config key (SECRET_KEY, DATABASE, ...).
      - user_lookup: callable(username) -> dict|None with at least
        {id, username, role}, or None if the username is unknown. Defaults to a SQLite
        lookup against the `users` table this module owns (see auth.py).
      - roles: list of role-name strings this app recognizes (default: ["user"]).
      - role_home_endpoints: {role: endpoint_name} - where each role lands right after
        login (default: {}, meaning every role falls back to "/").
      - nav_items: list of {"label": str, "endpoint": str, "roles": [str, ...],
        "badge": callable} dicts rendered in the top nav for a signed-in user; "roles"
        is optional - omit it (or leave it empty) to show the item to every signed-in
        user regardless of role. "badge" is also optional: a zero-argument callable
        returning an int, invoked fresh on every page render, shown as a small numbered
        badge next to the label whenever it returns a truthy value (e.g. a count of
        proposals awaiting review - see the `proposals` module's `count_pending()`).
      - brand: short text shown in the topbar and page title (default: "App").

    `import_name` should be your own app's `__name__` (e.g. pass `import_name=__name__`
    from your own `create_app()`), NOT left at the default - Flask resolves the app's
    root_path (and therefore its default `templates/` search folder, where render_ui()
    expects to find your own page templates under `templates/basic_app/...`) from
    whichever module constructs `Flask(...)`. Leaving this at its default would make
    Flask search *this* module's own folder instead of your app's, so any of your own
    page templates would raise TemplateNotFound.

    Blueprints beyond this module's own `auth` blueprint (e.g. a consuming app's own
    routes, or the `proposals` module) are registered by the caller after this returns.
    """
    config = config or {}
    app = Flask(import_name)
    app.config["SECRET_KEY"] = config.get("SECRET_KEY", "dev-secret-change-me")
    app.config["DATABASE"] = config.get("DATABASE", "app.db")
    app.config["BASIC_APP_ROLES"] = list(config.get("roles", ["user"]))
    app.config["BASIC_APP_ROLE_HOME_ENDPOINTS"] = dict(config.get("role_home_endpoints", {}))
    app.config["BASIC_APP_NAV_ITEMS"] = list(config.get("nav_items", []))
    app.config["BASIC_APP_USER_LOOKUP"] = config.get("user_lookup")
    app.config["BASIC_APP_BRAND"] = config.get("brand", "App")

    from .auth import bp as auth_bp
    app.register_blueprint(auth_bp)

    from .ui import nav_items_for_current_user
    from .auth import role_home_url

    @app.context_processor
    def _inject_basic_app_helpers():
        return {
            "basic_app_nav_items": nav_items_for_current_user(),
            "basic_app_home_url": role_home_url(),
        }

    return app
