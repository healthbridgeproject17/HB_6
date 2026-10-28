from flask import Blueprint, jsonify, request, g

from ..extensions import db
from ..models import User, Doctor
from ..utils.audit import log_action
from ..utils.decorators import role_required
from ..utils.validators import clean_email, password_problem

bp = Blueprint("admin", __name__)


@bp.post("/doctors")
@role_required("admin")
def create_doctor():
    body = request.get_json(silent=True) or {}
    name = (body.get("name") or "").strip()
    email = clean_email(body.get("email"))
    password = body.get("password")
    specialty = (body.get("specialty") or "").strip()[:120] or None
    license_no = (body.get("license_no") or "").strip()[:60] or None

    if len(name) < 2 or len(name) > 120:
        return jsonify(error="Name must be 2-120 characters."), 400
    if not email:
        return jsonify(error="Enter a valid email address."), 400
    problem = password_problem(password)
    if problem:
        return jsonify(error=problem), 400
    if User.query.filter_by(email=email).first():
        return jsonify(error="An account with this email already exists."), 409

    user = User(name=name, email=email, role="doctor")
    user.set_password(password)
    db.session.add(user)
    db.session.flush()
    db.session.add(Doctor(user_id=user.id, specialty=specialty, license_no=license_no))
    db.session.commit()

    log_action(g.current_user.id, "doctor_created", "user", user.id, detail=email)
    return jsonify(user={"id": user.id, "name": user.name, "email": user.email,
                         "role": "doctor", "specialty": specialty}), 201


@bp.get("/users")
@role_required("admin")
def list_users():
    role = request.args.get("role")
    query = User.query
    if role in ("patient", "doctor", "admin"):
        query = query.filter_by(role=role)
    users = query.order_by(User.id).all()
    return jsonify(users=[
        {"id": u.id, "name": u.name, "email": u.email, "role": u.role, "is_active": u.is_active}
        for u in users
    ])


@bp.patch("/users/<int:user_id>/active")
@role_required("admin")
def set_active(user_id):
    body = request.get_json(silent=True) or {}
    if not isinstance(body.get("is_active"), bool):
        return jsonify(error="is_active must be true or false."), 400
    user = db.session.get(User, user_id)
    if user is None:
        return jsonify(error="User not found."), 404
    if user.id == g.current_user.id:
        return jsonify(error="You cannot disable your own account."), 400
    user.is_active = body["is_active"]
    db.session.commit()
    log_action(g.current_user.id, "user_enabled" if user.is_active else "user_disabled",
               "user", user.id)
    return jsonify(user={"id": user.id, "is_active": user.is_active})
