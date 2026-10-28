from flask import request

from ..extensions import db
from ..models import AuditLog


def log_action(user_id, action, target_type=None, target_id=None, detail=None, commit=True):
    """Write one audit row. Never raises into the caller's request."""
    try:
        entry = AuditLog(
            user_id=user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            detail=(detail or "")[:500] or None,
            ip_address=(request.remote_addr or "")[:45] if request else None,
        )
        db.session.add(entry)
        if commit:
            db.session.commit()
    except Exception:  # auditing must not break the main action
        db.session.rollback()
