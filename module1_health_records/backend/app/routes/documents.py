import os

from flask import Blueprint, Response, current_app, g, jsonify, request

from ..extensions import db
from ..models import Document
from ..utils.audit import log_action
from ..utils.decorators import role_required
from ..utils.crypto import decrypt_bytes
from ..utils.documents import (
    DocumentError, delete_document_file, safe_display_name, save_document, validate_document,
)
from .patients import get_patient_or_error

bp = Blueprint("documents", __name__)

ALL_ROLES = ("patient", "doctor", "admin")
DOC_TYPES = ("prescription", "lab_report", "other")


def doc_payload(doc, user):
    from ..models import User
    uploader = db.session.get(User, doc.uploaded_by)
    return {
        "id": doc.id,
        "patient_id": doc.patient_id,
        "doc_type": doc.doc_type,
        "original_name": doc.original_name,
        "mime_type": doc.mime_type,
        "size_bytes": doc.size_bytes,
        "uploaded_at": doc.uploaded_at.isoformat() if doc.uploaded_at else None,
        "uploaded_by": uploader.name if uploader else None,
        "uploaded_by_id": doc.uploaded_by,
        "can_delete": user.role == "admin" or doc.uploaded_by == user.id,
    }


def load_document(doc_id):
    """Fetch a document and apply the owning patient's visibility rules."""
    doc = db.session.get(Document, doc_id)
    if doc is None:
        if g.current_user.role == "patient":
            return None, (jsonify(error="You do not have permission for this action."), 403)
        return None, (jsonify(error="Document not found."), 404)
    patient, err = get_patient_or_error(doc.patient_id)
    if err:
        return None, err
    return doc, None


@bp.post("/patients/<int:patient_id>/documents")
@role_required(*ALL_ROLES)
def upload_document(patient_id):
    """Patients upload to their own record; doctors and admins can upload for
    any patient. Works for files and for photos taken with the camera."""
    patient, err = get_patient_or_error(patient_id)
    if err:
        return err
    file = request.files.get("file")
    if file is None:
        return jsonify(error="Send the file in a form field named 'file'."), 400
    doc_type = (request.form.get("doc_type") or "").strip().lower()
    if doc_type not in DOC_TYPES:
        return jsonify(error="doc_type must be prescription, lab_report or other."), 400

    try:
        data, ext, mime = validate_document(file, current_app.config["MAX_DOCUMENT_BYTES"])
    except DocumentError as exc:
        return jsonify(error=str(exc)), 400

    folder = current_app.config["UPLOAD_FOLDER"]
    original = safe_display_name(file.filename)
    if not original.lower().endswith("." + ext):
        original = f"{os.path.splitext(original)[0]}.{ext}"  # camera shots are often unnamed
    stored = save_document(folder, patient.id, data, ext)
    doc = Document(
        patient_id=patient.id, uploaded_by=g.current_user.id, doc_type=doc_type,
        original_name=original, stored_path=stored, mime_type=mime, size_bytes=len(data),
    )
    db.session.add(doc)
    db.session.commit()
    log_action(g.current_user.id, "document_uploaded", "document", doc.id,
               detail=f"patient={patient.id} type={doc_type} size={len(data)}")
    return jsonify(document=doc_payload(doc, g.current_user)), 201


@bp.get("/patients/<int:patient_id>/documents")
@role_required(*ALL_ROLES)
def list_documents(patient_id):
    patient, err = get_patient_or_error(patient_id)
    if err:
        return err
    query = Document.query.filter_by(patient_id=patient.id)
    doc_type = request.args.get("doc_type")
    if doc_type in DOC_TYPES:
        query = query.filter_by(doc_type=doc_type)
    rows = query.order_by(Document.uploaded_at.desc(), Document.id.desc()).all()
    if g.current_user.role != "patient":
        log_action(g.current_user.id, "documents_listed", "patient", patient.id)
    return jsonify(documents=[doc_payload(d, g.current_user) for d in rows])


@bp.get("/documents/<int:doc_id>/file")
@role_required(*ALL_ROLES)
def get_document_file(doc_id):
    doc, err = load_document(doc_id)
    if err:
        return err
    full = os.path.join(current_app.config["UPLOAD_FOLDER"], doc.stored_path)
    if not os.path.isfile(full):
        return jsonify(error="The stored file is missing."), 404
    with open(full, "rb") as fh:  # read fully so no file handle stays open (Windows)
        data = decrypt_bytes(fh.read())
    if g.current_user.role != "patient":
        log_action(g.current_user.id, "document_viewed", "document", doc.id)
    response = Response(data, mimetype=doc.mime_type or "application/octet-stream")
    response.headers["Content-Disposition"] = f'inline; filename="{doc.original_name}"'
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@bp.delete("/documents/<int:doc_id>")
@role_required(*ALL_ROLES)
def delete_document(doc_id):
    doc, err = load_document(doc_id)
    if err:
        return err
    user = g.current_user
    if not (user.role == "admin" or doc.uploaded_by == user.id):
        return jsonify(error="You can only delete documents you uploaded."), 403
    from ..models import AnalysisJob, LabResult, Prescription
    from .analysis import delete_job_files
    if (Prescription.query.filter_by(source_document_id=doc.id).first() or LabResult.query.filter_by(document_id=doc.id).first()
            or AnalysisJob.query.filter_by(document_id=doc.id, review_status="confirmed").first()):
        return jsonify(error="This document is the source of confirmed results or prescriptions, so it cannot be deleted."), 409
    for job in AnalysisJob.query.filter_by(document_id=doc.id).all():
        delete_job_files(job.id)
        db.session.delete(job)
    stored = doc.stored_path
    patient_id = doc.patient_id
    db.session.delete(doc)
    db.session.commit()
    delete_document_file(current_app.config["UPLOAD_FOLDER"], stored)
    log_action(user.id, "document_deleted", "document", doc_id, detail=f"patient={patient_id}")
    return jsonify(deleted=True)
