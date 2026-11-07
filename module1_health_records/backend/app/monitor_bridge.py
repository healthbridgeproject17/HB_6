"""Connects the website to the Module 3 detection package (rwdetect). If rwdetect or its libraries
are not installed, the rest of the site works and the Security page says 'not available'.

The trained model is a Python pickle, so it is only loaded after its SHA-256 matches the value
written next to it by the training script (detects a swapped or damaged file). Only ever place model
files there that you created yourself."""
import json
import os
import sys
import threading

from flask import current_app

_cache = {"monitor": None, "model": None, "metrics": None}
_load_lock = threading.Lock()
score_lock = threading.Lock()      # one window is scored at a time


class MonitorUnavailable(RuntimeError):
    pass


def _root():
    return current_app.config["RWDETECT_PATH"]


def monitor():
    """The rwdetect.monitor module (pure decision logic)."""
    with _load_lock:
        if _cache["monitor"] is None:
            path = _root()
            if os.path.isdir(path) and path not in sys.path:
                sys.path.insert(0, path)
            try:
                from rwdetect import monitor as module
            except Exception as exc:       # missing folder or libraries
                raise MonitorUnavailable(f"The detection engine is not installed ({exc.__class__.__name__}).") from exc
            _cache["monitor"] = module
        return _cache["monitor"]


def model():
    """The trained detector, loaded once and checked against its checksum."""
    monitor()
    with _load_lock:
        if _cache["model"] is None:
            from rwdetect.model import DetectorModel
            path = os.path.join(_root(), "models", "model.joblib")
            meta = os.path.join(_root(), "models", "model.meta.json")
            try:
                with open(meta, encoding="utf-8") as fh:
                    expected = json.load(fh)["sha256"]
                _cache["model"] = DetectorModel.load(path, expected_sha256=expected)
            except Exception as exc:
                raise MonitorUnavailable(f"The trained model could not be loaded ({exc.__class__.__name__}). Run setup in the module3_ransomware folder.") from exc
        return _cache["model"]


def available():
    try:
        model()
        return True
    except MonitorUnavailable:
        return False


def summary():
    """The honest model summary shown on the Security page."""
    mod = monitor()
    with _load_lock:
        if _cache["metrics"] is None:
            try:
                with open(os.path.join(_root(), "models", "metrics.json"), encoding="utf-8") as fh:
                    _cache["metrics"] = mod.model_summary(json.load(fh))
            except Exception as exc:
                raise MonitorUnavailable(f"The model results file could not be read ({exc.__class__.__name__}).") from exc
        return _cache["metrics"]
