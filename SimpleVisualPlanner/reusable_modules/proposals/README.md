# `proposals` module

The floating "P" button any signed-in user sees on every page - submit an enhancement
idea, a new-feature request, or a bug report, tagged with exactly which page they were
on (or marked "General" if it wasn't about that specific page) - plus a reviewer screen
to see everything submitted and change its status/leave a comment.

Extracted from the RMS project's `app/routes_proposals.py` (submission), the proposals
tab of `app/routes_admin.py`/`templates/modern/admin_manage.html` (review), and the "P"
button + dialog in `templates/modern/base.html`. Depends on `basic_app` (role/session
helpers, `render_ui`, the floating-button hook point in `base.html`) and `database`
(schema registration, `get_db`).

## Install

Copy (or symlink) `reusable_modules/proposals/` alongside `reusable_modules/basic_app/`
and `reusable_modules/database/`, and import as `from reusable_modules import proposals`.

## Usage

```python
from reusable_modules import basic_app, proposals
from reusable_modules.database import init_db_extension, init_db

app = basic_app.create_app({...})
init_db_extension(app)

proposals.init_proposals(
    app,
    allowed_roles=("admin", "user"),   # who can submit - default: every configured role
    reviewer_role="admin",             # who can see/act on the review screen
    proposal_types=("enhancement", "bug", "new_feature"),
    statuses=("new", "accepted", "in_progress", "done", "rejected"),
)

with app.app_context():
    init_db()   # runs this module's `proposals` table schema too
```

That's it - no template work needed. `basic_app/base.html` already includes
`proposals/floating_button.html` (via `{% include ... ignore missing %}`, a soft
reference that's a no-op when `proposals` isn't installed), so once `init_proposals()`
has run, **every page that extends `basic_app/base.html` gets the floating button
automatically** - the current ones and any you add later, with no per-page template
work and nothing to remember. It renders nothing for a signed-out visitor either way.
Override the `floating_button` block with your own content (or with nothing) in one
specific page template if you want to suppress or replace the button on just that page.

Link to the reviewer screen from your own nav (via `basic_app`'s `nav_items` config, or
a plain link) - `{{ url_for('proposals.admin_review') }}`.

## Configuration options (`init_proposals()`, all optional except `app`)

| Argument | Default | What it does |
|---|---|---|
| `allowed_roles` | every role in `app.config["BASIC_APP_ROLES"]` | Which roles may submit a proposal (`/proposals/new`). |
| `reviewer_role` | `"admin"` | The single role that may see/act on `/proposals/admin`. |
| `proposal_types` | `("enhancement", "bug", "new_feature")` | Allowed values for the Type field. |
| `statuses` | `("new", "accepted", "in_progress", "done", "rejected")` | Allowed values for the Status field. |

**Why no database `CHECK` constraint on these two columns** (unlike RMS's own
`proposals` table): a `CHECK` would fix the allowed values at table-creation time, and
SQLite can't widen a `CHECK` in place afterward - the only way is the rebuild-and-rename
migration `database/migrations.py` provides. Since `proposal_types`/`statuses` are
meant to be configured per consuming app (and that configuration might reasonably change
as an app evolves), this module validates them in `routes.py` instead, against whatever
`init_proposals()` was last called with - so changing the allowed set is just a code
change, never a migration.

## Routes

- **`GET/POST /proposals/new`** - the submission form. `GET` renders a full page (see
  "Simplifications" below); `POST` validates and inserts a row, then redirects back to
  the `path` the proposal was reported against (the P-button dialog's own form posts
  here directly and reloads the same page). Role-checked against `allowed_roles`.
- **`GET/POST /proposals/admin`** - the reviewer screen: one card per proposal with an
  editable Title/Description/General flag/Type/Status/Admin comment and a Delete
  button. Role-checked against `reviewer_role`.

## Nav badge: `count_pending()`

`reusable_modules.proposals.count_pending(statuses=("new",))` returns how many
proposals still need reviewer attention - a ready-made counter for `basic_app`'s
nav-badge feature (see that module's README, "Nav badges"). Wire it to whichever nav
item points at the review screen:

```python
"nav_items": [
    {
        "label": "Review Proposals",
        "endpoint": "proposals.admin_review",
        "roles": ["admin"],
        "badge": proposals.count_pending,   # pass the function itself, don't call it
    },
],
```

The reviewer then sees a live "3" (or whatever) next to the nav link whenever proposals
are waiting, and nothing once the queue is empty. Pass a different `statuses` tuple
(e.g. `("new", "in_progress")`) if your app's definition of "needs attention" should be
broader than just brand-new submissions.

## What's simplified vs. RMS's own proposals feature

- **No Table view** - RMS's Admin Proposals tab has a Form view (what this module's
  `admin_review.html` reproduces) *and* a keyboard-navigable editable-grid Table view.
  Only Form view is included here; add a grid view yourself on top of this module's
  `proposals` table if you need it.
- **No `tester_comment`/`test_status` fields** - these are RMS's own internal QA-workflow
  columns (did a tester verify the fix), not a generic part of "submit an idea, review
  it." Add them as your own extra columns/form fields if your app needs the same
  tester-verification workflow.
- **No duplicate-row highlighting** (RMS's `_dup` flag via `table_utils.rows_with_meta`)
  - straightforward to add back using the `database` module's `rows_with_meta()` if you
    want it (pass e.g. `dup_keys=["path", "title", "submitted_by_username"]`).
- **No `CHECK` constraint on type/status** - see above.

## Assets used from `basic_app`

The dialog and cards use `basic_app`'s generic CSS classes only (`.btn`, `.card-title`,
`.form-grid`, `.field`, `.badge`, `.group-card*` - the last defined locally in
`admin_review.html`'s own `<style>` block, since it's specific to this module's card
layout rather than a generic pattern worth adding to `basic_app`'s stylesheet). No new
JS dependency on `basic_app/app.js` - the dialog's open/close and drag-to-move behavior
is self-contained inline `<script>` in `floating_button.html`.
