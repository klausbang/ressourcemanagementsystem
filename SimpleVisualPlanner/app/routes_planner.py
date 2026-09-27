"""Visual Planner (proposal id 5, extended by proposal id 6): a first, editable-only
prototype - one row per project, a 15-minute-resolution time axis (08:00-18:00), a
placed test rendered as a draggable block whose width follows its duration and which
spans two stacked lines (test name / tester initials). An "Unplanned" queue on the left
holds tests not yet placed - each one editable, and draggable onto its own project's row
(or, if that project has no row yet, onto the "New project" placeholder to create one,
which highlights briefly once created). An already-placed test can be dragged to a new
time on its own row, or back into the queue to unschedule it.

All of this happens client-side (see visual_planner.html's own <script>) - deliberately
in-memory/hardcoded, per the original proposal's own "later the data may com from the
database": there is no projects/tests table yet, and nothing placed, moved, or edited
here is persisted. Reloading the page resets it to the sample data below.
"""
from flask import Blueprint

from reusable_modules.basic_app.auth import require_role
from reusable_modules.basic_app.ui import render_ui

bp = Blueprint("planner", __name__)

PLANNER_START_HOUR = 8
PLANNER_END_HOUR = 18  # exclusive
SLOT_MINUTES = 15
SLOTS_PER_HOUR = 60 // SLOT_MINUTES
TOTAL_SLOTS = (PLANNER_END_HOUR - PLANNER_START_HOUR) * SLOTS_PER_HOUR
PLANNER_HOURS = list(range(PLANNER_START_HOUR, PLANNER_END_HOUR))

# Kept in one place so the template's pixel math and the client-side JS doing the same
# math for drag-and-drop always agree.
SLOT_WIDTH_PX = 18


def _slot_offset(hour: int, minute: int) -> int:
    return ((hour - PLANNER_START_HOUR) * 60 + minute) // SLOT_MINUTES


def _slot_span(duration_label: str) -> int:
    """duration_label is "hh:mm" - rounds to the nearest 15-minute step, minimum one."""
    hh, mm = duration_label.split(":")
    minutes = int(hh) * 60 + int(mm)
    return max(1, round(minutes / SLOT_MINUTES))


SAMPLE_PROJECTS = [
    {
        "name": "P26-1001",
        "customer": "Acme Instruments",
        "eut": "Multimeter Rev C",
        "placed": [
            {"hour": 9, "minute": 0, "duration": "02:00", "test": "RE", "tester": "MJ"},
            {"hour": 11, "minute": 0, "duration": "01:00", "test": "CI", "tester": "SI"},
        ],
    },
    {
        "name": "P26-1002",
        "customer": "Nova Mobile",
        "eut": "Handset X2",
        "placed": [],
    },
    {
        "name": "P26-1003",
        "customer": "Contoso Labs",
        "eut": "IoT Gateway",
        "placed": [
            {"hour": 10, "minute": 0, "duration": "01:30", "test": "CE", "tester": "MJ"},
        ],
    },
]

# The last one (P26-1004) deliberately has no row above yet, to demo dragging a test
# for a project that isn't on the grid yet (proposal id 6, point 5).
SAMPLE_UNPLANNED = [
    {"project": "P26-1001", "customer": "Acme Instruments", "eut": "Multimeter Rev C", "test": "RI", "tester": "SI", "duration": "00:45"},
    {"project": "P26-1002", "customer": "Nova Mobile", "eut": "Handset X2", "test": "RE", "tester": "MJ", "duration": "01:00"},
    {"project": "P26-1002", "customer": "Nova Mobile", "eut": "Handset X2", "test": "CI", "tester": "TL", "duration": "00:30"},
    {"project": "P26-1003", "customer": "Contoso Labs", "eut": "IoT Gateway", "test": "RI", "tester": "SM", "duration": "01:15"},
    {"project": "P26-1004", "customer": "Helios Devices", "eut": "Smart Thermostat", "test": "CE", "tester": "MJ", "duration": "01:00"},
]


@bp.route("/planner")
@require_role("planner", "admin")
def visual_planner():
    projects = []
    for project in SAMPLE_PROJECTS:
        placed = [
            {
                **item,
                "slot_offset": _slot_offset(item["hour"], item["minute"]),
                "slot_span": _slot_span(item["duration"]),
            }
            for item in project["placed"]
        ]
        projects.append({**project, "placed": placed})

    return render_ui(
        "basic_app/visual_planner.html",
        projects=projects,
        hours=PLANNER_HOURS,
        slots_per_hour=SLOTS_PER_HOUR,
        total_slots=TOTAL_SLOTS,
        slot_width=SLOT_WIDTH_PX,
        unplanned=SAMPLE_UNPLANNED,
    )
