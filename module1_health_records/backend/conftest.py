import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(__file__))


@pytest.fixture(autouse=True)
def fresh_upload_folder(tmp_path, monkeypatch):
    """Every test gets its own empty upload folder, so files from one test
    can never leak into another."""
    from app.config import TestConfig

    monkeypatch.setattr(TestConfig, "UPLOAD_FOLDER", str(tmp_path), raising=False)
