import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from flask import Blueprint, current_app, jsonify, request

from ..extensions import db
from ..models import AuditLog, PasswordResetToken, User
from ..utils.audit import log_action
from ..utils.mailer import send_email
from ..utils.validators import clean_email, password_problem

bp = Blueprint("password_reset", __name__)

GENERIC = "If that email belongs to an account, a reset link has been sent. It works for {minutes} minutes."


def _hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def _now():
    return datetime.now(timezone.utc)


def _expired(record):
    when = record.expires_at
    if when.tzinfo is None:            # SQLite (tests) returns times without a zone
        when = when.replace(tzinfo=timezone.utc)
    return when < _now()


def _count(action, hours=1, **filters):
    q = AuditLog.query.filter(AuditLog.action == action, AuditLog.created_at >= _now() - timedelta(hours=hours))
    for column, value in filters.items():
        q = q.filter(getattr(AuditLog, column) == value)
    return q.count()


@bp.post("/password-reset/request")
def request_reset():
    """Always answers the same way, whether or not the email has an account."""
    body = request.get_json(silent=True) or {}
    email = clean_email(body.get("email"))
    cfg = current_app.config
    message = GENERIC.format(minutes=cfg["RESET_TOKEN_MINUTES"])
    ip = (request.remote_addr or "")[:45]

    if not email:
        return jsonify(error="Enter a valid email address."), 400
    if _count("password_reset_requested", ip_address=ip) >= cfg["RESET_MAX_PER_IP_HOUR"] or \
            _count("password_reset_requested", detail=f"email={email}") >= cfg["RESET_MAX_PER_EMAIL_HOUR"]:
        return jsonify(error="Too many reset requests. Try again later."), 429

    user = User.query.filter_by(email=email).first()
    log_action(user.id if user else None, "password_reset_requested", "user", user.id if user else None,
               detail=f"email={email}")
    if user is None or not user.is_active:
        return jsonify(message=message)

    for old in PasswordResetToken.query.filter_by(user_id=user.id, used_at=None):
        old.used_at = _now()          # only the newest link works
    token = secrets.token_urlsafe(32)
    db.session.add(PasswordResetToken(user_id=user.id, token_hash=_hash(token),
                                      expires_at=_now() + timedelta(minutes=cfg["RESET_TOKEN_MINUTES"])))
    db.session.commit()

    link = f"{cfg['FRONTEND_URL']}/reset-password?token={token}"
    send_email(user.email, "Reset your HealthBridge password",
               f"Hello {user.name},\n\nSomeone asked to reset the password of your HealthBridge account. "
               f"Open this link to choose a new password (valid {cfg['RESET_TOKEN_MINUTES']} minutes, one use):\n\n{link}\n\n"
               "If this was not you, ignore this email: your password stays the same.")
    return jsonify(message=message)


@bp.post("/password-reset/confirm")
def confirm_reset():
    body = request.get_json(silent=True) or {}
    ip = (request.remote_addr or "")[:45]
    if _count("password_reset_failed", ip_address=ip) >= current_app.config["RESET_MAX_PER_IP_HOUR"]:
        return jsonify(error="Too many attempts. Try again later."), 429

    token = (body.get("token") or "").strip()
    record = PasswordResetToken.query.filter_by(token_hash=_hash(token)).first() if token else None
    user = db.session.get(User, record.user_id) if record else None
    if record is None or record.used_at is not None or _expired(record) or user is None or not user.is_active:
        log_action(None, "password_reset_failed", "user", None)
        return jsonify(error="This reset link is invalid or has expired. Ask for a new one."), 400

    problem = password_problem(body.get("new_password"))
    if problem:
        return jsonify(error=problem), 400

    user.set_password(body["new_password"])
    user.must_change_password = False
    user.token_version += 1            # signs out every existing session
    record.used_at = _now()
    for other in PasswordResetToken.query.filter_by(user_id=user.id, used_at=None):
        other.used_at = _now()
    db.session.commit()
    log_action(user.id, "password_reset_done", "user", user.id)
    return jsonify(ok=True)
