"""HealthBridge Module 2: medical document analysis pipeline (no web server in here)."""
from .extract import ExtractionError, extract_document  # noqa: F401
from .parse import analyze_document, check_identity  # noqa: F401
from .review import ReviewError, apply_review  # noqa: F401

__version__ = "0.6"
__all__ = ["extract_document", "analyze_document", "apply_review", "check_identity", "ExtractionError", "ReviewError"]
