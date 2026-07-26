# RMS Development Plan (Local to Cloud)

Last updated: 2026-07-21
Plan source: /memories/session/plan.md

## Goal
Build a lean first version of the Resource Management System by moving through three stages: static mockups, working local app, then Railway deployment. Keep documentation-first delivery in HTML, include architecture and ER diagrams as embedded PNG/SVG, and introduce basic role checks in the first working local version.

## Steps
1. Phase 1 - Scope Baseline and Documentation Skeleton
2. Extract the minimum SRS scope from the prompt into concise requirement groups: business context, user roles, core workflows, and non-functional constraints. This is the baseline for all later deliverables.
3. Define the documentation structure and navigation for a landing page that links SRS, architecture, ER model, development plan, and AI questions page.
4. Create a single documentation style/layout guideline so all pages share consistent headings, section order, and cross-links.
5. Phase 2 - First Demonstrator (Static Mockup, Local)
6. Specify static HTML wireframes (no backend dependency) for the essential workflows: resource catalog view, resource capability assignment view (admin), and resource-to-order assignment view (planner).
7. Prepare dummy example data aligned with the prompt scenarios (multimeter calibration order, vibration/humidity tests for a mobile phone product).
8. Define acceptance checks for mockups: visible role-specific pages, clear navigation, and representational data for resources/capabilities/orders.
9. Phase 3 - Minimal Working Local Application
10. Design backend scope for Flask + SQLite local runtime: entities, routes, validation rules, and minimal template rendering needed to support the two core role actions.
11. Add basic role checks in this stage (admin vs planner) with lightweight authentication/authorization suitable for demonstrator use.
12. Implement local CRUD and assignment flows in dependency order: resource/capability management first, then order/resource allocation.
13. Add seed script or seed routine for demo data so documentation scenarios are reproducible.
14. Phase 4 - Architecture and Data Design Deliverables
15. Produce web application architecture document describing client, Flask app layer, service/domain logic, data access, and SQLite database; include environment separation notes for future Railway deployment.
16. Produce ER model document covering core entities and relationships: users/roles, resources, capabilities, resource-capability mapping, customer orders, ordered tests, and resource allocations.
17. Embed architecture and ER diagrams as PNG/SVG in HTML documentation and cross-link them from the landing page.
18. Phase 5 - Cloud Deployment Readiness and Final Stage
19. Define deployment activities for Railway as a later stage: configuration variables, production database target (PostgreSQL), migration strategy from SQLite model, and deployment verification checklist.
20. Add staged rollout path in the plan: static local mockup -> working local Flask+SQLite -> stable packaged app -> Railway deployment.
21. Include post-deployment operational tasks: smoke tests, role-flow checks, and documentation updates.
22. Phase 6 - AI Collaboration and Open Questions Governance
23. Create an AI questions page in HTML with priority tags: Blocker, High, Medium, Low.
24. Seed initial unresolved questions around business rules and allocation constraints (for example, scheduling conflicts, capacity limits, and order priority rules).
25. Define a triage process for answering and retiring questions as requirements mature.

## Verification
1. Documentation completeness check: landing page links to all required pages and each page links back to landing.
2. SRS scope check: includes only minimal requirements needed for first demonstrator and explicitly marks out-of-scope items.
3. Mockup review check: static pages cover both required role workflows and both sample customer order scenarios.
4. Local app functional check: admin can add resources/capabilities and assign capabilities; planner can assign resources to orders.
5. Role check validation: unauthorized role cannot execute the other role's protected action.
6. Data design check: ER model relationships support many-to-many mapping where needed (resource-capability and order-resource allocation).
7. Deployment readiness check: Railway deployment checklist exists and maps local configuration to production equivalents.

## Decisions
- Local database for first working versions: SQLite.
- First stage UI: static HTML wireframes only.
- Role handling: include basic role checks in first working local version.
- Diagram embedding format in docs: PNG/SVG.
- Cloud deployment timing: final stage after stable local app.
- Duration estimates excluded by request; plan is activity/task based.

## Progress Tracker
Status legend: Not Started | In Progress | Done | Blocked

- Phase 1 - Scope Baseline and Documentation Skeleton: Done
- Phase 2 - First Demonstrator (Static Mockup, Local): Done
- Phase 3 - Minimal Working Local Application: Done
- Phase 4 - Architecture and Data Design Deliverables: Done
- Phase 5 - Cloud Deployment Readiness and Final Stage: Not Started
- Phase 6 - AI Collaboration and Open Questions Governance: Not Started

### Phase 1 Task Status
- Task 2 (Minimum SRS scope extraction): Done
- Task 3 (Documentation structure and landing navigation): Done
- Task 4 (Shared documentation style/layout guideline): Done

### Phase 2 Task Status
- Task 6 (Static wireframes for core workflows): Done
- Task 7 (Dummy example data for prompt scenarios): Done
- Task 8 (Acceptance checks for mockups): Done

### Phase 3 Task Status
- Task 10 (Backend scope and Flask+SQLite runtime design): Done
- Task 11 (Basic role checks for admin/planner): Done
- Task 12 (Local CRUD and order allocation flows): Done
- Task 13 (Seed routine for reproducible demo data): Done
- Task 12a (Planner order/ordered-test creation, added after initial Phase 3 completion): Done
- Task 12b (Full admin CRUD on users/capabilities/resources and full planner CRUD on orders/ordered-tests/allocations, added after initial Phase 3 completion): Done
- Task 12c (Sortable column headers and full-row duplicate highlighting on every listing table, added after initial Phase 3 completion): Done
- Task 12d (Multiple resources per ordered test, added after initial Phase 3 completion): Done
- Task 12e (Dual Simple/Modern interface with mode toggle and help pages, added after initial Phase 3 completion): Done

### Phase 4 Task Status
- Task 15 (Architecture document with local and cloud separation): Done
- Task 16 (Detailed ER model entities and relationships): Done
- Task 17 (Embed architecture and ER diagrams and cross-link docs): Done

## Activity Log
- 2026-07-21: Initial plan created from prompt and saved to project.
- 2026-07-21: Preferences confirmed for SQLite, static wireframes first, basic role checks in first working local app, PNG/SVG diagrams, and Railway in final stage.
- 2026-07-21: Phase 1 Task 2 completed by creating docs/srs.html with minimal grouped requirements and out-of-scope list.
- 2026-07-21: Phase 1 Task 3 completed by creating docs/index.html and core documentation placeholders for architecture, ER model, development plan, and AI questions.
- 2026-07-21: Phase 1 Task 4 completed by creating docs/doc-style-guide.html with shared documentation rules and change tracking guidance.
- 2026-07-21: Phase 2 Task 6 completed by creating three static wireframes for resource catalog, admin capability assignment, and planner order allocation.
- 2026-07-21: Phase 2 Task 7 completed by creating docs/mockup-dummy-data.html with scenario-aligned data.
- 2026-07-21: Phase 2 Task 8 completed by creating docs/mockup-acceptance-checks.html and linking all Phase 2 pages from docs/index.html.
- 2026-07-21: Phase 3 Task 10 completed by creating the minimal Flask app skeleton, SQLite schema, route placeholders, and docs/phase3-backend-scope.html.
- 2026-07-21: Phase 3 Task 11 completed by adding login/logout, session role handling, and admin/planner route guards.
- 2026-07-21: Phase 3 Task 12 completed by implementing admin capability/resource management and planner order allocation flows with validation.
- 2026-07-21: Phase 3 Task 13 completed by adding reproducible demo seed routines and app startup initialization for local demonstration data.
- 2026-07-21: Phase 4 Task 15 completed by replacing docs/architecture.html with detailed architecture documentation and embedding docs/architecture-diagram.svg.
- 2026-07-21: Phase 4 Task 16 completed by replacing docs/er-model.html with detailed entities/relationships and embedding docs/er-diagram.svg.
- 2026-07-21: Phase 4 Task 17 completed by cross-linking architecture and ER diagrams from docs/index.html and finalizing diagram embedding in both pages.
- 2026-07-25: Phase 3 Task 12a completed by adding planner-facing "Create Customer Order" and "Add Ordered Test" forms/routes (app/routes_planner.py, app/templates/planner_orders.html) with unique order-code and existing-order validation, and updating docs/phase3-backend-scope.html route/validation scope to match.
- 2026-07-25: Phase 3 Task 12c completed by adding app/table_utils.py (shared sort/duplicate-flag helper) and app/templates/_macros.html (sortable header link macro), wiring both into every listing table across resource_catalog.html, admin_manage.html, and planner_orders.html. Also fixed a pre-existing seed-data bug in app/db.py: init_demo_seed()'s ordered_tests inserts used INSERT OR IGNORE against a table with no matching unique constraint, so every dev-server reload (and Werkzeug's reloader double-imports the app once per start) silently duplicated the three seed ordered tests; added NOT EXISTS guards to make seeding idempotent. This bug was surfaced by, and is unrelated in origin to, the new duplicate-row highlighting feature.
- 2026-07-25: Phase 3 Task 12b completed by adding full CRUD to app/routes_admin.py (users, capabilities, resources, resource-capability mapping) and app/routes_planner.py (customer orders, ordered tests, allocations), with uniqueness checks on update, friendly errors on foreign-key-restricted deletes, and database-level cascade deletes for order/test hierarchies; templates updated with inline editable tables (admin_manage.html, planner_orders.html); docs/srs.html and docs/phase3-backend-scope.html updated to describe the CRUD and referential-integrity scope.
- 2026-07-25: Phase 3 Task 12d completed by changing the allocations table's uniqueness from single-column (ordered_test_id) to composite (ordered_test_id, resource_id) in app/db.py, so a planner can assign several different resources (equipment, facility, procedure, technician, etc.) to the same ordered test while still blocking the same resource being assigned twice to that test. app/routes_planner.py's assign_resource action switched from an upsert to a plain insert with a friendly "already assigned" check, and delete_allocation now removes one specific allocation (by allocation_id) instead of every allocation for a test. planner_orders.html's "Assign Resources to Ordered Tests" table now lists all currently assigned resources per test (each with its own Remove button) and offers only not-yet-assigned, capability-matching resources in the add dropdown. Updated docs/er-diagram.mmd (relationship changed from one-to-zero-or-one to one-to-zero-or-many) and regenerated docs/er-diagram.svg, plus docs/er-model.html, docs/srs.html, and docs/phase3-backend-scope.html to describe multi-resource allocation. The existing dev database's allocations table had to be dropped and recreated to pick up the new constraint, since SQLite does not support altering a UNIQUE constraint in place; any previously-made resource assignments were cleared by this migration (orders and ordered tests were not affected).
- 2026-07-25: Phase 3 Task 12e completed by introducing a session-based UI mode (`session['ui_mode']`, default "simple") with a `GET /ui-mode/<mode>` toggle route and a `render_ui()` helper (app/routes_common.py) that resolves every template as `<mode>/<template>`, so all existing routes/CRUD actions/field names are unchanged and only the rendered template differs. Moved the original templates under templates/simple/ unmodified apart from adding the toggle button and a Help link. Built a full parallel templates/modern/ interface (own base.html/layout, login, resource catalog with quick stats, admin and planner pages restructured into CSS-only tabbed sections, and a card-based multi-resource-assignment view with removable chips) styled by a new self-contained app/static/css/modern.css design system and a small app/static/js/modern.js (mobile nav toggle, flash auto-dismiss, confirm-before-delete). Added a new `/help` route with role/workflow/table-feature explanations rendered per-mode (templates/simple/help.html, templates/modern/help.html), plus inline contextual help text (card subtitles, section notes, a callout on the resource-assignment tab, and a tooltip explaining duplicate-row highlighting). Added docs/dual-ui.html describing the architecture and cross-linked it from docs/index.html; updated docs/srs.html (new non-functional usability requirement) and docs/phase3-backend-scope.html (template scope). Verified via an HTTP-level test script covering both modes, all roles, mode toggling with query-string preservation, CRUD through the modern forms, and duplicate-row rendering; also verified HTML tag balance across the new templates and CSS brace balance.

## Open Questions Queue Policy
- Blocker: Must be answered before current phase can continue.
- High: Should be answered within current phase.
- Medium: Can be deferred to a later phase.
- Low: Nice-to-have clarification.
