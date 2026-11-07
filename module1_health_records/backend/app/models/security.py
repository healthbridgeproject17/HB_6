from ..extensions import db
from .user import utcnow

INCIDENT_STATUSES = ("open", "acknowledged", "resolved", "false_positive")
OPEN_STATUSES = ("open", "acknowledged")
RISK_LEVELS = ("low", "medium", "high", "critical")
MACHINE_KINDS = ("simulated", "agent")


class MonitoredMachine(db.Model):
    """A machine the security monitor watches. 'simulated' machines are fed by the safe simulator;
    'agent' machines send their own telemetry using a secret token (only its hash is stored)."""

    __tablename__ = "monitored_machines"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(60), nullable=False, unique=True)
    kind = db.Column(db.String(10), nullable=False, default="simulated")
    token_hash = db.Column(db.String(64))                  # SHA-256 of the agent token; null for simulated machines
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    last_seen_at = db.Column(db.DateTime(timezone=True))
    window_count = db.Column(db.Integer, nullable=False, default=0)
    last_score = db.Column(db.Float)
    alert_state = db.Column(db.JSON)                       # memory of the alert rule, so a restart loses nothing
    isolated_simulated = db.Column(db.Boolean, nullable=False, default=False)   # a RECORD only: nothing real is isolated
    isolated_at = db.Column(db.DateTime(timezone=True))

    __table_args__ = (
        db.CheckConstraint("kind IN ('simulated','agent')", name="ck_machine_kind"),
    )


class TelemetryWindow(db.Model):
    """One scored 5-second window. Only the newest few hundred per machine are kept."""

    __tablename__ = "telemetry_windows"

    id = db.Column(db.Integer, primary_key=True)
    machine_id = db.Column(db.Integer, db.ForeignKey("monitored_machines.id"), nullable=False)
    seq = db.Column(db.Integer, nullable=False)            # 1, 2, 3 ... per machine
    ts = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    score = db.Column(db.Float, nullable=False)
    above = db.Column(db.Boolean, nullable=False)
    alert = db.Column(db.Boolean, nullable=False)
    sim_phase = db.Column(db.String(20))                   # simulator truth (benign / recon / encrypt ...), simulated machines only
    features = db.Column(db.JSON, nullable=False)

    __table_args__ = (
        db.UniqueConstraint("machine_id", "seq", name="uq_window_machine_seq"),
    )


class SecurityIncident(db.Model):
    __tablename__ = "security_incidents"

    id = db.Column(db.Integer, primary_key=True)
    machine_id = db.Column(db.Integer, db.ForeignKey("monitored_machines.id"), nullable=False, index=True)
    status = db.Column(db.String(14), nullable=False, default="open")
    risk_level = db.Column(db.String(10), nullable=False)
    peak_score = db.Column(db.Float, nullable=False)
    windows_above = db.Column(db.Integer, nullable=False, default=1)
    alert_count = db.Column(db.Integer, nullable=False, default=1)
    groups = db.Column(db.JSON)                            # kinds of suspicious behaviour seen
    reasons = db.Column(db.JSON)                           # plain-language things that stood out
    risk_why = db.Column(db.JSON)                          # how the risk level was reached
    is_simulated = db.Column(db.Boolean, nullable=False, default=False)
    sim_family = db.Column(db.String(30))                  # which simulated attack family was running (display only)
    opened_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    last_activity_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    closed_at = db.Column(db.DateTime(timezone=True))
    closed_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    note = db.Column(db.String(500))

    __table_args__ = (
        db.CheckConstraint("status IN ('open','acknowledged','resolved','false_positive')", name="ck_incident_status"),
        db.CheckConstraint("risk_level IN ('low','medium','high','critical')", name="ck_incident_risk"),
    )


class IncidentAction(db.Model):
    """What a person did about an incident. Every action here is a SIMULATED response (a record and a
    recommendation); nothing in this table changes a real machine or network."""

    __tablename__ = "incident_actions"

    id = db.Column(db.Integer, primary_key=True)
    incident_id = db.Column(db.Integer, db.ForeignKey("security_incidents.id"), nullable=False, index=True)
    action = db.Column(db.String(30), nullable=False)
    note = db.Column(db.String(300))
    performed_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    simulated = db.Column(db.Boolean, nullable=False, default=True)
