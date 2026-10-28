from flask import Blueprint, jsonify, request, g
from flask_jwt_extended import create_access_token

from ..extensions import db
from ..models import User, Patient
from ..utils.audit import log_action
from ..utils.decorators import role_required
from ..utils.health_id import generate_health_id
from ..utils.validators import SEXES, clean_email, parse_dob, password_problem

bp = Blueprint("auth", __name__)


def user_payload(user):
    data = {"id": user.id, "name": user.name, "email": user.email, "role": user.role}
    if user.role == "patient" and user.patient:
        data["health_id"] = user.patient.health_id
    return data


def issue_token(user):
    return create_access_token(identity=str(user.id), additional_claims={"role": user.role})


@bp.post("/register")
def register():
    """Public registration. Always creates a PATIENT. Doctors and admins can
    never be created here (role in the request body is ignored)."""
    body = request.get_json(silent=True) or {}

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
    return jsonify(access_token=issue_token(user), user=user_payload(user)), 201


@bp.post("/login")
def login():
    """Login for all roles. Optional 'portal' (patient/doctor/admin) makes the
    separate login pages refuse accounts of a different role."""
    body = request.get_json(silent=True) or {}
    email = clean_email(body.get("email"))
    password = body.get("password") or ""
    portal = (body.get("portal") or "").strip().lower() or None

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

    log_action(user.id, "login", "user", user.id)
    return jsonify(access_token=issue_token(user), user=user_payload(user))


@bp.get("/me")
@role_required("patient", "doctor", "admin")
def me():
    return jsonify(user=user_payload(g.current_user))
