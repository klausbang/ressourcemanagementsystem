"""Route-level and server-rendered-content checks for the Visual Planner (proposals id
5 and 6). The actual drag-and-drop interactions need a real browser - see
test_visual_planner_ui.py.
"""
from conftest import login


def test_denied_to_plain_user(client):
    login(client, "user.demo")
    r = client.get("/planner", follow_redirects=True)
    assert r.request.path == "/login"


def test_allowed_to_planner(client):
    login(client, "planner.demo")
    r = client.get("/planner")
    assert r.status_code == 200


def test_allowed_to_admin(client):
    login(client, "admin.demo")
    r = client.get("/planner")
    assert r.status_code == 200


def test_sample_projects_and_hours_render(client):
    login(client, "planner.demo")
    body = client.get("/planner").data.decode("utf-8")
    for project in ("P26-1001", "P26-1002", "P26-1003"):
        assert project in body
    for hour_label in ("08:00", "17:00"):
        assert hour_label in body
    # P26-1004 only exists in the unplanned queue - no row until dragged onto the
    # "New project" placeholder (that part is UI-only, see test_visual_planner_ui.py).
    assert 'data-project="P26-1004"' not in body


def test_placed_test_slot_math_matches_duration():
    from app.routes_planner import _slot_offset, _slot_span, SLOT_MINUTES

    assert _slot_offset(hour=9, minute=0) == 4  # (9-8)*60/15
    assert _slot_offset(hour=8, minute=15) == 1
    assert _slot_span("00:45") == 3
    assert _slot_span("02:00") == 8
    assert _slot_span("00:07") == 1  # rounds down to the minimum of one slot, never zero
    assert SLOT_MINUTES == 15
