"""Visual Planner (proposal id 5): a first, editable-only prototype - one row per
project, 1-hour columns, two sub-rows per project (test name on top, tester initials
underneath), an unplanned queue on the left that's draggable onto its own project's row.
Deliberately in-memory/hardcoded for now, per the proposal's own wording ("later the data
may com from the database") - there is no projects/tests table yet, and nothing placed
or edited here is persisted; reloading the page resets it to this sample data.
"""
from flask import Blueprint

from reusable_modules.basic_app.auth import require_role
from reusable_modules.basic_app.ui import render_ui

bp = Blueprint("planner", __name__)

PLANNER_HOURS = list(range(8, 18))  # 08:00-17:00, 1-hour columns

SAMPLE_PROJECTS = [
    {
        "name": "P26-1001",
        "placed": [
            {"hour": 9, "test": "RE", "tester": "MJ"},
            {"hour": 11, "test": "CI", "tester": "SI"},
        ],
    },
    {
        "name": "P26-1002",
        "placed": [],
    },
    {
        "name": "P26-1003",
        "placed": [
            {"hour": 10, "test": "CE", "tester": "MJ"},
        ],
    },
]

SAMPLE_UNPLANNED = [
    {"project_index": 0, "test": "RI", "tester": "SI"},
    {"project_index": 1, "test": "RE", "tester": "MJ"},
    {"project_index": 1, "test": "CI", "tester": "TL"},
    {"project_index": 2, "test": "RI", "tester": "SM"},
]


@bp.route("/planner")
@require_role("planner", "admin")
def visual_planner():
    placed_by_project_hour = {}
    for project_index, project in enumerate(SAMPLE_PROJECTS):
        for item in project["placed"]:
            placed_by_project_hour[(project_index, item["hour"])] = item

    return render_ui(
        "basic_app/visual_planner.html",
        projects=SAMPLE_PROJECTS,
        hours=PLANNER_HOURS,
        placed_by_project_hour=placed_by_project_hour,
        unplanned=SAMPLE_UNPLANNED,
    )
