from flask import Blueprint, g, jsonify, request

from ..extensions import db
from ..utils import second_factor as sf
from ..utils import totp
from ..utils.audit import log_action
from ..utils.decorators import role_required

bp = Blueprint("twofactor", __name__)
ANY = ("patient", "doctor", "admin")


@bp.post("/2fa/setup")
@role_required(*ANY)
def setup():
    """Step 1: make a new secret (not active yet). The user adds it to an authenticator app."""
    user = g.current_user
    if user.totp_enabled:
        return jsonify(error="Two-factor login is already on."), 409
    secret = totp.new_secret()
    sf.store_secret(user, secret)
    db.session.commit()
    return jsonify(secret=" ".join(secret[i:i + 4] for i in range(0, len(secret), 4)),
                   otpauth_uri=totp.provisioning_uri(secret, user.email))


@bp.post("/2fa/enable")
@role_required(*ANY)
def enable():
    """Step 2: prove the app works by entering a code. Backup codes are shown once."""
    user = g.current_user
    body = request.get_json(silent=True) or {}
    secret = sf.read_secret(user)
    if user.totp_enabled or not secret:
        return jsonify(error="Start the setup first."), 400
    step = totp.verify(secret, body.get("code"), last_step=user.totp_last_step or 0)
    if not step:
        return jsonify(error="That code is not right. Check the time on your phone and try the next code."), 400
    codes = totp.new_backup_codes()
    user.totp_enabled = True
    user.totp_last_step = step
    user.backup_code_hashes = [totp.hash_backup_code(c) for c in codes]
    db.session.commit()
    log_action(user.id, "two_factor_enabled", "user", user.id)
    return jsonify(ok=True, backup_codes=codes)


@bp.post("/2fa/disable")
@role_required(*ANY)
def disable():
    """Turning it off needs BOTH the password and a current code (or a backup code)."""
    user = g.current_user
    body = request.get_json(silent=True) or {}
    if not user.totp_enabled:
        return jsonify(error="Two-factor login is not on."), 400
    if not user.check_password(body.get("password") or "") or not sf.check_code(user, body.get("code")):
        db.session.rollback()
        log_action(user.id, "two_factor_disable_failed", "user", user.id)
        return jsonify(error="Your password or code is not right."), 400
    sf.clear_two_factor(user)
    db.session.commit()
    log_action(user.id, "two_factor_disabled", "user", user.id)
    return jsonify(ok=True)
