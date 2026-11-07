import numpy as np
import pytest
from sklearn.metrics import roc_auc_score

from rwdetect.features import BadWindow, FEATURE_INFO, FEATURES, clean_window
from rwdetect.simulate import FAMILIES, build_dataset, simulate_run


@pytest.fixture(scope="module")
def df():
    return build_dataset(120, 15, seed=3)


def test_same_seed_same_data_and_different_seed_different_data():
    a, b = build_dataset(8, 2, seed=5), build_dataset(8, 2, seed=5)
    assert a.equals(b) and not a.equals(build_dataset(8, 2, seed=6))


def test_schema_and_value_ranges(df):
    assert len(FEATURES) == 18 and set(FEATURES) <= set(df.columns)
    assert np.isfinite(df[FEATURES].to_numpy()).all()
    for name, (_, _, lo, hi) in FEATURE_INFO.items():
        assert df[name].min() >= lo - 1e-9 and df[name].max() <= hi + 1e-9, name


def test_labels_follow_the_attack_timeline(df):
    assert set(df.family.unique()) == {"benign", *FAMILIES}
    assert df[df.family == "benign"].label.eq(0).all()
    for run_id, g in df[df.family != "benign"].groupby("run_id"):
        onset = int(g.onset.iloc[0])
        assert 20 <= onset <= 70
        assert g[g.window < onset].label.eq(0).all() and (g[g.window >= onset].label == 1).any()
        assert g[g.phase == "sleep"].label.eq(0).all()


def test_slow_attackers_really_do_sleep(df):
    assert (df[df.family == "slow_drip"].phase == "sleep").mean() > 0.1


def test_no_single_number_gives_the_answer_away(df):
    aucs = {f: roc_auc_score(df.label, df[f]) for f in FEATURES}
    assert max(aucs.values()) < 0.95, aucs


def test_normal_activity_contains_the_confusing_cases(df):
    b = df[df.label == 0]
    assert (b.high_entropy_write_ratio > 0.9).mean() > 0.02        # archiving looks like encryption
    assert (b.suspicious_cmd_count > 0).mean() > 0.02              # IT admin work
    assert (b.smb_distinct_hosts >= 3).mean() > 0.01               # file-server users
    assert (b.files_renamed_per_s > 5).mean() > 0.02               # photo import / git
    assert (b.ext_change_ratio > 0.5).mean() > 0.02                # .tmp -> .docx, .crdownload -> .pdf


def test_regression_the_beacon_shortcut_is_gone(df):
    """An earlier version gave every encryption window a fixed beacon value, which made detection trivial."""
    enc = df[(df.family == "fast_encryptor") & (df.phase == "encrypt")]
    benign = df[df.label == 0]
    assert abs(enc.beacon_regularity.median() - benign.beacon_regularity.median()) < 0.15


def test_attack_runs_start_from_normal_activity():
    rows = simulate_run(np.random.SeedSequence(1), 0, "fast_encryptor")
    assert rows[0]["phase"] == "benign" and rows[-1]["phase"] in ("encrypt", "sleep")


# ---------------------------------------------------------------- telemetry from an agent
GOOD = {f: 1.0 for f in FEATURES}


def test_clean_window_accepts_good_input_and_clips():
    w = dict(GOOD, cpu_percent=250, high_entropy_write_ratio=-1, files_modified_per_s="12.5")
    out = clean_window(w)
    assert out["cpu_percent"] == 100 and out["high_entropy_write_ratio"] == 0 and out["files_modified_per_s"] == 12.5


@pytest.mark.parametrize("change", [{"cpu_percent": None}, {"cpu_percent": "abc"}, {"cpu_percent": float("nan")}, {"cpu_percent": float("inf")}])
def test_clean_window_rejects_unusable_values(change):
    with pytest.raises(BadWindow):
        clean_window(dict(GOOD, **change))


def test_clean_window_rejects_missing_fields():
    w = dict(GOOD)
    del w["beacon_regularity"]
    with pytest.raises(BadWindow) as exc:
        clean_window(w)
    assert "beacon_regularity" in str(exc.value)
