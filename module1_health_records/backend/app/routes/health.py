from flask import Blueprint, current_app, jsonify
from sqlalchemy import text

from ..extensions import db

bp = Blueprint("health", __name__)


@bp.get("/health")
def health():
    return jsonify(status="ok", service="healthbridge-api")


@bp.get("/health/db")
def health_db():
    try:
        db.session.execute(text("SELECT 1"))
        return jsonify(status="ok", database="connected")
    except Exception as exc:
        # the reason goes to the server log only; the error text can contain the database address
        current_app.logger.warning("Database health check failed: %s", exc)
        return jsonify(status="error", database="unreachable"), 500
