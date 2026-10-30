from functools import wraps

from flask import g, jsonify
from flask_jwt_extended import get_jwt, get_jwt_identity, verify_jwt_in_request

from ..extensions import db
from ..models import User


def role_required(*allowed_roles, allow_pending_password=False):
    """Backend permission check. The role is read from the DATABASE on every
    request (not trusted from the token). Refused: disabled accounts, tokens
    from before a logout/password change, and - until they set their own
    password - accounts created with a temporary one."""

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            user = db.session.get(User, int(get_jwt_identity()))
            if user is None or not user.is_active:
                return jsonify(error="Account not found or disabled."), 401
            if get_jwt().get("tv", 0) != user.token_version:
                return jsonify(error="Your session has ended. Please log in again."), 401
            if user.role not in allowed_roles:
                return jsonify(error="You do not have permission for this action."), 403
            if user.must_change_password and not allow_pending_password:
                return jsonify(error="You must change your temporary password first.",
                               code="password_change_required"), 403
            g.current_user = user
            return fn(*args, **kwargs)

        return wrapper

    return decorator
