from functools import wraps

from flask import jsonify, g
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity

from ..extensions import db
from ..models import User


def role_required(*allowed_roles):
    """Backend permission check. The role is read from the DATABASE on every
    request, not trusted from the token, and disabled accounts are refused."""

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            user = db.session.get(User, int(get_jwt_identity()))
            if user is None or not user.is_active:
                return jsonify(error="Account not found or disabled."), 401
            if user.role not in allowed_roles:
                return jsonify(error="You do not have permission for this action."), 403
            g.current_user = user
            return fn(*args, **kwargs)

        return wrapper

    return decorator
