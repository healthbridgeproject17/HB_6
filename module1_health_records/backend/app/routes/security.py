"""Security monitor API (Module 3). Admin only, except /telemetry, which an agent calls with its own token.

SAFETY: this API never changes a real machine, file or network. 'Isolation' is a recorded, SIMULATED
action plus a recommendation for a person. Everything an admin does here is written to the audit log."""
import random
import re
from collections import Counter
from datetime import datetime, timedelta, timezone

from flask import Blueprint, current_app, g, jsonify, request

from .. import monitor_bridge as bridge
from .. import monitor_service as svc
from ..extensions import db
from ..models import IncidentAction, MonitoredMachine, SecurityIncident, TelemetryWindow, User
from ..models.security import MACHINE_KINDS, OPEN_STATUSES
from ..utils.audit import log_action
from ..utils.decorators import role_required

bp = Blueprint("security", __name__)

NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._-]{1,59}$")
OFFLINE_SECONDS = 30            # an agent that has not reported for this long shows as offline
SIM_FAMILIES = ("benign", "fast_encryptor", "slow_drip", "network_spreader", "double_extortion")
SIMULATED_NOTE = "Recorded only. No real machine, file or network was changed."


def _now():
    return datetime.now(timezone.utc)


def _aware(dt):
    if dt is not None and dt.tzinfo is None:        # SQLite returns naive datetimes; everything is stored as UTC
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _iso(dt):
    dt = _aware(dt)
    return dt.isoformat() if dt else None


def _int_arg(name, default, low, high):
    try:
        value = int(request.args.get(name, default))
    except (TypeError, ValueError):
        return default
    return max(low, min(high, value))


def _machine_or_404(machine_id):
    machine = db.session.get(MonitoredMachine, machine_id)
    if machine is None:
        return None, (jsonify(error="Machine not found."), 404)
    return machine, None


def _unavailable(exc):
    return jsonify(error=str(exc), code="monitor_unavailable"), 503


# ------------------------------------------------------------------ payloads
def machine_status(machine, incident, threshold):
    if not machine.is_active:
        return "disabled"
    if incident is not None:
        return "incident"
    if not machine.window_count:
        return "no_data"
    last = _aware(machine.last_seen_at)
    if machine.kind == "agent" and last and (_now() - last).total_seconds() > OFFLINE_SECONDS:
        return "offline"
    if threshold is not None and machine.last_score is not None and machine.last_score >= threshold:
        return "suspicious"
    return "normal"


def machine_payload(machine, incident, running, threshold):
    return {"id": machine.id, "name": machine.name, "kind": machine.kind, "is_active": machine.is_active,
            "status": machine_status(machine, incident, threshold), "last_seen_at": _iso(machine.last_seen_at),
            "last_score": machine.last_score, "windows": machine.window_count or 0,
            "isolated_simulated": machine.isolated_simulated, "isolated_at": _iso(machine.isolated_at),
            "open_incident": {"id": incident.id, "risk_level": incident.risk_level, "status": incident.status} if incident else None,
            "simulation": running.get(machine.id)}


def incident_payload(inc, machine=None, actions=None):
    out = {"id": inc.id, "machine_id": inc.machine_id, "machine_name": machine.name if machine else None,
           "status": inc.status, "risk_level": inc.risk_level, "peak_score": inc.peak_score,
           "windows_above": inc.windows_above, "alert_count": inc.alert_count, "groups": inc.groups or [],
           "reasons": inc.reasons or [], "risk_why": inc.risk_why or [], "is_simulated": inc.is_simulated,
           "sim_family": inc.sim_family, "opened_at": _iso(inc.opened_at), "last_activity_at": _iso(inc.last_activity_at),
           "closed_at": _iso(inc.closed_at), "note": inc.note,
           "machine_isolated_simulated": machine.isolated_simulated if machine else None}
    if actions is not None:
        names = {}
        out["actions"] = []
        for a in actions:
            if a.performed_by and a.performed_by not in names:
                u = db.session.get(User, a.performed_by)
                names[a.performed_by] = u.name if u else "unknown"
            out["actions"].append({"id": a.id, "action": a.action, "note": a.note, "simulated": a.simulated,
                                   "by": names.get(a.performed_by), "at": _iso(a.created_at)})
    return out


def window_payload(w):
    return {"seq": w.seq, "ts": _iso(w.ts), "score": w.score, "above": w.above, "alert": w.alert,
            "phase": w.sim_phase, "features": w.features}


def _threshold():
    try:
        return bridge.model().threshold
    except bridge.MonitorUnavailable:
        return None


# ------------------------------------------------------------------ overview
@bp.get("/security/overview")
@role_required("admin")
def overview():
    message = None
    try:
        threshold = bridge.model().threshold
    except bridge.MonitorUnavailable as exc:
        threshold, message = None, str(exc)
    running = svc.running_simulations()
    machines = MonitoredMachine.query.order_by(MonitoredMachine.id).all()
    open_rows = SecurityIncident.query.filter(SecurityIncident.status.in_(OPEN_STATUSES)).order_by(SecurityIncident.id.desc()).all()
    by_machine = {}
    for inc in open_rows:
        by_machine.setdefault(inc.machine_id, inc)          # newest open incident of each machine
    risk = Counter(i.risk_level for i in open_rows)
    return jsonify(available=threshold is not None, message=message,
                   machines=[machine_payload(m, by_machine.get(m.id), running, threshold) for m in machines],
                   open_incidents=len(open_rows), open_by_risk={k: risk.get(k, 0) for k in ("critical", "high", "medium", "low")},
                   threshold=threshold, window_seconds=5)


@bp.get("/security/model")
@role_required("admin")
def model_summary():
    try:
        return jsonify(summary=bridge.summary())
    except bridge.MonitorUnavailable as exc:
        return _unavailable(exc)


# ------------------------------------------------------------------ machines
@bp.post("/security/machines")
@role_required("admin")
def create_machine():
    body = request.get_json(silent=True) or {}
    name = (body.get("name") or "").strip()
    kind = body.get("kind") or "simulated"
    if not NAME_RE.match(name):
        return jsonify(error="Name must be 2-60 characters: letters, numbers, spaces, dots, dashes."), 400
    if kind not in MACHINE_KINDS:
        return jsonify(error="Kind must be 'simulated' or 'agent'."), 400
    if MonitoredMachine.query.count() >= current_app.config["MONITOR_MAX_MACHINES"]:
        return jsonify(error="The machine limit has been reached."), 409
    if MonitoredMachine.query.filter(db.func.lower(MonitoredMachine.name) == name.lower()).first():
        return jsonify(error="A machine with this name already exists."), 409
    token = None
    machine = MonitoredMachine(name=name, kind=kind, created_by=g.current_user.id)
    if kind == "agent":
        token, machine.token_hash = svc.make_token()
    db.session.add(machine)
    db.session.commit()
    log_action(g.current_user.id, "security_machine_added", "machine", machine.id, detail=f"{name} ({kind})")
    out = {"machine": machine_payload(machine, None, {}, _threshold())}
    if token:
        out["token"] = token
        out["token_note"] = "Copy this token now. It is shown only once and cannot be recovered; create a new one if it is lost."
    return jsonify(out), 201


@bp.post("/security/machines/<int:machine_id>/token")
@role_required("admin")
def rotate_token(machine_id):
    machine, err = _machine_or_404(machine_id)
    if err:
        return err
    if machine.kind != "agent":
        return jsonify(error="Only agent machines use a token."), 400
    token, machine.token_hash = svc.make_token()
    db.session.commit()
    log_action(g.current_user.id, "security_token_rotated", "machine", machine.id, detail=machine.name)
    return jsonify(token=token, token_note="Copy this token now. The old token no longer works. It is shown only once.")


@bp.patch("/security/machines/<int:machine_id>/active")
@role_required("admin")
def set_machine_active(machine_id):
    machine, err = _machine_or_404(machine_id)
    if err:
        return err
    body = request.get_json(silent=True) or {}
    if not isinstance(body.get("is_active"), bool):
        return jsonify(error="is_active must be true or false."), 400
    machine.is_active = body["is_active"]
    if not machine.is_active:
        svc.stop_simulation(machine.id)
    db.session.commit()
    log_action(g.current_user.id, "security_machine_enabled" if machine.is_active else "security_machine_disabled",
               "machine", machine.id, detail=machine.name)
    return jsonify(machine=machine_payload(machine, svc.open_incident_of(machine.id), svc.running_simulations(), _threshold()))


# ------------------------------------------------------------------ telemetry from an agent
@bp.post("/security/telemetry")
def telemetry():
    """An agent sends one 5-second window: header X-Agent-Token, body {"window": {18 numbers}}."""
    machine = svc.machine_for_token(request.headers.get("X-Agent-Token", ""))
    if machine is None:
        return jsonify(error="Unknown or disabled agent token."), 401
    body = request.get_json(silent=True)
    window = body.get("window") if isinstance(body, dict) else None
    if not isinstance(window, dict):
        return jsonify(error='Send JSON like {"window": {...}}.'), 400
    since = _now() - timedelta(seconds=60)
    if TelemetryWindow.query.filter(TelemetryWindow.machine_id == machine.id, TelemetryWindow.ts >= since).count() >= current_app.config["MONITOR_AGENT_MAX_PER_MINUTE"]:
        return jsonify(error="Too many windows. An agent should send one every 5 seconds."), 429
    try:
        svc.ingest_window(machine, window)
    except bridge.MonitorUnavailable as exc:
        return _unavailable(exc)
    except ValueError as exc:                       # BadWindow: names the field only, never the data
        return jsonify(error=str(exc)[:200]), 400
    return jsonify(received=True)


# ------------------------------------------------------------------ live feed
@bp.get("/security/feed")
@role_required("admin")
def feed():
    machine, err = _machine_or_404(_int_arg("machine_id", 0, 0, 10**9))
    if err:
        return err
    limit, after = _int_arg("limit", 60, 1, 300), _int_arg("after_seq", 0, 0, 10**9)
    rows = (TelemetryWindow.query.filter(TelemetryWindow.machine_id == machine.id, TelemetryWindow.seq > after)
            .order_by(TelemetryWindow.seq.desc()).limit(limit).all())
    return jsonify(machine_id=machine.id, threshold=_threshold(), windows=[window_payload(w) for w in reversed(rows)])


# ------------------------------------------------------------------ incidents
@bp.get("/security/incidents")
@role_required("admin")
def list_incidents():
    status = request.args.get("status", "all")
    query = SecurityIncident.query
    if status == "open":
        query = query.filter(SecurityIncident.status.in_(OPEN_STATUSES))
    elif status == "closed":
        query = query.filter(SecurityIncident.status.not_in(OPEN_STATUSES))
    elif status != "all":
        return jsonify(error="status must be open, closed or all."), 400
    machine_id = _int_arg("machine_id", 0, 0, 10**9)
    if machine_id:
        query = query.filter(SecurityIncident.machine_id == machine_id)
    rows = query.order_by(SecurityIncident.id.desc()).limit(_int_arg("limit", 50, 1, 200)).all()
    machines = {m.id: m for m in MonitoredMachine.query.filter(MonitoredMachine.id.in_({r.machine_id for r in rows})).all()} if rows else {}
    return jsonify(incidents=[incident_payload(r, machines.get(r.machine_id)) for r in rows])


def _incident_or_404(incident_id):
    inc = db.session.get(SecurityIncident, incident_id)
    if inc is None:
        return None, None, (jsonify(error="Incident not found."), 404)
    return inc, db.session.get(MonitoredMachine, inc.machine_id), None


def _actions(inc):
    return IncidentAction.query.filter_by(incident_id=inc.id).order_by(IncidentAction.id).all()


@bp.get("/security/incidents/<int:incident_id>")
@role_required("admin")
def incident_detail(incident_id):
    inc, machine, err = _incident_or_404(incident_id)
    if err:
        return err
    return jsonify(incident=incident_payload(inc, machine, _actions(inc)))


def _note(body):
    note = (body.get("note") or "").strip()
    return note[:300] or None


@bp.post("/security/incidents/<int:incident_id>/acknowledge")
@role_required("admin")
def acknowledge(incident_id):
    inc, machine, err = _incident_or_404(incident_id)
    if err:
        return err
    if inc.status != "open":
        return jsonify(error="Only an open incident can be acknowledged."), 409
    body = request.get_json(silent=True) or {}
    inc.status = "acknowledged"
    db.session.add(IncidentAction(incident_id=inc.id, action="acknowledge", note=_note(body), performed_by=g.current_user.id, simulated=False))
    db.session.commit()
    log_action(g.current_user.id, "security_incident_acknowledged", "incident", inc.id, detail=machine.name)
    return jsonify(incident=incident_payload(inc, machine, _actions(inc)))


@bp.post("/security/incidents/<int:incident_id>/close")
@role_required("admin")
def close_incident(incident_id):
    """Close an incident as 'resolved' (a real problem that was dealt with) or 'false_positive' (a false alarm)."""
    inc, machine, err = _incident_or_404(incident_id)
    if err:
        return err
    body = request.get_json(silent=True) or {}
    outcome = body.get("outcome")
    if outcome not in ("resolved", "false_positive"):
        return jsonify(error="outcome must be 'resolved' or 'false_positive'."), 400
    if inc.status not in OPEN_STATUSES:
        return jsonify(error="This incident is already closed."), 409
    note = _note(body)
    if outcome == "resolved" and not note:
        return jsonify(error="Describe what was done (the note is required when resolving)."), 400
    inc.status, inc.closed_at, inc.closed_by, inc.note = outcome, _now(), g.current_user.id, note
    db.session.add(IncidentAction(incident_id=inc.id, action=outcome, note=note, performed_by=g.current_user.id, simulated=False))
    db.session.commit()
    log_action(g.current_user.id, "security_incident_" + outcome, "incident", inc.id, detail=f"{machine.name}: {note or ''}")
    return jsonify(incident=incident_payload(inc, machine, _actions(inc)))


@bp.post("/security/incidents/<int:incident_id>/respond")
@role_required("admin")
def respond(incident_id):
    """SIMULATED response. 'isolate' and 'release' only record what a person would do; they change nothing real."""
    inc, machine, err = _incident_or_404(incident_id)
    if err:
        return err
    body = request.get_json(silent=True) or {}
    action = body.get("action")
    if action not in ("isolate", "release"):
        return jsonify(error="action must be 'isolate' or 'release'."), 400
    if action == "isolate":
        if inc.status not in OPEN_STATUSES:
            return jsonify(error="Only an open incident can trigger an isolation."), 409
        if machine.isolated_simulated:
            return jsonify(error="This machine is already marked as isolated (simulated)."), 409
        machine.isolated_simulated, machine.isolated_at = True, _now()
        record, audit = "isolate_simulated", "security_isolation_simulated"
        detail = f"SIMULATED isolation of {machine.name} (incident #{inc.id}); no real machine or network was changed"
    else:
        if not machine.isolated_simulated:
            return jsonify(error="This machine is not marked as isolated."), 409
        machine.isolated_simulated, machine.isolated_at = False, None
        record, audit = "release_simulated", "security_release_simulated"
        detail = f"SIMULATED release of {machine.name} (incident #{inc.id}); no real machine or network was changed"
    db.session.add(IncidentAction(incident_id=inc.id, action=record, note=_note(body), performed_by=g.current_user.id, simulated=True))
    db.session.commit()
    log_action(g.current_user.id, audit, "incident", inc.id, detail=detail)
    return jsonify(incident=incident_payload(inc, machine, _actions(inc)), simulated=True, message=SIMULATED_NOTE)


# ------------------------------------------------------------------ simulated machines
@bp.post("/security/machines/<int:machine_id>/simulate")
@role_required("admin")
def simulate_start(machine_id):
    """Play a SIMULATED virtual machine into the monitor: ordinary use, or ordinary use followed by an attack-like pattern."""
    machine, err = _machine_or_404(machine_id)
    if err:
        return err
    if machine.kind != "simulated" or not machine.is_active:
        return jsonify(error="Simulations run only on active simulated machines."), 400
    body = request.get_json(silent=True) or {}
    family = body.get("family", "benign")
    if family not in SIM_FAMILIES:
        return jsonify(error=f"family must be one of {', '.join(SIM_FAMILIES)}."), 400
    try:
        tick = float(body.get("tick", 1.0))
        lead_in = int(body.get("lead_in", 8))
        seed = int(body["seed"]) if body.get("seed") is not None else random.randrange(1, 2**31)
    except (TypeError, ValueError):
        return jsonify(error="tick, lead_in and seed must be numbers."), 400
    if not 0.1 <= tick <= 5 or not 0 <= lead_in <= 30:
        return jsonify(error="tick must be 0.1-5 seconds and lead_in 0-30 windows."), 400
    open_incident = svc.open_incident_of(machine.id)
    if open_incident is not None:
        return jsonify(error=f"Close incident #{open_incident.id} on this machine before starting another simulation."), 409
    try:
        run = svc.start_simulation(current_app._get_current_object(), machine, family, seed, tick, lead_in)
    except bridge.MonitorUnavailable as exc:
        return _unavailable(exc)
    except svc.SimulationError as exc:
        return jsonify(error=str(exc)), 409
    log_action(g.current_user.id, "security_simulation_started", "machine", machine.id, detail=f"{machine.name}: {family}")
    return jsonify(run=run, simulated=True), 202


@bp.post("/security/machines/<int:machine_id>/simulate/stop")
@role_required("admin")
def simulate_stop(machine_id):
    machine, err = _machine_or_404(machine_id)
    if err:
        return err
    was_running = svc.stop_simulation(machine.id)
    if was_running:
        log_action(g.current_user.id, "security_simulation_stopped", "machine", machine.id, detail=machine.name)
    return jsonify(stopped=was_running)


@bp.delete("/security/demo-data")
@role_required("admin")
def clear_demo_data():
    """Wipe the windows and incidents of SIMULATED machines (for a fresh demo). Agent machines are never touched."""
    ids = [m.id for m in MonitoredMachine.query.filter_by(kind="simulated").all()]
    for mid in ids:
        svc.stop_simulation(mid)
    removed = {"incidents": 0, "windows": 0}
    if ids:
        with svc.ingest_lock:
            inc_ids = [i.id for i in SecurityIncident.query.filter(SecurityIncident.machine_id.in_(ids)).all()]
            if inc_ids:
                IncidentAction.query.filter(IncidentAction.incident_id.in_(inc_ids)).delete(synchronize_session=False)
            removed["incidents"] = SecurityIncident.query.filter(SecurityIncident.machine_id.in_(ids)).delete(synchronize_session=False)
            removed["windows"] = TelemetryWindow.query.filter(TelemetryWindow.machine_id.in_(ids)).delete(synchronize_session=False)
            MonitoredMachine.query.filter(MonitoredMachine.id.in_(ids)).update(
                {"window_count": 0, "last_seen_at": None, "last_score": None, "alert_state": None,
                 "isolated_simulated": False, "isolated_at": None}, synchronize_session=False)
            db.session.commit()
    log_action(g.current_user.id, "security_demo_data_cleared", "machine", None,
               detail=f"{removed['incidents']} incidents, {removed['windows']} windows (simulated machines only)")
    return jsonify(removed=removed)
