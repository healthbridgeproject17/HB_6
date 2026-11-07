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


# make the Module 2 package importable for the analysis tests
_medai = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "module2_medical_ai"))
if os.path.isdir(_medai) and _medai not in sys.path:
    sys.path.insert(0, _medai)
