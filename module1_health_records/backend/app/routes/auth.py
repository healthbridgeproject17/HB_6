from datetime import datetime, timedelta, timezone

from flask import Blueprint, current_app, g, jsonify, request
from flask_jwt_extended import create_access_token, set_access_cookies, unset_jwt_cookies

from ..extensions import db
from ..models import AuditLog, Patient, User
from ..utils import second_factor as sf
from ..utils.audit import log_action
from ..utils.decorators import role_required
from ..utils.health_id import generate_health_id
from ..utils.validators import SEXES, clean_email, parse_dob, password_problem

bp = Blueprint("auth", __name__)


def user_payload(user):
    data = {"id": user.id, "name": user.name, "email": user.email, "role": user.role,
            "must_change_password": user.must_change_password, "two_factor_enabled": bool(user.totp_enabled)}
    if user.role == "patient" and user.patient:
        data["health_id"] = user.patient.health_id
    return data


def issue_token(user):
    return create_access_token(
        identity=str(user.id), additional_claims={"role": user.role, "tv": user.token_version}
    )


def session_response(user, status=200):
    """The website sends 'X-Auth-Mode: cookie': it then gets the login as an HttpOnly cookie and
    never sees the token. Other callers (tests, tools) get the token in the reply as before."""
    token = issue_token(user)
    if request.headers.get("X-Auth-Mode") == "cookie":
        response = jsonify(user=user_payload(user))
        set_access_cookies(response, token)
    else:
        response = jsonify(access_token=token, user=user_payload(user))
    response.status_code = status
    return response


def _since(**delta):
    return datetime.now(timezone.utc) - timedelta(**delta)


def login_locked(email):
    """Too many wrong passwords for this email recently? (counted from the audit log)"""
    limit = current_app.config["LOGIN_MAX_FAILURES"]
    minutes = current_app.config["LOGIN_LOCK_MINUTES"]
    failures = AuditLog.query.filter(
        AuditLog.action == "login_failed",
        AuditLog.detail == f"email={email}",
        AuditLog.created_at >= _since(minutes=minutes),
    ).count()
    return failures >= limit


@bp.post("/register")
def register():
    """Public registration. Always creates a PATIENT. Doctors and admins can
    never be created here (role in the request body is ignored)."""
    body = request.get_json(silent=True) or {}

    recent = AuditLog.query.filter(
        AuditLog.action == "register",
        AuditLog.ip_address == (request.remote_addr or ""),
        AuditLog.created_at >= _since(hours=1),
    ).count()
    if recent >= current_app.config["REGISTER_MAX_PER_IP_HOUR"]:
        return jsonify(error="Too many sign-ups from this network. Try again later."), 429

    name = (body.get("name") or "").strip()
    email = clean_email(body.get("email"))
    password = body.get("password")
    sex = (body.get("sex") or "").strip().lower() or None
    phone = (body.get("phone") or "").strip()[:30] or None

    if len(name) < 2 or len(name) > 120:
        return jsonify(error="Name must be 2-120 characters."), 400
    if not email:
        return jsonify(error="Enter a valid email address."), 400
    problem = password_problem(password)
    if problem:
        return jsonify(error=problem), 400
    if sex and sex not in SEXES:
        return jsonify(error="Sex must be male, female or other."), 400
    dob, dob_error = parse_dob(body.get("dob"))
    if dob_error:
        return jsonify(error=dob_error), 400

    if User.query.filter_by(email=email).first():
        return jsonify(error="An account with this email already exists."), 409

    user = User(name=name, email=email, role="patient")
    user.set_password(password)
    db.session.add(user)
    db.session.flush()
    patient = Patient(
        user_id=user.id, health_id=generate_health_id(), dob=dob, sex=sex, phone=phone
    )
    db.session.add(patient)
    db.session.commit()

    log_action(user.id, "register", "user", user.id)
    return session_response(user, 201)


@bp.post("/login")
def login():
    """Login for all roles. Optional 'portal' (patient/doctor/admin) makes the
    separate login pages refuse accounts of a different role."""
    body = request.get_json(silent=True) or {}
    email = clean_email(body.get("email"))
    password = body.get("password") or ""
    portal = (body.get("portal") or "").strip().lower() or None

    if email and login_locked(email):
        return jsonify(error="Too many failed attempts. Try again in "
                             f"{current_app.config['LOGIN_LOCK_MINUTES']} minutes."), 429

    user = User.query.filter_by(email=email).first() if email else None
    if user is None or not user.check_password(password):
        log_action(user.id if user else None, "login_failed", "user", user.id if user else None,
                   detail=f"email={email}")
        return jsonify(error="Invalid email or password."), 401
    if not user.is_active:
        return jsonify(error="This account has been disabled."), 403
    if portal and portal != user.role:
        log_action(user.id, "login_wrong_portal", "user", user.id, detail=f"portal={portal}")
        return jsonify(error="Invalid email or password."), 401

    if user.totp_enabled:
        # password was right; the account also needs its second step before any login is issued
        return jsonify(mfa_required=True, ticket=sf.make_ticket(user))

    log_action(user.id, "login", "user", user.id)
    return session_response(user)


@bp.post("/login/2fa")
def login_second_step():
    """Second step: the ticket from /login plus a 6-digit code (or a backup code)."""
    body = request.get_json(silent=True) or {}
    data = sf.read_ticket(body.get("ticket"))
    user = db.session.get(User, data["uid"]) if data else None
    if user is None or not user.totp_enabled or user.token_version != data["tv"]:
        return jsonify(error="That sign-in step expired. Enter your password again."), 401
    if login_locked(user.email):
        return jsonify(error="Too many failed attempts. Try again in "
                             f"{current_app.config['LOGIN_LOCK_MINUTES']} minutes."), 429
    if not user.is_active:
        return jsonify(error="This account has been disabled."), 403
    if not sf.check_code(user, body.get("code")):
        db.session.rollback()
        log_action(user.id, "login_failed", "user", user.id, detail=f"email={user.email}")
        return jsonify(error="That code is not right."), 401
    db.session.commit()
    log_action(user.id, "login", "user", user.id, detail="two-factor")
    return session_response(user)


@bp.get("/me")
@role_required("patient", "doctor", "admin", allow_pending_password=True)
def me():
    return jsonify(user=user_payload(g.current_user))


@bp.post("/change-password")
@role_required("patient", "doctor", "admin", allow_pending_password=True)
def change_password():
    """Change your own password. All older login tokens stop working and a
    fresh one is returned so this session carries on."""
    user = g.current_user
    body = request.get_json(silent=True) or {}
    current = body.get("current_password") or ""
    new = body.get("new_password")
    if not user.check_password(current):
        log_action(user.id, "password_change_failed", "user", user.id)
        return jsonify(error="Your current password is incorrect."), 400
    problem = password_problem(new)
    if problem:
        return jsonify(error=problem), 400
    if new == current:
        return jsonify(error="Choose a password different from the current one."), 400
    user.set_password(new)
    user.must_change_password = False
    user.token_version += 1
    db.session.commit()
    log_action(user.id, "password_changed", "user", user.id)
    return session_response(user)


@bp.post("/logout")
@role_required("patient", "doctor", "admin", allow_pending_password=True)
def logout():
    """Ends every login session of this account (all devices)."""
    user = g.current_user
    user.token_version += 1
    db.session.commit()
    log_action(user.id, "logout", "user", user.id)
    response = jsonify(ok=True)
    unset_jwt_cookies(response)
    return response


@bp.post("/session/clear")
def clear_session():
    """Removes the login cookies from this browser (used when a session has already expired)."""
    response = jsonify(ok=True)
    unset_jwt_cookies(response)
    return response
