"""Time-based one-time codes (RFC 6238), the 6-digit codes of authenticator apps.
Standard library only, so there is no extra package to install."""
import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote

STEP_SECONDS = 30
DIGITS = 6


def new_secret():
    """20 random bytes as base32 text (the 'setup key' typed into the authenticator app)."""
    return base64.b32encode(secrets.token_bytes(20)).decode()


def _hotp(secret_b32, counter, digits=DIGITS):
    key = base64.b32decode(secret_b32.replace(" ", "").upper() + "=" * (-len(secret_b32.replace(" ", "")) % 8))
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    number = (struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF) % (10 ** digits)
    return str(number).zfill(digits)


def code_at(secret_b32, when=None, digits=DIGITS):
    return _hotp(secret_b32, int((time.time() if when is None else when) // STEP_SECONDS), digits)


def verify(secret_b32, code, last_step=0, when=None):
    """Returns the time step that matched, or None. One step either side is accepted
    (clock drift). A step that is not newer than last_step is refused, so a code
    cannot be used twice."""
    code = "".join(ch for ch in str(code or "") if ch.isdigit())
    if len(code) != DIGITS:
        return None
    now_step = int((time.time() if when is None else when) // STEP_SECONDS)
    for step in (now_step, now_step - 1, now_step + 1):
        if step > last_step and hmac.compare_digest(_hotp(secret_b32, step), code):
            return step
    return None


def provisioning_uri(secret_b32, account, issuer="HealthBridge"):
    return (f"otpauth://totp/{quote(issuer)}:{quote(account)}?secret={secret_b32}"
            f"&issuer={quote(issuer)}&algorithm=SHA1&digits={DIGITS}&period={STEP_SECONDS}")


def new_backup_codes(count=8):
    """Single-use recovery codes like 'a1b2c-3d4e5'."""
    return [f"{secrets.token_hex(5)[:5]}-{secrets.token_hex(5)[:5]}" for _ in range(count)]


def hash_backup_code(code):
    clean = "".join(ch for ch in str(code or "").lower() if ch.isalnum())
    return hashlib.sha256(clean.encode()).hexdigest()
