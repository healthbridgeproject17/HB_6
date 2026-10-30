import os

from flask import Blueprint, Response, current_app, g, jsonify, request

from ..extensions import db
from ..models import Patient, User
from ..utils.audit import log_action
from ..utils.crypto import decrypt_bytes
from ..utils.decorators import role_required
from ..utils.photos import PhotoError, delete_photo, process_photo, save_photo
from ..utils.validators import SEXES, clean_phone, parse_dob

bp = Blueprint("patients", __name__)

ALL_ROLES = ("patient", "doctor", "admin")


def patient_payload(p):
    return {
        "id": p.id,
        "health_id": p.health_id,
        "name": p.user.name,
        "email": p.user.email,
        "dob": p.dob.isoformat() if p.dob else None,
        "sex": p.sex,
        "phone": p.phone,
        "emergency_contact": p.emergency_contact,
        "allergies": p.allergies,
        "has_photo": bool(p.photo_path),
    }


def get_patient_or_error(patient_id, *, write=False):
    """Load a patient and enforce who may see (or change) them.

    Patient: only their own profile. Doctor: view any, change none.
    Admin: view and change any. Returns (patient, error_response)."""
    patient = db.session.get(Patient, patient_id)
    user = g.current_user
    if user.role == "patient":
        # 403 for other patients' ids, same answer whether or not the id exists
        if patient is None or patient.user_id != user.id:
            return None, (jsonify(error="You do not have permission for this action."), 403)
    elif patient is None:
        return None, (jsonify(error="Patient not found."), 404)
    if write and user.role == "doctor":
        return None, (jsonify(error="Doctors cannot edit patient profiles."), 403)
    return patient, None


@bp.get("")
@role_required("doctor", "admin")
def list_patients():
    q = (request.args.get("q") or "").strip()
    page = max(request.args.get("page", 1, type=int), 1)
    per_page = min(max(request.args.get("per_page", 20, type=int), 1), 100)

    query = Patient.query.join(User, Patient.user_id == User.id)
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(Patient.health_id.ilike(like), User.name.ilike(like)))
    total = query.count()
    rows = query.order_by(Patient.id).offset((page - 1) * per_page).limit(per_page).all()

    log_action(g.current_user.id, "patient_search", detail=f"q={q}" if q else "list all")
    return jsonify(
        patients=[
            {"id": p.id, "health_id": p.health_id, "name": p.user.name,
             "dob": p.dob.isoformat() if p.dob else None, "sex": p.sex, "has_photo": bool(p.photo_path)}
            for p in rows
        ],
        page=page, per_page=per_page, total=total,
    )


@bp.get("/me")
@role_required("patient")
def my_profile():
    patient = Patient.query.filter_by(user_id=g.current_user.id).first()
    if patient is None:
        return jsonify(error="Patient profile not found."), 404
    return jsonify(patient=patient_payload(patient))


@bp.get("/<int:patient_id>")
@role_required(*ALL_ROLES)
def get_patient(patient_id):
    patient, err = get_patient_or_error(patient_id)
    if err:
        return err
    if g.current_user.role != "patient":
        log_action(g.current_user.id, "patient_viewed", "patient", patient.id)
    return jsonify(patient=patient_payload(patient))


@bp.put("/<int:patient_id>")
@role_required(*ALL_ROLES)
def update_patient(patient_id):
    patient, err = get_patient_or_error(patient_id, write=True)
    if err:
        return err
    body = request.get_json(silent=True) or {}
    changed = []

    if "name" in body:
        name = (body.get("name") or "").strip()
        if len(name) < 2 or len(name) > 120:
            return jsonify(error="Name must be 2-120 characters."), 400
        patient.user.name = name
        changed.append("name")
    if "dob" in body:
        dob, error = parse_dob(body.get("dob"))
        if error:
            return jsonify(error=error), 400
        patient.dob = dob
        changed.append("dob")
    if "sex" in body:
        sex = (body.get("sex") or "").strip().lower() or None
        if sex and sex not in SEXES:
            return jsonify(error="Sex must be male, female or other."), 400
        patient.sex = sex
        changed.append("sex")
    if "phone" in body:
        phone, error = clean_phone(body.get("phone"))
        if error:
            return jsonify(error=error), 400
        patient.phone = phone
        changed.append("phone")
    if "emergency_contact" in body:
        value = (body.get("emergency_contact") or "").strip()
        if len(value) > 120:
            return jsonify(error="Emergency contact is too long."), 400
        patient.emergency_contact = value or None
        changed.append("emergency_contact")
    if "allergies" in body:
        value = (body.get("allergies") or "").strip()
        if len(value) > 1000:
            return jsonify(error="Allergies text is too long (max 1000)."), 400
        patient.allergies = value or None
        changed.append("allergies")

    db.session.commit()
    # audit records WHICH fields changed, never the values themselves
    log_action(g.current_user.id, "patient_updated", "patient", patient.id,
               detail="fields=" + ",".join(changed))
    return jsonify(patient=patient_payload(patient))


@bp.post("/<int:patient_id>/photo")
@role_required("patient", "admin")
def upload_photo(patient_id):
    patient, err = get_patient_or_error(patient_id, write=True)
    if err:
        return err
    file = request.files.get("photo")
    if file is None:
        return jsonify(error="Send the image in a form field named 'photo'."), 400
    folder = current_app.config["UPLOAD_FOLDER"]
    try:
        jpeg = process_photo(file, current_app.config["MAX_PHOTO_BYTES"])
    except PhotoError as exc:
        return jsonify(error=str(exc)), 400

    old = patient.photo_path
    patient.photo_path = save_photo(folder, patient.id, jpeg)
    db.session.commit()
    delete_photo(folder, old)
    log_action(g.current_user.id, "photo_uploaded", "patient", patient.id)
    return jsonify(patient=patient_payload(patient)), 201


@bp.get("/<int:patient_id>/photo")
@role_required(*ALL_ROLES)
def get_photo(patient_id):
    patient, err = get_patient_or_error(patient_id)
    if err:
        return err
    if not patient.photo_path:
        return jsonify(error="No photo. Show the fallback avatar."), 404
    full = os.path.join(current_app.config["UPLOAD_FOLDER"], patient.photo_path)
    if not os.path.isfile(full):
        return jsonify(error="Photo file missing."), 404
    # Read the (small, <=512px) photo into memory so no file handle stays open;
    # an open handle blocks replacing/deleting the file on Windows.
    with open(full, "rb") as fh:
        data = decrypt_bytes(fh.read())
    response = Response(data, mimetype="image/jpeg")
    response.headers["Cache-Control"] = "private, no-store"
    return response


@bp.delete("/<int:patient_id>/photo")
@role_required("patient", "admin")
def delete_patient_photo(patient_id):
    patient, err = get_patient_or_error(patient_id, write=True)
    if err:
        return err
    delete_photo(current_app.config["UPLOAD_FOLDER"], patient.photo_path)
    patient.photo_path = None
    db.session.commit()
    log_action(g.current_user.id, "photo_deleted", "patient", patient.id)
    return jsonify(patient=patient_payload(patient))
