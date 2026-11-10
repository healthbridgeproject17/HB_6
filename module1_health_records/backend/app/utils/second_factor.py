"""Shared helpers for two-factor login: stored secret, checking a code, short-lived login ticket."""
from flask import current_app
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from ..extensions import db
from . import totp
from .crypto import decrypt_bytes, encrypt_bytes

TICKET_SECONDS = 300   # time allowed between the password step and the code step


def store_secret(user, secret):
    user.totp_secret_enc = encrypt_bytes(secret.encode()).decode()


def read_secret(user):
    if not user.totp_secret_enc:
        return None
    return decrypt_bytes(user.totp_secret_enc.encode()).decode()


def check_code(user, code):
    """True if `code` is a current authenticator code or an unused backup code (which is then used up).
    Changes are added to the session; the caller commits."""
    secret = read_secret(user)
    if secret:
        step = totp.verify(secret, code, last_step=user.totp_last_step or 0)
        if step:
            user.totp_last_step = step
            return True
    hashed = totp.hash_backup_code(code)
    remaining = list(user.backup_code_hashes or [])
    if hashed in remaining:
        remaining.remove(hashed)
        user.backup_code_hashes = remaining   # a new list, so the change is saved
        return True
    return False


def clear_two_factor(user):
    user.totp_secret_enc = None
    user.totp_enabled = False
    user.totp_last_step = 0
    user.backup_code_hashes = None


def _serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="hb-login-ticket")


def make_ticket(user):
    """A short-lived note 'this person passed the password step'. It is NOT a login token:
    the API does not accept it anywhere except the code step."""
    return _serializer().dumps({"uid": user.id, "tv": user.token_version})


def read_ticket(ticket):
    try:
        data = _serializer().loads(ticket or "", max_age=TICKET_SECONDS)
    except (BadSignature, SignatureExpired):
        return None
    return data


__all__ = ["store_secret", "read_secret", "check_code", "clear_two_factor", "make_ticket", "read_ticket", "db"]
