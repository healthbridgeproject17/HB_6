import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from flask import current_app

_MAGIC = b"gAAAA"  # every Fernet token starts with this


def _fernet():
    key = current_app.config.get("DOCUMENT_ENCRYPTION_KEY") or ""
    if not key:
        # Development convenience only: derive a key from SECRET_KEY. Production
        # refuses to start without an explicit DOCUMENT_ENCRYPTION_KEY.
        digest = hashlib.sha256(("hb-files:" + current_app.config["SECRET_KEY"]).encode()).digest()
        key = base64.urlsafe_b64encode(digest).decode()
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_bytes(data: bytes) -> bytes:
    return _fernet().encrypt(data)


def decrypt_bytes(blob: bytes) -> bytes:
    """Decrypt a stored file. Files saved before encryption existed (they do not
    look like Fernet tokens) are returned as they are."""
    if not blob.startswith(_MAGIC):
        return blob
    try:
        return _fernet().decrypt(blob)
    except InvalidToken:
        raise ValueError("Stored file cannot be decrypted (wrong encryption key?).")
