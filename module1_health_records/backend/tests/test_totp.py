import base64

from app.utils import totp

# RFC 6238 test secret ("12345678901234567890") and its published answer for time 59 s
SECRET = base64.b32encode(b"12345678901234567890").decode()


def test_matches_the_published_rfc_value():
    assert totp._hotp(SECRET, 59 // 30, digits=8) == "94287082"
    assert totp.code_at(SECRET, when=59) == "287082"


def test_verify_accepts_current_and_neighbouring_step_only():
    assert totp.verify(SECRET, "287082", when=59) == 1
    assert totp.verify(SECRET, "287082", when=59 + 30) == 1      # one step of clock drift
    assert totp.verify(SECRET, "287082", when=59 + 120) is None  # too old


def test_a_code_cannot_be_used_twice():
    step = totp.verify(SECRET, "287082", when=59)
    assert totp.verify(SECRET, "287082", last_step=step, when=59) is None


def test_bad_input_is_refused():
    for bad in ("", None, "12345", "abcdef", "0000000"):
        assert totp.verify(SECRET, bad, when=59) is None


def test_secret_and_backup_codes_look_right():
    assert len(totp.new_secret()) == 32
    codes = totp.new_backup_codes()
    assert len(codes) == 8 and len(set(codes)) == 8
    assert totp.hash_backup_code(codes[0].upper()) == totp.hash_backup_code(codes[0].replace("-", " "))


def test_provisioning_uri():
    uri = totp.provisioning_uri(SECRET, "a@b.com")
    assert uri.startswith("otpauth://totp/HealthBridge:a%40b.com?secret=") and "digits=6" in uri
