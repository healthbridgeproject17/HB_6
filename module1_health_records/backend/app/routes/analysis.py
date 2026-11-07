import os
import re
from datetime import date, datetime, timedelta, timezone

from flask import Blueprint, Response, current_app, g, jsonify, request

from .. import analysis_bridge as bridge
from ..extensions import db
from ..models import AnalysisJob, Document, LabResult, Patient, Prescription
from ..utils.audit import log_action
from ..utils.crypto import decrypt_bytes, encrypt_bytes
from ..utils.decorators import role_required
from .documents import load_document
from .patients import get_patient_or_error

bp = Blueprint("analysis", __name__)

ALL_ROLES = ("patient", "doctor", "admin")
REVIEW_ROLES = ("patient", "doctor")        # admins can read results but never write clinical data
HEAVY = ("extraction",)                     # raw line positions are not sent to the browser


def now():
    return datetime.now(timezone.utc)


def _age(dob):
    if not dob:
        return None
    today = date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


# ------------------------------------------------------------------ running a job
def analysis_dir(job_id):
    return os.path.join(current_app.config["UPLOAD_FOLDER"], "analysis", f"job_{job_id}")


def delete_job_files(job_id):
    folder = analysis_dir(job_id)
    if os.path.isdir(folder):
        for name in os.listdir(folder):
            try:
                os.remove(os.path.join(folder, name))
            except OSError:
                pass
        try:
            os.rmdir(folder)
        except OSError:
            pass


def run_job(app, job_id):
    with app.app_context():
        job = db.session.get(AnalysisJob, job_id)
        if job is None:
            return
        job.status, job.started_at = "running", now()
        db.session.commit()
        try:
            medai = bridge.medai()
            doc = db.session.get(Document, job.document_id)
            patient = db.session.get(Patient, job.patient_id)
            with open(os.path.join(app.config["UPLOAD_FOLDER"], doc.stored_path), "rb") as fh:
                data = decrypt_bytes(fh.read())
            context = {"name": patient.user.name, "sex": patient.sex, "age": _age(patient.dob)}
            with bridge.ocr_lock:
                result = medai.analyze_document(data, patient=context, with_images=True)
            images = result.pop("_images", {})
            os.makedirs(analysis_dir(job.id), exist_ok=True)
            for number, jpeg in images.items():
                with open(os.path.join(analysis_dir(job.id), f"page_{number}.jpg"), "wb") as fh:
                    fh.write(encrypt_bytes(jpeg))
            job.result = bridge.plain(result)
            job.page_count = result["extraction"]["page_count"]
            job.original_level = (result.get("triage") or {}).get("level")
            job.engine_version, job.rules_version = result["versions"]["engine"], result["versions"]["rules"]
            job.status = "done"
        except Exception as exc:
            db.session.rollback()
            job = db.session.get(AnalysisJob, job_id)
            job.status = "failed"
            known = exc.__class__.__name__ in ("ExtractionError", "AnalysisUnavailable")
            job.error_message = str(exc)[:300] if known else "The analysis failed. Try again, or enter the details by hand."
            if not known:
                app.logger.exception("Analysis job %s failed", job_id)
        job.finished_at = now()
        db.session.commit()


def fail_stale_jobs():
    cutoff = now() - timedelta(minutes=current_app.config["ANALYSIS_STALE_MINUTES"])
    stale = AnalysisJob.query.filter(AnalysisJob.status.in_(("queued", "running")), AnalysisJob.created_at < cutoff).all()
    for job in stale:
        job.status, job.error_message, job.finished_at = "failed", "The analysis was interrupted. Please run it again.", now()
    if stale:
        db.session.commit()


# ------------------------------------------------------------------ payloads
def job_summary(job):
    result = job.result or {}
    triage = result.get("triage") or {}
    return {"id": job.id, "document_id": job.document_id, "patient_id": job.patient_id, "status": job.status, "error": job.error_message,
            "review_status": job.review_status, "created_at": job.created_at.isoformat() if job.created_at else None,
            "finished_at": job.finished_at.isoformat() if job.finished_at else None, "document_type": result.get("document_type"),
            "level": triage.get("level"), "needs_review": (result.get("summary") or {}).get("needs_review"), "confirmed_by_role": job.confirmed_by_role}


def job_detail(job, user):
    out = job_summary(job)
    doc = db.session.get(Document, job.document_id)
    out["document_name"] = doc.original_name if doc else None
    out["document_mime"] = doc.mime_type if doc else None
    out["confirmed_at"] = job.confirmed_at.isoformat() if job.confirmed_at else None
    out["versions"] = {"engine": job.engine_version, "rules": job.rules_version}
    out["original_level"] = job.original_level
    if job.status == "done" and job.result:
        r = {k: v for k, v in job.result.items() if k not in HEAVY and k != "report"}
        r["pages"] = [{k: p[k] for k in ("page", "width", "height", "method", "mean_confidence", "quality")} for p in job.result["extraction"]["pages"]]
        r["report"] = {"patient": job.result["report"]["patient"]}
        if user.role in ("doctor", "admin"):
            r["report"]["clinician"] = job.result["report"]["clinician"]
        out["analysis"] = r
    return out


def get_job_or_error(job_id):
    job = db.session.get(AnalysisJob, job_id)
    if job is None:
        if g.current_user.role == "patient":
            return None, (jsonify(error="You do not have permission for this action."), 403)
        return None, (jsonify(error="Analysis not found."), 404)
    patient, err = get_patient_or_error(job.patient_id)
    if err:
        return None, err
    return job, None


# ------------------------------------------------------------------ routes
@bp.post("/documents/<int:doc_id>/analyze")
@role_required(*ALL_ROLES)
def start_analysis(doc_id):
    doc, err = load_document(doc_id)
    if err:
        return err
    if not bridge.available():
        return jsonify(error="The document analysis engine is not installed on this server."), 503
    fail_stale_jobs()
    if AnalysisJob.query.filter(AnalysisJob.document_id == doc.id, AnalysisJob.status.in_(("queued", "running"))).first():
        return jsonify(error="This document is already being analysed."), 409
    recent = AnalysisJob.query.filter(AnalysisJob.requested_by == g.current_user.id, AnalysisJob.created_at >= now() - timedelta(hours=1)).count()
    if recent >= current_app.config["ANALYSIS_MAX_PER_HOUR"]:
        return jsonify(error="Too many analyses requested. Try again later."), 429

    job = AnalysisJob(document_id=doc.id, patient_id=doc.patient_id, requested_by=g.current_user.id, status="queued")
    db.session.add(job)
    db.session.commit()
    log_action(g.current_user.id, "analysis_requested", "document", doc.id, detail=f"job={job.id}")
    app = current_app._get_current_object()
    if current_app.config["ANALYSIS_SYNC"]:
        run_job(app, job.id)
        db.session.refresh(job)
        return jsonify(job=job_summary(job)), 201
    bridge.executor().submit(run_job, app, job.id)
    return jsonify(job=job_summary(job)), 202


@bp.get("/documents/<int:doc_id>/analyses")
@role_required(*ALL_ROLES)
def document_analyses(doc_id):
    doc, err = load_document(doc_id)
    if err:
        return err
    fail_stale_jobs()
    jobs = AnalysisJob.query.filter_by(document_id=doc.id).order_by(AnalysisJob.id.desc()).all()
    return jsonify(analyses=[job_summary(j) for j in jobs])


@bp.get("/patients/<int:patient_id>/analyses")
@role_required(*ALL_ROLES)
def patient_analyses(patient_id):
    patient, err = get_patient_or_error(patient_id)
    if err:
        return err
    fail_stale_jobs()
    jobs = AnalysisJob.query.filter_by(patient_id=patient.id).order_by(AnalysisJob.id.desc()).all()
    return jsonify(analyses=[dict(job_summary(j), document_name=(db.session.get(Document, j.document_id).original_name)) for j in jobs])


@bp.get("/analysis/<int:job_id>")
@role_required(*ALL_ROLES)
def get_analysis(job_id):
    job, err = get_job_or_error(job_id)
    if err:
        return err
    if job.status in ("queued", "running"):
        fail_stale_jobs()
        db.session.refresh(job)
    if g.current_user.role != "patient":
        log_action(g.current_user.id, "analysis_viewed", "analysis", job.id)
    return jsonify(analysis_job=job_detail(job, g.current_user))


@bp.get("/analysis/<int:job_id>/pages/<int:page>/image")
@role_required(*ALL_ROLES)
def page_image(job_id, page):
    job, err = get_job_or_error(job_id)
    if err:
        return err
    path = os.path.join(analysis_dir(job.id), f"page_{page}.jpg")
    if not os.path.isfile(path):
        return jsonify(error="No picture for this page."), 404
    with open(path, "rb") as fh:
        data = decrypt_bytes(fh.read())
    response = Response(data, mimetype="image/jpeg")
    response.headers["Cache-Control"] = "private, no-store"
    return response


@bp.put("/analysis/<int:job_id>/review")
@role_required(*REVIEW_ROLES)
def review_analysis(job_id):
    """Save corrections, and optionally confirm. Confirming turns lab values into
    saved results; prescriptions become DRAFTS (patients) or confirmed (doctors)."""
    job, err = get_job_or_error(job_id)
    if err:
        return err
    if job.status != "done" or not job.result:
        return jsonify(error="The analysis is not finished."), 409
    if job.review_status == "confirmed":
        return jsonify(error="This analysis was already confirmed and can no longer be changed."), 409

    body = request.get_json(silent=True) or {}
    medai = bridge.medai()
    patient = db.session.get(Patient, job.patient_id)
    context = {"name": patient.user.name, "sex": patient.sex, "age": _age(patient.dob)}
    try:
        updated = medai.apply_review(job.result, body.get("edits") or {}, context)
    except medai.ReviewError as exc:
        return jsonify(error=str(exc)), 400
    except (TypeError, ValueError, AttributeError, KeyError):
        return jsonify(error="The corrections could not be understood."), 400
    updated = bridge.plain(updated)

    confirm = body.get("confirm") is True
    if confirm:
        problem = confirm_problem(updated, body)
        if problem:
            job.result = updated          # keep the corrections made so far
            db.session.commit()
            return jsonify(error=problem, analysis_job=job_detail(job, g.current_user)), 400

    job.result = updated
    changed = len(updated.get("review_log") or [])
    if confirm:
        save_confirmed(job, updated, g.current_user)
    db.session.commit()
    log_action(g.current_user.id, "analysis_confirmed" if confirm else "analysis_reviewed", "analysis", job.id, detail=f"changes={changed}")
    return jsonify(analysis_job=job_detail(job, g.current_user))


def rx_text(item, field):
    """The tidy text to save for a prescription field (e.g. '500 mg', not '500mg')."""
    data = item[field]
    if data["status"] == "missing":
        return None
    value = data.get("value")
    if field in ("strength", "dose", "route", "duration") and isinstance(value, dict) and value.get("text"):
        return value["text"][:80]
    text = data.get("printed") or ""
    if field == "frequency":
        text = re.sub(r"(?<=[A-Za-z])\.(?=[A-Za-z])", ", ", text)
        text = re.sub(r"\s*,\s*", ", ", text).strip()
        text = text[:1].upper() + text[1:]
    return text[:80] or None


def confirm_problem(a, body):
    items = a["lab_results"] + a["prescription_items"]
    if a["document_type"] == "unknown" or not items:
        return "There is nothing to confirm. Add the values by hand or upload a clearer picture."
    identity = a.get("identity")
    if identity and identity["status"] != "match" and body.get("acknowledge_identity") is not True:
        return identity["message"] + " Tick the box to confirm this document belongs to this patient."
    waiting = [i for i in items if i["needs_review"]]
    if waiting:
        return f"{len(waiting)} item(s) still need checking. Correct each one, or accept it if it matches the original."
    return None


def save_confirmed(job, a, user):
    on_doc = a.get("patient_on_document") or {}
    collected = None
    for key in ("collected", "reported", "date"):
        if on_doc.get(key):
            try:
                collected = date.fromisoformat(on_doc[key])
            except ValueError:
                pass
            break
    for r in a["lab_results"]:
        interp = r.get("interpretation") or {}
        db.session.add(LabResult(patient_id=job.patient_id, analysis_job_id=job.id, document_id=job.document_id, test_key=r["test_key"], test_name=r["test"],
                                 value=r["value"], unit=(r.get("unit") or "")[:30] or None, ref_text=((r.get("reference") or {}).get("text") or "")[:60] or None,
                                 status=interp.get("status"), severity=interp.get("severity"), collected_on=collected, confirmed_by=user.id, confirmed_by_role=user.role))
    doctor = user.doctor if user.role == "doctor" else None
    for it in a["prescription_items"]:
        rx = Prescription(patient_id=job.patient_id, doctor_id=doctor.id if doctor else None, medicine=(it["medicine"]["value"] or "")[:200],
                          strength=rx_text(it, "strength"), dose=rx_text(it, "dose"), route=rx_text(it, "route"),
                          frequency=rx_text(it, "frequency"), duration=rx_text(it, "duration"),
                          start_date=date.today(), status="confirmed" if doctor else "draft", source_document_id=job.document_id)
        if doctor:
            rx.confirmed_by_doctor_id, rx.confirmed_at = doctor.id, now()
        db.session.add(rx)
    job.review_status, job.confirmed_by, job.confirmed_by_role, job.confirmed_at = "confirmed", user.id, user.role, now()


@bp.get("/analysis/tests")
@role_required(*ALL_ROLES)
def known_tests():
    from medai.catalog import TESTS
    return jsonify(tests=[{"key": k, "label": t["label"], "unit": t["unit"], "group": t["group"]} for k, t in TESTS.items()])


@bp.get("/patients/<int:patient_id>/lab-results")
@role_required(*ALL_ROLES)
def lab_results(patient_id):
    patient, err = get_patient_or_error(patient_id)
    if err:
        return err
    query = LabResult.query.filter_by(patient_id=patient.id)
    if request.args.get("test_key"):
        query = query.filter_by(test_key=request.args["test_key"])
    rows = query.order_by(LabResult.collected_on.desc().nullslast(), LabResult.id.desc()).all()
    if g.current_user.role != "patient":
        log_action(g.current_user.id, "lab_results_viewed", "patient", patient.id)
    return jsonify(lab_results=[{"id": r.id, "test_key": r.test_key, "test": r.test_name, "value": r.value, "unit": r.unit, "reference": r.ref_text, "status": r.status,
                                 "severity": r.severity, "collected_on": r.collected_on.isoformat() if r.collected_on else None,
                                 "confirmed_by_role": r.confirmed_by_role, "analysis_id": r.analysis_job_id, "document_id": r.document_id} for r in rows])
