"""Honest measurement: window-level scores, and the numbers an operator cares about
(how many attacks are caught, how fast, and how many false alarms per machine-hour)."""
import numpy as np
from scipy.stats import chi2
from sklearn.metrics import average_precision_score, roc_auc_score

from .alerting import AlertRule
from .features import WINDOW_SECONDS


def choose_threshold(y, scores, max_fpr=0.005):
    """The lowest threshold whose false-positive rate on benign windows is at most max_fpr."""
    benign = np.sort(np.asarray(scores)[np.asarray(y) == 0])[::-1]
    k = int(np.floor(max_fpr * len(benign)))
    return float(np.nextafter(benign[min(k, len(benign) - 1)], np.inf))


def wilson(k, n, z=1.96):
    """95% confidence interval for a rate k/n (n is often small, so a plain percentage is misleading)."""
    if n == 0:
        return [0.0, 1.0]
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return [float(max(0, centre - half)), float(min(1, centre + half))]


def poisson_upper(count, hours):
    """95% upper bound on an event rate per hour when `count` events were seen in `hours` hours."""
    return float(chi2.ppf(0.975, 2 * (count + 1)) / 2 / hours) if hours else float("inf")


def window_metrics(y, scores, thr):
    y, scores = np.asarray(y), np.asarray(scores)
    flag = scores >= thr
    tp, fp = int((flag & (y == 1)).sum()), int((flag & (y == 0)).sum())
    fn, tn = int((~flag & (y == 1)).sum()), int((~flag & (y == 0)).sum())
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return {"roc_auc": float(roc_auc_score(y, scores)), "pr_auc": float(average_precision_score(y, scores)), "precision": precision, "recall": recall,
            "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0, "false_positive_rate": fp / (fp + tn) if fp + tn else 0.0,
            "tp": tp, "fp": fp, "fn": fn, "tn": tn}


def run_level(df, scores, thr, rule=None):
    """Per-run results with the alert rule: attacks caught, delay in windows, false alarms per machine-hour."""
    rule = rule or AlertRule()
    df = df.assign(_score=np.asarray(scores))
    caught, delays, false_alarms, benign_windows = {}, {}, 0, 0
    by_family = {}
    for run_id, g in df.groupby("run_id", sort=False):
        g = g.sort_values("window")
        alerts = rule.alerts((g._score.to_numpy() >= thr))
        family, onset = g.family.iloc[0], int(g.onset.iloc[0])
        if family == "benign":
            false_alarms += len(alerts)
            benign_windows += len(g)
            continue
        early = [a for a in alerts if a < onset]
        late = [a for a in alerts if a >= onset]
        false_alarms += len(early)
        benign_windows += onset
        stats = by_family.setdefault(family, {"runs": 0, "caught": 0, "delays": []})
        stats["runs"] += 1
        if late:
            stats["caught"] += 1
            stats["delays"].append(late[0] - onset)
    hours = benign_windows * WINDOW_SECONDS / 3600
    runs = sum(s["runs"] for s in by_family.values())
    got = sum(s["caught"] for s in by_family.values())
    delays = [d for s in by_family.values() for d in s["delays"]]
    return {
        "attack_runs": runs, "attacks_caught": got, "detection_rate": got / runs if runs else 0.0,
        "median_delay_windows": float(np.median(delays)) if delays else None, "p90_delay_windows": float(np.percentile(delays, 90)) if delays else None,
        "median_delay_seconds": float(np.median(delays)) * WINDOW_SECONDS if delays else None,
        "detection_ci95": wilson(got, runs),
        "false_alarms": false_alarms, "benign_hours": hours, "false_alarms_per_machine_hour": false_alarms / hours if hours else 0.0,
        "false_alarms_upper95_per_machine_hour": poisson_upper(false_alarms, hours),
        "by_family": {f: {"runs": s["runs"], "detection_rate": s["caught"] / s["runs"],
                          "median_delay_windows": float(np.median(s["delays"])) if s["delays"] else None} for f, s in by_family.items()},
    }


def precision_at_prevalence(recall, fpr, prevalence):
    """What precision would be if attacks were as rare as `prevalence` (share of windows that are attacks)."""
    tp, fp = recall * prevalence, fpr * (1 - prevalence)
    return tp / (tp + fp) if tp + fp else 0.0
