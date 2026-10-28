from flask import Flask
from flask_cors import CORS

from .config import Config
from .extensions import db, jwt, migrate


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    CORS(app, resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}})

    db.init_app(app)
    jwt.init_app(app)
    migrate.init_app(app, db)

    from . import models  # noqa: F401  (registers tables with SQLAlchemy)
    from .routes.health import bp as health_bp
    app.register_blueprint(health_bp, url_prefix="/api/v1")

    from .routes.auth import bp as auth_bp
    from .routes.admin import bp as admin_bp
    app.register_blueprint(auth_bp, url_prefix="/api/v1/auth")
    app.register_blueprint(admin_bp, url_prefix="/api/v1/admin")

    from .routes.patients import bp as patients_bp
    app.register_blueprint(patients_bp, url_prefix="/api/v1/patients")

    from flask import jsonify

    @app.errorhandler(413)
    def too_large(_):
        return jsonify(error="File is too large."), 413

    from .cli import register_cli
    register_cli(app)

    return app
