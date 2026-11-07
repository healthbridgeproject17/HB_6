import json
import os

import numpy as np
import pandas as pd
import pytest

from rwdetect import train
from rwdetect.alerting import AlertRule
from rwdetect.dataset import build_dataset, split_runs
from rwdetect.evaluate import choose_threshold, poisson_upper, precision_at_prevalence, run_level, window_metrics, wilson
from rwdetect.features import BadWindow, FEATURES
from rwdetect.model import DetectorModel
from rwdetect.simulate import FAMILIES


# ---------------------------------------------------------------- splitting
def test_split_is_by_whole_run_and_covers_every_family():
    df = build_dataset(60, 10, seed=1)
    parts = split_runs(df, seed=2)
    ids = {k: set(v.run_id) for k, v in parts.items()}
    assert not (ids["train"] & ids["val"]) and not (ids["train"] & ids["test"]) and not (ids["val"] & ids["test"])
    assert sum(len(v) for v in ids.values()) == df.run_id.nunique()
    for part in parts.values():
        assert set(part.family) == {"benign", *FAMILIES}
    assert 0.5 < len(ids["train"]) / df.run_id.nunique() < 0.7


# ---------------------------------------------------------------- alert rule
def test_alert_needs_k_of_m_then_waits_for_cooldown():
    rule = AlertRule(k=2, m=3, cooldown=4)
    assert rule.alerts([1, 0, 0, 0, 0, 0]) == []                      # one blip is not an alert
    assert rule.alerts([1, 0, 1, 0, 0, 0]) == [2]                     # 2 of the last 3
    assert rule.alerts([1, 1, 1, 1, 1, 1, 1, 1, 1, 1]) == [1, 6]      # one alert per episode
    with pytest.raises(ValueError):
        AlertRule(k=4, m=3)


def test_streaming_state_matches_batch():
    rng = np.random.default_rng(0)
    flags = rng.random(300) < 0.3
    rule = AlertRule()
    state = rule.state()
    assert [i for i, f in enumerate(flags) if state.update(bool(f))] == rule.alerts(flags)


# ---------------------------------------------------------------- measurement
def test_threshold_keeps_false_positives_under_the_limit():
    rng = np.random.default_rng(1)
    y = np.r_[np.zeros(5000), np.ones(500)]
    s = np.r_[rng.normal(0, 1, 5000), rng.normal(2, 1, 500)]
    for target in (0.05, 0.01, 0.001):
        thr = choose_threshold(y, s, target)
        assert window_metrics(y, s, thr)["false_positive_rate"] <= target


def test_window_metrics_on_known_cases():
    y = np.array([0, 0, 0, 1, 1])
    good = window_metrics(y, np.array([0.1, 0.2, 0.3, 0.8, 0.9]), 0.5)
    assert good["roc_auc"] == 1 and good["precision"] == 1 and good["recall"] == 1 and good["false_positive_rate"] == 0
    bad = window_metrics(y, np.array([0.9, 0.8, 0.7, 0.2, 0.1]), 0.5)
    assert bad["recall"] == 0 and bad["roc_auc"] == 0


def test_run_level_counts_catches_delay_and_false_alarms():
    def run(run_id, family, onset, scores):
        return pd.DataFrame({"run_id": run_id, "window": range(len(scores)), "family": family, "onset": onset, "label": [int(i >= onset >= 0) for i in range(len(scores))], "s": scores})
    hi, lo = 0.9, 0.1
    attack_ok = run(1, "fast_encryptor", 20, [lo] * 20 + [lo, hi, hi, hi] + [hi] * 10)       # first alert 2 windows after the onset
    attack_missed = run(2, "slow_drip", 20, [lo] * 40)
    attack_early = run(3, "slow_drip", 30, [hi, hi] + [lo] * 28 + [lo] * 10)                    # alert BEFORE the attack = false alarm
    benign_noisy = run(4, "benign", -1, [hi, hi] + [lo] * 98)
    benign_quiet = run(5, "benign", -1, [lo] * 100)
    df = pd.concat([attack_ok, attack_missed, attack_early, benign_noisy, benign_quiet], ignore_index=True)
    r = run_level(df, df.s.to_numpy(), 0.5, AlertRule(k=2, m=3, cooldown=12))
    assert r["attack_runs"] == 3 and r["attacks_caught"] == 1 and abs(r["detection_rate"] - 1 / 3) < 1e-9
    assert r["median_delay_windows"] == 2 and r["false_alarms"] == 2
    assert r["by_family"]["fast_encryptor"]["detection_rate"] == 1 and r["by_family"]["slow_drip"]["detection_rate"] == 0
    assert r["benign_hours"] == pytest.approx((200 + 20 + 20 + 30) * 5 / 3600)


def test_confidence_intervals_are_honest_about_small_samples():
    low, high = wilson(40, 40)
    assert 0.9 < low < 1.0 and high == pytest.approx(1.0)
    assert wilson(0, 0) == [0.0, 1.0]
    assert poisson_upper(0, 25) == pytest.approx(3.69 / 25, rel=0.02)          # "rule of three"
    assert poisson_upper(5, 25) > 5 / 25


def test_base_rate_makes_precision_collapse():
    assert precision_at_prevalence(0.95, 0.001, 0.1) > 0.9
    assert precision_at_prevalence(0.95, 0.001, 1e-6) < 0.001


# ---------------------------------------------------------------- the whole pipeline, small
@pytest.fixture(scope="module")
def trained(tmp_path_factory):
    out = tmp_path_factory.mktemp("models")
    metrics = train.run(n_benign=80, n_per_family=10, seed=11, out_dir=str(out), log=lambda *a: None, with_ablation=False)
    return out, metrics


def test_training_writes_model_metrics_and_card(trained):
    out, m = trained
    for name in ("model.joblib", "model.meta.json", "metrics.json", "MODEL_CARD.md"):
        assert os.path.isfile(out / name)
    assert m["chosen"] in train.SUPERVISED
    card = (out / "MODEL_CARD.md").read_text(encoding="utf-8")
    for heading in ("not trained or tested on real ransomware", "Models compared", "Unseen attack types", "Limits you should state out loud", "Choosing how sensitive"):
        assert heading in card
    assert json.load(open(out / "metrics.json"))["sha256"] == m["sha256"]


def test_learned_models_beat_the_naive_baselines(trained):
    _, m = trained
    best = m["models"][m["chosen"]]
    assert best["test_windows"]["pr_auc"] > 0.8 and best["test_runs"]["detection_rate"] >= 0.7
    assert best["test_windows"]["pr_auc"] > m["models"]["isolation_forest"]["test_windows"]["pr_auc"]
    assert set(m["leave_one_family_out"]["gradient_boosting"]) == set(FAMILIES)


def test_saved_model_loads_scores_and_checks_its_checksum(trained):
    out, m = trained
    path = str(out / "model.joblib")
    model = DetectorModel.load(path, expected_sha256=m["sha256"])
    assert model.kind == m["chosen"] and model.rule.as_dict() == m["alert_rule"]
    df = build_dataset(10, 3, seed=99)
    attack = df[(df.phase == "encrypt") & (df.family == "fast_encryptor")].iloc[0]
    quiet = df[(df.family == "benign") & (df.benign_profile == "idle")].iloc[0]
    s_attack, s_quiet = model.score_window(attack[FEATURES].to_dict()), model.score_window(quiet[FEATURES].to_dict())
    assert 0 <= s_quiet <= 1 and s_attack >= model.threshold > s_quiet
    with pytest.raises(ValueError):
        DetectorModel.load(path, expected_sha256="0" * 64)
    with pytest.raises(BadWindow):
        model.score_window({"cpu_percent": 5})


# ---------------------------------------------------------------- the shipped model and the demo
SHIPPED = os.path.join(os.path.dirname(__file__), "..", "models", "model.joblib")


@pytest.mark.skipif(not os.path.isfile(SHIPPED), reason="shipped model not present")
def test_demo_catches_an_attack_and_leaves_a_normal_machine_alone():
    from rwdetect.demo import run_demo
    caught = [run_demo("fast_encryptor", seed=s)["delay_windows"] for s in range(1, 9)]
    assert sum(d is not None for d in caught) >= 7
    quiet = [run_demo("benign", seed=s)["false_alarms"] for s in range(1, 9)]
    assert sum(quiet) <= 2
    lines = []
    run_demo("slow_drip", seed=3, show=lines.append)
    assert lines and "simulator truth" in lines[0]
