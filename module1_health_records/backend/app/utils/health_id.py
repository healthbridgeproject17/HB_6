from datetime import datetime, timezone

from sqlalchemy import text

from ..extensions import db
from ..models.user import Patient


def generate_health_id() -> str:
    """Return a unique ID like HB-2026-000001.

    On PostgreSQL (NeonDB) a database sequence guarantees uniqueness even when
    two patients register at the same moment. SQLite (tests) falls back to max+1.
    """
    year = datetime.now(timezone.utc).year
    if db.engine.dialect.name == "postgresql":
        seq = db.session.execute(text("SELECT nextval('health_id_seq')")).scalar()
    else:
        seq = (db.session.query(db.func.count(Patient.id)).scalar() or 0) + 1
    return f"HB-{year}-{int(seq):06d}"
