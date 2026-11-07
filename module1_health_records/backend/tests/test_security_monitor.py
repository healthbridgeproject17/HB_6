"""Phase 3.3: the security monitor (machines, telemetry, incidents, SIMULATED response).

The detection logic itself is tested in module3_ransomware/tests. These tests check the website side:
permissions, storage, the audit log, and that nothing is ever done to a real machine."""
import hashlib
import os
import shutil

import pytest

pytest.importorskip("sklearn")
pytest.importorskip("pandas")

from app import create_app  # noqa: E402
from app import monitor_bridge as bridge  # noqa: E402
from app.config import TestConfig  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models import AuditLog, IncidentAction, MonitoredMachine, SecurityIncident, TelemetryWindow, User  # noqa: E402
from rwdetect.features import FEATURES  # noqa: E402
from rwdetect.monitor import demo_stream  # noqa: E402


@pytest.fixture()
def client():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        admin = User(name="Admin", email="admin@test.com", role="admin")
        admin.set_password("AdminPass1")
        db.session.add(admin)
        db.session.commit()
        c = app.test_client()
        c.app_ref = app
        yield c
        db.session.remove()
        db.drop_all()


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def login(client, email="admin@test.com", password="AdminPass1"):
    return client.post("/api/v1/auth/login", json={"email": email, "password": password}).get_json()["access_token"]


@pytest.fixture()
def admin(client):
    return auth(login(client))


def add_machine(client, admin, name="PC-1", kind="simulated"):
    r = client.post("/api/v1/security/machines", headers=admin, json={"name": name, "kind": kind})
    assert r.status_code == 201, r.get_json()
    return r.get_json()


def simulate(client, admin, machine_id, family, seed):
    r = client.post(f"/api/v1/security/machines/{machine_id}/simulate", headers=admin, json={"family": family, "seed": seed, "tick": 0.1})
    assert r.status_code == 202, r.get_json()
    return r.get_json()


def window_of(row):
    return {k: row[k] for k in FEATURES}


def audit_actions():
    db.session.expire_all()
    return [a.action for a in AuditLog.query.order_by(AuditLog.id).all()]


# ------------------------------------------------------------------ permissions
def test_every_security_page_is_admin_only(client):
    client.post("/api/v1/auth/register", json={"name": "Pat", "email": "pat@test.com", "password": "Patient123", "sex": "female", "dob": "1990-01-01"})
    patient = auth(login(client, "pat@test.com", "Patient123"))
    calls = [("get", "/security/overview"), ("get", "/security/model"), ("get", "/security/incidents"), ("get", "/security/feed?machine_id=1"),
             ("post", "/security/machines"), ("post", "/security/machines/1/simulate"), ("post", "/security/incidents/1/respond"),
             ("post", "/security/incidents/1/acknowledge"), ("post", "/security/incidents/1/close"), ("delete", "/security/demo-data")]
    for method, path in calls:
        assert getattr(client, method)("/api/v1" + path).status_code == 401, path                      # not logged in
        assert getattr(client, method)("/api/v1" + path, headers=patient).status_code == 403, path    # a patient


# ------------------------------------------------------------------ machines and tokens
def test_create_machine_validation(client, admin):
    post = lambda body: client.post("/api/v1/security/machines", headers=admin, json=body)  # noqa: E731
    assert post({"name": "x"}).status_code == 400
    assert post({"name": "<script>"}).status_code == 400
    assert post({"name": "Good-PC", "kind": "real_isolation"}).status_code == 400
    assert post({"name": "Good-PC"}).status_code == 201
    assert post({"name": "good-pc"}).status_code == 409                      # same name in other letters


def test_machine_limit(client, admin):
    client.app_ref.config["MONITOR_MAX_MACHINES"] = 2
    add_machine(client, admin, "A1")
    add_machine(client, admin, "A2")
    assert client.post("/api/v1/security/machines", headers=admin, json={"name": "A3"}).status_code == 409


def test_agent_token_is_shown_once_and_only_its_hash_is_stored(client, admin):
    out = add_machine(client, admin, "Agent-PC", "agent")
    token = out["token"]
    assert token.startswith("hbm_") and "once" in out["token_note"]
    machine = db.session.get(MonitoredMachine, out["machine"]["id"])
    assert machine.token_hash == hashlib.sha256(token.encode()).hexdigest() and token not in str(machine.token_hash)
    assert "token" not in client.get("/api/v1/security/overview", headers=admin).get_data(as_text=True).replace("token_note", "")
    assert all(token not in (a.detail or "") for a in AuditLog.query.all())      # never written to the audit log
    assert "token" not in add_machine(client, admin, "Sim-PC")                   # simulated machines get no token


def test_token_rotation_replaces_the_old_token(client, admin):
    out = add_machine(client, admin, "Agent-PC", "agent")
    old, mid = out["token"], out["machine"]["id"]
    new = client.post(f"/api/v1/security/machines/{mid}/token", headers=admin).get_json()["token"]
    assert new != old
    body = {"window": dict.fromkeys(FEATURES, 0.0)}
    assert client.post("/api/v1/security/telemetry", headers={"X-Agent-Token": old}, json=body).status_code == 401
    assert client.post("/api/v1/security/telemetry", headers={"X-Agent-Token": new}, json=body).status_code == 200
    sim = add_machine(client, admin, "Sim-PC")["machine"]["id"]
    assert client.post(f"/api/v1/security/machines/{sim}/token", headers=admin).status_code == 400
    assert "security_token_rotated" in audit_actions()


def test_disabled_machine_cannot_send_telemetry(client, admin):
    out = add_machine(client, admin, "Agent-PC", "agent")
    headers, mid = {"X-Agent-Token": out["token"]}, out["machine"]["id"]
    body = {"window": dict.fromkeys(FEATURES, 0.0)}
    assert client.post("/api/v1/security/telemetry", headers=headers, json=body).status_code == 200
    assert client.patch(f"/api/v1/security/machines/{mid}/active", headers=admin, json={"is_active": False}).status_code == 200
    assert client.post("/api/v1/security/telemetry", headers=headers, json=body).status_code == 401
    assert client.patch(f"/api/v1/security/machines/{mid}/active", headers=admin, json={"is_active": "no"}).status_code == 400


# ------------------------------------------------------------------ telemetry from an agent
def test_telemetry_needs_a_valid_token_and_a_valid_window(client, admin):
    out = add_machine(client, admin, "Agent-PC", "agent")
    url, good = "/api/v1/security/telemetry", {"window": dict.fromkeys(FEATURES, 0.0)}
    assert client.post(url, json=good).status_code == 401
    assert client.post(url, headers={"X-Agent-Token": "hbm_wrong"}, json=good).status_code == 401
    assert client.post(url, headers={"X-Agent-Token": "x" * 500}, json=good).status_code == 401
    h = {"X-Agent-Token": out["token"]}
    assert client.post(url, headers=h, json=good).get_json() == {"received": True}
    assert client.post(url, headers=h, data="not json", content_type="text/plain").status_code == 400
    assert client.post(url, headers=h, json={"window": [1, 2, 3]}).status_code == 400
    missing = dict(good["window"])
    del missing["cpu_percent"]
    r = client.post(url, headers=h, json={"window": missing})
    assert r.status_code == 400 and "cpu_percent" in r.get_json()["error"]
    assert client.post(url, headers=h, json={"window": dict(good["window"], cpu_percent="very high")}).status_code == 400
    assert db.session.get(MonitoredMachine, out["machine"]["id"]).window_count == 1       # bad windows are not stored


def test_agent_rate_limit(client, admin):
    client.app_ref.config["MONITOR_AGENT_MAX_PER_MINUTE"] = 3
    h = {"X-Agent-Token": add_machine(client, admin, "Agent-PC", "agent")["token"]}
    body = {"window": dict.fromkeys(FEATURES, 0.0)}
    assert [client.post("/api/v1/security/telemetry", headers=h, json=body).status_code for _ in range(4)] == [200, 200, 200, 429]


def test_an_agent_attack_opens_one_incident_and_the_system_audits_it(client, admin):
    out = add_machine(client, admin, "Agent-PC", "agent")
    h = {"X-Agent-Token": out["token"]}
    for row in demo_stream("fast_encryptor", 3)[:30]:
        assert client.post("/api/v1/security/telemetry", headers=h, json={"window": window_of(row)}).status_code == 200
    incidents = client.get("/api/v1/security/incidents?status=open", headers=admin).get_json()["incidents"]
    assert len(incidents) == 1
    inc = incidents[0]
    assert inc["machine_name"] == "Agent-PC" and inc["risk_level"] in ("low", "medium", "high", "critical")
    assert inc["is_simulated"] is False and inc["reasons"] and inc["risk_why"]       # a real agent's incident is not marked as simulated
    opened = AuditLog.query.filter_by(action="security_incident_opened").all()
    assert len(opened) == 1 and opened[0].user_id is None and "Agent-PC" in opened[0].detail


# ------------------------------------------------------------------ simulated machines
def test_simulated_attack_opens_an_incident_that_escalates(client, admin):
    mid = add_machine(client, admin)["machine"]["id"]
    run = simulate(client, admin, mid, "network_spreader", 0)["run"]
    assert run["windows"] == 50 and run["played"] == 50
    overview = client.get("/api/v1/security/overview", headers=admin).get_json()
    assert overview["available"] is True and overview["open_incidents"] == 1 and overview["open_by_risk"]["critical"] == 1
    m = overview["machines"][0]
    assert m["status"] == "incident" and m["open_incident"]["risk_level"] == "critical" and m["windows"] == 50
    inc = client.get("/api/v1/security/incidents", headers=admin).get_json()["incidents"]
    assert len(inc) == 1 and inc[0]["is_simulated"] is True and inc[0]["sim_family"] == "network_spreader"
    assert {"spread", "encryption"} <= set(inc[0]["groups"])
    actions = audit_actions()
    assert actions.count("security_incident_opened") == 1 and actions.count("security_incident_escalated") == 2   # medium -> high -> critical
    assert "security_simulation_started" in actions


def test_a_normal_simulated_machine_opens_no_incident(client, admin):
    mid = add_machine(client, admin)["machine"]["id"]
    simulate(client, admin, mid, "benign", 500)
    assert client.get("/api/v1/security/incidents", headers=admin).get_json()["incidents"] == []
    assert client.get("/api/v1/security/overview", headers=admin).get_json()["machines"][0]["status"] in ("normal", "suspicious")


def test_feed_returns_windows_in_order_and_supports_after_seq(client, admin):
    mid = add_machine(client, admin)["machine"]["id"]
    simulate(client, admin, mid, "network_spreader", 0)
    feed = client.get(f"/api/v1/security/feed?machine_id={mid}&limit=60", headers=admin).get_json()
    seqs = [w["seq"] for w in feed["windows"]]
    assert seqs == sorted(seqs) and seqs[-1] == 50 and len(seqs) == 50
    first = feed["windows"][0]
    assert set(first["features"]) == set(FEATURES) and first["phase"] == "benign" and 0 <= first["score"] <= 1
    assert {w["phase"] for w in feed["windows"]} - {"benign"}                      # simulator truth for the shaded chart
    newer = client.get(f"/api/v1/security/feed?machine_id={mid}&after_seq=45", headers=admin).get_json()["windows"]
    assert [w["seq"] for w in newer] == [46, 47, 48, 49, 50]
    assert client.get("/api/v1/security/feed?machine_id=999", headers=admin).status_code == 404
    assert client.get(f"/api/v1/security/feed?machine_id={mid}&limit=abc", headers=admin).status_code == 200


def test_only_the_newest_windows_are_kept(client, admin):
    client.app_ref.config["MONITOR_KEEP_WINDOWS"] = 10
    mid = add_machine(client, admin)["machine"]["id"]
    simulate(client, admin, mid, "benign", 500)
    rows = TelemetryWindow.query.filter_by(machine_id=mid).order_by(TelemetryWindow.seq).all()
    machine = db.session.get(MonitoredMachine, mid)
    assert len(rows) == 10 and rows[-1].seq == machine.window_count and rows[0].seq == machine.window_count - 9


def test_alert_state_is_stored_so_a_restart_loses_nothing(client, admin):
    mid = add_machine(client, admin)["machine"]["id"]
    simulate(client, admin, mid, "network_spreader", 0)
    db.session.expire_all()
    state = db.session.get(MonitoredMachine, mid).alert_state
    assert set(state) == {"recent", "scores", "quiet"} and len(state["scores"]) <= 3
    assert SecurityIncident.query.filter_by(machine_id=mid).count() == 1       # the attack carried on past the cooldown: still one incident


def test_simulation_input_checks(client, admin):
    sim = add_machine(client, admin, "Sim-PC")["machine"]["id"]
    agent = add_machine(client, admin, "Agent-PC", "agent")["machine"]["id"]
    url = lambda i: f"/api/v1/security/machines/{i}/simulate"  # noqa: E731
    assert client.post(url(agent), headers=admin, json={"family": "benign"}).status_code == 400          # agents are real, not simulated
    assert client.post(url(sim), headers=admin, json={"family": "real_ransomware"}).status_code == 400
    assert client.post(url(sim), headers=admin, json={"family": "benign", "tick": 0}).status_code == 400
    assert client.post(url(sim), headers=admin, json={"family": "benign", "lead_in": 99}).status_code == 400
    assert client.post(url(sim), headers=admin, json={"family": "benign", "seed": "x"}).status_code == 400
    assert client.post(url(9999), headers=admin, json={"family": "benign"}).status_code == 404
    client.patch(f"/api/v1/security/machines/{sim}/active", headers=admin, json={"is_active": False})
    assert client.post(url(sim), headers=admin, json={"family": "benign"}).status_code == 400            # disabled


# ------------------------------------------------------------------ incidents and the SIMULATED response
def attack_incident(client, admin, name="PC-1"):
    mid = add_machine(client, admin, name)["machine"]["id"]
    simulate(client, admin, mid, "network_spreader", 0)
    return mid, client.get(f"/api/v1/security/incidents?machine_id={mid}", headers=admin).get_json()["incidents"][0]["id"]


def test_response_workflow_is_recorded_and_audited(client, admin):
    mid, iid = attack_incident(client, admin)
    base = f"/api/v1/security/incidents/{iid}"

    r = client.post(base + "/acknowledge", headers=admin, json={"note": "Looking now"})
    assert r.status_code == 200 and r.get_json()["incident"]["status"] == "acknowledged"
    assert client.post(base + "/acknowledge", headers=admin).status_code == 409

    r = client.post(base + "/respond", headers=admin, json={"action": "isolate", "note": "Pull it off the network"})
    body = r.get_json()
    assert r.status_code == 200 and body["simulated"] is True and "No real machine" in body["message"]
    assert body["incident"]["machine_isolated_simulated"] is True
    assert body["incident"]["actions"][-1]["action"] == "isolate_simulated" and body["incident"]["actions"][-1]["simulated"] is True
    assert client.post(base + "/respond", headers=admin, json={"action": "isolate"}).status_code == 409
    assert client.post(base + "/respond", headers=admin, json={"action": "delete_all_files"}).status_code == 400
    assert client.get("/api/v1/security/overview", headers=admin).get_json()["machines"][0]["isolated_simulated"] is True

    assert client.post(base + "/respond", headers=admin, json={"action": "release"}).status_code == 200
    assert client.post(base + "/respond", headers=admin, json={"action": "release"}).status_code == 409

    assert client.post(base + "/close", headers=admin, json={"outcome": "resolved"}).status_code == 400          # a note is required
    assert client.post(base + "/close", headers=admin, json={"outcome": "maybe"}).status_code == 400
    r = client.post(base + "/close", headers=admin, json={"outcome": "resolved", "note": "Machine rebuilt from backup"})
    assert r.status_code == 200 and r.get_json()["incident"]["status"] == "resolved" and r.get_json()["incident"]["closed_at"]
    assert client.post(base + "/close", headers=admin, json={"outcome": "resolved", "note": "again"}).status_code == 409
    assert client.post(base + "/respond", headers=admin, json={"action": "isolate"}).status_code == 409        # closed incident

    detail = client.get(base, headers=admin).get_json()["incident"]
    assert [a["action"] for a in detail["actions"]] == ["acknowledge", "isolate_simulated", "release_simulated", "resolved"]
    assert all(a["by"] == "Admin" for a in detail["actions"])
    assert client.get("/api/v1/security/incidents?status=open", headers=admin).get_json()["incidents"] == []
    assert len(client.get("/api/v1/security/incidents?status=closed", headers=admin).get_json()["incidents"]) == 1
    assert client.get("/api/v1/security/incidents?status=bogus", headers=admin).status_code == 400
    assert client.get("/api/v1/security/incidents/99999", headers=admin).status_code == 404

    actions = audit_actions()
    for expected in ("security_incident_acknowledged", "security_isolation_simulated", "security_release_simulated", "security_incident_resolved"):
        assert expected in actions
    isolation = AuditLog.query.filter_by(action="security_isolation_simulated").one()
    assert "SIMULATED" in isolation.detail and "no real machine" in isolation.detail and isolation.user_id is not None
    assert IncidentAction.query.filter_by(action="isolate_simulated").one().simulated is True


def test_a_false_alarm_can_be_closed_without_a_note(client, admin):
    _, iid = attack_incident(client, admin)
    r = client.post(f"/api/v1/security/incidents/{iid}/close", headers=admin, json={"outcome": "false_positive"})
    assert r.status_code == 200 and r.get_json()["incident"]["status"] == "false_positive"
    assert "security_incident_false_positive" in audit_actions()


def test_a_new_incident_opens_after_the_old_one_is_closed(client, admin):
    mid, iid = attack_incident(client, admin)
    r = client.post(f"/api/v1/security/machines/{mid}/simulate", headers=admin, json={"family": "benign"})
    assert r.status_code == 409 and f"#{iid}" in r.get_json()["error"]            # close the open incident first
    client.post(f"/api/v1/security/incidents/{iid}/close", headers=admin, json={"outcome": "resolved", "note": "done"})
    simulate(client, admin, mid, "double_extortion", 0)
    rows = client.get(f"/api/v1/security/incidents?machine_id={mid}", headers=admin).get_json()["incidents"]
    assert len(rows) == 2 and rows[0]["status"] == "open" and rows[1]["status"] == "resolved"


# ------------------------------------------------------------------ demo reset, model summary, CLI
def test_clear_demo_data_only_touches_simulated_machines(client, admin):
    sim, _ = attack_incident(client, admin, "Sim-PC")
    out = add_machine(client, admin, "Agent-PC", "agent")
    client.post("/api/v1/security/telemetry", headers={"X-Agent-Token": out["token"]}, json={"window": dict.fromkeys(FEATURES, 0.0)})
    removed = client.delete("/api/v1/security/demo-data", headers=admin).get_json()["removed"]
    assert removed["incidents"] == 1 and removed["windows"] == 50
    machines = {m["name"]: m for m in client.get("/api/v1/security/overview", headers=admin).get_json()["machines"]}
    assert machines["Sim-PC"]["windows"] == 0 and machines["Sim-PC"]["status"] == "no_data" and machines["Sim-PC"]["isolated_simulated"] is False
    assert machines["Agent-PC"]["windows"] == 1                       # a real agent's history is never wiped by the demo reset
    assert IncidentAction.query.count() == 0
    assert "security_demo_data_cleared" in audit_actions()
    simulate(client, admin, sim, "benign", 500)                       # and the machine works again from window 1
    assert client.get(f"/api/v1/security/feed?machine_id={sim}&limit=1", headers=admin).get_json()["windows"][0]["seq"] > 0


def test_model_summary_is_honest(client, admin):
    s = client.get("/api/v1/security/model", headers=admin).get_json()["summary"]
    assert s["data"]["synthetic"] is True and s["model"] == "gradient_boosting"
    text = " ".join(s["caveats"]).lower()
    assert "synthetic" in text and "simulated" in text
    assert set(s["unseen_families"]) == {"fast_encryptor", "slow_drip", "network_spreader", "double_extortion"}


def test_seed_security_command_is_repeatable(client):
    runner = client.app_ref.test_cli_runner()
    assert "3 simulated machine(s) added" in runner.invoke(args=["seed-security"]).output
    assert "0 simulated machine(s) added" in runner.invoke(args=["seed-security"]).output
    assert MonitoredMachine.query.filter_by(kind="simulated").count() == 3


# ------------------------------------------------------------------ when the detection engine is not usable
def test_the_site_survives_a_missing_or_tampered_model(client, admin, monkeypatch, tmp_path):
    mid = add_machine(client, admin)["machine"]["id"]
    source = os.path.join(client.app_ref.config["RWDETECT_PATH"], "models")
    shutil.copytree(source, tmp_path / "models")
    with open(tmp_path / "models" / "model.joblib", "ab") as fh:
        fh.write(b"tampered")                                         # the checksum in model.meta.json no longer matches
    monkeypatch.setitem(bridge._cache, "model", None)
    client.app_ref.config["RWDETECT_PATH"] = str(tmp_path)
    overview = client.get("/api/v1/security/overview", headers=admin)
    assert overview.status_code == 200 and overview.get_json()["available"] is False
    assert "could not be loaded" in overview.get_json()["message"]
    r = client.post(f"/api/v1/security/machines/{mid}/simulate", headers=admin, json={"family": "benign"})
    assert r.status_code == 503 and r.get_json()["code"] == "monitor_unavailable"
