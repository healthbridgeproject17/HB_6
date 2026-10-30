import re
from datetime import date

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
SEXES = ("male", "female", "other")


def clean_email(value):
    value = (value or "").strip().lower()
    return value if EMAIL_RE.match(value) and len(value) <= 255 else None


def password_problem(password):
    """Return a message if the password is too weak, else None."""
    if not isinstance(password, str) or len(password) < 8:
        return "Password must be at least 8 characters."
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        return "Password must contain at least one letter and one number."
    if len(password.encode("utf-8")) > 72:
        return "Password must be at most 72 characters."
    return None


def parse_dob(value):
    """Accept YYYY-MM-DD, reject future dates. Returns (date|None, error|None)."""
    if value in (None, ""):
        return None, None
    try:
        d = date.fromisoformat(value)
    except (TypeError, ValueError):
        return None, "Date of birth must be YYYY-MM-DD."
    if d > date.today():
        return None, "Date of birth cannot be in the future."
    return d, None


PHONE_RE = re.compile(r"^[0-9+\-() ]{7,20}$")


def clean_phone(value):
    """Return (phone|None, error|None)."""
    value = (value or "").strip()
    if not value:
        return None, None
    if not PHONE_RE.match(value):
        return None, "Phone must be 7-20 characters: digits, + - ( ) and spaces."
    return value, None
