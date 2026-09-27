from conftest import login


def test_denied_to_non_admin(client):
    login(client, "user.demo")
    r = client.get("/users", follow_redirects=True)
    assert r.request.path == "/login"


def test_lists_seeded_demo_users(client):
    login(client, "admin.demo")
    r = client.get("/users")
    assert r.status_code == 200
    body = r.data.decode("utf-8")
    for username in ("admin.demo", "user.demo", "planner.demo"):
        assert username in body


def test_create_user(client, app):
    login(client, "admin.demo")
    r = client.post(
        "/users",
        data={"action": "create_user", "username": "newplanner", "role": "planner"},
        follow_redirects=True,
    )
    assert b"newplanner" in r.data

    from reusable_modules.database import get_db

    with app.app_context():
        row = get_db().execute(
            "SELECT role FROM users WHERE username = 'newplanner'"
        ).fetchone()
    assert row["role"] == "planner"


def test_duplicate_username_rejected(client):
    login(client, "admin.demo")
    client.post(
        "/users",
        data={"action": "create_user", "username": "dup", "role": "user"},
        follow_redirects=True,
    )
    r = client.post(
        "/users",
        data={"action": "create_user", "username": "dup", "role": "user"},
        follow_redirects=True,
    )
    assert b"already taken" in r.data


def test_update_user_renames_and_reassigns_role(client, app):
    login(client, "admin.demo")
    client.post(
        "/users",
        data={"action": "create_user", "username": "temp", "role": "user"},
        follow_redirects=True,
    )

    from reusable_modules.database import get_db

    with app.app_context():
        user_id = get_db().execute(
            "SELECT id FROM users WHERE username = 'temp'"
        ).fetchone()["id"]

    client.post(
        "/users",
        data={
            "action": "update_user",
            "user_id": str(user_id),
            "username": "renamed",
            "role": "planner",
        },
        follow_redirects=True,
    )

    with app.app_context():
        row = get_db().execute(
            "SELECT username, role FROM users WHERE id = ?", (user_id,)
        ).fetchone()
    assert (row["username"], row["role"]) == ("renamed", "planner")


def test_cannot_delete_own_account(client, app):
    login(client, "admin.demo")

    from reusable_modules.database import get_db

    with client.session_transaction() as sess:
        admin_id = sess["user_id"]

    r = client.post(
        "/users",
        data={"action": "delete_user", "user_id": str(admin_id)},
        follow_redirects=True,
    )
    assert b"delete your own account" in r.data

    with app.app_context():
        still_there = get_db().execute(
            "SELECT 1 FROM users WHERE id = ?", (admin_id,)
        ).fetchone()
    assert still_there is not None


def test_delete_user(client, app):
    login(client, "admin.demo")
    client.post(
        "/users",
        data={"action": "create_user", "username": "todelete", "role": "user"},
        follow_redirects=True,
    )

    from reusable_modules.database import get_db

    with app.app_context():
        user_id = get_db().execute(
            "SELECT id FROM users WHERE username = 'todelete'"
        ).fetchone()["id"]

    client.post(
        "/users",
        data={"action": "delete_user", "user_id": str(user_id)},
        follow_redirects=True,
    )

    with app.app_context():
        row = get_db().execute("SELECT 1 FROM users WHERE id = ?", (user_id,)).fetchone()
    assert row is None
