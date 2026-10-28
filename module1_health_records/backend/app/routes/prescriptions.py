from datetime import datetime, timezone

from flask import Blueprint, g, jsonify, request

from ..extensions import db
from ..models import Prescription
from ..utils.audit import log_action
from ..utils.decorators import role_required
from .patients import get_patient_or_error

bp = Blueprint("prescriptions", __name__)

ALL_ROLES = ("patient", "doctor", "admin")
STATUSES = ("draft", "confirmed", "discontinued")

# dose, strength, route, frequency and duration stay separate fields
TEXT_FIELDS = {
    "medicine": 200, "strength": 60, "dose": 60, "route": 40, "frequency": 80, "duration": 80,
}


def rx_payload(rx):
    return {
        "id": rx.id,
        "patient_id": rx.patient_id,
        "doctor": rx.doctor.user.name if rx.doctor else None,
        "medicine": rx.medicine,
        "strength": rx.strength,
        "dose": rx.dose,
        "route": rx.route,
        "frequency": rx.frequency,
        "duration": rx.duration,
        "start_date": rx.start_date.isoformat() if rx.start_date else None,
        "end_date": rx.end_date.isoformat() if rx.end_date else None,
        "status": rx.status,
        "confirmed_at": rx.confirmed_at.isoformat() if rx.confirmed_at else None,
        "created_at": rx.created_at.isoformat() if rx.created_at else None,
    }


def parse_date(value, label):
    if value in (None, ""):
        return None, None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date(), None
    except (TypeError, ValueError):
        return None, f"{label} must be YYYY-MM-DD."


def read_fields(body, *, creating):
    """Validate prescription fields. Returns (values, error)."""
    values = {}
    for name, max_len in TEXT_FIELDS.items():
        if name in body or (creating and name == "medicine"):
            text = (body.get(name) or "").strip()
            if name == "medicine" and len(text) < 2:
                return None, "Medicine name is required."
            if len(text) > max_len:
                return None, f"{name} is too long (max {max_len})."
            values[name] = text or None
    for name in ("start_date", "end_date"):
        if name in body:
            parsed, error = parse_date(body.get(name), name)
            if error:
                return None, error
            values[name] = parsed
    return values, None


def dates_ok(start, end):
    return not (start and end and end < start)


@bp.get("/patients/<int:patient_id>/prescriptions")
@role_required(*ALL_ROLES)
def list_prescriptions(patient_id):
    patient, err = get_patient_or_error(patient_id)
    if err:
        return err
    query = Prescription.query.filter_by(patient_id=patient.id)
    status = request.args.get("status")
    if status in STATUSES:
        query = query.filter_by(status=status)
    rows = query.order_by(Prescription.created_at.desc(), Prescription.id.desc()).all()
    if g.current_user.role != "patient":
        log_action(g.current_user.id, "prescriptions_viewed", "patient", patient.id)
    return jsonify(prescriptions=[rx_payload(r) for r in rows])


@bp.post("/patients/<int:patient_id>/prescriptions")
@role_required("doctor")
def create_prescription(patient_id):
    patient, err = get_patient_or_error(patient_id)
    if err:
        return err
    body = request.get_json(silent=True) or {}
    values, error = read_fields(body, creating=True)
    if error:
        return jsonify(error=error), 400
    if not dates_ok(values.get("start_date"), values.get("end_date")):
        return jsonify(error="end_date cannot be before start_date."), 400
    status = (body.get("status") or "confirmed").strip().lower()
    if status not in ("draft", "confirmed"):
        return jsonify(error="status must be draft or confirmed."), 400

    doctor = g.current_user.doctor
    rx = Prescription(patient_id=patient.id, doctor_id=doctor.id, status=status, **values)
    if status == "confirmed":
        rx.confirmed_by_doctor_id = doctor.id
        rx.confirmed_at = datetime.now(timezone.utc)
    db.session.add(rx)
    db.session.commit()
    log_action(g.current_user.id, "prescription_created", "prescription", rx.id,
               detail=f"patient={patient.id} medicine={rx.medicine} status={status}")
    return jsonify(prescription=rx_payload(rx)), 201


def load_for_doctor(rx_id):
    rx = db.session.get(Prescription, rx_id)
    if rx is None:
        return None, (jsonify(error="Prescription not found."), 404)
    return rx, None


@bp.put("/prescriptions/<int:rx_id>")
@role_required("doctor")
def update_prescription(rx_id):
    rx, err = load_for_doctor(rx_id)
    if err:
        return err
    body = request.get_json(silent=True) or {}
    values, error = read_fields(body, creating=False)
    if error:
        return jsonify(error=error), 400
    if "medicine" in values and not values["medicine"]:
        return jsonify(error="Medicine name cannot be empty."), 400

    if "status" in body:
        new_status = (body.get("status") or "").strip().lower()
        if new_status not in ("confirmed", "discontinued"):
            return jsonify(error="status can be changed to confirmed or discontinued. Use /confirm for drafts."), 400
        if new_status == "confirmed" and rx.status == "draft":
            return jsonify(error="Use the confirm action to confirm a draft prescription."), 400
        values["status"] = new_status

    start = values.get("start_date", rx.start_date)
    end = values.get("end_date", rx.end_date)
    if not dates_ok(start, end):
        return jsonify(error="end_date cannot be before start_date."), 400

    # audit trail keeps old -> new so every clinical change is traceable
    changes = []
    for key, new in values.items():
        old = getattr(rx, key)
        if old != new:
            changes.append(f"{key}: {old} -> {new}")
            setattr(rx, key, new)
    db.session.commit()
    log_action(g.current_user.id, "prescription_updated", "prescription", rx.id,
               detail="; ".join(changes) or "no changes")
    return jsonify(prescription=rx_payload(rx))


@bp.put("/prescriptions/<int:rx_id>/confirm")
@role_required("doctor")
def confirm_prescription(rx_id):
    """Only a doctor can turn a draft (e.g. from OCR) into a confirmed prescription."""
    rx, err = load_for_doctor(rx_id)
    if err:
        return err
    if rx.status != "draft":
        return jsonify(error="Only draft prescriptions can be confirmed."), 409
    rx.status = "confirmed"
    rx.confirmed_by_doctor_id = g.current_user.doctor.id
    rx.confirmed_at = datetime.now(timezone.utc)
    db.session.commit()
    log_action(g.current_user.id, "prescription_confirmed", "prescription", rx.id)
    return jsonify(prescription=rx_payload(rx))
