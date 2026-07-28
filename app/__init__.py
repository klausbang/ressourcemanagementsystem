from flask import Flask

from .db import close_db, init_db, init_demo_seed
from .routes_common import bp as common_bp
from .routes_admin import bp as admin_bp
from .routes_planner import bp as planner_bp
from .routes_technician import bp as technician_bp
from .routes_reports import bp as reports_bp


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "dev-secret-change-me"
    app.config["DATABASE"] = "rms.db"

    app.teardown_appcontext(close_db)

    app.register_blueprint(common_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(planner_bp)
    app.register_blueprint(technician_bp)
    app.register_blueprint(reports_bp)

    with app.app_context():
        init_db()
        init_demo_seed()

    @app.cli.command("init-db")
    def init_db_command() -> None:
        init_db()
        print("Database initialized.")

    @app.cli.command("seed-demo")
    def seed_demo_command() -> None:
        init_db()
        init_demo_seed()
        print("Demo data seeded.")

    return app
