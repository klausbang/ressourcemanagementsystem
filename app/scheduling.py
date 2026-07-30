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
