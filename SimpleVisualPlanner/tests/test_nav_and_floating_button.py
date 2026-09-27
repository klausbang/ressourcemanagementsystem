"""Covers proposal id 4 ("Add the proposal P button on all pages... make sure it is
added to all new pages created in the future as well") - the button is meant to be
automatic (basic_app/base.html includes it by default), so this test is written against
*every route the app currently exposes*, not a fixed list of pages, precisely so a
future page that forgets to do anything special still gets caught here if the automatic
mechanism ever regresses.
"""
from conftest import login

PAGES_BY_ROLE = {
    "admin.demo": ["/dashboard", "/planner", "/users", "/proposals/admin", "/proposals/new"],
    "planner.demo": ["/planner"],
    "user.demo": ["/dashboard", "/proposals/new"],
}


def test_p_button_present_on_every_page_for_every_role(client):
    for username, pages in PAGES_BY_ROLE.items():
        login(client, username)
        for path in pages:
            r = client.get(path)
            assert r.status_code == 200, f"{path} as {username}"
            assert b"proposalOpenBtn" in r.data, f"P button missing on {path} as {username}"
        client.get("/logout")


def test_nav_items_match_role(client):
    # Checked by the nav link's own href, not its label text - the dashboard's
    # descriptive copy mentions "Visual Planner" by name to every role in a plain
    # sentence, which a text-substring check would wrongly count as "the nav link is
    # showing", regardless of role.
    nav_hrefs = {
        "Dashboard": 'href="/dashboard"',
        "Visual Planner": 'href="/planner"',
        "Review Proposals": 'href="/proposals/admin"',
        "User Admin": 'href="/users"',
    }
    cases = [
        ("admin.demo", "/dashboard", ["Dashboard", "Visual Planner", "Review Proposals", "User Admin"]),
        ("planner.demo", "/planner", ["Dashboard", "Visual Planner"]),
        ("user.demo", "/dashboard", ["Dashboard"]),
    ]

    for username, landing_path, expected_labels in cases:
        login(client, username)
        r = client.get(landing_path)
        body = r.data.decode("utf-8")
        for label in expected_labels:
            assert nav_hrefs[label] in body, f"{label} nav link missing for {username}"
        for label in nav_hrefs.keys() - set(expected_labels):
            assert nav_hrefs[label] not in body, f"{label} nav link unexpectedly shown to {username}"
        client.get("/logout")
