from ..extensions import db
from .user import utcnow


class AnalysisJob(db.Model):
    """One run of the document analysis. 'result' holds the structured reading;
    it is updated as the person corrects it and is only trusted once confirmed."""

    __tablename__ = "analysis_jobs"

    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey("documents.id"), nullable=False, index=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patients.id"), nullable=False, index=True)
    requested_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    status = db.Column(db.String(12), nullable=False, default="queued")   # queued / running / done / failed
    error_message = db.Column(db.String(500))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    started_at = db.Column(db.DateTime(timezone=True))
    finished_at = db.Column(db.DateTime(timezone=True))
    result = db.Column(db.JSON)
    page_count = db.Column(db.Integer)
    original_level = db.Column(db.String(20))        # urgency before any human correction
    engine_version = db.Column(db.String(40))
    rules_version = db.Column(db.String(40))
    review_status = db.Column(db.String(12), nullable=False, default="pending")   # pending / confirmed
    confirmed_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    confirmed_by_role = db.Column(db.String(20))
    confirmed_at = db.Column(db.DateTime(timezone=True))

    __table_args__ = (
        db.CheckConstraint("status IN ('queued','running','done','failed')", name="ck_analysis_status"),
        db.CheckConstraint("review_status IN ('pending','confirmed')", name="ck_analysis_review_status"),
    )


class LabResult(db.Model):
    """A lab value that a person has checked and confirmed, kept as structured data."""

    __tablename__ = "lab_results"

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patients.id"), nullable=False, index=True)
    analysis_job_id = db.Column(db.Integer, db.ForeignKey("analysis_jobs.id"), nullable=False, index=True)
    document_id = db.Column(db.Integer, db.ForeignKey("documents.id"), nullable=False)
    test_key = db.Column(db.String(40), nullable=False, index=True)
    test_name = db.Column(db.String(80), nullable=False)
    value = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(30))
    ref_text = db.Column(db.String(60))
    status = db.Column(db.String(14))      # normal / low / high / not_assessed
    severity = db.Column(db.String(12))
    collected_on = db.Column(db.Date)
    confirmed_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    confirmed_by_role = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
