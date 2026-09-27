"""Real-browser tests for the Visual Planner's drag-and-drop (proposal id 6): a plain
Flask test client can't exercise client-side JS at all, and this feature is nothing but
client-side JS (see visual_planner.html), so these are the only tests that actually
prove it works - a code read or a DOM-content check would not have caught, for example,
the cross-project drop guard being backwards.

Marked `ui` (see pytest.ini) so the fast suite can be run on its own with `-m "not ui"`;
these are slower (real browser + real HTTP server per test) and need Playwright's
Chromium browser installed (`playwright install chromium`).

Note on technique: Playwright's Locator.drag_to() drives real OS-level mouse events,
which some environments' virtual displays don't turn into genuine HTML5 drag events
(dragstart/dragover/drop) the way a real user's cursor drag does - and this feature is
built entirely on those events, not on mouse position. So each drag here is performed by
dispatching real `DragEvent`s directly (a standard, documented technique for testing
native HTML5 drag-and-drop headlessly), sharing one `DataTransfer` between the source and
target the same way the browser itself would.
"""
import re

import pytest

pytestmark = pytest.mark.ui

DND_HELPER = """
window.__simDnd = function (sourceEl, targetEl, clientX, clientY) {
  var dt = new DataTransfer();
  function fire(type, elem, cx, cy) {
    var ev = new DragEvent(type, { bubbles: true, cancelable: true, clientX: cx, clientY: cy });
    Object.defineProperty(ev, 'dataTransfer', { value: dt });
    elem.dispatchEvent(ev);
  }
  var srect = sourceEl.getBoundingClientRect();
  fire('dragstart', sourceEl, srect.left + srect.width / 2, srect.top + srect.height / 2);
  fire('dragenter', targetEl, clientX, clientY);
  fire('dragover', targetEl, clientX, clientY);
  fire('drop', targetEl, clientX, clientY);
  fire('dragend', sourceEl, clientX, clientY);
};
"""


def sim_drag(page, source_locator, target_locator, off_x=20, off_y=20):
    box = target_locator.bounding_box()
    src = source_locator.element_handle()
    tgt = target_locator.element_handle()
    page.evaluate(
        "([src, tgt, x, y]) => window.__simDnd(src, tgt, x, y)",
        [src, tgt, box["x"] + off_x, box["y"] + off_y],
    )


def queue_card_with_test(page, test_name):
    """A queue card whose *test* field is exactly `test_name` - not just a card whose
    text happens to contain it somewhere. Playwright's `has_text` does a case-insensitive
    *substring* match across the whole element's text, so a loose `.filter(has_text="RE")`
    also matches a card whose EUT reads "Multimeter Rev C" (contains "re"); scoping the
    match to the `.vp-card-test` child with an exact, anchored regex avoids that."""
    return page.locator("#vpQueue .vp-card").filter(
        has=page.locator(".vp-card-test", has_text=re.compile(f"^{re.escape(test_name)}$"))
    )


@pytest.fixture
def planner_page(live_server, page):
    """A page already logged in as planner.demo and sitting on /planner, with the drag
    simulation helper installed."""
    page.add_init_script(script=DND_HELPER)
    page.goto(live_server + "/login")
    page.fill("#username", "planner.demo")
    page.click("button[type=submit]")
    page.wait_for_url("**/planner")
    return page


def test_initial_state(planner_page):
    page = planner_page
    assert page.locator("#vpRows .vp-row:not(.vp-placeholder-row)").count() == 3
    assert page.locator("#vpQueue .vp-card").count() == 5


def test_drag_unplanned_test_onto_own_project(planner_page):
    page = planner_page
    # Two cards have test "RI" (P26-1001 and P26-1003); P26-1001's is first in DOM order.
    ri_card = queue_card_with_test(page, "RI").first
    band = page.locator('.vp-row[data-project="P26-1001"] .vp-band')

    sim_drag(page, ri_card, band, off_x=300, off_y=20)

    assert page.locator('.vp-row[data-project="P26-1001"] .vp-block').count() == 3
    assert page.locator("#vpQueue .vp-card").count() == 4
    # duration 00:45 -> 3 slots * 18px slot width = 54px
    new_block = page.locator('.vp-row[data-project="P26-1001"] .vp-block').nth(2)
    assert new_block.evaluate("el => el.style.width") == "54px"


def test_cross_project_drop_is_rejected(planner_page):
    page = planner_page
    # The P26-1002 card whose test is exactly "RE" - not P26-1001's RI card, whose EUT
    # text ("Multimeter Rev C") would also match a loose case-insensitive "RE" filter.
    re_card = queue_card_with_test(page, "RE").first
    wrong_band = page.locator('.vp-row[data-project="P26-1001"] .vp-band')

    sim_drag(page, re_card, wrong_band, off_x=100, off_y=20)

    assert page.locator('.vp-row[data-project="P26-1001"] .vp-block').count() == 2
    assert page.locator("#vpQueue .vp-card").count() == 5


def test_drop_on_placeholder_creates_new_project_row(planner_page):
    page = planner_page
    assert page.locator('.vp-row[data-project="P26-1004"]').count() == 0

    new_project_card = page.locator("#vpQueue .vp-card").filter(has_text="Helios Devices")
    placeholder_band = page.locator(".vp-placeholder-row .vp-band")
    sim_drag(page, new_project_card, placeholder_band, off_x=200, off_y=20)

    assert page.locator('.vp-row[data-project="P26-1004"]').count() == 1
    assert page.locator('.vp-row[data-project="P26-1004"] .vp-block').count() == 1
    assert page.locator("#vpQueue .vp-card").count() == 4
    assert page.locator("#vpRows .vp-row:not(.vp-placeholder-row)").count() == 4
    last_row_class = page.locator("#vpRows > div").last.get_attribute("class")
    assert "vp-placeholder-row" in last_row_class  # placeholder always stays last


def test_move_placed_block_to_new_time(planner_page):
    page = planner_page
    block = page.locator('.vp-row[data-project="P26-1003"] .vp-block').first
    before_left = block.evaluate("el => el.style.left")
    band = page.locator('.vp-row[data-project="P26-1003"] .vp-band')

    sim_drag(page, block, band, off_x=400, off_y=20)

    after_left = page.locator('.vp-row[data-project="P26-1003"] .vp-block').first.evaluate(
        "el => el.style.left"
    )
    assert after_left != before_left
    assert page.locator('.vp-row[data-project="P26-1003"] .vp-block').count() == 1


def test_drag_placed_block_back_to_queue_unschedules_it(planner_page):
    page = planner_page
    block = page.locator('.vp-row[data-project="P26-1003"] .vp-block').first

    sim_drag(page, block, page.locator("#vpQueue"), off_x=50, off_y=50)

    assert page.locator('.vp-row[data-project="P26-1003"] .vp-block').count() == 0
    assert page.locator("#vpQueue .vp-card").count() == 6
    # Two cards now have test "CE": the seeded P26-1004 one, and this newly-unscheduled
    # one - distinguish by project, since test name alone isn't unique here.
    unscheduled = queue_card_with_test(page, "CE").filter(has_text="P26-1003")
    assert unscheduled.count() == 1


def test_card_fields_are_editable(planner_page):
    page = planner_page
    project_field = page.locator("#vpQueue .vp-card").first.locator(".vp-card-project")
    project_field.click()
    page.keyboard.press("Control+A")
    page.keyboard.type("EDITED-PROJECT")
    assert project_field.inner_text().strip() == "EDITED-PROJECT"


def test_no_javascript_errors_on_page(live_server, page):
    errors = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    page.add_init_script(script=DND_HELPER)
    page.goto(live_server + "/login")
    page.fill("#username", "planner.demo")
    page.click("button[type=submit]")
    page.wait_for_url("**/planner")
    assert errors == []
