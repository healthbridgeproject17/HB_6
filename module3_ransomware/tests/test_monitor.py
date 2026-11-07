"""Tests for the live-monitor decisions (rwdetect.monitor). The monitor logic has no web framework
and no database, so everything here runs on its own."""
import ast
import glob
import json
import os

import pytest

from rwdetect import monitor
from rwdetect.alerting import AlertRule
from rwdetect.features import BadWindow, FEATURES
from rwdetect.model import DetectorModel
from rwdetect.monitor import (assess, demo_stream, findings, model_summary, new_state, risk_level, risk_points,
                              update_incident)
from rwdetect.simulate import FAMILIES

HERE = os.path.dirname(os.path.dirname(__file__))
MODEL_PATH = os.path.join(HERE, "models", "model.joblib")
METRICS_PATH = os.path.join(HERE, "models", "metrics.json")


@pytest.fixture(scope="module")
def model():
    return DetectorModel.load(MODEL_PATH)


def quiet_window(**over):
    w = dict.fromkeys(FEATURES, 0.0)
    w.update(write_entropy_mean=4.0, cpu_percent=5.0, out_in_ratio=0.5)
    w.update(over)
    return w


def features_of(row):
    return {k: row[k] for k in FEATURES}


# ------------------------------------------------------------ what stood out
def test_quiet_window_has_no_findings():
    assert findings(quiet_window()) == []


def test_findings_name_the_behaviour_groups():
    w = quiet_window(high_entropy_write_ratio=0.95, files_modified_per_s=40, files_renamed_per_s=30, ext_change_ratio=0.95,
                     suspicious_cmd_count=2, smb_distinct_hosts=12, bytes_out_mb_per_s=8, out_in_ratio=50,
                     beacon_regularity=0.9, rare_dest_count=3, dns_nxdomain_per_s=3, distinct_dirs_touched=40)
    got = findings(w)
    assert {g for g, _ in got} == set(monitor.GROUPS)
    assert len({t for _, t in got}) == len(got)           # no sentence twice


def test_archiving_alone_is_not_flagged_as_encryption():
    # a zip job: random-looking data, but only one file per second and no renames
    assert findings(quiet_window(high_entropy_write_ratio=0.95, files_modified_per_s=1, write_entropy_mean=7.9)) == []


def test_findings_reject_bad_windows():
    with pytest.raises(BadWindow):
        findings({"files_modified_per_s": 1})


# ------------------------------------------------------------ risk levels (worked by hand)
@pytest.mark.parametrize("score,groups,above,expected_total,expected_level", [
    (0.80, [], 2, 0, "low"),                                                    # barely over the threshold, nothing to point at
    (0.93, ["encryption"], 2, 2, "low"),                                        # 1 + 1 + 0
    (0.99, ["encryption"], 2, 3, "medium"),                                     # 2 + 1 + 0
    (0.99, ["encryption", "backup_tampering"], 2, 4, "high"),                   # 2 + 2 + 0
    (0.99, ["encryption"], 6, 4, "high"),                                       # 2 + 1 + 1 (30 s)
    (0.99, ["encryption"], 24, 5, "high"),                                      # 2 + 1 + 2 (2 min): one behaviour alone stays High
    (0.99, ["encryption", "spread", "outside_contact"], 2, 5, "high"),          # 2 + 3 + 0
    (0.99, ["encryption", "spread", "outside_contact"], 6, 6, "critical"),      # 2 + 3 + 1
    (0.99, ["encryption", "backup_tampering"], 24, 6, "critical"),              # 2 + 2 + 2
    (0.99, list(monitor.GROUPS), 99, 7, "critical"),                            # behaviour points are capped at 3
])
def test_risk_points_and_level(score, groups, above, expected_total, expected_level):
    assert risk_points(score, groups, above)["total"] == expected_total
    assert risk_level(score, groups, above) == expected_level


def test_more_evidence_never_lowers_risk():
    order = {lvl: i for i, lvl in enumerate(monitor.LEVELS)}
    base = order[risk_level(0.95, ["encryption"], 2)]
    assert order[risk_level(0.99, ["encryption"], 2)] >= base
    assert order[risk_level(0.95, ["encryption", "spread"], 2)] >= base
    assert order[risk_level(0.95, ["encryption"], 30)] >= base


# ------------------------------------------------------------ one window at a time
def test_streaming_assess_matches_the_batch_alert_rule(model):
    rows = demo_stream("fast_encryptor", seed=3)
    state, flags, alerts = new_state(), [], []
    for i, r in enumerate(rows):
        state = json.loads(json.dumps(state))              # state must survive being stored as JSON between windows
        v = assess(model, features_of(r), state)
        state = v.state
        flags.append(v.above)
        if v.alert:
            alerts.append(i)
    assert alerts == model.rule.alerts(flags)
    assert alerts                                           # the attack was noticed


def test_state_is_small_and_json_safe(model):
    v = assess(model, quiet_window(), None)
    json.dumps(v.state)
    assert set(v.state) == {"recent", "scores", "quiet"}
    assert len(v.state["scores"]) <= model.rule.m


def test_assess_rejects_unusable_windows(model):
    with pytest.raises(BadWindow):
        assess(model, {"cpu_percent": "high"}, None)
    bad = quiet_window()
    bad["cpu_percent"] = float("nan")
    with pytest.raises(BadWindow):
        assess(model, bad, None)


def test_out_of_range_numbers_are_clipped_not_crashing(model):
    v = assess(model, quiet_window(cpu_percent=5000, files_modified_per_s=1e12), None)
    assert 0.0 <= v.score <= 1.0


# ------------------------------------------------------------ incidents
def run_stream(model, rows, threshold=None):
    threshold = model.threshold if threshold is None else threshold
    state, incident, log = new_state(), None, []
    for i, r in enumerate(rows):
        v = assess(model, features_of(r), state)
        state = v.state
        incident, event = update_incident(incident, v, threshold)
        if event:
            log.append((i, event, incident["risk"]))
    return incident, log


@pytest.mark.parametrize("family", FAMILIES)
def test_attacks_open_exactly_one_incident_and_it_is_reported_once(model, family):
    caught = 0
    for seed in range(10):
        incident, log = run_stream(model, demo_stream(family, seed))
        if incident is None:
            continue
        caught += 1
        assert [e for _, e, _ in log].count("opened") == 1
        assert log[0][1] == "opened"
        # never before the attack starts (lead-in is 8 windows = no false alarm), and within 4 minutes.
        # Fast attacks open within a few windows; a slow "sleeping" attack can take much longer (see the model card).
        assert 8 <= log[0][0] <= 8 + 45
    assert caught >= 9                                       # at least 9 of 10 simulated attacks noticed


def test_risk_only_goes_up_within_an_incident(model):
    order = {lvl: i for i, lvl in enumerate(monitor.LEVELS)}
    for seed in range(8):
        _, log = run_stream(model, demo_stream("double_extortion", seed))
        ranks = [order[r] for _, _, r in log]
        assert ranks == sorted(ranks)
        assert [e for _, e, _ in log].count("escalated") == len({r for r in ranks}) - 1


def test_long_attack_ends_at_high_or_critical(model):
    for seed in range(8):
        incident, _ = run_stream(model, demo_stream("network_spreader", seed))
        assert incident["risk"] in ("high", "critical")
        assert incident["windows_above"] >= monitor.LONG_WINDOWS
        assert incident["risk_why"] and len(incident["reasons"]) <= monitor.MAX_REASONS


def test_normal_machines_rarely_open_incidents_and_never_critical(model):
    opened = 0
    for seed in range(40):
        incident, _ = run_stream(model, demo_stream("benign", 500 + seed))
        if incident:
            opened += 1
            assert incident["risk"] in ("low", "medium")
    assert opened <= 2                                       # 40 machines x 7+ minutes of ordinary use


def test_one_noisy_window_is_not_an_incident(model):
    spike = quiet_window(high_entropy_write_ratio=0.99, files_modified_per_s=300, files_renamed_per_s=250, ext_change_ratio=0.99,
                         write_entropy_mean=7.95, distinct_dirs_touched=60)
    rows = [quiet_window()] * 5 + [spike] + [quiet_window()] * 6
    incident, log = run_stream(model, [dict(r) for r in rows])
    assert incident is None and log == []


def test_update_with_no_incident_and_no_alert_changes_nothing(model):
    v = assess(model, quiet_window(), None)
    assert update_incident(None, v, model.threshold) == (None, None)


# ------------------------------------------------------------ simulated machines
def test_demo_stream_starts_the_attack_after_the_lead_in():
    rows = demo_stream("fast_encryptor", seed=5, lead_in=8)
    phases = [r["phase"] for r in rows]
    assert set(phases[:8]) == {"benign"} and phases[8] != "benign"
    assert set(rows[0]) == set(FEATURES) | {"phase", "family"}


def test_benign_stream_has_no_attack_and_is_repeatable():
    a, b = demo_stream("benign", seed=9), demo_stream("benign", seed=9)
    assert a == b and {r["phase"] for r in a} == {"benign"}
    assert demo_stream("benign", seed=10) != a


def test_demo_stream_rejects_unknown_family_and_caps_length():
    with pytest.raises(ValueError):
        demo_stream("real_malware", 1)
    assert len(demo_stream("benign", 1, max_windows=30)) == 30


# ------------------------------------------------------------ model summary and safety
def test_model_summary_is_honest():
    s = model_summary(json.load(open(METRICS_PATH)))
    assert s["data"]["synthetic"] is True and s["model"] == "gradient_boosting"
    assert set(s["unseen_families"]) == set(FAMILIES)
    text = " ".join(s["caveats"]).lower()
    assert "synthetic" in text and "simulated" in text and "never-seen" in text
    assert s["seen_families"]["false_alarms_upper95_per_machine_hour"] > s["seen_families"]["false_alarms_per_machine_hour"]


def test_the_package_cannot_touch_the_system():
    """Safety check: no rwdetect file imports anything that could run programs, open sockets or copy/delete files."""
    forbidden = {"subprocess", "socket", "shutil", "requests", "urllib", "http", "ctypes", "multiprocessing", "ftplib", "smtplib"}
    for path in glob.glob(os.path.join(HERE, "rwdetect", "*.py")):
        tree = ast.parse(open(path, encoding="utf-8").read())
        for node in ast.walk(tree):
            names = [a.name.split(".")[0] for a in node.names] if isinstance(node, ast.Import) else \
                    [(node.module or "").split(".")[0]] if isinstance(node, ast.ImportFrom) and node.level == 0 else []
            assert not (set(names) & forbidden), f"{os.path.basename(path)} imports {set(names) & forbidden}"
