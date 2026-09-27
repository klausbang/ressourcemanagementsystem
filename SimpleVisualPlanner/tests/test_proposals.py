from conftest import login


def test_submit_proposal_creates_row(client, app):
    login(client, "user.demo")
    r = client.post(
        "/proposals/new",
        data={
            "path": "/dashboard",
            "proposal_type": "enhancement",
            "title": "Test proposal",
            "description": "A description.",
        },
        follow_redirects=True,
    )
    assert r.status_code == 200

    from reusable_modules.database import get_db

    with app.app_context():
        row = get_db().execute(
            "SELECT * FROM proposals WHERE title = 'Test proposal'"
        ).fetchone()
    assert row is not None
    assert row["submitted_by_username"] == "user.demo"
    assert row["status"] == "new"


def test_submit_requires_title(client):
    login(client, "user.demo")
    r = client.post(
        "/proposals/new",
        data={"path": "/dashboard", "proposal_type": "bug", "title": ""},
        follow_redirects=True,
    )
    assert b"title is required" in r.data


def test_review_screen_denied_to_non_admin(client):
    login(client, "user.demo")
    r = client.get("/proposals/admin", follow_redirects=True)
    assert r.request.path == "/login"


def test_review_screen_allowed_to_admin(client):
    login(client, "admin.demo")
    r = client.get("/proposals/admin")
    assert r.status_code == 200


def test_update_proposal_persists_status_and_comment(client, app):
    login(client, "user.demo")
    client.post(
        "/proposals/new",
        data={"path": "/dashboard", "proposal_type": "bug", "title": "Fix me"},
        follow_redirects=True,
    )
    client.get("/logout")
    login(client, "admin.demo")

    from reusable_modules.database import get_db

    with app.app_context():
        proposal_id = get_db().execute(
            "SELECT id FROM proposals WHERE title = 'Fix me'"
        ).fetchone()["id"]

    r = client.post(
        "/proposals/admin",
        data={
            "action": "update_proposal",
            "proposal_id": str(proposal_id),
            "title": "Fix me",
            "description": "",
            "proposal_type": "bug",
            "status": "accepted",
            "admin_comment": "Looks good.",
        },
        follow_redirects=True,
    )
    assert r.status_code == 200

    with app.app_context():
        row = get_db().execute(
            "SELECT status, admin_comment, updated_at FROM proposals WHERE id = ?",
            (proposal_id,),
        ).fetchone()
    assert row["status"] == "accepted"
    assert row["admin_comment"] == "Looks good."
    assert row["updated_at"]


def test_delete_proposal(client, app):
    login(client, "user.demo")
    client.post(
        "/proposals/new",
        data={"path": "/dashboard", "proposal_type": "bug", "title": "Delete me"},
        follow_redirects=True,
    )
    client.get("/logout")
    login(client, "admin.demo")

    from reusable_modules.database import get_db

    with app.app_context():
        proposal_id = get_db().execute(
            "SELECT id FROM proposals WHERE title = 'Delete me'"
        ).fetchone()["id"]

    client.post(
        "/proposals/admin",
        data={"action": "delete_proposal", "proposal_id": str(proposal_id)},
        follow_redirects=True,
    )

    with app.app_context():
        row = get_db().execute(
            "SELECT 1 FROM proposals WHERE id = ?", (proposal_id,)
        ).fetchone()
    assert row is None


def test_count_pending_reflects_new_proposals(client, app):
    from reusable_modules.proposals import count_pending

    with app.app_context():
        assert count_pending() == 0

    login(client, "user.demo")
    client.post(
        "/proposals/new",
        data={"path": "/dashboard", "proposal_type": "bug", "title": "Pending one"},
        follow_redirects=True,
    )

    with app.app_context():
        assert count_pending() == 1


def test_nav_badge_shows_pending_count_to_admin(client):
    login(client, "user.demo")
    client.post(
        "/proposals/new",
        data={"path": "/dashboard", "proposal_type": "bug", "title": "Badge test"},
        follow_redirects=True,
    )
    client.get("/logout")
    login(client, "admin.demo")

    r = client.get("/dashboard")
    body = r.data.decode("utf-8")
    assert 'nav-badge">1<' in body
