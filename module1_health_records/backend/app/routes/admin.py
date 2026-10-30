from flask import Blueprint, jsonify, request, g

from ..extensions import db
from datetime import date, datetime, timedelta, timezone

from ..models import AuditLog, User, Doctor
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

    user = User(name=name, email=email, role="doctor", must_change_password=True)
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
    user.token_version += 1  # also ends any session that is still open
    db.session.commit()
    log_action(g.current_user.id, "user_enabled" if user.is_active else "user_disabled",
               "user", user.id)
    return jsonify(user={"id": user.id, "is_active": user.is_active})


def _audit_payload(entry, users):
    actor = users.get(entry.user_id)
    return {
        "id": entry.id,
        "created_at": entry.created_at.isoformat() if entry.created_at else None,
        "user_id": entry.user_id,
        "user_name": actor.name if actor else None,
        "user_role": actor.role if actor else None,
        "action": entry.action,
        "target_type": entry.target_type,
        "target_id": entry.target_id,
        "detail": entry.detail,
        "ip_address": entry.ip_address,
    }


@bp.get("/audit-logs")
@role_required("admin")
def audit_logs():
    """Admin-only, read-only view of the audit trail (newest first).
    Filters: user_id, action, target_type, target_id, since, until (YYYY-MM-DD)."""
    query = AuditLog.query
    user_id = request.args.get("user_id", type=int)
    target_id = request.args.get("target_id", type=int)
    action = (request.args.get("action") or "").strip()
    target_type = (request.args.get("target_type") or "").strip()
    if user_id is not None:
        query = query.filter(AuditLog.user_id == user_id)
    if target_id is not None:
        query = query.filter(AuditLog.target_id == target_id)
    if action:
        query = query.filter(AuditLog.action == action)
    if target_type:
        query = query.filter(AuditLog.target_type == target_type)

    for name, op in (("since", "ge"), ("until", "lt")):
        raw = request.args.get(name)
        if raw:
            try:
                day = date.fromisoformat(raw)
            except ValueError:
                return jsonify(error=f"{name} must be YYYY-MM-DD."), 400
            start = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
            if name == "until":
                start += timedelta(days=1)  # until is inclusive of that whole day
            query = query.filter(AuditLog.created_at >= start if op == "ge" else AuditLog.created_at < start)

    page = max(request.args.get("page", 1, type=int), 1)
    per_page = min(max(request.args.get("per_page", 50, type=int), 1), 100)
    total = query.count()
    rows = (
        query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .offset((page - 1) * per_page).limit(per_page).all()
    )
    ids = {r.user_id for r in rows if r.user_id}
    users = {u.id: u for u in User.query.filter(User.id.in_(ids)).all()} if ids else {}
    return jsonify(logs=[_audit_payload(r, users) for r in rows],
                   page=page, per_page=per_page, total=total)


@bp.get("/audit-logs/actions")
@role_required("admin")
def audit_actions():
    rows = db.session.query(AuditLog.action).distinct().order_by(AuditLog.action).all()
    return jsonify(actions=[r[0] for r in rows])
