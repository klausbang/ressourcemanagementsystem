# RMS - Resource Management System

A web-based planning and execution system for a test laboratory, replacing three
separate spreadsheets (a project-pipeline sheet, a production/resource schedule,
and a per-EUT test plan) with one system built around a single source of truth.

Flask + SQLite locally; Railway/PostgreSQL is the intended path for later cloud
deployment (not yet done).

## Start here

Read these in order before making changes:

1. **`docs/srs.html`** - the Software Requirements Specification. The authoritative
   statement of what the system does and why, organized by functional area
   (Projects, Test Plan, Resources, Constraints, Calendar, Status, Planning,
   Rescheduling, Visualization, Reporting, Feedback/Proposals, Nice-to-have).
   Read this first for *what* the system is supposed to do.
2. **`docs/architecture.html`** - runtime components, request flow, and how the
   Flask blueprints/domain modules fit together. Read this for *how* it's built.
3. **`docs/design-guide.html`** - the UI's visual language and behavioural
   conventions (design tokens, navigation/tabs, forms, tables, the editable-grid
   component, icon meanings, accessibility, a checklist for building a new page
   consistently) - written specifically so a new developer can build a
   consistent-looking page without guessing.
4. **`docs/dual-ui.html`** - RMS ships two interfaces (Simple: plain HTML, no JS;
   Modern: styled, tabbed, some JS) over identical routes and data. Read this
   before touching any template.
5. **`docs/page-overview.html`** - every page/tab in the app, one row each: path,
   intended role, what it does, editable vs. view-only, buttons, sortable, which
   UI mode(s). The fastest way to find "where does X live."
6. **`docs/er-model.html`** - the data model (Mermaid ER diagrams, searchable).
7. **`PROJECT_PLAN.md`** - the full phase-by-phase build history and a detailed
   Activity Log entry for nearly every change ever made. This is the project's
   memory: if you want to know *why* something is the way it is, or what was
   tried and rejected, it's almost certainly logged there. It's long - grep it,
   don't try to read it front to back.
8. **`docs/index.html`** - links to all of the above plus several more (ai
   questions/open decisions, ER model, development plan, wireframes, mockup
   acceptance checks, brochure, customer-discovery source documents).

## Running it locally

```bash
python -m venv venv
./venv/Scripts/python -m pip install -r requirements.txt   # Windows
# source venv/bin/activate && pip install -r requirements.txt   # macOS/Linux
./venv/Scripts/python run.py                                # Windows
# python run.py                                              # macOS/Linux
```

Flask starts on `http://127.0.0.1:5000` (or `:5055` if you've overridden the
port for a test run - see below). The SQLite database (`rms.db`) is created
and seeded automatically on first run via `app/db.py:init_db()` /
`init_demo_seed()` - no manual migration step needed for a fresh checkout.

Demo logins (no passwords - this is a demonstrator, see docs/srs.html section
11, Out of Scope): `admin.demo`, `planner.demo`, `technician.demo`,
`technician2.demo`. Enter the username at `/login`; role is looked up from it.

## Project layout

```
app/
  __init__.py            Flask app factory (create_app)
  db.py                   Schema, migrations (rebuild-and-rename for CHECK
                          changes - SQLite can't ALTER a CHECK in place),
                          seed data, sandbox_items table
  routes_common.py        Login/logout, UI-mode toggle, resource catalog, help
  routes_admin.py         Admin tabs: users/capabilities/resources/mappings/
                          exclusion groups/templates/absences/proposals/customers
  routes_planner.py       Planner tabs, order workspace, dashboard, schedule
  routes_technician.py    Technician dashboard, work order lifecycle
  routes_reports.py       Test report fill-in/submit/review/approval
  routes_proposals.py     The "P" button / proposal submission flow
  routes_sandbox.py       Admin-only editable-grid prototyping area (not a
                          product feature - see docs/srs.html open questions)
  scheduling.py           Mutual-exclusion conflict checks, dependency/cycle
                          checks, planned-overlap and reschedule-suggestion logic
  history.py              Append-only activity-history recording
  table_utils.py          Shared sortable-header + duplicate-row-highlight logic
  templates/
    simple/               Plain-HTML, zero-JS interface
    modern/               Styled, tabbed, JS-enabled interface
  static/
    css/modern.css         Design tokens + all Modern-UI component styles
    js/modern.js            Dirty-form tracking, mobile nav, confirm-delete
    js/sandbox.js            Shared parsing helpers + the reusable editable-
                              grid engine (RmsSandbox.createEditableGrid)
docs/                     All specification/reference documentation (HTML)
PROJECT_PLAN.md           Phase-by-phase plan, verification checks, activity log
CLAUDE.md                 Instructions for an AI coding assistant working here
```

## Working conventions (short version - see CLAUDE.md and docs/design-guide.html for the full versions)

- Every route renders through `render_ui()`, not `render_template()` directly,
  so it resolves to the current session's Simple or Modern template automatically.
- A SQLite `CHECK` constraint can't be widened with `ALTER TABLE ADD COLUMN` -
  widening one means a full rebuild-and-rename (see `_migrate_users_table` /
  `_migrate_proposals_table` in `app/db.py` for the pattern).
- Business rules (proposals workflow, verification discipline, DB migration
  rules) that came up repeatedly enough to be worth writing down live in
  PROJECT_PLAN.md's Activity Log and in this project's AI-assistant memory
  (see CLAUDE.md) - check there before re-deriving something from scratch.
