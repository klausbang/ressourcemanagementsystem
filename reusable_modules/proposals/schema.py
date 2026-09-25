"""proposals table schema. Deliberately no CHECK constraint on proposal_type/status (RMS's
own proposals table has one, but its allowed values are fixed at table-creation time) -
here they're validated in routes.py against whatever proposal_types/statuses the
consuming app passed to init_proposals(), so a new type/status can be configured later
without ever needing RMS's rebuild-and-rename CHECK-widening migration (see the
`database` module's migrations.py) for this table.

No FK from submitted_by_user_id/admin_user_id to a `users` table either - proposals
doesn't require basic_app specifically (any module/app that has its own idea of "current
user id" can supply one), so any cross-module reference is left to the application level,
consistent with the FK-avoidance pattern documented in RMS's own CLAUDE.md for
cross-module references.
"""

PROPOSALS_SCHEMA = """
CREATE TABLE IF NOT EXISTS proposals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT NOT NULL,
    proposal_type TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    submitted_by_user_id INTEGER,
    submitted_by_username TEXT,
    created_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'new',
    admin_comment TEXT,
    admin_user_id INTEGER,
    updated_at TEXT,
    is_general INTEGER NOT NULL DEFAULT 0
);
"""
