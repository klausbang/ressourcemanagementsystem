# RMS Development Plan (Local to Cloud)

Last updated: 2026-07-28
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
26. Phase 7 - Technician Workflow and Test Reports
27. Add a Test Technician role: a technician user account optionally links to its own technician resource, which determines which planner-allocated tests appear on that user's dashboard.
28. Build a technician dashboard (Modern UI only) showing assigned tests, the equipment/facility allocated alongside the technician, and a per-test work order lifecycle (planned/in_progress/on_hold/completed).
29. Add a test procedure library (capability-scoped process description, required equipment/facility, safety notes) plus a structured, ordered checklist of check-items with pre-authored expected values, for use in test reports.
30. Add test report generation from a work order: a fillable template pre-loaded with test/order/equipment identification, technician name, unit-under-test fields, and one row per check-item with its expected value; technician fills in actual values, results, overall result, and notes.
31. Add a technician-then-reviewer sign-off workflow (draft -> submitted -> approved/rejected, reopenable on rejection), where the reviewer must be a different technician or a planner, plus a shared reports queue/history view.
32. Style the test report as a single printable A4 page usable both blank (during the test) and completed (after sign-off).
33. Refresh core documentation (SRS, architecture, ER model/diagram, dual-UI notes, backend scope) to describe the Phase 7 additions, and produce a one-page sales brochure summarizing RMS capabilities.
34. Phase 8 - EUT (Unit Under Test) as a First-Class Entity
35. Add an EUTs table so a project can hold multiple EUTs, each with a name and optional serial number.
36. Let a test activity (ordered_test) optionally reference the EUT it belongs to, without breaking existing EUT-less test activities.
37. Extend planner UI (Simple and Modern) to manage EUTs per order and tag test activities to one.
38. Seed a multi-EUT demo order and update ER model/diagram and architecture docs to describe the EUT entity.
39. Phase 9 - Lab and Equipment Mutual-Exclusion Constraints
40. Model mutual-exclusion groups of facility resources (e.g. CON chamber: CE/CI; SAC chamber: RE/RI) that cannot run with overlapping time windows.
41. Enforce the conflict check when a planner schedules or reschedules a work order, with a clear explanation of which activity it conflicts with.
42. Add a site field (TLC/TLS) to facility/equipment resources and warn (not block) on cross-site overlap of shared equipment.
43. Surface constraint conflicts inline in the existing schedule/Gantt view.
44. Phase 10 - Standard Project Activity Template
45. Define a reusable, ordered standard activity template (Kick-off through EUT return) that an admin/planner can maintain.
46. Let a planner apply the template to a new EUT to bulk-create its test activities in one step, then freely reorder/add/remove per project.
47. Phase 11 - Project and Discipline Dashboard
48. Add project-level status and a weekly free-text note, replacing the equivalent Sprint.xls columns.
49. Derive discipline-level status from underlying test activity/work order status rather than separate manual entry.
50. Build a dashboard listing active projects with status, discipline status, and upcoming milestones, plus a read-only completed-projects history view.
51. Surface constraint conflicts and activities missing an EUT/date/procedure on the dashboard.
52. Phase 12 - Staff and Customer Calendar
53. Add staff absence/vacation records per technician and customer on-site day records per project.
54. Surface both on the schedule and dashboard views for the affected dates.
55. Phase 13 - Change History and Audit Trail
56. Add an append-only history record for schedule-affecting changes to a test activity (resource assignment, scheduling, status).
57. Add a per-activity history view answering "who moved this, when, and why."
58. Phase 14 - Dynamic Rescheduling Assistant (stretch, Could)
59. Let a facility reservation span multiple consecutive days as a single booking.
60. When an activity is delayed, failed, or its EUT is replaced, suggest how directly dependent downstream activities (per the Phase 10 template ordering) could shift, for the planner to accept or ignore manually. Full automatic optimization/conflict auto-resolution stays out of scope.

## Verification
1. Documentation completeness check: landing page links to all required pages and each page links back to landing.
2. SRS scope check: includes only minimal requirements needed for first demonstrator and explicitly marks out-of-scope items.
3. Mockup review check: static pages cover both required role workflows and both sample customer order scenarios.
4. Local app functional check: admin can add resources/capabilities and assign capabilities; planner can assign resources to orders.
5. Role check validation: unauthorized role cannot execute the other role's protected action.
6. Data design check: ER model relationships support many-to-many mapping where needed (resource-capability and order-resource allocation).
7. Deployment readiness check: Railway deployment checklist exists and maps local configuration to production equivalents.
8. EUT check: a project can have multiple EUTs; test activities can optionally be tagged to one and filtered/reported per EUT.
9. Constraint check: two activities in the same mutual-exclusion group cannot be scheduled with overlapping windows; the rejection names the conflicting activity and time.
10. Template check: applying the standard activity template creates all its activities, in the chosen order, in one step.
11. Dashboard check: project/discipline status and milestones are derived from underlying activity data, not entered a second time, and stay consistent with it.
12. Calendar check: a technician's absence and a customer's on-site day are visibly flagged on the schedule/dashboard for the correct dates.
13. History check: a schedule-affecting change to a test activity produces a visible history entry recording who changed it and when.

## Decisions
- Local database for first working versions: SQLite.
- First stage UI: static HTML wireframes only.
- Role handling: include basic role checks in first working local version.
- Diagram embedding format in docs: PNG/SVG.
- Cloud deployment timing: final stage after stable local app.
- Duration estimates excluded by request; plan is activity/task based.
- Customer discovery source for Phases 8-14: a shared ChatGPT conversation transcript with the customer, archived to the repo as `Jens_chatgpt_historic.md` for traceability.
- SRS restructured as v0.3 around the chapter list the customer's own consultant proposed (Projects, Test Plan, Resources, Constraints, Calendar, Status Management, Planning, Rescheduling, Visualization, Reporting, Integrations, Usability, Nice-to-have), with Must/Should/Could priority and a BR/FR/AC numbering split, per explicit customer request. Existing v0.1/v0.2 requirements were carried forward unchanged in meaning and marked Delivered.
- A test activity's EUT reference (Phase 8) is optional, not mandatory, so existing single-EUT projects and previously-created test activities keep working without a data migration forcing a value onto them.
- Phases 8-14 are deliberately kept small and independently demoable, so customer feedback after each one can confirm (or redirect) the approach before the next phase is committed.

## Progress Tracker
Status legend: Not Started | In Progress | Done | Blocked

- Phase 1 - Scope Baseline and Documentation Skeleton: Done
- Phase 2 - First Demonstrator (Static Mockup, Local): Done
- Phase 3 - Minimal Working Local Application: Done
- Phase 4 - Architecture and Data Design Deliverables: Done
- Phase 5 - Cloud Deployment Readiness and Final Stage: Not Started
- Phase 6 - AI Collaboration and Open Questions Governance: Not Started
- Phase 7 - Technician Workflow and Test Reports: Done
- Phase 8 - EUT (Unit Under Test) as a First-Class Entity: Done
- Phase 9 - Lab and Equipment Mutual-Exclusion Constraints: Done
- Phase 10 - Standard Project Activity Template: Done
- Phase 11 - Project and Discipline Dashboard: Done
- Phase 12 - Staff and Customer Calendar: Not Started
- Phase 13 - Change History and Audit Trail: Not Started
- Phase 14 - Dynamic Rescheduling Assistant (stretch): Not Started

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

### Phase 7 Task Status
- Task 27 (Test Technician role with linked-resource dashboard scoping): Done
- Task 28 (Technician dashboard: assigned tests, allocated resources, work order lifecycle): Done
- Task 29 (Test procedure library with structured, expected-value checklist): Done
- Task 30 (Test report generation from work orders, fillable template): Done
- Task 31 (Technician/reviewer sign-off workflow and shared reports queue): Done
- Task 32 (Printable A4 test report styling): Done
- Task 33 (Documentation refresh and sales brochure): Done

### Phase 8 Task Status
- Task 35 (EUTs table, optional per project): Done
- Task 36 (Optional eut_id reference on ordered_tests): Done
- Task 37 (Planner UI: EUT management + tagging, Simple and Modern): Done
- Task 38 (Seed multi-EUT demo order; update ER model/diagram and architecture docs): Done

### Phase 9 Task Status
- Task 40 (Mutual-exclusion groups of facility resources): Done
- Task 41 (Conflict check with clear explanation): Done, scoped to the work-order start/resume transition rather than creation-time scheduling (see SRS FR-CON-2 design note) plus a passive inline flag in the Schedule tab for conflicts that arise after the fact
- Task 42 (Site field on facility/equipment resources): Done (data field only)
- Task 43 (Constraint conflicts surfaced inline in the schedule/Gantt view): Done
- Not done in this phase (explicitly deferred to Phase 14): FR-CON-3 cross-site double-booking warning, FR-CON-4 multi-day facility reservations

### Phase 10 Task Status
- Task 45 (Reusable, ordered standard activity template maintained by admin): Done
- Task 46 (Planner applies a template to bulk-create activities, then freely reorders/adds/removes): Done

### Phase 11 Task Status
- Task 48 (Project-level status and weekly note): Done, as a derived status plus the two genuinely manual fields (weekly_note, waiting_for_customer) rather than a separately-entered status, per BR-001
- Task 49 (Discipline-level status derived from underlying activity/work-order status): Done, with an admin-settable discipline field on capabilities plus a name-based fallback for activities with no capability, pending customer confirmation of the full taxonomy
- Task 50 (Dashboard: active projects with status/discipline/milestones, plus read-only completed-project history): Done
- Task 51 (Constraint conflicts and gaps surfaced on the dashboard): Done, scoped to a live (system-wide, not just one day) conflict flag plus unscheduled/missing-procedure counts; "missing an EUT or a scheduled date" from the original task wording was narrowed to these two concrete, unambiguous gaps

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
- 2026-07-26: Phase 7 Tasks 27-28 completed by adding a `technician` role (app/db.py: CHECK constraint extended, new `users.linked_resource_id` column with an in-place migration for existing SQLite files since SQLite can't alter a CHECK/FK in place), a new `work_orders` table, and `app/routes_technician.py` + `templates/modern/technician_dashboard.html` (Modern-only, see docs/dual-ui.html section 7): a dashboard of tests allocated to the technician's linked resource, showing co-allocated equipment/facility, with work orders moving through planned/in_progress/on_hold/completed. Seeded a second technician account/resource (technician2.demo/TECH-103) and a completed example work order for demo purposes.
- 2026-07-26: Phase 7 Tasks 29-32 completed by adding `test_procedures`/`procedure_checks` (structured, expected-value checklists per procedure, seeded for all three demo capabilities) and `test_reports`/`report_steps` tables, plus `app/routes_reports.py` and three Modern-only templates (`report_detail.html`, `reports_list.html`). A technician generates a report from a work order once a procedure is set, pre-filled with test/order/equipment/technician identification and one row per check-item; fills in actual values/results/overall result/notes and submits (locks the report, time-stamps sign-off); any *other* technician or a planner approves/rejects (rejection requires a comment) from a shared reports queue; a rejected report can be reopened. The report page doubles as a single printable A4 form (`@page` sizing, `@media print` chrome hiding) for use both blank and completed. Verified end-to-end via an isolated throwaway order (created, exercised the full create/fill/submit/approve flow, then deleted to leave real in-progress user data untouched) plus targeted permission-boundary checks (self-review blocked, reject-without-comment blocked, premature-submit blocked).
- 2026-07-28: Phase 7 Task 33 completed: refreshed docs/srs.html (v2: Test Technician role, work order/test procedure/test report requirements, updated data/non-functional/out-of-scope sections), docs/architecture.html + docs/architecture-diagram.svg (new blueprints, migration helper, review-permission notes), docs/er-diagram.mmd + regenerated docs/er-diagram.svg + docs/er-model.html (five new entities and their relationships), docs/dual-ui.html (new section 7 documenting the Modern-only exception for technician/report pages), docs/phase3-backend-scope.html and docs/index.html (entity/route/template/navigation updates), and docs/doc-style-guide.html (added Test Technician to the role-name convention). Added docs/brochure.html, a self-contained one-page A4 sales brochure (feature grid, 4-step workflow, role summary, tech stack); verified single-page fit and visual layout via a headless-Chrome PDF/screenshot render before finalizing. Archived to GitHub afterward.
- 2026-07-30: Customer discovery reviewed (shared ChatGPT conversation transcript, saved as `Jens_chatgpt_historic.md`) covering the customer's current three-document workflow (Sprint.xls pipeline, Projects.xls production schedule, a separate testplan) and their consultant's proposed requirements structure. Rewrote docs/srs.html as v0.3, restructured around the customer's own chapter list (Projects, Test Plan, Resources, Constraints, Calendar, Status Management, Planning, Rescheduling, Visualization, Reporting, Integrations, Usability, Nice-to-have) with Must/Should/Could priority and a BR-/FR-&lt;area&gt;-n/AC- numbering scheme; existing v0.1/v0.2 requirements carried forward unchanged in meaning and marked Delivered. Added matching open questions to docs/ai-questions.html. Added Phases 8-14 to PROJECT_PLAN.md (EUT entity; lab/equipment mutual-exclusion constraints; standard project activity template; project/discipline dashboard; staff/customer calendar; change history/audit trail; dynamic rescheduling assistant), each scoped as a small, independently demoable increment per explicit request to avoid a single large rewrite.
- 2026-07-30: Phase 8 (EUT as a first-class entity) implemented: added a `euts` table (app/db.py) and an optional `eut_id` FK on `ordered_tests` (`ON DELETE SET NULL`, so deleting an EUT unlinks rather than deletes its test activities), with a migration helper for existing SQLite files that rebuilds the table (a plain `ALTER TABLE ADD COLUMN` cannot attach an `ON DELETE` action to a column added after table creation, unlike a fresh `CREATE TABLE`). Added EUT create/update/delete actions and an optional `eut_id` on add/update-test to app/routes_planner.py, with server-side validation that a test's EUT belongs to the same order. Extended both app/templates/simple/planner_orders.html and app/templates/modern/planner_orders.html with an EUT management section and an EUT column/selector on the ordered-tests and resource-assignment tables, plus updated both help.html pages. Seeded a second EUT ("Prototype Unit B") under ORD-2026-002 with its own Vibration Test activity, alongside the existing "Prototype Unit A" (matching the pre-existing seeded work order/report's serial number), to demonstrate multiple EUTs per project; added a one-time backfill so pre-Phase-8 dev databases link their existing Vibration/Humidity Test rows to Prototype Unit A instead of leaving them EUT-less. Updated docs/er-diagram.mmd + regenerated docs/er-diagram.svg, docs/er-model.html, docs/architecture.html, docs/phase3-backend-scope.html, and docs/index.html for the new entity. Verified with an end-to-end Flask test-client script (both UI modes render the EUT section and seeded EUTs; create/tag/reject-cross-order/delete-unlinks flow all behave correctly) run against the real dev database, plus a double-`create_app()` idempotency check; this verification caught and fixed two real bugs before they could reach the customer demo &mdash; the ADD-COLUMN migration silently dropping the `ON DELETE SET NULL` action (causing EUT deletion to fail with a foreign-key error instead of unlinking), and the original seed data's `INSERT OR IGNORE`/`NOT EXISTS` guards matching by order+test-name only, so introducing a second same-named test under one order caused a work-order/allocation seed collision and, on a pre-existing dev database, left the original test row's EUT link unset.
- 2026-07-30: `Jens_chatgpt_historic.md` (the customer discovery source referenced above) added to .gitignore at the user's request so it is never included in a GitHub archive/commit, despite being read locally for requirements traceability.
- 2026-07-30: Fixed an access-control gap noticed after Phase 8: the resource catalog was reachable at `/` with no login required at all. Split the root route in app/routes_common.py into a public `GET /` landing page (new `common.home`, rendering a new `landing.html` in each UI mode) that redirects a signed-in user straight to the catalog, and a `GET /catalog` route (kept as the `common.resource_catalog` endpoint, so every existing `url_for` reference and sortable-column link still resolves) now gated behind `require_any_role("admin", "planner", "technician")`. Updated both base.html navs so the "Catalog"/"Resource Catalog" link and the brand/home link only appear or point usefully once signed in. Updated docs/srs.html (new FR-USE-4), docs/architecture.html, and docs/phase3-backend-scope.html to match. Verified with a Flask test-client script: an anonymous request to `/` gets the landing page with no resource data in it, `/catalog` redirects anonymous requests to login, and a signed-in user is redirected from `/` to `/catalog` and can view it in both UI modes.
- 2026-07-30: Per follow-up feedback, replaced the just-added catalog-focused redirect with role-based routing: added `role_home_url()` and a `ROLE_HOME_ENDPOINT` map (admin/planner/technician) to app/routes_common.py, used by `login()`, `home()` (`/`), and `set_ui_mode()`'s fallback, so each role lands on its own workspace (Admin/Planner/Technician) instead of the catalog; `logout()` now sends to `/` (the landing page) instead. Removed the Catalog/"Resource Catalog" nav link entirely from both templates/simple/base.html and templates/modern/base.html and the matching stale help text from templates/simple/help.html &mdash; the catalog route itself still works (unchanged access control) but is no longer linked from anywhere in the UI, pending a confirmed need for it. Updated docs/srs.html (new FR-USE-5), docs/architecture.html, and docs/phase3-backend-scope.html to match. Verified with a Flask test-client script across all three roles and both UI modes: login and a bare `/` both land on the correct role workspace, no page renders a Catalog link, and logout returns to the landing page.
- 2026-07-30: Archived Phase 8 + the access-control fix to GitHub (commit `2c0d451` on `customer-application`), then started Phase 9 (Lab and Equipment Mutual-Exclusion Constraints). Added `exclusion_groups` and `exclusion_group_resources` tables plus an optional `resources.site` column to app/db.py (with a plain-ADD-COLUMN migration for `site`, since it carries no FK/CHECK and needs no table rebuild, unlike Phase 8's `eut_id`). Added admin CRUD for exclusion groups and their facility-resource membership, and a `site` field on the resource forms, to app/routes_admin.py and both admin_manage.html templates (new Exclusion Groups tab/section). Added `app/scheduling.py:find_running_conflict`, called from `routes_technician.py`'s `start_work_order` and `resume_work_order`: blocks the transition to in_progress, with a message naming the conflicting work order/order/test, if another work order sharing a resource or exclusion group is already in_progress. Scoped the block to the start/resume transition rather than creation-time scheduling, since a work order's `scheduled_date` carries no time-of-day and can't support a precise overlap check (documented as a design note in SRS FR-CON-2). Added a passive complement in `routes_planner.py:_load_schedule_context`: any two activities visible on the Schedule/Gantt tab that share a resource or exclusion group and have overlapping actual/inferred time windows are flagged (🚫 icon, red outline, tooltip naming the conflict) even if the hard block didn't catch them (e.g. one test overran into the next one's start) &mdash; this needed the allocation query to also select `resource_id` (previously only `code`/`name`/`resource_type`) and a small `_resources_conflict` helper checking both same-resource and shared-exclusion-group membership. Seeded the customer's own literal example: CE/CI capabilities on two "CON Chamber" facility resources (TLC) and RE/RI on two "SAC Chamber" facility resources (TLS), one exclusion group per chamber pair, and a new demo order (ORD-2026-003, Contoso Labs) with a CE and a CI test whose work orders are seeded already overlapping (bypassing the app's own checks, to demonstrate the passive Gantt flag specifically) rather than seeded consistent. Explicitly did not implement FR-CON-3 (cross-site double-booking warning) or FR-CON-4 (multi-day facility reservations) this phase; both stay in Phase 14. Updated docs/srs.html (FR-RES-5/FR-CON-1/FR-CON-2/FR-PLN-3 marked Delivered, design note added, traceability table and open questions updated), docs/ai-questions.html, docs/er-diagram.mmd + regenerated docs/er-diagram.svg, docs/er-model.html, docs/architecture.html, docs/phase3-backend-scope.html, docs/index.html, and both help.html pages. Verified with test-client scripts: exclusion-group CRUD and resource `site` edits round-trip correctly in both UI modes; a work order sharing a resource with an already-in_progress one is blocked from starting with the expected message and its status stays `planned`; an unrelated technician's normal flow is unaffected; the seeded CE/CI conflict shows the conflict marker on the Schedule tab for 2026-08-03 and no other day shows a false positive. Caught and fixed one bug before considering this done: the first seed attempt placed the two conflicting work orders' start times far enough apart (09:00 and 10:00) that the Gantt's own 1-hour fallback duration for still-running work orders made them adjacent rather than overlapping, so no conflict was flagged; moved the second one to 09:30 to genuinely overlap.
- 2026-07-30: Archived Phase 9 to GitHub (commit `9f0458d` on `customer-application`), then started Phase 10 (Standard Project Activity Template). Added `activity_templates` and `activity_template_items` tables plus an optional `sequence` column on `ordered_tests` to app/db.py; `sequence` uses a plain ADD COLUMN migration (no FK/CHECK) with a one-time backfill that assigns a stable 1..N order per (order_id, eut_id) group from current id order, so pre-existing rows get a real starting sequence instead of NULL. Added admin CRUD for activity templates and their items to app/routes_admin.py and both admin_manage.html templates (new Activity Templates tab/section), including up/down reordering within a template and automatic renumbering after a delete. Added a planner `apply_template` action (bulk-creates ordered_tests from a template's items, continuing the target order/EUT's sequence counter) and a `move_test` action (swaps sequence with the adjacent row in the same order/EUT scope) to app/routes_planner.py, plus a `#`/Reorder column and an "Apply an activity template" card in both planner_orders.html templates; changed `update_test` to reassign a fresh sequence when a test's EUT changes, since its old sequence was only meaningful in the old scope. Seeded one template, "Standard EMC Test Sequence", matching the customer's literal step list (Kick-off through EUT return) with RE/RI/CI/CE items mapped to their existing capabilities, plus a new demo order (ORD-2026-004, Helios Devices) with two EUTs: "Rev A" bulk-created directly from the template (shows the result) and "Rev B" left empty on purpose (so applying the template live is part of the demo). Updated docs/srs.html (FR-TP-4 marked Delivered, new AC-FR-TP-4.1, traceability table and data requirements/open questions updated), docs/ai-questions.html, docs/er-diagram.mmd + regenerated docs/er-diagram.svg, docs/er-model.html, docs/architecture.html, docs/phase3-backend-scope.html, docs/index.html, and both help.html pages. Verified with test-client scripts: template CRUD, item reorder, and delete-then-resequence all round-trip correctly; applying the template to Rev B (via a direct POST, mirroring the real form) produces all 17 activities in template order; moving a test up/down swaps sequence with its neighbor and reports "already at that end" past the boundary; a full apply-and-reorder pass through a throwaway order and cleanup left the database as it found it.

- 2026-07-30: Archived Phase 10 to GitHub (commit `7bd1c49` on `customer-application`), then started Phase 11 (Project and Discipline Dashboard). Added a nullable `discipline` column to capabilities, `weekly_note`/`waiting_for_customer` columns to customer_orders, and a new `milestones` table to app/db.py (all plain ADD COLUMN/CREATE TABLE migrations, no FK/CHECK involved). Deliberately did *not* add a stored project-status column: per BR-001 (Single Source of Truth), overall project status and per-discipline status are computed at read time in a new `app/routes_planner.py:_load_dashboard_context` from the aggregate status of the project's/discipline's ordered_tests' work_orders (Planned/In Progress/Reporting/Completed), with `waiting_for_customer` overriding the displayed label when set - weekly_note and waiting_for_customer are the only two fields with no other source in the system, so they're the only ones stored and manually edited. A discipline groups activities via their required capability's `discipline` field (seeded: Calibration, Environmental, EMC), falling back to name-based buckets ("Report" / "Project Management") for activities with no capability, explicitly flagged as a stopgap pending the customer confirming the real taxonomy. Added `app/scheduling.py:find_all_running_conflicts` (a system-wide sibling to Phase 9's day-scoped Gantt check) so the dashboard can flag a project if any of its in-progress activities conflicts with another project's. Added a new `GET/POST /planner/dashboard` route with actions to save a project's weekly note/waiting-for-customer flag and to create/delete a milestone, plus `dashboard.html` in both UI modes (active-project cards with status/discipline badges, gap counts, conflict flag, milestones; a read-only completed-projects table) and a Dashboard nav link visible to the planner role. Seeded a weekly note and milestones on a couple of demo projects and flagged one as waiting-for-customer. Updated docs/srs.html (FR-PRJ-3/4, FR-STA-2, FR-VIS-1/2 marked Delivered, a design note on the derivation rules and discipline fallback, traceability table and open questions updated), docs/ai-questions.html, docs/er-diagram.mmd + regenerated docs/er-diagram.svg, docs/er-model.html, docs/architecture.html, docs/phase3-backend-scope.html, docs/index.html, and both help.html pages. Verified with test-client scripts: the dashboard renders in both UI modes and correctly reflects a project independently edited through the live running app during this session (customer name changed via the UI, not by this work) - its "Waiting for Customer" status and conflict flag both still compute correctly against that live data, which was a better test of the derivation logic than a clean seed would have been; weekly-note/waiting-for-customer save and milestone create/delete all round-tripped correctly on a throwaway order that was cleaned up afterward.

## Open Questions Queue Policy
- Blocker: Must be answered before current phase can continue.
- High: Should be answered within current phase.
- Medium: Can be deferred to a later phase.
- Low: Nice-to-have clarification.
