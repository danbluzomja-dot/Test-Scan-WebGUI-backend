import click
from flask import Flask, jsonify

from .extensions import db
from flask_migrate import Migrate

migrate = Migrate()


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY="development-only-change-me",
        BADGE_HASH_KEY="development-badge-key-change-me",
        SQLALCHEMY_DATABASE_URI="sqlite:///production.db",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )
    app.config.from_prefixed_env()
    if test_config: app.config.update(test_config)
    db.init_app(app)
    migrate.init_app(app, db)
    from .api import bp as api_bp
    from .auth import bp as auth_bp
    from .web import bp as web_bp
    app.register_blueprint(auth_bp); app.register_blueprint(api_bp); app.register_blueprint(web_bp)

    @app.get("/health")
    def health(): return jsonify(status="ok")

    @app.cli.command("init-db")
    def init_db():
        db.create_all(); click.echo("Database initialized.")

    @app.cli.command("seed-demo")
    def seed_demo():
        from .api import badge_digest
        from .models import Application, User, Workflow
        db.create_all()
        if User.query.filter_by(username="admin").first():
            click.echo("Demo data already exists."); return
        app_row = Application(key="demo", name="Demo Production Line")
        admin = User(username="admin", role="admin", badge_hash=badge_digest("ADMIN-001")); admin.set_password("change-me")
        workflow = Workflow(application=app_row, name="Demo Assembly", published=True, definition={"steps": [
            {"key": "assembly", "name": "Assembly", "station_key": "STATION-1", "form_schema": {"notes": {"type": "text"}}},
            {"key": "qc", "name": "Final QC", "station_key": "QC-1", "form_schema": {"passed": {"type": "boolean", "required": True}}, "hardware_schema": {"torque": {"unit": "Nm"}}}
        ]})
        admin.applications.append(app_row); db.session.add_all([app_row, admin, workflow]); db.session.commit()
        click.echo("Created admin/change-me, badge ADMIN-001, and demo workflow.")
    return app
