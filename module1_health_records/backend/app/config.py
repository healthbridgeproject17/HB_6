import os
import tempfile
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()


def _database_url():
    url = os.getenv("DATABASE_URL", "")
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg://", 1)
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    if not url or url.startswith("paste-your"):
        return "sqlite:///dev.db"
    return url


MEDAI_DEFAULT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "module2_medical_ai"))
RWDETECT_DEFAULT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "module3_ransomware"))
BASE_UPLOAD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "uploads"))


class Config:
    ENV_NAME = os.getenv("FLASK_ENV", "development").lower()
    DOCUMENT_ENCRYPTION_KEY = os.getenv("DOCUMENT_ENCRYPTION_KEY", "")
    MEDAI_PATH = os.getenv("MEDAI_PATH", MEDAI_DEFAULT)
    ANALYSIS_SYNC = False            # True runs the analysis inside the request (tests)
    ANALYSIS_WORKERS = int(os.getenv("ANALYSIS_WORKERS", "2"))   # documents analysed at the same time (1-4); each uses extra memory
    ANALYSIS_MAX_PER_HOUR = 20       # per user
    ANALYSIS_STALE_MINUTES = 15
    RWDETECT_PATH = os.getenv("RWDETECT_PATH", RWDETECT_DEFAULT)   # Module 3 folder (detection engine + trained model)
    MONITOR_SIM_SYNC = False          # True plays a simulation inside the request (tests)
    MONITOR_MAX_MACHINES = 20
    MONITOR_MAX_SIMULATIONS = 4       # simulated machines playing at the same time
    MONITOR_KEEP_WINDOWS = 400        # newest windows kept per machine (400 x 5 s = about 33 minutes)
    MONITOR_AGENT_MAX_PER_MINUTE = 30 # an agent should send 12 per minute
    LOGIN_MAX_FAILURES = 5
    LOGIN_LOCK_MINUTES = 15
    REGISTER_MAX_PER_IP_HOUR = 20
    # Email (password reset). MAIL_BACKEND "console" only writes to the server log (development);
    # "smtp" really sends and needs the SMTP_* values.
    MAIL_BACKEND = os.getenv("MAIL_BACKEND", "console").lower()
    SMTP_HOST = os.getenv("SMTP_HOST", "")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
    MAIL_FROM = os.getenv("MAIL_FROM", "HealthBridge <no-reply@healthbridge.local>")
    FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")   # used in email links
    RESET_TOKEN_MINUTES = 30
    RESET_MAX_PER_EMAIL_HOUR = 3
    RESET_MAX_PER_IP_HOUR = 10
    UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", BASE_UPLOAD_DIR)   # on a host, point this at a persistent disk
    MAX_PHOTO_BYTES = 2 * 1024 * 1024  # 2 MB
    MAX_DOCUMENT_BYTES = 10 * 1024 * 1024  # 10 MB per report/prescription
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-jwt-secret")
    SQLALCHEMY_DATABASE_URI = _database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=2)
    # Login can travel two ways: the website uses an HttpOnly cookie (JavaScript cannot read it),
    # while tests and tools may still send "Authorization: Bearer ...".
    JWT_TOKEN_LOCATION = ["headers", "cookies"]
    JWT_COOKIE_SECURE = ENV_NAME == "production"     # HTTPS only on the live site
    JWT_COOKIE_SAMESITE = "Lax"
    JWT_COOKIE_CSRF_PROTECT = True                   # cookie logins must send X-CSRF-TOKEN on changes
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
    MAX_CONTENT_LENGTH = 12 * 1024 * 1024  # whole request (file + form overhead)


class TestConfig(Config):
    TESTING = True
    MAIL_BACKEND = "memory"          # emails are kept in app.extensions["outbox"]
    ENV_NAME = "testing"
    ANALYSIS_SYNC = True
    MONITOR_SIM_SYNC = True
    DOCUMENT_ENCRYPTION_KEY = ""
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    UPLOAD_FOLDER = tempfile.mkdtemp(prefix="hb_test_uploads_")
