"""The trained detector: a model, its alert threshold and rule, and what it was trained on."""
import hashlib
import json
import os
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd

from .alerting import AlertRule
from .features import FEATURES, clean_window


def raw_scores(estimator, frame):
    X = frame[FEATURES]
    if hasattr(estimator, "predict_proba"):
        return estimator.predict_proba(X)[:, 1]
    return -estimator.decision_function(X)      # anomaly detectors: higher = stranger


class RuleBaseline:
    """What a simple hand-written rule would do (for comparison with the learned models)."""
    name = "rule_baseline"

    def fit(self, X, y=None):
        return self

    def predict_proba(self, X):
        s = X["high_entropy_write_ratio"].to_numpy() * (X["ext_change_ratio"].to_numpy() + np.minimum(X["files_modified_per_s"].to_numpy() / 50, 1)) / 2
        return np.column_stack([1 - s, s])


class DetectorModel:
    def __init__(self, estimator, kind, threshold, rule=None, meta=None):
        self.estimator, self.kind, self.threshold = estimator, kind, float(threshold)
        self.rule = rule or AlertRule()
        self.meta = meta or {}

    def score_frame(self, frame):
        return raw_scores(self.estimator, frame)

    def score_window(self, window: dict) -> float:
        """Score one telemetry window from an agent. Raises BadWindow for unusable input."""
        row = clean_window(window)
        return float(self.score_frame(pd.DataFrame([row], columns=FEATURES))[0])

    def save(self, path):
        meta = dict(self.meta, kind=self.kind, threshold=self.threshold, rule=self.rule.as_dict(), features=FEATURES,
                    saved_at=datetime.now(timezone.utc).isoformat())
        joblib.dump({"estimator": self.estimator, "meta": meta}, path)
        digest = hashlib.sha256(open(path, "rb").read()).hexdigest()
        json.dump(dict(meta, sha256=digest), open(os.path.splitext(path)[0] + ".meta.json", "w"), indent=2)
        return digest

    @classmethod
    def load(cls, path, expected_sha256=None):
        """Model files are Python pickles: only load files you created yourself. The checksum
        check detects a file that was swapped or damaged."""
        if expected_sha256:
            actual = hashlib.sha256(open(path, "rb").read()).hexdigest()
            if actual != expected_sha256:
                raise ValueError("The model file does not match its checksum. Refusing to load it.")
        blob = joblib.load(path)
        meta = blob["meta"]
        if meta["features"] != FEATURES:
            raise ValueError("The model was trained on different features than this code expects.")
        return cls(blob["estimator"], meta["kind"], meta["threshold"], AlertRule(**meta["rule"]), meta)
