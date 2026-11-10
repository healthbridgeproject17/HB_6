import threading
import time

from app import create_app
from app import analysis_bridge as bridge
from app.config import TestConfig


def _fresh_executor(monkeypatch, workers):
    monkeypatch.setattr(bridge, "_executor", None)
    app = create_app(TestConfig)
    app.config["ANALYSIS_WORKERS"] = workers
    with app.app_context():
        return bridge.executor()


def test_pool_size_follows_setting_and_is_limited(monkeypatch):
    assert _fresh_executor(monkeypatch, 3)._max_workers == 3
    assert _fresh_executor(monkeypatch, 0)._max_workers == 1
    assert _fresh_executor(monkeypatch, 50)._max_workers == 4


def test_two_jobs_run_at_the_same_time(monkeypatch):
    pool = _fresh_executor(monkeypatch, 2)
    both_started = threading.Barrier(2, timeout=5)

    def job():
        both_started.wait()   # only passes if two jobs are running together
        return True

    futures = [pool.submit(job), pool.submit(job)]
    assert [f.result(timeout=10) for f in futures] == [True, True]


def test_extra_jobs_wait_their_turn(monkeypatch):
    pool = _fresh_executor(monkeypatch, 1)
    order = []
    futures = [pool.submit(lambda i=i: (time.sleep(0.05), order.append(i))) for i in range(3)]
    for f in futures:
        f.result(timeout=10)
    assert order == [0, 1, 2]
