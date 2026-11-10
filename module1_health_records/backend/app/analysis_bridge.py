"""Connects the website to the Module 2 analysis package (medai). If medai or
its libraries are not installed, the rest of the site works and analysis
reports 'not available'."""
import json
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor

from flask import current_app

_module = None
_executor = None
_executor_lock = threading.Lock()


class AnalysisUnavailable(RuntimeError):
    pass


def medai():
    global _module
    if _module is None:
        path = current_app.config["MEDAI_PATH"]
        if os.path.isdir(path) and path not in sys.path:
            sys.path.insert(0, path)
        try:
            import medai as module
        except Exception as exc:  # missing folder or libraries
            raise AnalysisUnavailable(f"The analysis engine is not installed ({exc.__class__.__name__}).")
        _module = module
    return _module


def available():
    try:
        medai()
        return True
    except AnalysisUnavailable:
        return False


def executor():
    """A small pool: up to ANALYSIS_WORKERS documents are analysed at the same time;
    the rest wait in line (their job stays 'queued')."""
    global _executor
    with _executor_lock:
        if _executor is None:
            workers = max(1, min(int(current_app.config.get("ANALYSIS_WORKERS", 2)), 4))
            _executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="analysis")
    return _executor


def plain(obj):
    """Make an analysis result safe to store as JSON (numpy numbers etc.)."""
    return json.loads(json.dumps(obj, default=lambda o: o.item() if hasattr(o, "item") else str(o)))
