"""Append-only change history for test activities (Phase 13).

Answers "who moved this test, when, and (where provided) why" per activity,
without needing a separate audit system: each schedule-affecting change
(resource assignment, reordering, EUT reassignment, work order lifecycle)
writes one row here. See docs/srs.html FR-NTH-1.
"""

import sqlite3
from datetime import datetime


def record(
    db: sqlite3.Connection,
    ordered_test_id: int,
    user_id: int | None,
    username: str | None,
    action: str,
    detail: str,
    reason: str | None = None,
) -> None:
    db.execute(
        """
        INSERT INTO activity_history (ordered_test_id, changed_at, user_id, username, action, detail, reason)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (ordered_test_id, datetime.now().strftime("%Y-%m-%d %H:%M"), user_id, username, action, detail, reason),
    )
