from conftest import login


def test_login_page_loads(client):
    r = client.get("/login")
    assert r.status_code == 200
    assert b"Username" in r.data


def test_unknown_username_rejected(client):
    r = login(client, "nobody.here")
    assert r.status_code == 200
    assert b"Unknown user" in r.data


def test_admin_lands_on_dashboard(client):
    r = login(client, "admin.demo")
    assert r.status_code == 200
    assert r.request.path == "/dashboard"


def test_user_lands_on_dashboard(client):
    r = login(client, "user.demo")
    assert r.request.path == "/dashboard"


def test_planner_lands_on_visual_planner(client):
    """role_home_endpoints routes "planner" straight to their own tool, not the
    generic dashboard - see app/__init__.py."""
    r = login(client, "planner.demo")
    assert r.request.path == "/planner"


def test_logout_clears_session(client):
    login(client, "admin.demo")
    client.get("/logout")
    r = client.get("/dashboard", follow_redirects=True)
    assert r.request.path == "/login"
