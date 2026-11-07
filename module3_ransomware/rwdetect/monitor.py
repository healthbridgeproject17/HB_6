"""Decisions for the LIVE monitor (Phase 3.3): no web framework and no database in here,
so everything can be tested on its own. The website's backend only stores what this
module decides.

    one telemetry window --assess()--> score, alert yes/no, what stood out
    alert / high windows --update_incident()--> open or update an incident, with a risk level

Nothing in this module touches files, processes or networks. It only does arithmetic on
the numbers an agent (or the simulator) reports."""
from dataclasses import dataclass, field

import numpy as np

from .features import FEATURES, WINDOW_SECONDS, clean_window
from .simulate import FAMILIES, simulate_run

LEVELS = ("low", "medium", "high", "critical")

# What kinds of suspicious behaviour a window can show. Risk goes up when several different
# kinds show up together, because a real attack usually does more than one thing.
GROUPS = ("encryption", "backup_tampering", "spread", "outside_contact")
GROUP_LABELS = {
    "encryption": "File encryption behaviour",
    "backup_tampering": "Backup or recovery tampering",
    "spread": "Spreading to other machines",
    "outside_contact": "Suspicious outside contact",
}

SUSTAINED_WINDOWS = 6       # 6 windows = 30 seconds of the behaviour carrying on
LONG_WINDOWS = 24           # 24 windows = 2 minutes
MAX_REASONS = 8


# ------------------------------------------------------------------ what stood out
def findings(w: dict) -> list:
    """Plain-language reasons from simple rules on the window's own numbers.

    These say WHAT LOOKED UNUSUAL in the numbers. They are not the model's inner workings:
    the model can raise an alert for a mixture of small signals that none of these rules catch."""
    f = clean_window(w)
    out = []
    if f["high_entropy_write_ratio"] >= 0.6 and f["files_modified_per_s"] >= 3:
        out.append(("encryption", "Files are being rewritten with random-looking data (what encryption produces)"))
    if f["files_renamed_per_s"] >= 2 and f["ext_change_ratio"] >= 0.6:
        out.append(("encryption", "Many files are being renamed to a new file extension"))
    if f["distinct_dirs_touched"] >= 15 and f["files_modified_per_s"] >= 5:
        out.append(("encryption", "File changes are spread across many folders at once"))
    if f["suspicious_cmd_count"] >= 1:
        out.append(("backup_tampering", "Commands that delete backups or switch off recovery were run"))
    if f["smb_distinct_hosts"] >= 5:
        out.append(("spread", "This machine is contacting many other machines on file-sharing ports"))
    if f["bytes_out_mb_per_s"] >= 2 and f["out_in_ratio"] >= 3:
        out.append(("outside_contact", "A lot more data is leaving the machine than coming in"))
    if f["beacon_regularity"] >= 0.8 and f["rare_dest_count"] >= 1:
        out.append(("outside_contact", "Clock-like connections to a destination this machine has never used before"))
    if f["dns_nxdomain_per_s"] >= 2:
        out.append(("outside_contact", "Many failed name look-ups (random-looking domain names)"))
    return out


# ------------------------------------------------------------------ risk level
def risk_points(score: float, groups, windows_above: int) -> dict:
    """Three things add up to a risk level. Each is easy to explain and to check by hand.

    1. How sure the model is (mean score of the recent high windows): >= 0.97 -> 2, >= 0.90 -> 1, else 0
    2. How many DIFFERENT kinds of suspicious behaviour are visible (encryption, backup tampering,
       spreading, outside contact), up to 3 points. Real attacks usually do more than one thing.
    3. How long it has carried on: 30 seconds or more -> 1, 2 minutes or more -> 2
    """
    confidence = 2 if score >= 0.97 else 1 if score >= 0.90 else 0
    behaviours = min(len(set(groups)), 3)
    persistence = 2 if windows_above >= LONG_WINDOWS else 1 if windows_above >= SUSTAINED_WINDOWS else 0
    return {"confidence": confidence, "behaviours": behaviours, "persistence": persistence,
            "total": confidence + behaviours + persistence}


def risk_level(score: float, groups, windows_above: int) -> str:
    """Total 0-2 Low, 3 Medium, 4-5 High, 6 or more Critical (see docs/MODULE3_MONITOR.md)."""
    total = risk_points(score, groups, windows_above)["total"]
    return LEVELS[0 if total <= 2 else 1 if total == 3 else 2 if total <= 5 else 3]


def risk_why(score: float, groups, windows_above: int) -> list:
    """The same three points as short sentences, for the incident screen."""
    p = risk_points(score, groups, windows_above)
    seconds = windows_above * WINDOW_SECONDS
    return [
        f"Model confidence {score:.0%} (+{p['confidence']})",
        f"{len(set(groups))} kind(s) of suspicious behaviour seen (+{p['behaviours']})",
        f"High windows so far: {windows_above}, about {seconds} seconds (+{p['persistence']})",
    ]


def level_rank(level: str) -> int:
    return LEVELS.index(level)


# ------------------------------------------------------------------ one window
@dataclass
class Verdict:
    score: float
    above: bool                 # score reached the alert threshold
    alert: bool                 # the k-of-m rule fired in this window
    state: dict                 # alert-rule memory to store for the next window
    findings: list = field(default_factory=list)
    values: dict = field(default_factory=dict)      # the 18 numbers after validation (out-of-range values clipped)


def new_state() -> dict:
    return {"recent": [], "scores": [], "quiet": 0}


def _load_state(rule, saved: dict):
    state = rule.state()
    state.recent.extend(bool(x) for x in (saved or {}).get("recent", [])[-rule.m:])
    state.quiet = max(0, int((saved or {}).get("quiet", 0)))
    return state


def assess(model, window: dict, saved_state: dict = None) -> Verdict:
    """Score one window and run the alert rule. `saved_state` is what the previous call returned
    (kept per machine, so the monitor survives a restart). Raises BadWindow for unusable input."""
    clean = clean_window(window)
    score = model.score_window(clean)
    above = score >= model.threshold
    state = _load_state(model.rule, saved_state)
    alert = state.update(above)
    scores = list((saved_state or {}).get("scores", []))[-(model.rule.m - 1):] + [round(score, 4)]
    return Verdict(score=score, above=above, alert=alert,
                   state={"recent": [bool(x) for x in state.recent], "scores": scores, "quiet": state.quiet},
                   findings=findings(clean), values=clean)


# ------------------------------------------------------------------ incidents
def _merge(old, new, limit=None):
    out = list(old)
    for item in new:
        if item not in out:
            out.append(item)
    return out[:limit] if limit else out


def update_incident(incident, verdict: Verdict, threshold: float):
    """Decide what the latest window means for the machine's open incident.

    `incident` is None, or a dict describing the machine's open incident:
        {risk, risk_why, peak_score, windows_above, alert_count, groups: [..], reasons: [..]}
    Returns (incident, event). `event` is "opened", "escalated", "updated" or None (nothing changed).
    The risk level only ever goes UP within one incident; a person closes it."""
    groups = [g for g, _ in verdict.findings]
    reasons = [t for _, t in verdict.findings]

    if incident is None:
        if not verdict.alert:
            return None, None
        above_scores = [s for s in verdict.state["scores"] if s >= threshold] or [verdict.score]
        windows_above = max(1, sum(verdict.state["recent"]))
        incident = {
            "peak_score": round(max(above_scores), 4), "windows_above": windows_above, "alert_count": 1,
            "groups": _merge([], groups), "reasons": _merge([], reasons, MAX_REASONS),
        }
        conf = float(np.mean(above_scores))
        incident["risk"] = risk_level(conf, incident["groups"], windows_above)
        incident["risk_why"] = risk_why(conf, incident["groups"], windows_above)
        return incident, "opened"

    before = dict(incident)
    incident = dict(incident, groups=list(incident["groups"]), reasons=list(incident["reasons"]))
    if verdict.above:
        incident["windows_above"] += 1
        incident["peak_score"] = round(max(incident["peak_score"], verdict.score), 4)
        incident["groups"] = _merge(incident["groups"], groups)
        incident["reasons"] = _merge(incident["reasons"], reasons, MAX_REASONS)
    if verdict.alert:
        incident["alert_count"] += 1
    recent_above = [s for s in verdict.state["scores"] if s >= threshold]
    if recent_above:
        conf = float(np.mean(recent_above))
        candidate = risk_level(conf, incident["groups"], incident["windows_above"])
        incident["risk_why"] = risk_why(conf, incident["groups"], incident["windows_above"])
        if level_rank(candidate) > level_rank(incident["risk"]):
            incident["risk"] = candidate
            return incident, "escalated"
    return incident, ("updated" if incident != before else None)


# ------------------------------------------------------------------ simulated machines
def demo_stream(family: str, seed: int, lead_in: int = 8, max_windows: int = 240) -> list:
    """Simulated windows for one virtual machine, for the dashboard demo.

    The attack starts `lead_in` windows after the stream begins (normal activity first), so a
    demo does not wait minutes. family="benign" gives ordinary activity only.
    Each row has the 18 features plus 'phase' (simulator truth, for display only) and 'family'."""
    if family != "benign" and family not in FAMILIES:
        raise ValueError(f"family must be 'benign' or one of {list(FAMILIES)}")
    rows = simulate_run(np.random.SeedSequence(int(seed)), 0, family)
    if family != "benign":
        onset = int(rows[0]["onset"])
        rows = rows[max(0, onset - lead_in):]
    out = []
    for r in rows[:max_windows]:
        row = {name: float(r[name]) for name in FEATURES}
        row["phase"] = r["phase"]
        row["family"] = family
        out.append(row)
    return out


# ------------------------------------------------------------------ model summary
def model_summary(metrics: dict) -> dict:
    """The honest, short version of models/metrics.json for the dashboard."""
    chosen = metrics["chosen"]
    runs = metrics["models"][chosen]["test_runs"]
    unseen = metrics.get("leave_one_family_out", {}).get(chosen, {})
    caveats = [
        "Trained and tested on synthetic data written from published descriptions of ransomware. This demonstrates a method; it is not a measure of real-world detection.",
        f"The false-alarm rate comes from only {runs['benign_hours']:.0f} hours of simulated normal activity, so it is uncertain (upper bound {runs['false_alarms_upper95_per_machine_hour']:.2f} per machine-hour).",
    ]
    if unseen:
        worst = min(unseen, key=lambda k: unseen[k]["detection_rate"])
        caveats.append(f"A never-seen attack family ('{worst}') was caught in only {unseen[worst]['detection_rate']:.0%} of runs, "
                       f"with a median delay of {unseen[worst]['median_delay_windows'] * WINDOW_SECONDS:.0f} seconds.")
    caveats.append("Isolation here is SIMULATED: the system records and recommends it. No real machine or network is changed.")
    return {
        "model": chosen,
        "threshold": round(metrics["models"][chosen]["threshold"], 3),
        "alert_rule": metrics["alert_rule"],
        "window_seconds": WINDOW_SECONDS,
        "data": {"synthetic": True, "windows": metrics["data"]["windows"],
                 "benign_runs": metrics["data"]["benign_runs"],
                 "attack_runs_per_family": metrics["data"]["attack_runs_per_family"]},
        "seen_families": {
            "attack_runs": runs["attack_runs"], "detection_rate": runs["detection_rate"],
            "detection_ci95": runs["detection_ci95"], "median_delay_seconds": runs["median_delay_seconds"],
            "false_alarms_per_machine_hour": round(runs["false_alarms_per_machine_hour"], 3),
            "false_alarms_upper95_per_machine_hour": round(runs["false_alarms_upper95_per_machine_hour"], 3),
            "benign_hours": round(runs["benign_hours"], 1),
        },
        "unseen_families": {k: {"detection_rate": v["detection_rate"],
                                "median_delay_seconds": v["median_delay_windows"] * WINDOW_SECONDS}
                            for k, v in unseen.items()},
        "top_features": [{"feature": f["feature"], "importance": round(f["importance"], 3)}
                         for f in metrics.get("feature_importance", [])[:5]],
        "caveats": caveats,
    }
