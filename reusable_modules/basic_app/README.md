# `basic_app` module

A reusable Flask app factory plus a self-contained, styled page shell: sticky topbar
with a configurable brand/nav, session-based login/logout (passwordless username
lookup, like a demonstrator - pluggable if you need something stronger), flash messages,
and a mobile-friendly responsive layout. No JavaScript framework, no build step - one
CSS file and one small JS file, both served by this module itself.

Extracted from the RMS project's `app/__init__.py`, `app/routes_common.py`, and its
Modern UI (`templates/modern/base.html`, `static/css/modern.css`,
`static/js/modern.js`) - only the Modern styled UI was carried over; RMS's separate
Simple (no-JS) UI was dropped for this library.

## Install

No packaging yet - copy (or symlink) `reusable_modules/basic_app/` into your project
next to `reusable_modules/database/` (it depends on that module for its `users` table
and connection lifecycle) and import as `from reusable_modules import basic_app`.

## Usage

```python
from reusable_modules import basic_app
from reusable_modules.database import init_db_extension, init_db

app = basic_app.create_app(
    {
        "SECRET_KEY": "change-me-in-real-deployments",
        "DATABASE": "myapp.db",
        "brand": "My App",
        "roles": ["admin", "user"],
        "role_home_endpoints": {"admin": "core.dashboard", "user": "core.dashboard"},
        "nav_items": [
            {"label": "Dashboard", "endpoint": "core.dashboard"},
            {"label": "Admin only page", "endpoint": "core.admin_page", "roles": ["admin"]},
        ],
    },
    import_name=__name__,   # required in practice - see "import_name" note below
)

init_db_extension(app)   # wires up the database module's per-request connection
# ... register your own blueprints, and any other reusable module (e.g. proposals) ...
with app.app_context():
    init_db()            # runs every registered schema fragment, including this
                          # module's own `users` table

# seed at least one user so there's something to log in as:
with app.app_context():
    from reusable_modules.database import get_db
    db = get_db()
    db.execute("INSERT OR IGNORE INTO users (username, role) VALUES ('admin', 'admin')")
    db.commit()
```

Then visit `/login`, sign in as `admin` (no password), and you land on whatever
`role_home_endpoints["admin"]` points to.

## `import_name` - not optional in practice

`create_app(config, import_name=__name__)`'s second argument isn't a `config` dict key
because Flask needs it *before* it can even construct the `Flask` object - always pass
your own module's `__name__` here. Flask resolves the app's `root_path` (and therefore
where it looks for your own page templates, under `templates/basic_app/...`) from
whichever module calls `Flask(import_name)`; leaving this at its default makes Flask
search *this* module's own folder instead of your app's, and any of your own page
templates will raise `TemplateNotFound`. See `SimpleVisualPlanner/app/__init__.py` for
a working example.

## Configuration options (all optional)

| Key | Default | What it does |
|---|---|---|
| `SECRET_KEY` | `"dev-secret-change-me"` | Flask's session-signing key. Set a real one for anything beyond local dev. |
| `DATABASE` | `"app.db"` | Passed straight to the `database` module - see that module's README. |
| `brand` | `"App"` | Short text shown in the topbar and `<title>`. |
| `roles` | `["user"]` | The role-name strings your app recognizes. Stored on `app.config["BASIC_APP_ROLES"]` for other modules (e.g. `proposals`) to default from. |
| `role_home_endpoints` | `{}` | `{role: endpoint_name}` - where a signed-in user of that role lands after login (and what the brand link in the topbar points at). A role with no entry falls back to `/`. |
| `nav_items` | `[]` | `[{"label", "endpoint", "roles", "badge"}]` - top nav links shown to a signed-in user. Omit `"roles"` (or leave it `[]`) to show an item to everyone signed in, regardless of role. `"badge"` is optional: a zero-argument callable returning an int, invoked fresh on every page render, shown as a small numbered badge next to the label whenever it returns a truthy value - see "Nav badges" below. |
| `user_lookup` | SQLite `users` table lookup | `callable(username) -> {"id", "username", "role"} | None`. Override this to back logins with anything else - a different table, an external directory, real password checking (this module never touches passwords itself either way). |

## What you get

- **`reusable_modules.basic_app.create_app(config)`** - the Flask app factory.
- **`reusable_modules.basic_app.auth`**:
  - `require_role(*roles)` - decorator restricting a view: `@require_role("admin")`.
  - `current_role()` / `current_user()` - read the signed-in session.
  - `role_home_url()` - the URL for the current role's configured landing page.
  - Routes: `GET/POST /login`, `GET /logout`.
- **`reusable_modules.basic_app.ui`**:
  - `render_ui(template_path, **context)` - a thin wrapper around Flask's own
    `render_template()` that injects default context every page gets
    (`current_role`/`current_user`). Pass the template's full path relative to whichever
    registered template folder it lives in, same as you would to `render_template()`
    directly - there's no automatic prefix. Use it (rather than `render_template()`) so
    any future default context this module adds reaches every page automatically.
  - `nav_items_for_current_user()` - the configured `nav_items` filtered to what the
    current role should see (used internally by `base.html`, exposed in case you need it
    elsewhere too).
- **`reusable_modules.basic_app.enable_user_admin(app, manager_role="admin", roles=())`**
  - opt-in CRUD screen (list/add/edit/delete a user, assign a role) for this module's own
    `users` table, at `GET/POST /users` (endpoint name `"user_admin"`, no blueprint
    prefix). `roles` is the dropdown of assignable roles (default: whatever `roles` you
    passed to `create_app()`). Not called automatically by `create_app()` - call it
    yourself, any time afterward, only if your app actually wants this screen exposed:

    ```python
    app = basic_app.create_app({...}, import_name=__name__)
    basic_app.enable_user_admin(app, manager_role="admin")
    # ... then link to it from your own nav_items:
    # {"label": "User Admin", "endpoint": "user_admin", "roles": ["admin"]}
    ```

    A manager can't delete the account they're currently signed in as (editing your own
    row is fine and keeps the session in sync). Its page (like every page extending
    `basic_app/base.html`) gets the `proposals` module's floating "P" button
    automatically if `proposals` is installed - see "Template inheritance" below.

## Template inheritance

Your own page templates extend `basic_app/base.html`:

```jinja
{% extends "basic_app/base.html" %}
{% block title %}Dashboard{% endblock %}
{% block content %}
  <div class="page-header">
    <div class="eyebrow">Overview</div>
    <h1>Dashboard</h1>
  </div>
  <div class="card">...</div>
{% endblock %}
```

Place the file at `your_app/templates/basic_app/dashboard.html` in your own app's
template folder (Flask searches your app's own `templates/` directory - resolved from
the `import_name` you passed to `create_app()`, see above - before any blueprint's;
namespacing your own pages under the same `basic_app/` subfolder this module's own
templates use is a convention worth keeping, not a requirement, but avoids ever
colliding with a filename this module or another reusable module happens to use), then
render it with `render_ui("basic_app/dashboard.html")` from your view.

There's also a `{% block floating_button %}{% include "proposals/floating_button.html"
ignore missing %}{% endblock %}` right before `</body>` in `base.html` - every page gets
the `proposals` module's floating "P" button automatically, on every current page and
any future one, with zero per-page work, as long as `proposals` is installed and
`init_proposals()` was called (its template registers under exactly that path). Jinja's
`ignore missing` means this is a soft reference, not a hard import - an app that never
installs `proposals` at all just renders nothing here instead of raising
`TemplateNotFound`, so `basic_app` still works standalone. Override the block with your
own content (or with nothing) in a specific page template if you want to suppress or
replace the button on just that one page.

## Nav badges

Any `nav_items` entry can carry a small numbered badge - e.g. a count of proposals
awaiting review on a "Review Proposals" link - by giving it a `"badge"` callable:

```python
def count_something_pending() -> int:
    from reusable_modules.database import get_db
    db = get_db()
    return db.execute("SELECT COUNT(*) FROM my_table WHERE needs_action = 1").fetchone()[0]

"nav_items": [
    {"label": "My Queue", "endpoint": "core.queue", "badge": count_something_pending},
],
```

The callable takes no arguments and returns an int; it's invoked fresh on every page
render (inside `nav_items_for_current_user()`, called from `base.html`'s nav loop via
the `basic_app_nav_items` context processor), so the badge is never stale, and it's
simply not shown when the count is `0` (or the item has no `"badge"` at all). It needs an
active app/request context to call `get_db()` - guaranteed here, since it only ever runs
while a page is being rendered.

The `proposals` module ships a ready-made one for its own table -
`reusable_modules.proposals.count_pending()` - see that module's README for the
one-line way to wire it to its own review screen's nav link. This mechanism itself lives
here in `basic_app` (not in `proposals`) specifically so *any* module or app-specific nav
item can use it, not just the proposals review screen.

## Available CSS classes (`app.css`)

Design tokens (CSS custom properties: `--color-primary`, `--radius-md`, etc.), topbar/
nav, `.btn`/`.btn-primary`/`.btn-secondary`/`.btn-danger`/`.btn-ghost` (+ `.btn-sm`/
`.btn-block`), `.flash`/`.flash-info`/`.flash-error`, `.page`/`.page-header`/`.card`/
`.stat-strip`/`.stat-tile`, `.form-grid`/`.field`, `.table-wrap`/`table.modern-table`,
`.badge`, `.nav-badge` (the nav-badge counter above), `.empty-state`, `.callout`,
`.auth-wrap`/`.auth-card`, `.section-head`/`.section-help`. Deliberately excludes
RMS-specific component classes (Gantt charts,
the editable-grid prototype, work-order cards, etc.) - add your own domain classes on
top of these generic ones in your own app's stylesheet.

## Available JS behavior (`app.js`)

Mobile nav toggle, flash message auto-dismiss (6s) + manual close, `data-confirm="..."`
attribute on any button/link triggers a native `confirm()` before the action proceeds,
and automatic dirty-form tracking (a form's own Save/submit button stays disabled until
something in it changes, plus a native "leave without saving?" prompt if you navigate
away with an unsaved change) - all zero-config, just markup conventions.
