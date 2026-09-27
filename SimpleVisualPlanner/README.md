# SimpleVisualPlanner

A Flask app built on the reusable module library in `../reusable_modules/`
(`basic_app` + `database` + `proposals`), with its own first real domain feature - the
Visual Planner - grown on top through its own accepted-proposal review cycle.

## What it does

- Login/logout via `basic_app` (passwordless, username-only - three demo users, one per
  role, are seeded automatically on first run, see below).
- A **Visual Planner** (`/planner`, planner/admin roles) - one row per project, a
  15-minute-resolution time axis, and an "Unplanned" queue of tests waiting to be
  scheduled. Drag a test onto its project's row (a block's width follows its duration),
  onto "New project" if that project isn't listed yet, or drag an already-placed test to
  a new time or back into the queue. Every field is directly editable. Still a
  client-side-only prototype - nothing here is persisted to the database yet.
- One dashboard page (`/dashboard`) listing what's working, with role-gated links to the
  Visual Planner, proposals review, and user admin screens.
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

- `admin.demo` - lands on the dashboard; also sees the Visual Planner, "Review
  Proposals", and "User Admin" nav links.
- `user.demo` - lands on the dashboard only.
- `planner.demo` - lands directly on the Visual Planner (their own tool), and sees no
  other admin-only links.

The SQLite database (`simplevisualplanner.db`, created next to `run.py` on first run) is
gitignored, same as RMS's own `rms.db` - delete it and restart to reset to a clean state
(the three demo users will be re-seeded).

## Sharing this app during development

(Proposal id 8.) By default `python run.py` only listens on `127.0.0.1` - not reachable
from any other device, DynDNS or not. To let someone else actually reach it:

**1. Set a real secret first.** `SECRET_KEY` defaults to the value checked into this
repo (`dev-secret-change-me`) - fine for solo localhost use, but the moment anyone else
can reach this instance, that default is effectively public (anyone who's seen this repo
knows it, and could forge a session cookie for your running instance with it). Set a real
one as an environment variable before doing anything below:

```bash
# macOS/Linux
export SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
# Windows PowerShell
$env:SECRET_KEY = python -c "import secrets; print(secrets.token_hex(32))"
```

**2. Bind to all interfaces, not just localhost:**

```bash
# macOS/Linux
HOST=0.0.0.0 python run.py
# Windows PowerShell
$env:HOST = "0.0.0.0"; python run.py
```

This alone makes the app reachable from other devices on your **local network** already
(`http://<your-PC's-LAN-IP>:5000/`) - enough if the other person is on the same Wi-Fi/LAN.
`run.py` automatically turns Werkzeug's debug/auto-reload mode **off** whenever `HOST`
isn't `127.0.0.1` - its interactive in-browser debugger lets anyone who can reach it run
arbitrary Python on your machine, so it must never be on for anything reachable beyond
your own machine.

**3. To reach it from another network entirely** (the actual question - DynDNS), you
need something to route traffic from the internet to your PC. Two ways:

- **DynDNS + port forwarding** (what was asked): register a free DynDNS hostname,
  point your router's dynamic-DNS client at it, and forward an external port (e.g. 8443)
  to port 5000 on this PC. Works, but exposes your home IP and requires router
  configuration; leaving a port forwarded and open is itself an ongoing exposure even
  after this specific session ends, so remember to close it again afterward.
- **A tunneling tool (recommended instead, for exactly this "just for now" use case)**:
  e.g. [ngrok](https://ngrok.com) (`ngrok http 5000`) or a
  [Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/)
  gives you a temporary public HTTPS URL pointing at your local port, with **no router
  configuration and no open port** - close the tunnel and the exposure is gone
  immediately. This is genuinely the better fit for "share with one person, for now,
  during development" than DynDNS, which is built for something semi-permanent.

**`tunnel.bat` automates the Cloudflare Tunnel path above** - steps 1 and 2 (random
secret, debug forced off) plus starting/stopping the tunnel itself, in one command:

```bat
tunnel.bat restart   REM starts the app if needed, (re)starts the tunnel, prints the
                     REM new https://...trycloudflare.com address
tunnel.bat status    REM is it running, and what's the current address
tunnel.bat stop      REM stop the tunnel (leaves the local app running)
tunnel.bat help      REM full usage
```

Needs `cloudflared` on PATH or installed at its default location (`winget install --id
Cloudflare.cloudflared -e`) - no Cloudflare account needed for this quick-tunnel mode.
A fresh random `*.trycloudflare.com` address is issued every time `restart` runs; it
doesn't require or use a domain you own. Logs and PID files live in the gitignored
`.run/` folder next to `tunnel.bat`.

**Either way**: this app's login is passwordless-by-username (see "Run it" above) -
*anyone* who has the URL can sign in as `admin.demo` and reach every screen, including
User Admin. That's an acceptable trade-off for a trusted one-on-one review session, but
means the URL itself is the only thing standing between "just this one person" and
"anyone who finds it" - don't post it anywhere public, and tear the tunnel/port-forward
down when you're done. None of this is meant to survive into production - as the
proposal itself says, a real deployment needs a real WSGI server, real authentication,
and a properly firewalled/reverse-proxied setup, not `python run.py` reachable from the
internet.

## Deploying to Vercel

The tunnel above is for one-off "look at this now" sharing; for something that actually
stays up, this app can run on Vercel's free Hobby plan - but **only after the database
was migrated off SQLite**. Vercel's serverless functions have no persistent local disk
(only an ephemeral `/tmp`, not shared across invocations), so a SQLite file would reset
constantly - a new user or proposal could vanish the moment a different (or recycled)
container serves the next request. This has already been done:
`reusable_modules/database` now supports Postgres as a second backend, chosen purely by
what `app.config["DATABASE"]` looks like - a `postgres://`/`postgresql://` URL means
Postgres, anything else is still a local SQLite file path, so `python run.py` for local
dev is completely unaffected. Verified against a real local Postgres server (not just
read through): the full test suite passes against both backends (see "Running the
tests" below), and a full simulation of the actual Vercel scenario - a standalone copy
of just this folder, no sibling `reusable_modules/`, talking to Postgres through the
same `api/index.py` entry point Vercel uses - passed end to end (login, submitting and
reviewing a proposal, the Visual Planner, User Admin).

**One architectural note worth knowing:** `reusable_modules/` normally lives as this
project's sibling in the git checkout (`../reusable_modules/`), not inside
`SimpleVisualPlanner/` itself. Vercel's "Root Directory" setting (below) only deploys
the one folder you point it at, so this project also carries its own vendored copy at
`SimpleVisualPlanner/reusable_modules/` - `app/__init__.py` prefers the live sibling
copy when it exists (local dev), and only falls back to the vendored one when it
doesn't (a standalone deployment - i.e. Vercel). **If you change anything under the
top-level `reusable_modules/` later, re-copy it into
`SimpleVisualPlanner/reusable_modules/` before deploying**, or Vercel will keep serving
the old version. (`cp -r reusable_modules/* SimpleVisualPlanner/reusable_modules/` from
the repo root, excluding `__pycache__`.)

### What's already done (code + config, all committed)

- Postgres support in `reusable_modules/database` (`postgres.py`), with the schema and
  every query translated automatically - nothing in `basic_app`/`proposals`/`user_admin`
  needed to change.
- `requirements.txt` includes `psycopg[binary]` (only actually imported when the
  `DATABASE` setting is a Postgres URL).
- `create_app()` reads the Postgres connection string from `DATABASE_URL`, falling back
  to `POSTGRES_URL` (the name Vercel's own Postgres integration auto-injects), falling
  back to the local SQLite file if neither is set.
- `api/index.py` - the Vercel entry point (a WSGI `app` object, same `create_app()` as
  everywhere else) - and `vercel.json`, routing every path to it so Flask's own routing
  handles the whole app. *Vercel's exact recommended config can change; if their
  dashboard suggests something different from `vercel.json` when you import the
  project, follow their prompt rather than this file.*
- The vendored `reusable_modules/` copy described above.

### What you need to do (needs your Vercel/GitHub login - I can't do these for you)

1. **Push is already done** (see the end of this conversation for the commit) - the
   `reusable-modules` branch on `klausbang/ressourcemanagementsystem` has everything
   above.
2. **Create the Vercel project**: on [vercel.com](https://vercel.com) (you're
   `klaus.bang.andersen@gmail.com`) → Add New → Project → import
   `klausbang/ressourcemanagementsystem` from GitHub (authorize the Vercel GitHub App if
   this is its first import from your account).
3. **Set the Root Directory** to `SimpleVisualPlanner` in the import screen (or Project
   Settings → General afterward) - without this, Vercel will try to build the whole
   repo, including the unrelated RMS app in `app/`.
4. **Set the Production Branch to `reusable-modules`** (Project Settings → Git) unless
   you'd rather merge that branch into `master` first and deploy from there - either
   works, but the code only exists on `reusable-modules` right now.
5. **Add a Postgres database**: Project → Storage tab → Create Database → Postgres.
   Connecting it to the project auto-adds `POSTGRES_URL` (and related) environment
   variables - no manual copy-pasting needed.
6. **Set a real `SECRET_KEY`**: Project Settings → Environment Variables → add
   `SECRET_KEY` = a random value (this one's freshly generated and not used anywhere
   else - fine to use as-is, or generate your own the same way as in "Sharing this app
   during development" above):
   ```
   cb6838e7ee0703d82c010b61b38a3e7c92ed23c4d67ba7f07f379f740654931f
   ```
7. **Deploy** (Vercel does this automatically once the above is set, or click Deploy/
   Redeploy if it already ran before the database/env vars were added).
8. **Verify persistence**: open the `*.vercel.app` URL, log in as `admin.demo`, submit a
   test proposal, reload the page (or wait a bit for the container to recycle) and
   confirm it's still there - that's the actual proof the Postgres migration is doing
   its job, not just that the page loads.

That's genuinely everything - once steps 2-7 are done, every future `git push` to
`reusable-modules` redeploys automatically.

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

## Running the tests

A pytest suite (proposal id 7: "run before releasing", using standard tools) lives in
`tests/` - 36 tests as of this writing, split into a fast set (Flask test client - no
browser, no server, sub-second) and a `ui`-marked set (a real Chromium browser via
Playwright, driving a real live instance of the app - needed because the Visual
Planner's drag-and-drop is pure client-side JS that a test client can't execute at all).

**Setup** (once):
```bash
pip install -r requirements-dev.txt
playwright install chromium   # only needed for the ui-marked tests
```

**Run**:
```bash
python run_tests.py           # fast suite only - run this before every commit
python run_tests.py --ui      # just the browser tests
python run_tests.py --all     # everything (what to run before a release)
```

Each run writes `test-report.html` (gitignored - it's a build artifact, regenerated
every run) with a clear pass/fail summary at the top, followed by full detail - open it
in a browser. Extra arguments are passed straight through to pytest, e.g.
`python run_tests.py -k user_admin` or `python run_tests.py --all -x` (stop on first
failure).

`tests/conftest.py` provides the fixtures every test file builds on: `app`/`client` (an
isolated scratch-SQLite-backed instance per test - see `create_app()`'s
`config_overrides` parameter, added specifically so the suite never reads or writes the
real `simplevisualplanner.db`) and `live_server` (the same, but served over real HTTP on
an ephemeral port, for the `ui`-marked browser tests).

**Testing against Postgres too**: set `TEST_POSTGRES_URL` to a running Postgres server's
connection string and the `app`-fixture-based tests each run *twice* - once against
SQLite (as always) and once against that Postgres server (reset to empty between tests) -
proving `reusable_modules/database`'s two backends actually behave the same, not just
that each one loads. Unset (the default), nothing changes - the whole suite is SQLite-only,
exactly as before Postgres support existed:

```bash
# any reachable Postgres server - e.g. a throwaway local one, or your Vercel/Neon database
TEST_POSTGRES_URL="postgresql://user:pass@host:5432/dbname" python run_tests.py
```

**Keep adding tests as functionality grows** (per the proposal that asked for this
suite in the first place) - one file per feature area is the existing convention
(`test_auth.py`, `test_proposals.py`, `test_user_admin.py`, `test_visual_planner.py` +
`test_visual_planner_ui.py`, `test_nav_and_floating_button.py` for cross-cutting
concerns like the P button and role-gated nav). A new page or module earns its own test
file the same way; a UI interaction that's pure client-side JS earns a `ui`-marked test
in the corresponding `_ui.py` file, since nothing else actually exercises it.
