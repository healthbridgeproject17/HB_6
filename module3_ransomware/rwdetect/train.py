"""Builds the synthetic data, compares detection models, picks one, and writes the
model together with an honest model card.

    python -m rwdetect.train            full run (a couple of minutes)
    python -m rwdetect.train --small    quick run for testing"""
import argparse
import json
import os
import time

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier, IsolationForest, RandomForestClassifier
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, StandardScaler

from . import __version__
from .alerting import AlertRule
from .dataset import build_dataset, save_csv, split_runs
from .evaluate import choose_threshold, precision_at_prevalence, run_level, window_metrics
from .features import FEATURES, FEATURE_INFO, WINDOW_SECONDS
from .model import DetectorModel, RuleBaseline, raw_scores
from .simulate import FAMILIES

OPERATING_FPRS = [0.005, 0.002, 0.001, 0.0005, 0.0002, 0.0001]   # share of normal windows allowed above the threshold
MIN_DETECTION = 0.90     # operating point rule: the fewest false alarms that still catch at least 90% of attacks (on validation data)
SUPERVISED = ["logistic_regression", "random_forest", "gradient_boosting"]
LABELS = {"logistic_regression": "Logistic regression", "random_forest": "Random forest", "gradient_boosting": "Gradient boosting",
          "isolation_forest": "Isolation forest (no attack examples)", "rule_baseline": "Simple hand-written rule"}


def make(name, seed):
    if name == "logistic_regression":
        return Pipeline([("log", FunctionTransformer(np.log1p)), ("scale", StandardScaler()), ("clf", LogisticRegression(max_iter=3000, class_weight="balanced"))])
    if name == "random_forest":
        return RandomForestClassifier(n_estimators=100, max_depth=12, min_samples_leaf=10, class_weight="balanced_subsample", n_jobs=-1, random_state=seed)
    if name == "gradient_boosting":
        return HistGradientBoostingClassifier(max_iter=150, max_depth=6, learning_rate=0.1, class_weight="balanced", random_state=seed)
    if name == "isolation_forest":
        return IsolationForest(n_estimators=200, random_state=seed, n_jobs=-1)
    return RuleBaseline()


def fit(name, train, seed):
    est = make(name, seed)
    if name == "isolation_forest":
        est.fit(train.loc[train.label == 0, FEATURES])      # learns only what normal looks like
    elif name == "rule_baseline":
        est.fit(None)
    else:
        est.fit(train[FEATURES], train.label)
    return est


def operating_points(est, splits, rule):
    val_s, test_s = raw_scores(est, splits["val"]), raw_scores(est, splits["test"])
    points = []
    for f in OPERATING_FPRS:
        thr = choose_threshold(splits["val"].label, val_s, f)
        v, t = run_level(splits["val"], val_s, thr, rule), run_level(splits["test"], test_s, thr, rule)
        w = window_metrics(splits["test"].label, test_s, thr)
        points.append({"max_fpr": f, "threshold": thr, "val_detection": v["detection_rate"], "val_false_alarms_per_hour": v["false_alarms_per_machine_hour"],
                       "test_detection": t["detection_rate"], "test_false_alarms_per_hour": t["false_alarms_per_machine_hour"],
                       "test_median_delay_windows": t["median_delay_windows"], "test_window_recall": w["recall"], "test_window_pr_auc": w["pr_auc"]})
    return points


def pick_point(points):
    ok = [p for p in points if p["val_detection"] >= MIN_DETECTION]
    return min(ok, key=lambda p: (p["val_false_alarms_per_hour"], -p["val_detection"])) if ok else max(points, key=lambda p: p["val_detection"])


def ablation(name, splits, seed):
    """Retrain without each feature in turn. If dropping ONE feature collapses the score,
    the data has a shortcut (or the detector depends on a single sensor)."""
    from sklearn.metrics import average_precision_score
    train, test = splits["train"], splits["test"]

    def score(cols):
        est = make(name, seed)
        est.fit(train[cols], train.label)
        return average_precision_score(test.label, est.predict_proba(test[cols])[:, 1])

    base = score(FEATURES)
    return {"baseline_pr_auc": base, "drops": sorted(({"feature": f, "pr_auc_without": score([c for c in FEATURES if c != f])} for f in FEATURES),
                                                      key=lambda d: d["pr_auc_without"])}


def lofo(name, splits, full, seed, rule, max_fpr):
    """Leave one attack family out: train WITHOUT it, then see whether it is still caught."""
    out = {}
    for family in FAMILIES:
        keep = lambda d: d[d.family != family]  # noqa: E731
        est = fit(name, keep(splits["train"]), seed)
        val = keep(splits["val"])
        thr = choose_threshold(val.label, raw_scores(est, val), max_fpr)
        held = full[full.family == family]
        evalset = __import__("pandas").concat([splits["test"][splits["test"].family == "benign"], held], ignore_index=True)
        s = raw_scores(est, evalset)
        w = window_metrics(evalset.label, s, thr)
        r = run_level(evalset, s, thr, rule)
        out[family] = {"window_recall": w["recall"], "detection_rate": r["by_family"][family]["detection_rate"],
                       "median_delay_windows": r["by_family"][family]["median_delay_windows"]}
    return out


def run(n_benign=500, n_per_family=50, seed=42, out_dir="models", log=print, with_ablation=True):
    started = time.time()
    rule = AlertRule()
    log(f"Building the synthetic data set ({n_benign} benign + {n_per_family * len(FAMILIES)} attack runs)...")
    df = build_dataset(n_benign, n_per_family, seed)
    splits = split_runs(df, seed=seed + 1)
    log(f"  {len(df):,} windows, {df.label.mean():.1%} of them attack; train/val/test runs: " + "/".join(str(s.run_id.nunique()) for s in splits.values()))

    results, fitted, points = {}, {}, {}
    for name in SUPERVISED + ["isolation_forest", "rule_baseline"]:
        est = fit(name, splits["train"], seed)
        fitted[name] = est
        points[name] = operating_points(est, splits, rule)
        op = pick_point(points[name])
        test_s, val_s = raw_scores(est, splits["test"]), raw_scores(est, splits["val"])
        results[name] = {"threshold": op["threshold"], "max_fpr": op["max_fpr"], "validation_pr_auc": window_metrics(splits["val"].label, val_s, op["threshold"])["pr_auc"],
                         "test_windows": window_metrics(splits["test"].label, test_s, op["threshold"]), "test_runs": run_level(splits["test"], test_s, op["threshold"], rule),
                         "operating_points": points[name]}
        log(f"  {LABELS[name]:40} test PR-AUC {results[name]['test_windows']['pr_auc']:.3f}  window recall {results[name]['test_windows']['recall']:.2f}  "
            f"attacks caught {results[name]['test_runs']['detection_rate']:.0%}  false alarms/machine-hour {results[name]['test_runs']['false_alarms_per_machine_hour']:.3f}")

    best = max(SUPERVISED, key=lambda n: results[n]["validation_pr_auc"])
    log(f"Chosen (best validation PR-AUC): {LABELS[best]}")
    log("Leave-one-family-out check (how it copes with an attack type it has never seen)...")
    holdout = {n: lofo(n, splits, df, seed, rule, results[n]["max_fpr"]) for n in SUPERVISED}
    sample = splits["val"].sample(min(15000, len(splits["val"])), random_state=seed)
    imp = permutation_importance(fitted[best], sample[FEATURES], sample.label, scoring="average_precision", n_repeats=3, random_state=seed)
    importance = sorted(zip(FEATURES, imp.importances_mean), key=lambda x: -x[1])
    log("Dropping each feature in turn (shortcut check)...")
    ablate = ablation(best, splits, seed) if with_ablation else None

    metrics = {"version": __version__, "seed": seed, "min_detection_rule": MIN_DETECTION, "alert_rule": rule.as_dict(), "chosen": best,
               "data": {"windows": len(df), "attack_share": float(df.label.mean()), "benign_runs": n_benign, "attack_runs_per_family": n_per_family,
                        "window_seconds": WINDOW_SECONDS, "families": FAMILIES}, "models": results, "leave_one_family_out": holdout,
               "feature_importance": [{"feature": f, "importance": float(v)} for f, v in importance], "ablation": ablate}
    os.makedirs(out_dir, exist_ok=True)
    model = DetectorModel(fitted[best], best, results[best]["threshold"], rule,
                          meta={"library": "scikit-learn", "trained_on": "synthetic telemetry", "seed": seed, "test_pr_auc": results[best]["test_windows"]["pr_auc"],
                                "test_detection_rate": results[best]["test_runs"]["detection_rate"], "rwdetect_version": __version__})
    metrics["sha256"] = model.save(os.path.join(out_dir, "model.joblib"))
    json.dump(metrics, open(os.path.join(out_dir, "metrics.json"), "w"), indent=2)
    open(os.path.join(out_dir, "MODEL_CARD.md"), "w", encoding="utf-8").write(model_card(metrics))
    sample_rows = df.groupby("family", group_keys=False).apply(lambda g: g.sample(min(len(g), 150), random_state=seed))
    save_csv(sample_rows.sort_values(["run_id", "window"]), os.path.join(os.path.dirname(out_dir) or ".", "data", "sample_windows.csv")) if os.path.isdir(os.path.join(os.path.dirname(out_dir) or ".", "data")) else None
    log(f"Done in {time.time() - started:.0f}s. Model, metrics and model card written to {out_dir}")
    return metrics


def model_card(m):
    best = m["chosen"]
    r, w = m["models"][best]["test_runs"], m["models"][best]["test_windows"]
    rows = "\n".join(f"| {LABELS[n]} | {v['test_windows']['pr_auc']:.3f} | {v['test_windows']['recall']:.0%} | {v['test_windows']['false_positive_rate']:.2%} | "
                     f"{v['test_runs']['detection_rate']:.0%} | {v['test_runs']['false_alarms_per_machine_hour']:.2f} |" for n, v in m["models"].items())
    fam = "\n".join(f"| {f} | {v['detection_rate']:.0%} | {v['median_delay_windows'] if v['median_delay_windows'] is not None else 'never'} |" for f, v in r["by_family"].items())
    lo = "\n".join(f"| {f} | " + " | ".join(f"{m['leave_one_family_out'][n][f]['detection_rate']:.0%}" for n in SUPERVISED) + " |" for f in FAMILIES)
    imp = "\n".join(f"| {x['feature']} | {FEATURE_INFO[x['feature']][1]} | {x['importance']:.3f} |" for x in m["feature_importance"][:8])
    per_year = r["false_alarms_per_machine_hour"] * 24 * 365
    op_rows = "\n".join(f"| {p['max_fpr']:.2%}{' (chosen)' if abs(p['threshold'] - m['models'][best]['threshold']) < 1e-12 else ''} | {p['test_detection']:.0%} | {p['test_median_delay_windows'] if p['test_median_delay_windows'] is not None else 'never'} | "
                         f"{p['test_false_alarms_per_hour']:.3f} | {p['test_window_recall']:.0%} |" for p in m["models"][best]["operating_points"])
    ab = m.get("ablation")
    ab_text = ("\n## Shortcut check (retrain without one feature at a time)\nBaseline PR-AUC "
               f"{ab['baseline_pr_auc']:.3f}. The five features whose removal hurts most:\n\n| Feature removed | PR-AUC without it |\n|---|---|\n"
               + "\n".join(f"| {d['feature']} | {d['pr_auc_without']:.3f} |" for d in ab["drops"][:5]) +
               "\n\nIf one row collapses, the data has a shortcut or the detector leans on one sensor.\n") if ab else ""
    return f"""# Model card: HealthBridge ransomware detector (v{m['version']})

**What it is.** A classifier that scores each {m['data']['window_seconds']}-second window of endpoint and network telemetry from 0 (normal) to 1 (looks like ransomware),
plus an alert rule: **{m['alert_rule']['k']} high windows out of the last {m['alert_rule']['m']}**, then a {m['alert_rule']['cooldown']}-window quiet period.
Chosen model: **{LABELS[best]}**. The alert threshold is the one with the fewest false alarms that still catches at least {m['min_detection_rule']:.0%} of attacks on validation data.

**What it is NOT.** It is not trained or tested on real ransomware or real company traffic. It is a method demonstration on synthetic data. Do not rely on it to protect real systems.

## Data (synthetic)
{m['data']['windows']:,} windows ({m['data']['attack_share']:.0%} attack) from {m['data']['benign_runs']} normal virtual machines and {m['data']['attack_runs_per_family']} attack runs for each of
4 behaviour families ({', '.join(m['data']['families'])}). Every distribution is an assumption written from published descriptions of ransomware behaviour.
Normal activity includes deliberately confusing cases: archiving (random-looking writes), photo imports (many renames), IT admin work (backup commands), file-server use (many machines contacted).
Each run is an independent virtual machine, and train / validation / test are split by whole run, so no machine is in two sets.

## Models compared (test set, never used for choosing anything)
| Model | PR-AUC | Window recall | Window false-positive rate | Attacks caught (with alert rule) | False alarms per machine-hour |
|---|---|---|---|---|---|
{rows}

## Choosing how sensitive to be (chosen model, test data)
A stricter threshold means fewer false alarms but more missed or slower detections. Pick the row that fits how many false alarms people will tolerate.

| Normal windows allowed above threshold | Attacks caught | Median delay (windows) | False alarms per machine-hour | Window recall |
|---|---|---|---|---|
{op_rows}

## Result for the chosen model with the alert rule
- Attacks caught: **{r['detection_rate']:.0%}** of {r['attack_runs']} test attack runs (95% confidence interval {r['detection_ci95'][0]:.0%} to {r['detection_ci95'][1]:.0%}); median delay **{r['median_delay_windows']} windows ({r['median_delay_seconds']:.0f} s)** after the first malicious activity.
- False alarms: **{r['false_alarms_per_machine_hour']:.3f} per machine-hour** on normal activity, measured over only **{r['benign_hours']:.0f} hours** of test data. The 95% upper bound is **{r['false_alarms_upper95_per_machine_hour']:.2f} per machine-hour**: a few dozen hours cannot show a rate this small, so real tuning needs weeks of real normal traffic.
- Window-level false-positive rate and the false alarm rate above are different things: one false alarm needs several high windows in a row.

| Attack family | Caught | Median delay (windows) |
|---|---|---|
{fam}

## Unseen attack types (leave one family out)
Trained without the family in the row, then asked to find it. This is closer to real life than the table above, because real attackers are not in your training data.

| Held-out family | {' | '.join(LABELS[n] for n in SUPERVISED)} |
|---|{'---|' * len(SUPERVISED)}
{lo}

## What drives the score (permutation importance on validation data)
| Feature | Meaning | Importance |
|---|---|---|
{imp}

{ab_text}
## Limits you should state out loud
1. **Synthetic data.** Scores here show the model learns the assumptions in the simulator (an earlier version of the simulator had a shortcut, found by checking feature importance, which made every result 100%). Real telemetry will be messier and results will be worse.
2. **Base rates.** Real attacks are extremely rare. Even a rate of {r['false_alarms_per_machine_hour']:.3f} false alarms per machine-hour is about {per_year:,.0f} per machine per year, and attacks are rare, so on a real network almost every alert would be a false alarm unless the threshold is tuned on real normal traffic. A real deployment must be tuned on real normal traffic.
3. **Adaptive attackers.** An attacker who knows the thresholds can slow down (see slow_drip) or imitate normal activity.
4. **Telemetry gaps.** The model assumes an agent reports all 18 numbers every {m['data']['window_seconds']} seconds. Missing or tampered telemetry is a blind spot.
5. **Model file safety.** The model is a Python pickle (SHA-256 `{m['sha256'][:16]}...`). Only load files you created.
6. **Response.** The system recommends and records a SIMULATED isolation. It never changes a real machine or network.
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--small", action="store_true")
    ap.add_argument("--out", default="models")
    a = ap.parse_args()
    run(*(150, 20) if a.small else (500, 50), out_dir=a.out, with_ablation=not a.small)


if __name__ == "__main__":
    main()
