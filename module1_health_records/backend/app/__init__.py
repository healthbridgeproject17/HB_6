from flask import Flask
from flask_cors import CORS

from .config import Config
from .extensions import db, jwt, migrate


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    _check_production_settings(app)

    CORS(app, resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}}, supports_credentials=True)

    db.init_app(app)
    jwt.init_app(app)
    migrate.init_app(app, db)

    from . import models  # noqa: F401  (registers tables with SQLAlchemy)
    from .routes.health import bp as health_bp
    app.register_blueprint(health_bp, url_prefix="/api/v1")

    from .routes.auth import bp as auth_bp
    from .routes.admin import bp as admin_bp
    app.register_blueprint(auth_bp, url_prefix="/api/v1/auth")
    from .routes.twofactor import bp as twofactor_bp
    app.register_blueprint(twofactor_bp, url_prefix="/api/v1/auth")
    from .routes.password_reset import bp as password_reset_bp
    app.register_blueprint(password_reset_bp, url_prefix="/api/v1/auth")
    app.register_blueprint(admin_bp, url_prefix="/api/v1/admin")

    from .routes.patients import bp as patients_bp
    app.register_blueprint(patients_bp, url_prefix="/api/v1/patients")

    from .routes.records import bp as records_bp
    from .routes.prescriptions import bp as prescriptions_bp
    app.register_blueprint(records_bp, url_prefix="/api/v1")
    app.register_blueprint(prescriptions_bp, url_prefix="/api/v1")

    from .routes.medication import bp as medication_bp
    app.register_blueprint(medication_bp, url_prefix="/api/v1")

    from .routes.documents import bp as documents_bp
    app.register_blueprint(documents_bp, url_prefix="/api/v1")

    from .routes.analysis import bp as analysis_bp
    app.register_blueprint(analysis_bp, url_prefix="/api/v1")

    from .routes.security import bp as security_bp
    app.register_blueprint(security_bp, url_prefix="/api/v1")

    from flask import jsonify

    @app.errorhandler(413)
    def too_large(_):
        return jsonify(error="File is too large."), 413

    @app.errorhandler(404)
    def not_found(_):
        return jsonify(error="Not found."), 404

    @app.errorhandler(405)
    def not_allowed(_):
        return jsonify(error="Method not allowed."), 405

    @app.errorhandler(500)
    def server_error(exc):
        # details go to the server log only, never to the browser
        app.logger.exception("Unhandled error: %s", exc)
        return jsonify(error="Something went wrong on the server."), 500

    @app.after_request
    def security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=()")
        # patient data must never sit in a shared cache
        response.headers["Cache-Control"] = "no-store"
        if app.config["ENV_NAME"] == "production":
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response

    from .cli import register_cli
    register_cli(app)

    return app


def _check_production_settings(app):
    """In production, refuse to start with weak or default secrets."""
    cfg = app.config
    if cfg["ENV_NAME"] != "production":
        return
    problems = []
    for key in ("SECRET_KEY", "JWT_SECRET_KEY", "DOCUMENT_ENCRYPTION_KEY"):
        value = cfg.get(key) or ""
        if len(value) < 32 or value.startswith("dev-") or value.startswith("change-this"):
            problems.append(f"{key} must be a random value of at least 32 characters")
    if cfg["SQLALCHEMY_DATABASE_URI"].startswith("sqlite"):
        problems.append("DATABASE_URL must point to PostgreSQL (NeonDB)")
    if "*" in cfg["CORS_ORIGINS"]:
        problems.append("CORS_ORIGINS must list your real website address, not *")
    if problems:
        raise RuntimeError("Unsafe production configuration: " + "; ".join(problems))
