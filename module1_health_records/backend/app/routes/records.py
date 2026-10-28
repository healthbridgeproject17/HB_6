from flask import Blueprint, g, jsonify, request

from ..extensions import db
from ..models import MedicalRecord
from ..utils.audit import log_action
from ..utils.decorators import role_required
from .patients import get_patient_or_error

bp = Blueprint("records", __name__)

RECORD_TYPES = ("diagnosis", "note", "visit")
ALL_ROLES = ("patient", "doctor", "admin")


def record_payload(r, superseded=False):
    return {
        "id": r.id,
        "patient_id": r.patient_id,
        "record_type": r.record_type,
        "title": r.title,
        "details": r.details,
        "doctor": r.doctor.user.name if r.doctor else None,
        "amended_from_id": r.amended_from_id,
        "amendment_reason": r.amendment_reason,
        "superseded": superseded,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


def superseded_ids(patient_id):
    rows = (
        db.session.query(MedicalRecord.amended_from_id)
        .filter(MedicalRecord.patient_id == patient_id, MedicalRecord.amended_from_id.isnot(None))
        .all()
    )
    return {r[0] for r in rows}


def validate_fields(body, *, require_title):
    title = body.get("title")
    details = body.get("details")
    if require_title or title is not None:
        title = (title or "").strip()
        if len(title) < 3 or len(title) > 200:
            return None, "Title must be 3-200 characters."
    if details is not None:
        details = str(details).strip()
        if len(details) > 5000:
            return None, "Details are too long (max 5000 characters)."
    return {"title": title, "details": details}, None


@bp.get("/patients/<int:patient_id>/records")
@role_required(*ALL_ROLES)
def list_records(patient_id):
    patient, err = get_patient_or_error(patient_id)
    if err:
        return err
    include_history = request.args.get("include_history") == "true"
    old = superseded_ids(patient.id)
    rows = (
        MedicalRecord.query.filter_by(patient_id=patient.id)
        .order_by(MedicalRecord.created_at.desc(), MedicalRecord.id.desc())
        .all()
    )
    if not include_history:
        rows = [r for r in rows if r.id not in old]
    if g.current_user.role != "patient":
        log_action(g.current_user.id, "records_viewed", "patient", patient.id)
    return jsonify(records=[record_payload(r, r.id in old) for r in rows])


@bp.post("/patients/<int:patient_id>/records")
@role_required("doctor")
def create_record(patient_id):
    patient, err = get_patient_or_error(patient_id, write=False)
    if err:
        return err
    body = request.get_json(silent=True) or {}
    record_type = (body.get("record_type") or "note").strip().lower()
    if record_type not in RECORD_TYPES:
        return jsonify(error="record_type must be diagnosis, note or visit."), 400
    fields, error = validate_fields(body, require_title=True)
    if error:
        return jsonify(error=error), 400

    record = MedicalRecord(
        patient_id=patient.id,
        doctor_id=g.current_user.doctor.id,
        record_type=record_type,
        title=fields["title"],
        details=fields["details"],
        created_by_user_id=g.current_user.id,
    )
    db.session.add(record)
    db.session.commit()
    log_action(g.current_user.id, "record_created", "medical_record", record.id,
               detail=f"patient={patient.id} type={record_type}")
    return jsonify(record=record_payload(record)), 201


@bp.post("/records/<int:record_id>/amend")
@role_required("doctor", "admin")
def amend_record(record_id):
    """Corrections are NEW rows that point at the original. The original is
    never edited or deleted, so the full history stays traceable."""
    original = db.session.get(MedicalRecord, record_id)
    if original is None:
        return jsonify(error="Record not found."), 404
    if record_id in superseded_ids(original.patient_id):
        return jsonify(error="This record was already amended. Amend the latest version."), 409

    body = request.get_json(silent=True) or {}
    reason = (body.get("reason") or "").strip()
    if len(reason) < 5 or len(reason) > 500:
        return jsonify(error="Give a reason for the amendment (5-500 characters)."), 400
    fields, error = validate_fields(body, require_title=False)
    if error:
        return jsonify(error=error), 400
    if fields["title"] is None and fields["details"] is None:
        return jsonify(error="Provide a new title and/or details."), 400

    user = g.current_user
    amended = MedicalRecord(
        patient_id=original.patient_id,
        doctor_id=user.doctor.id if user.role == "doctor" else original.doctor_id,
        record_type=original.record_type,
        title=fields["title"] if fields["title"] is not None else original.title,
        details=fields["details"] if fields["details"] is not None else original.details,
        amended_from_id=original.id,
        created_by_user_id=user.id,
        amendment_reason=reason,
    )
    db.session.add(amended)
    db.session.commit()
    log_action(user.id, "record_amended", "medical_record", amended.id,
               detail=f"from={original.id} by={user.role} reason={reason}")
    return jsonify(record=record_payload(amended)), 201


@bp.get("/records/<int:record_id>/history")
@role_required(*ALL_ROLES)
def record_history(record_id):
    record = db.session.get(MedicalRecord, record_id)
    if record is None:
        # patients get the same answer for missing and foreign ids
        if g.current_user.role == "patient":
            return jsonify(error="You do not have permission for this action."), 403
        return jsonify(error="Record not found."), 404
    patient, err = get_patient_or_error(record.patient_id)
    if err:
        return err

    by_id = {r.id: r for r in MedicalRecord.query.filter_by(patient_id=patient.id).all()}
    children = {r.amended_from_id: r for r in by_id.values() if r.amended_from_id}
    head = record
    while head.amended_from_id:
        head = by_id[head.amended_from_id]
    chain = [head]
    while chain[-1].id in children:
        chain.append(children[chain[-1].id])
    if g.current_user.role != "patient":
        log_action(g.current_user.id, "record_history_viewed", "medical_record", record.id)
    return jsonify(history=[record_payload(r, r is not chain[-1]) for r in chain])
