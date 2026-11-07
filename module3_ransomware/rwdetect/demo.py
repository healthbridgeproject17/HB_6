"""Watch the detector work on one simulated machine, window by window.

    python -m rwdetect.demo --family fast_encryptor
    python -m rwdetect.demo --family slow_drip --seed 4
    python -m rwdetect.demo --family benign

Nothing here touches your files or network: the telemetry is simulated numbers."""
import argparse
import os

import numpy as np

from .features import FEATURES, WINDOW_SECONDS
from .model import DetectorModel
from .simulate import FAMILIES, simulate_run

DEFAULT_MODEL = os.path.join(os.path.dirname(__file__), "..", "models", "model.joblib")


def run_demo(family="fast_encryptor", seed=1, model_path=DEFAULT_MODEL, show=None):
    model = DetectorModel.load(model_path)
    rows = simulate_run(np.random.SeedSequence(seed), 0, family)
    state = model.rule.state()
    onset = int(rows[0]["onset"])
    alerts = []
    for r in rows:
        score = model.score_window({f: r[f] for f in FEATURES})
        above = score >= model.threshold
        alert = state.update(above)
        if alert:
            alerts.append(r["window"])
        if show:
            bar = "#" * int(round(score * 30))
            show(f"{r['window']:4d}  t={r['window'] * WINDOW_SECONDS:5d}s  {bar:<30} {score:4.2f} {'high' if above else '    '} {'<<< ALERT' if alert else ''}"
                 f"   (simulator truth: {r['phase']})")
    return {"family": family, "windows": len(rows), "onset": onset if family != "benign" else None, "alerts": alerts,
            "delay_windows": (min((a for a in alerts if a >= onset), default=None) - onset) if family != "benign" and any(a >= onset for a in alerts) else None,
            "false_alarms": len([a for a in alerts if family == "benign" or a < onset])}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--family", default="fast_encryptor", choices=["benign", *FAMILIES])
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    a = ap.parse_args()
    out = run_demo(a.family, a.seed, a.model, show=print)
    print()
    if a.family == "benign":
        print(f"Normal machine for {out['windows']} windows: {out['false_alarms']} false alarm(s).")
    elif out["delay_windows"] is None:
        print(f"MISSED: the attack began at window {out['onset']} and no alert was raised.")
    else:
        print(f"Attack began at window {out['onset']}; first alert {out['delay_windows']} window(s) later ({out['delay_windows'] * WINDOW_SECONDS} seconds). False alarms before it: {out['false_alarms']}.")


if __name__ == "__main__":
    main()
