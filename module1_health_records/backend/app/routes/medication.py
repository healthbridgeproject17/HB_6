from datetime import date, datetime, timedelta, timezone

from flask import Blueprint, g, jsonify, request

from ..extensions import db
from ..models import MedicationLog, Prescription
from ..utils.audit import log_action
from ..utils.decorators import role_required
from .patients import get_patient_or_error

bp = Blueprint("medication", __name__)

ALL_ROLES = ("patient", "doctor", "admin")
MAX_BACKDATE = timedelta(days=7)


def log_payload(entry):
    return {
        "id": entry.id,
        "prescription_id": entry.prescription_id,
        "status": entry.status,
        "logged_at": entry.logged_at.isoformat() if entry.logged_at else None,
        "note": entry.note,
    }


def is_active(rx, today):
    if rx.status != "confirmed":
        return False
    if rx.start_date and rx.start_date > today:
        return False
    if rx.end_date and rx.end_date < today:
        return False
    return True


def parse_logged_at(value):
    """Optional ISO timestamp from the patient. Defaults to now (server time).
    Future times and times older than 7 days are refused."""
    now = datetime.now(timezone.utc)
    if value in (None, ""):
        return now, None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None, "logged_at must be an ISO date-time, e.g. 2026-10-28T08:30:00."
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    if parsed > now + timedelta(minutes=2):
        return None, "logged_at cannot be in the future."
    if parsed < now - MAX_BACKDATE:
        return None, "logged_at cannot be more than 7 days in the past."
    return parsed, None


def load_prescription(rx_id):
    """Fetch a prescription and apply the same visibility rules as its patient."""
    rx = db.session.get(Prescription, rx_id)
    if rx is None:
        if g.current_user.role == "patient":
            return None, (jsonify(error="You do not have permission for this action."), 403)
        return None, (jsonify(error="Prescription not found."), 404)
    patient, err = get_patient_or_error(rx.patient_id)
    if err:
        return None, err
    return rx, None


@bp.post("/prescriptions/<int:rx_id>/log")
@role_required("patient")
def record_dose(rx_id):
    """Patient records that they took or skipped a dose. Only the patient who
    owns the prescription can do this; doctors and admins only view."""
    rx, err = load_prescription(rx_id)
    if err:
        return err
    if rx.status != "confirmed":
        return jsonify(error="You can only record doses for confirmed prescriptions."), 409

    body = request.get_json(silent=True) or {}
    status = (body.get("status") or "").strip().lower()
    if status not in ("taken", "skipped"):
        return jsonify(error="status must be taken or skipped."), 400
    note = (body.get("note") or "").strip()
    if len(note) > 255:
        return jsonify(error="Note is too long (max 255)."), 400
    logged_at, error = parse_logged_at(body.get("logged_at"))
    if error:
        return jsonify(error=error), 400

    entry = MedicationLog(
        prescription_id=rx.id, patient_id=rx.patient_id,
        status=status, logged_at=logged_at, note=note or None,
    )
    db.session.add(entry)
    db.session.commit()
    log_action(g.current_user.id, "medication_logged", "prescription", rx.id, detail=status)
    return jsonify(log=log_payload(entry)), 201


@bp.get("/prescriptions/<int:rx_id>/logs")
@role_required(*ALL_ROLES)
def list_logs(rx_id):
    rx, err = load_prescription(rx_id)
    if err:
        return err
    limit = min(max(request.args.get("limit", 30, type=int), 1), 200)
    rows = (
        MedicationLog.query.filter_by(prescription_id=rx.id)
        .order_by(MedicationLog.logged_at.desc(), MedicationLog.id.desc())
        .limit(limit).all()
    )
    if g.current_user.role != "patient":
        log_action(g.current_user.id, "medication_logs_viewed", "prescription", rx.id)
    return jsonify(logs=[log_payload(r) for r in rows])


@bp.get("/patients/<int:patient_id>/medication")
@role_required(*ALL_ROLES)
def medication_schedule(patient_id):
    """Schedule from confirmed prescriptions, with 'last taken' taken ONLY from
    what the patient actually recorded. No log means 'Not recorded'."""
    patient, err = get_patient_or_error(patient_id)
    if err:
        return err
    today = date.today()
    prescriptions = (
        Prescription.query.filter_by(patient_id=patient.id, status="confirmed")
        .order_by(Prescription.id).all()
    )
    items = []
    for rx in prescriptions:
        logs = (
            MedicationLog.query.filter_by(prescription_id=rx.id)
            .order_by(MedicationLog.logged_at.desc(), MedicationLog.id.desc()).all()
        )
        last_taken = next((l for l in logs if l.status == "taken"), None)
        items.append({
            "prescription_id": rx.id,
            "medicine": rx.medicine,
            "strength": rx.strength,
            "dose": rx.dose,
            "route": rx.route,
            "frequency": rx.frequency,
            "duration": rx.duration,
            "start_date": rx.start_date.isoformat() if rx.start_date else None,
            "end_date": rx.end_date.isoformat() if rx.end_date else None,
            "active": is_active(rx, today),
            "last_taken_at": last_taken.logged_at.isoformat() if last_taken else None,
            "last_taken_display": last_taken.logged_at.isoformat() if last_taken else "Not recorded",
            "last_entry": log_payload(logs[0]) if logs else None,
            "taken_count": sum(1 for l in logs if l.status == "taken"),
            "skipped_count": sum(1 for l in logs if l.status == "skipped"),
        })
    if g.current_user.role != "patient":
        log_action(g.current_user.id, "medication_viewed", "patient", patient.id)
    return jsonify(medication=items)
