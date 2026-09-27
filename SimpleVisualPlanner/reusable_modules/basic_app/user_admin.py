"""Optional CRUD screen for basic_app's own `users` table (list/add/edit/delete a user,
assign one of the configured roles) - opt-in via enable_user_admin(app, ...), since not
every consuming app wants user management exposed as its own screen (an app whose
user_lookup isn't even backed by this table, for instance, has nothing for this screen
to manage).

Routes are added directly to the Flask app object (app.add_url_rule), not to the `auth`
blueprint, because enable_user_admin() runs after create_app() has already registered
that blueprint - adding a brand-new route to an already-registered blueprint object
would not take effect on that app instance.
"""
from flask import Flask, current_app, flash, redirect, request, session, url_for

from reusable_modules.database import get_db

from .auth import current_role
from .ui import render_ui


def _manager_role() -> str:
    return current_app.config.get("BASIC_APP_USER_ADMIN_MANAGER_ROLE", "admin")


def _allowed_roles() -> tuple:
    return current_app.config.get("BASIC_APP_USER_ADMIN_ROLES", ())


def _deny(required_role: str):
    flash(f"Access denied. Required role: {required_role}.", "error")
    return redirect(url_for("auth.login"))


def _user_admin_view():
    manager_role = _manager_role()
    if current_role() != manager_role:
        return _deny(manager_role)

    db = get_db()
    allowed_roles = _allowed_roles()

    if request.method == "POST":
        action = request.form.get("action", "")

        if action == "create_user":
            username = request.form.get("username", "").strip()
            role = request.form.get("role", "").strip()
            if not username or role not in allowed_roles:
                flash("A username and a valid role are required.", "error")
            elif db.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone():
                flash(f'Username "{username}" is already taken.', "error")
            else:
                db.execute("INSERT INTO users (username, role) VALUES (?, ?)", (username, role))
                db.commit()
                flash(f'User "{username}" created.', "info")

        elif action == "update_user":
            user_id = request.form.get("user_id", "").strip()
            username = request.form.get("username", "").strip()
            role = request.form.get("role", "").strip()
            if not (user_id and username and role in allowed_roles):
                flash("A username and a valid role are required.", "error")
            elif db.execute(
                "SELECT 1 FROM users WHERE username = ? AND id != ?", (username, user_id)
            ).fetchone():
                flash(f'Username "{username}" is already taken.', "error")
            else:
                db.execute("UPDATE users SET username = ?, role = ? WHERE id = ?", (username, role, user_id))
                db.commit()
                # Keep the current session in sync if a manager edits their own account,
                # so the topbar/role-gated nav doesn't show stale data until next login.
                if str(session.get("user_id")) == user_id:
                    session["username"] = username
                    session["role"] = role
                flash("User updated.", "info")

        elif action == "delete_user":
            user_id = request.form.get("user_id", "").strip()
            if user_id and str(session.get("user_id")) == user_id:
                flash("You can't delete your own account while signed in as it.", "error")
            else:
                db.execute("DELETE FROM users WHERE id = ?", (user_id,))
                db.commit()
                flash("User deleted.", "info")

        return redirect(url_for("user_admin"))

    users = [dict(r) for r in db.execute("SELECT id, username, role FROM users ORDER BY username").fetchall()]
    return render_ui("basic_app/user_admin.html", users=users, allowed_roles=allowed_roles)


def enable_user_admin(
    app: Flask,
    manager_role: str = "admin",
    roles: tuple[str, ...] = (),
) -> None:
    """Turn on the user-management screen at GET/POST /users (endpoint name
    "user_admin"), restricted to `manager_role`.

    - manager_role: the single role allowed to see/act on this screen (default: "admin").
    - roles: the roles a manager may assign to a user via the dropdown (default: whatever
      "roles" was passed to basic_app.create_app(), i.e. app.config["BASIC_APP_ROLES"]).

    Call any time after basic_app.create_app() - order relative to init_db()/other
    modules doesn't matter, since this only adds a route, not a schema fragment (the
    `users` table is already registered by basic_app itself).
    """
    app.config["BASIC_APP_USER_ADMIN_MANAGER_ROLE"] = manager_role
    app.config["BASIC_APP_USER_ADMIN_ROLES"] = tuple(roles) or tuple(app.config.get("BASIC_APP_ROLES", ()))
    app.add_url_rule("/users", endpoint="user_admin", view_func=_user_admin_view, methods=["GET", "POST"])
