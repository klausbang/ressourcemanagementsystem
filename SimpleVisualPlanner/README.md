# SimpleVisualPlanner

A minimal Flask app assembled entirely from the reusable module library in
`../reusable_modules/` (`basic_app` + `database` + `proposals`) - no other domain
features yet. More functionality will be added later; for now this demonstrates that the
three modules compose into a working app with almost no glue code (`app/__init__.py`
and `app/routes_core.py` are the only files in this project that aren't a module's own
code or a page template).

## What it does

- Login/logout via `basic_app` (passwordless, username-only - three demo users, one per
  role, are seeded automatically on first run, see below).
- One dashboard page (`/dashboard`) listing what's working, with admin-only links to the
  proposals review and user admin screens.
- A working floating "P" button (bottom-right of every page, automatically - including
  any added later) for submitting an enhancement/bug/new-feature proposal, via the
  `proposals` module.
- An admin-only "Review Proposals" screen (`/proposals/admin`) to see everything
  submitted, change its status, and leave a comment - its nav link shows a live badge
  counting proposals still awaiting review.
- An admin-only "User Admin" screen (`/users`) to add, rename, or remove users and
  assign each one a role (`admin`, `user`, or `planner`), via `basic_app`'s
  `enable_user_admin()`.

## Run it

From this folder:

```bash
pip install -r requirements.txt
python run.py
```

Then open `http://127.0.0.1:5000/` and log in as one of the seeded demo users (no
password needed):

- `admin.demo` - lands on the dashboard, also sees the "Review Proposals" and "User
  Admin" nav links.
- `user.demo` - lands on the dashboard only.
- `planner.demo` - lands on the dashboard only (a plain, non-admin role, seeded so
  "planner" - one of the three role types the User Admin screen offers - has at least
  one real example account).

The SQLite database (`simplevisualplanner.db`, created next to `run.py` on first run) is
gitignored, same as RMS's own `rms.db` - delete it and restart to reset to a clean state
(the three demo users will be re-seeded).

## How it's assembled (`app/__init__.py`)

```python
app = basic_app.create_app({...})       # Flask app + login/logout + page shell
init_db_extension(app)                  # database module's per-request connection lifecycle
init_proposals(app, ...)                # registers the proposals blueprint + schema
basic_app.enable_user_admin(app, ...)   # registers the /users CRUD screen
# ... register this project's own "core" blueprint (routes_core.py) ...
with app.app_context():
    init_db()                           # runs every registered module's schema fragment
```

See `../reusable_modules/basic_app/README.md`, `.../database/README.md`, and
`.../proposals/README.md` for what each module offers and how to configure it -
everything used here (roles, nav items, role-home-endpoints, allowed proposal
types/statuses, the user-admin manager role) is plain configuration, not a fork of the
module's code.
