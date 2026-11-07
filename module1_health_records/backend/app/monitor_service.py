"""The security monitor's working parts: scoring a window, keeping incidents, running simulated machines.

The decisions come from rwdetect.monitor (tested on its own). This file stores them.
Nothing here changes a real machine or network: 'isolation' is only a record."""
import hashlib
import hmac
import secrets
import threading
from datetime import datetime, timezone

from flask import current_app

from . import monitor_bridge as bridge
from .extensions import db
from .models import MonitoredMachine, SecurityIncident, TelemetryWindow
from .models.security import OPEN_STATUSES
from .utils.audit import log_action

ingest_lock = threading.Lock()      # windows are stored one at a time, so sequence numbers never clash
_runs = {}                          # machine id -> running simulation (lives in this server process)
_runs_lock = threading.Lock()


def now():
    return datetime.now(timezone.utc)


# ------------------------------------------------------------------ agent tokens
def make_token():
    """A new random secret for an agent. Shown to the admin once; only its hash is stored."""
    token = "hbm_" + secrets.token_urlsafe(32)
    return token, hash_token(token)


def hash_token(token):
    return hashlib.sha256(token.encode()).hexdigest()


def machine_for_token(token):
    """The active agent machine that owns this token, or None."""
    if not token or len(token) > 200:
        return None
    digest = hash_token(token)
    machine = MonitoredMachine.query.filter_by(token_hash=digest, kind="agent").first()
    if machine is None or not hmac.compare_digest(machine.token_hash, digest) or not machine.is_active:
        return None
    return machine


# ------------------------------------------------------------------ incidents
def open_incident_of(machine_id):
    return (SecurityIncident.query.filter(SecurityIncident.machine_id == machine_id,
                                          SecurityIncident.status.in_(OPEN_STATUSES))
            .order_by(SecurityIncident.id.desc()).first())


def _as_dict(row):
    return {"risk": row.risk_level, "risk_why": list(row.risk_why or []), "peak_score": row.peak_score,
            "windows_above": row.windows_above, "alert_count": row.alert_count,
            "groups": list(row.groups or []), "reasons": list(row.reasons or [])}


def _apply(row, inc, at):
    row.risk_level, row.risk_why = inc["risk"], inc.get("risk_why", [])
    row.peak_score, row.windows_above, row.alert_count = inc["peak_score"], inc["windows_above"], inc["alert_count"]
    row.groups, row.reasons = list(inc["groups"]), list(inc["reasons"])
    row.last_activity_at = at


# ------------------------------------------------------------------ one window
def ingest_window(machine, window, sim_phase=None, sim_family=None):
    """Score one telemetry window for `machine`, store it, and open / update the machine's incident.
    Raises rwdetect's BadWindow for unusable input and MonitorUnavailable if the engine is missing."""
    mon, model = bridge.monitor(), bridge.model()
    with ingest_lock:
        with bridge.score_lock:
            verdict = mon.assess(model, window, machine.alert_state)
        at = now()
        machine.window_count = (machine.window_count or 0) + 1
        seq = machine.window_count
        machine.last_seen_at, machine.last_score = at, round(verdict.score, 4)
        machine.alert_state = verdict.state
        db.session.add(TelemetryWindow(
            machine_id=machine.id, seq=seq, ts=at, score=round(verdict.score, 4), above=verdict.above, alert=verdict.alert,
            sim_phase=sim_phase, features={k: round(float(v), 4) for k, v in verdict.values.items()}))
        cutoff = seq - int(current_app.config["MONITOR_KEEP_WINDOWS"])      # forget windows older than the newest N
        if cutoff > 0:
            TelemetryWindow.query.filter(TelemetryWindow.machine_id == machine.id, TelemetryWindow.seq <= cutoff).delete(synchronize_session=False)

        row = open_incident_of(machine.id)
        updated, event = mon.update_incident(_as_dict(row) if row else None, verdict, model.threshold)
        old_risk = row.risk_level if row else None
        if event == "opened":
            row = SecurityIncident(machine_id=machine.id, status="open", risk_level=updated["risk"], peak_score=updated["peak_score"],
                                   windows_above=updated["windows_above"], alert_count=updated["alert_count"], groups=updated["groups"],
                                   reasons=updated["reasons"], risk_why=updated.get("risk_why", []), is_simulated=sim_phase is not None,
                                   sim_family=sim_family if sim_phase is not None else None, opened_at=at, last_activity_at=at)
            db.session.add(row)
        elif event is not None:
            _apply(row, updated, at)
        db.session.commit()
        incident_id = row.id if row else None
        name, risk = machine.name, (row.risk_level if row else None)

    # the audit log records what the SYSTEM decided; admins' own actions are logged by the routes
    if event == "opened":
        log_action(None, "security_incident_opened", "incident", incident_id, detail=f"{name}: {risk} risk (model score {updated['peak_score']:.2f})")
    elif event == "escalated":
        log_action(None, "security_incident_escalated", "incident", incident_id, detail=f"{name}: {old_risk} -> {risk}")
    return {"score": round(verdict.score, 4), "above": verdict.above, "alert": verdict.alert,
            "incident_id": incident_id, "event": event, "risk": risk}


# ------------------------------------------------------------------ simulated machines
class SimulationError(ValueError):
    pass


def running_simulations():
    with _runs_lock:
        return {mid: {"family": r["family"], "window": r["window"], "total": r["total"]} for mid, r in _runs.items()}


def start_simulation(app, machine, family, seed, tick, lead_in):
    """Play a simulated virtual machine into the monitor, one window per `tick` seconds.
    (A real window is 5 seconds; the simulation is sped up so a demo does not take minutes.)"""
    mon = bridge.monitor()
    try:
        rows = mon.demo_stream(family, seed, lead_in=lead_in)
    except ValueError as exc:
        raise SimulationError(str(exc)) from exc
    sync = app.config["MONITOR_SIM_SYNC"]
    machine.alert_state = None            # a new simulated session starts with a fresh alert memory
    db.session.commit()
    with _runs_lock:
        if machine.id in _runs:
            raise SimulationError("A simulation is already running on this machine. Stop it first.")
        if len(_runs) >= app.config["MONITOR_MAX_SIMULATIONS"]:
            raise SimulationError("Too many simulations are running at once. Stop one first.")
        if not sync:
            _runs[machine.id] = {"family": family, "window": 0, "total": len(rows), "stop": threading.Event()}
    if sync:                                  # tests: play everything now, in this request
        for row in rows:
            ingest_window(machine, {k: v for k, v in row.items() if k not in ("phase", "family")}, sim_phase=row["phase"], sim_family=family)
        return {"family": family, "windows": len(rows), "played": len(rows)}
    stop = _runs[machine.id]["stop"]
    threading.Thread(target=_play, args=(app, machine.id, rows, family, tick, stop), daemon=True, name=f"sim-{machine.id}").start()
    return {"family": family, "windows": len(rows), "played": 0}


def _play(app, machine_id, rows, family, tick, stop):
    try:
        with app.app_context():
            for i, row in enumerate(rows):
                if stop.is_set():
                    break
                machine = db.session.get(MonitoredMachine, machine_id)
                if machine is None or not machine.is_active:
                    break
                try:
                    ingest_window(machine, {k: v for k, v in row.items() if k not in ("phase", "family")}, sim_phase=row["phase"], sim_family=family)
                except Exception:
                    db.session.rollback()
                    app.logger.exception("Simulated window failed on machine %s", machine_id)
                    break
                with _runs_lock:
                    if machine_id in _runs:
                        _runs[machine_id]["window"] = i + 1
                db.session.remove()
                stop.wait(tick)
            db.session.remove()
    finally:
        with _runs_lock:
            _runs.pop(machine_id, None)


def stop_simulation(machine_id):
    with _runs_lock:
        run = _runs.get(machine_id)
        if run:
            run["stop"].set()
        return run is not None


def stop_all_simulations():
    with _runs_lock:
        for run in _runs.values():
            run["stop"].set()
