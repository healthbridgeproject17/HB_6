from ..extensions import db
from .user import Doctor, utcnow  # noqa: F401


class MedicalRecord(db.Model):
    """Doctor-authored clinical entry. Corrections are new rows pointing at
    the original via amended_from_id, so history is never silently rewritten."""

    __tablename__ = "medical_records"

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patients.id"), nullable=False, index=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey("doctors.id"))
    record_type = db.Column(db.String(30), nullable=False, default="note")  # diagnosis/note/visit
    title = db.Column(db.String(200), nullable=False)
    details = db.Column(db.Text)
    amended_from_id = db.Column(db.Integer, db.ForeignKey("medical_records.id"))
    created_by_user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", name="fk_medical_records_created_by")
    )
    amendment_reason = db.Column(db.String(500))
    doctor = db.relationship("Doctor", lazy="joined")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)


class Document(db.Model):
    __tablename__ = "documents"

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patients.id"), nullable=False, index=True)
    uploaded_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    doc_type = db.Column(db.String(30), nullable=False)  # prescription/lab_report/photo/other
    original_name = db.Column(db.String(255), nullable=False)
    stored_path = db.Column(db.String(500), nullable=False)
    mime_type = db.Column(db.String(100))
    size_bytes = db.Column(db.Integer)
    uploaded_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)


class Prescription(db.Model):
    __tablename__ = "prescriptions"

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patients.id"), nullable=False, index=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey("doctors.id"))
    medicine = db.Column(db.String(200), nullable=False)
    strength = db.Column(db.String(60))
    dose = db.Column(db.String(60))
    route = db.Column(db.String(40))
    frequency = db.Column(db.String(80))
    duration = db.Column(db.String(80))
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    # draft = not yet verified by a doctor (e.g. from OCR); only doctors confirm
    status = db.Column(db.String(20), nullable=False, default="draft")
    source_document_id = db.Column(db.Integer, db.ForeignKey("documents.id"))
    confirmed_by_doctor_id = db.Column(
        db.Integer, db.ForeignKey("doctors.id", name="fk_prescriptions_confirmed_by")
    )
    confirmed_at = db.Column(db.DateTime(timezone=True))
    doctor = db.relationship("Doctor", foreign_keys=[doctor_id], lazy="joined")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)

    __table_args__ = (
        db.CheckConstraint(
            "status IN ('draft','confirmed','discontinued')", name="ck_prescriptions_status"
        ),
    )


class MedicationLog(db.Model):
    __tablename__ = "medication_logs"

    id = db.Column(db.Integer, primary_key=True)
    prescription_id = db.Column(db.Integer, db.ForeignKey("prescriptions.id"), nullable=False, index=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patients.id"), nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False)  # taken / skipped
    logged_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    note = db.Column(db.String(255))

    __table_args__ = (
        db.CheckConstraint("status IN ('taken','skipped')", name="ck_medlog_status"),
    )


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), index=True)
    action = db.Column(db.String(60), nullable=False)
    target_type = db.Column(db.String(40))
    target_id = db.Column(db.Integer)
    detail = db.Column(db.String(500))
    ip_address = db.Column(db.String(45))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
