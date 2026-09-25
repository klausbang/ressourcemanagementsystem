"""Page-rendering helper, generalized from RMS's app/routes_common.py:render_ui(). RMS
resolves f"{ui_mode}/{template_name}" because it ships two parallel UIs (Simple/Modern);
this module ships only the Modern-styled one, so there's no mode prefix to resolve - but
render_ui() still exists as its own function (rather than every caller using Flask's
render_template() directly) as a single place to inject default context every page
gets (current_role/current_user), and so a future second UI mode could add a prefix back
here without every call site changing.

Pass the template's full path relative to whichever registered template folder it lives
in - "basic_app/dashboard.html" for your own app's pages (see basic_app's README on
where those live), "proposals/admin_review.html" for a page the proposals module itself
provides (its own routes already do this - you don't normally call it with that path
yourself). There is deliberately no automatic prefix: an earlier version of this module
always prepended "basic_app/", which broke as soon as a second module (proposals) needed
to render its own differently-namespaced templates - multi-module composition is the
whole point of this library, so an unprefixed pass-through is correct here even though
it costs a few extra characters at each call site.
"""
from flask import current_app, render_template, session

from .auth import current_role, current_user


def render_ui(template_path: str, **context):
    context.setdefault("current_role", current_role())
    context.setdefault("current_user", current_user())
    return render_template(template_path, **context)


def nav_items_for_current_user() -> list[dict]:
    """The configured nav_items visible to whoever is currently signed in: everything if
    no "roles" key is set on an item, otherwise only if the current role is listed.
    Nothing at all if no one is signed in.

    Each returned item also carries a resolved "badge_count" key. An item's own
    "badge" config value - a zero-argument callable returning an int, e.g. a query
    counting rows that need attention - is invoked fresh here, every call (i.e. every
    page render), so the count in the nav is never stale. An item with no "badge"
    configured gets "badge_count": None. base.html renders a small numbered badge next
    to the label whenever "badge_count" is truthy (0 or None shows nothing).
    """
    if not session.get("username"):
        return []
    role = current_role()
    items = current_app.config.get("BASIC_APP_NAV_ITEMS", [])
    visible = [item for item in items if not item.get("roles") or role in item["roles"]]
    resolved = []
    for item in visible:
        item = dict(item)
        badge = item.get("badge")
        item["badge_count"] = badge() if callable(badge) else None
        resolved.append(item)
    return resolved
