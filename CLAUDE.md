# CLAUDE.md

Instructions for an AI coding assistant (Claude Code) working in this repository.
Read `README.md` first for project orientation, then this file for how to work here.

## What this project is

RMS is a Flask + SQLite web app for a test laboratory - see `docs/srs.html` for
the full requirements spec and `docs/architecture.html` for the runtime design.
Two full UI interfaces exist over identical routes/data: **Simple** (plain HTML,
zero JS) and **Modern** (styled, tabbed, some JS) - see `docs/dual-ui.html`.

This project has been built almost entirely through a recurring, user-driven
proposal workflow (see below), phase by phase, with a very thorough written
history in `PROJECT_PLAN.md`. Before assuming something needs to be figured out
from scratch, grep `PROJECT_PLAN.md` and `docs/ai-questions.html` - it has
probably already been decided, tried, or explicitly deferred.

## The recurring "check proposals" workflow

The user periodically says something like **"Check proposals in the database
and implement them"** or **"Check approved proposals and implement them"**.
This is an established, standing instruction with a specific meaning:

1. Query the **real** `rms.db`'s `proposals` table directly (not a copy) for
   actionable rows - `status='new'` for "check proposals", `status='accepted'`
   for "check approved proposals". A submitted-by-the-user test/backlog entry
   explicitly marked as such in its own description should be left untouched,
   whatever its status.
2. Implement each one. Decide scope by precedent: a genuinely new capability
   gets a new SRS requirement ID (see `docs/srs.html` section 8); a pure UX/bug
   fix does not; a documentation-only request gets a thorough Activity Log
   entry but not a numbered Phase in the feature sense.
3. Verify thoroughly (see Verification discipline below) - functional tests,
   and for anything with real client-side JS interaction, a real headless-browser
   test (Playwright), not just a code read.
4. Update documentation to match (see Documentation sync below).
5. Mark each implemented proposal `status='done'` in the real `rms.db`, with a
   specific `admin_comment` describing what was actually built:
   ```sql
   UPDATE proposals SET status='done', admin_comment=?, updated_at=? WHERE id=?
   ```
6. Update `PROJECT_PLAN.md` (Steps / Progress Tracker / Task Status / Verification
   / Activity Log) with a detailed entry - this file is the project's memory of
   record; write it as if for someone with zero conversation context.
7. Commit with a message ending `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>`.
8. **Always ask before pushing** - never push to `customer-application` (or any
   branch) without explicit confirmation for that specific push, every time.

## Database migration rule (SQLite CHECK/FK limitations)

A plain `ALTER TABLE ... ADD COLUMN` cannot attach or widen a `CHECK` constraint,
and cannot attach a `FOREIGN KEY ... ON DELETE` action to an existing table's
column - SQLite doesn't support either. Two established patterns in `app/db.py`:

- **Widening a CHECK** (e.g. adding a new allowed status/type value, or a new
  column that needs one): do a full **rebuild-and-rename** - create
  `<table>_new` with the target schema, `INSERT INTO ... SELECT` copying old
  data with computed defaults for new columns, `DROP TABLE`, `ALTER TABLE ...
  RENAME TO`, wrapped in `PRAGMA foreign_keys = OFF`/`ON`. See
  `_migrate_users_table` and `_migrate_proposals_table` for the pattern.
  Detect "already migrated" by reading the table's own CHECK clause text out
  of `sqlite_master.sql` (not `PRAGMA table_info`, which doesn't expose CHECK
  clauses), combined with column-existence checks, so the migration is a
  correct no-op on a second run.
- **A new column needing `ON DELETE` semantics** (e.g. a nullify-on-delete
  reference): add the column with **no declared SQL foreign key at all**, and
  enforce the cascade/nullify/restrict behavior at the **application level**
  in the route handler instead, with an inline comment explaining why. Only a
  genuinely fresh `CREATE TABLE` gets a real declared FK. (Rediscovered/
  reapplied at least three times historically - `ordered_tests.eut_id`,
  `customer_orders.customer_id`, `ordered_tests.template_application_id` -
  worth just doing this up front rather than re-debugging it.)

Before running any real-DB migration for real: test it first against a **copy**
of the live `rms.db` (e.g. `cp rms.db <scratch>/migration_test.db`), verifying
row-count preservation, new-value insertability, and idempotency on a second
`init_db()` call.

## Verification discipline

`create_app()` unconditionally runs `init_db()`/`init_demo_seed()` against the
**real** `rms.db` path before any test script gets a chance to redirect it.
This is harmless by itself (idempotent), but means: **always** override
`app.config["DATABASE"]` to an isolated temp/scratch path immediately after
calling `create_app()`, before any `client.post(...)` mutation - otherwise
test-client mutations land in the real dev database.

```python
app = create_app()
app.config["DATABASE"] = "<temp path>"
app.config["TESTING"] = True
with app.app_context():
    from app.db import init_db, init_demo_seed
    init_db(); init_demo_seed()
```

For anything with real client-side JS interaction (drag, keyboard shortcuts,
auto-submit-on-change, the editable grid, dialog behavior, etc.), a functional
test alone is not enough - static analysis has repeatedly missed real bugs that
only a live browser catches (event-ordering issues, focus/tabindex quirks,
event bubbling into the wrong handler). Use Playwright against a real local
Flask dev server (`app.run(port=5055)` with an overridden `DATABASE`, started
in the background, health-checked with curl, torn down afterward via
`netstat`/`taskkill`) rather than trusting a code read.

## Dual-UI conventions

- Every route renders through `app/routes_common.py:render_ui(template_name,
  **context)`, never Flask's `render_template()` directly - it resolves to
  `f"{mode}/{template_name}"` based on `session["ui_mode"]`.
- No route, action name, or form field differs between modes - only the
  template. Adding a page means creating both `templates/simple/x.html` and
  `templates/modern/x.html`.
- A feature that is inherently JS-dependent (spreadsheet-style bulk editing,
  drag handles, keyboard shortcuts) is built Modern-only, but Simple must still
  get full data access to the same fields through ordinary form controls - see
  `docs/dual-ui.html` section 8. Don't skip Simple's data access, and don't
  invent a degraded low-fidelity version just so Simple has "something".
- The only fully Modern-only *pages* (no Simple equivalent at all) are the
  Technician workspace and Test Reports - see `docs/dual-ui.html` section 7 for
  why, before adding a new exception to that rule.

## Documentation sync (do this every time, not just when asked)

Every proposal-driven change should update the docs that describe it, in the
same commit as the code:

- `docs/srs.html` - add/extend a Functional Requirement if the change is a new
  capability; add a revision-history bullet either way; extend the
  traceability table (section 12) and, if relevant, the open questions
  (section 13).
- `docs/architecture.html` - extend the Scope paragraph and Runtime Components
  section if a new module/blueprint/pattern was introduced.
- `docs/design-guide.html` - add a bullet (and a **Gotcha:** note if a real bug
  was found) for any new UI pattern, component, or convention.
- `docs/page-overview.html` - update the affected page/tab row(s) if buttons,
  fields, or behavior changed.
- `docs/ai-questions.html` - resolve any open question the change answers;
  add new ones the change raises.
- `PROJECT_PLAN.md` - Steps, Progress Tracker, Task Status, Verification, and
  a detailed Activity Log entry (see the "check proposals" workflow above).

After editing any `docs/*.html` file, sanity-check tag balance before
committing (a lenient open/close count per tag, or a full `html.parser`-based
nesting check) - these files are hand-edited HTML with no build step to catch
a stray unclosed tag.

## Git discipline

- Create new commits; don't amend unless explicitly asked.
- Never use `--no-verify` or otherwise bypass hooks.
- **Always ask before `git push`**, every single time, even if a previous push
  in the same session was approved - approval for one push is not standing
  approval for the next one.
- Commit messages end with `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>`.
- Don't stage `rms.db`, `rms.db.bak`, or any other `*.db` file (gitignored) -
  double-check `git status` after a broad add.
- Clean up stray scratchpad/download-artifact files from the repo root before
  committing if a headless-browser test or manual export happened to drop one
  there.

## Running and testing locally

```bash
./venv/Scripts/python run.py        # Windows; python run.py elsewhere
```
Demo logins: `admin.demo`, `planner.demo`, `technician.demo`,
`technician2.demo` (username only, no password - see `docs/srs.html` section
11, this is an intentional demonstrator limitation, not a gap to "fix").
