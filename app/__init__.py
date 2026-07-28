import os

from flask import Flask
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_socketio import SocketIO

from .config import DevelopmentConfig

# Extensions
db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
socketio = SocketIO(cors_allowed_origins="*")


def create_app(config_object=None):
    app = Flask(__name__, static_folder='../frontend', static_url_path='/')
    app.config.from_object(config_object or DevelopmentConfig)

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    socketio.init_app(app)

    # Register blueprints
    from .routes import api_bp
    app.register_blueprint(api_bp)

    # Register CLI commands
    try:
        from .cli import register_cli
        register_cli(app)
    except Exception:
        # CLI registration is optional for some environments
        pass

    # create a simple route to serve the demo frontend
    @app.route('/')
    def index():
        return app.send_static_file('index.html')

    return app
