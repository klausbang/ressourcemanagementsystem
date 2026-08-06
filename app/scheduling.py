"""Lab/equipment mutual-exclusion conflict checking (Phase 9).

A conflict exists when two *different* ordered tests would both have a work
order "in progress" at the same time while sharing either the exact same
resource, or two different resources that belong to the same admin-defined
exclusion group (e.g. two facility resources that are really the same shared
physical chamber). See docs/srs.html section 8.4 (FR-CON) for the requirement
this implements, and its accompanying design note for why the check is scoped
to the in_progress transition rather than to creation-time scheduling.
"""

import sqlite3
from datetime import date, timedelta


def find_running_conflict(
    db: sqlite3.Connection, ordered_test_id: int, exclude_work_order_id: int | None = None
) -> dict | None:
    """If starting/resuming ordered_test_id's work order right now would conflict with
    another currently in_progress work order (same resource, or same exclusion group),
    return details of that conflict. Otherwise return None."""

    resource_rows = db.execute(
        "SELECT resource_id FROM allocations WHERE ordered_test_id = ?", (ordered_test_id,)
    ).fetchall()
    resource_ids = {row["resource_id"] for row in resource_rows}
    if not resource_ids:
        return None

    group_rows = db.execute(
        f"""
        SELECT DISTINCT egr2.resource_id
        FROM exclusion_group_resources egr1
        JOIN exclusion_group_resources egr2 ON egr2.group_id = egr1.group_id
        WHERE egr1.resource_id IN ({','.join('?' for _ in resource_ids)})
        """,
        list(resource_ids),
    ).fetchall()
    conflict_resource_ids = resource_ids | {row["resource_id"] for row in group_rows}

    placeholders = ",".join("?" for _ in conflict_resource_ids)
    exclude_clause = "AND wo.id != ?" if exclude_work_order_id else ""
    params = list(conflict_resource_ids) + [ordered_test_id] + (
        [exclude_work_order_id] if exclude_work_order_id else []
    )

    row = db.execute(
        f"""
        SELECT
            wo.work_order_code, o.order_code, ot.test_name, r.code AS resource_code
        FROM allocations a
        JOIN resources r ON r.id = a.resource_id
        JOIN ordered_tests ot ON ot.id = a.ordered_test_id
        JOIN customer_orders o ON o.id = ot.order_id
        JOIN work_orders wo ON wo.ordered_test_id = ot.id
        WHERE a.resource_id IN ({placeholders})
          AND ot.id != ?
          AND wo.status = 'in_progress'
          {exclude_clause}
        LIMIT 1
        """,
        params,
    ).fetchone()

    if row is None:
        return None
    return dict(row)


def conflict_message(conflict: dict) -> str:
    return (
        f"Cannot start: {conflict['resource_code']} is already in use by "
        f"{conflict['work_order_code']} ({conflict['order_code']} / {conflict['test_name']}), "
        f"which is still in progress."
    )


def find_all_running_conflicts(db: sqlite3.Connection) -> list[tuple[dict, dict]]:
    """Every pair of currently in_progress work orders that conflict (same resource or
    exclusion group), system-wide - not scoped to one day like the planner's Gantt view.
    Used by the project dashboard (FR-VIS-2) to flag a project as currently in conflict."""

    rows = db.execute(
        """
        SELECT wo.id AS work_order_id, wo.work_order_code, wo.ordered_test_id,
               ot.order_id, o.order_code, ot.test_name
        FROM work_orders wo
        JOIN ordered_tests ot ON ot.id = wo.ordered_test_id
        JOIN customer_orders o ON o.id = ot.order_id
        WHERE wo.status = 'in_progress'
        """
    ).fetchall()
    if len(rows) < 2:
        return []

    resources_by_test: dict[int, set] = {}
    for row in db.execute("SELECT ordered_test_id, resource_id FROM allocations").fetchall():
        resources_by_test.setdefault(row["ordered_test_id"], set()).add(row["resource_id"])

    groups_by_resource: dict[int, set] = {}
    for row in db.execute("SELECT group_id, resource_id FROM exclusion_group_resources").fetchall():
        groups_by_resource.setdefault(row["resource_id"], set()).add(row["group_id"])

    def _conflicts(res_ids_a: set, res_ids_b: set) -> bool:
        if res_ids_a & res_ids_b:
            return True
        groups_a = set().union(*(groups_by_resource.get(rid, set()) for rid in res_ids_a)) if res_ids_a else set()
        groups_b = set().union(*(groups_by_resource.get(rid, set()) for rid in res_ids_b)) if res_ids_b else set()
        return bool(groups_a & groups_b)

    conflicts = []
    for i in range(len(rows)):
        for j in range(i + 1, len(rows)):
            a, b = rows[i], rows[j]
            if a["ordered_test_id"] == b["ordered_test_id"]:
                continue
            a_ids = resources_by_test.get(a["ordered_test_id"], set())
            b_ids = resources_by_test.get(b["ordered_test_id"], set())
            if _conflicts(a_ids, b_ids):
                conflicts.append((dict(a), dict(b)))
    return conflicts


def find_unmet_dependency(db: sqlite3.Connection, ordered_test_id: int) -> dict | None:
    """If ordered_test_id has a prerequisite (see Phase 14, activity_dependencies) whose
    work order isn't completed yet, return details of the first one found. Otherwise None."""

    row = db.execute(
        """
        SELECT o.order_code, ot.test_name, wo.status AS wo_status
        FROM activity_dependencies ad
        JOIN ordered_tests ot ON ot.id = ad.depends_on_ordered_test_id
        JOIN customer_orders o ON o.id = ot.order_id
        LEFT JOIN work_orders wo ON wo.ordered_test_id = ot.id
        WHERE ad.ordered_test_id = ?
          AND (wo.status IS NULL OR wo.status != 'completed')
        LIMIT 1
        """,
        (ordered_test_id,),
    ).fetchone()
    return dict(row) if row else None


def unmet_dependency_message(dep: dict) -> str:
    status = dep["wo_status"] or "not started"
    return (
        f"Cannot start: this activity depends on {dep['test_name']} ({dep['order_code']}), "
        f"which is not yet completed (currently {status})."
    )


def would_create_dependency_cycle(db: sqlite3.Connection, ordered_test_id: int, new_dependency_id: int) -> bool:
    """True if making ordered_test_id depend on new_dependency_id would create a cycle,
    i.e. new_dependency_id (transitively, via its own prerequisites) already depends on
    ordered_test_id."""

    visited: set[int] = set()
    stack = [new_dependency_id]
    while stack:
        current = stack.pop()
        if current == ordered_test_id:
            return True
        if current in visited:
            continue
        visited.add(current)
        rows = db.execute(
            "SELECT depends_on_ordered_test_id FROM activity_dependencies WHERE ordered_test_id = ?",
            (current,),
        ).fetchall()
        stack.extend(row["depends_on_ordered_test_id"] for row in rows)
    return False


def find_planned_facility_overlaps(db: sqlite3.Connection) -> list[tuple[dict, dict]]:
    """Pairs of ordered tests with overlapping *planned* date windows (Phase 15, FR-CON-4)
    that share a facility resource or exclusion group. Unlike find_running_conflict, neither
    activity needs to have started (or even been allocated a work order) yet - this is a
    forward-looking warning at the planning stage, using the planned_start_date/
    planned_end_date added in Phase 14. A facility reservation is already "a single booking"
    (one row on the activity, not one row per day), so this is the missing check on top of
    that: two such single-row bookings whose date ranges overlap on the same facility."""

    rows = db.execute(
        """
        SELECT DISTINCT ot.id AS ordered_test_id, ot.order_id, o.order_code, ot.test_name,
               ot.planned_start_date, ot.planned_end_date
        FROM ordered_tests ot
        JOIN customer_orders o ON o.id = ot.order_id
        JOIN allocations a ON a.ordered_test_id = ot.id
        JOIN resources r ON r.id = a.resource_id
        WHERE ot.planned_start_date IS NOT NULL AND ot.planned_end_date IS NOT NULL
          AND r.resource_type = 'facility'
        """
    ).fetchall()
    if len(rows) < 2:
        return []

    resources_by_test: dict[int, set] = {}
    for row in db.execute(
        """
        SELECT a.ordered_test_id, r.id AS resource_id
        FROM allocations a JOIN resources r ON r.id = a.resource_id
        WHERE r.resource_type = 'facility'
        """
    ).fetchall():
        resources_by_test.setdefault(row["ordered_test_id"], set()).add(row["resource_id"])

    groups_by_resource: dict[int, set] = {}
    for row in db.execute("SELECT group_id, resource_id FROM exclusion_group_resources").fetchall():
        groups_by_resource.setdefault(row["resource_id"], set()).add(row["group_id"])

    def _shares_facility(res_ids_a: set, res_ids_b: set) -> bool:
        if res_ids_a & res_ids_b:
            return True
        groups_a = set().union(*(groups_by_resource.get(rid, set()) for rid in res_ids_a)) if res_ids_a else set()
        groups_b = set().union(*(groups_by_resource.get(rid, set()) for rid in res_ids_b)) if res_ids_b else set()
        return bool(groups_a & groups_b)

    overlaps = []
    for i in range(len(rows)):
        for j in range(i + 1, len(rows)):
            a, b = rows[i], rows[j]
            if a["ordered_test_id"] == b["ordered_test_id"]:
                continue
            a_ids = resources_by_test.get(a["ordered_test_id"], set())
            b_ids = resources_by_test.get(b["ordered_test_id"], set())
            if not _shares_facility(a_ids, b_ids):
                continue
            if a["planned_start_date"] <= b["planned_end_date"] and b["planned_start_date"] <= a["planned_end_date"]:
                overlaps.append((dict(a), dict(b)))
    return overlaps


def next_work_order_code(db: sqlite3.Connection) -> str:
    # Based on the numeric suffix of existing codes, not MAX(id): seed data's work order
    # codes don't necessarily follow the id sequence, so an id-based next code can collide
    # with an existing one that was assigned out of sequence. Shared by the technician
    # self-service work order creation and the planner-side visual scheduling (Phase 28).
    max_num = 0
    for row in db.execute("SELECT work_order_code FROM work_orders").fetchall():
        code = row["work_order_code"] or ""
        if code.startswith("WO-"):
            try:
                max_num = max(max_num, int(code[3:]))
            except ValueError:
                pass
    return f"WO-{max_num + 1:04d}"


def suggest_placement(db: sqlite3.Connection, ordered_test_id: int, lookahead_days: int = 21) -> dict | None:
    """Phase 28 (visual scheduling, FR-PLN-6): propose the earliest (technician, date) pair
    an unscheduled ordered test could be placed on, so the planner has a one-click default
    instead of guessing. Day-level only (no time-of-day column exists yet - see
    docs/ai-questions.html). A candidate day is skipped if:
      - the technician already has a non-completed work order scheduled that day, or
      - the technician has a staff_absence covering that day, or
      - any equipment/facility resource already allocated to this ordered test (Phase 5/9)
        already has another work order scheduled that day (a day-granularity cousin of the
        facility/equipment overlap concern in find_planned_facility_overlaps above).
    Candidate technicians are every technician-role user whose linked resource has the
    ordered test's required capability, in username order; if the test has no
    required_capability_id, every technician-role user is a candidate. Returns None if no
    slot is found within lookahead_days - the planner then places manually. This is a
    suggestion only: nothing is written to the database here."""

    test = db.execute(
        "SELECT required_capability_id, planned_start_date FROM ordered_tests WHERE id = ?",
        (ordered_test_id,),
    ).fetchone()
    if test is None:
        return None

    if test["required_capability_id"]:
        technicians = db.execute(
            """
            SELECT DISTINCT u.id AS user_id, u.username
            FROM users u
            JOIN resources r ON r.id = u.linked_resource_id
            JOIN resource_capabilities rc ON rc.resource_id = r.id
            WHERE u.role = 'technician' AND rc.capability_id = ?
            ORDER BY u.username
            """,
            (test["required_capability_id"],),
        ).fetchall()
    else:
        technicians = db.execute(
            "SELECT id AS user_id, username FROM users WHERE role = 'technician' ORDER BY username"
        ).fetchall()
    if not technicians:
        return None

    other_resource_ids = {
        row["resource_id"]
        for row in db.execute(
            """
            SELECT a.resource_id FROM allocations a
            JOIN resources r ON r.id = a.resource_id
            WHERE a.ordered_test_id = ? AND r.resource_type IN ('equipment', 'facility')
            """,
            (ordered_test_id,),
        ).fetchall()
    }

    start_day = date.today()
    if test["planned_start_date"]:
        planned = date.fromisoformat(test["planned_start_date"])
        if planned > start_day:
            start_day = planned

    for offset in range(lookahead_days):
        day = start_day + timedelta(days=offset)
        day_iso = day.isoformat()

        if other_resource_ids:
            placeholders = ",".join("?" for _ in other_resource_ids)
            busy_resource = db.execute(
                f"""
                SELECT 1
                FROM allocations a
                JOIN work_orders wo ON wo.ordered_test_id = a.ordered_test_id
                WHERE a.resource_id IN ({placeholders})
                  AND a.ordered_test_id != ?
                  AND wo.status != 'completed'
                  AND wo.scheduled_date = ?
                LIMIT 1
                """,
                list(other_resource_ids) + [ordered_test_id, day_iso],
            ).fetchone()
            if busy_resource:
                continue

        for tech in technicians:
            busy = db.execute(
                """
                SELECT 1 FROM work_orders
                WHERE technician_user_id = ? AND status != 'completed' AND scheduled_date = ?
                LIMIT 1
                """,
                (tech["user_id"], day_iso),
            ).fetchone()
            if busy:
                continue

            absent = db.execute(
                """
                SELECT 1 FROM staff_absences a
                JOIN users u ON u.linked_resource_id = a.resource_id
                WHERE u.id = ? AND a.start_date <= ? AND a.end_date >= ?
                LIMIT 1
                """,
                (tech["user_id"], day_iso, day_iso),
            ).fetchone()
            if absent:
                continue

            return {
                "technician_user_id": tech["user_id"],
                "technician_username": tech["username"],
                "scheduled_date": day_iso,
            }

    return None


def find_reschedule_suggestions(db: sqlite3.Connection) -> list[dict]:
    """Phase 15, FR-RSC-2: when a prerequisite finished late (or is already overdue and
    still not complete), suggest shifting its direct dependent's planned window by the
    same number of days, for the planner to accept (apply the shift) or ignore (dismiss,
    see reschedule_dismissals). This is assisted, not automatic - nothing changes until
    the planner accepts a specific suggestion."""

    today_iso = date.today().isoformat()
    rows = db.execute(
        """
        SELECT
            ad.id AS dependency_id, ad.depends_on_ordered_test_id,
            dep.id AS ordered_test_id, dep_o.order_code AS dep_order_code, dep.test_name AS dep_test_name,
            dep.planned_start_date AS dep_planned_start, dep.planned_end_date AS dep_planned_end,
            pre.test_name AS pre_test_name, pre_o.order_code AS pre_order_code,
            pre.planned_end_date AS pre_planned_end,
            pre_wo.status AS pre_wo_status, pre_wo.completed_at AS pre_completed_at
        FROM activity_dependencies ad
        JOIN ordered_tests dep ON dep.id = ad.ordered_test_id
        JOIN customer_orders dep_o ON dep_o.id = dep.order_id
        LEFT JOIN work_orders dep_wo ON dep_wo.ordered_test_id = dep.id
        JOIN ordered_tests pre ON pre.id = ad.depends_on_ordered_test_id
        JOIN customer_orders pre_o ON pre_o.id = pre.order_id
        LEFT JOIN work_orders pre_wo ON pre_wo.ordered_test_id = pre.id
        WHERE pre.planned_end_date IS NOT NULL
          AND dep.planned_start_date IS NOT NULL AND dep.planned_end_date IS NOT NULL
          AND (dep_wo.status IS NULL OR dep_wo.status != 'completed')
        """
    ).fetchall()
    if not rows:
        return []

    dismissed = {
        (row["ordered_test_id"], row["depends_on_ordered_test_id"])
        for row in db.execute(
            "SELECT ordered_test_id, depends_on_ordered_test_id FROM reschedule_dismissals"
        ).fetchall()
    }

    suggestions = []
    for row in rows:
        if (row["ordered_test_id"], row["depends_on_ordered_test_id"]) in dismissed:
            continue
        if row["pre_wo_status"] == "completed" and row["pre_completed_at"]:
            reference = row["pre_completed_at"].split(" ")[0]
        elif row["pre_wo_status"] != "completed" and row["pre_planned_end"] < today_iso:
            reference = today_iso
        else:
            continue  # not late (yet)

        delay_days = (date.fromisoformat(reference) - date.fromisoformat(row["pre_planned_end"])).days
        if delay_days <= 0:
            continue

        new_start = (date.fromisoformat(row["dep_planned_start"]) + timedelta(days=delay_days)).isoformat()
        new_end = (date.fromisoformat(row["dep_planned_end"]) + timedelta(days=delay_days)).isoformat()

        suggestions.append(
            {
                "dependency_id": row["dependency_id"],
                "ordered_test_id": row["ordered_test_id"],
                "order_code": row["dep_order_code"],
                "test_name": row["dep_test_name"],
                "prerequisite_test_name": row["pre_test_name"],
                "prerequisite_order_code": row["pre_order_code"],
                "delay_days": delay_days,
                "current_planned_start": row["dep_planned_start"],
                "current_planned_end": row["dep_planned_end"],
                "suggested_planned_start": new_start,
                "suggested_planned_end": new_end,
            }
        )
    return suggestions
