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
    UPLOAD_FOLDER = BASE_UPLOAD_DIR
    MAX_PHOTO_BYTES = 2 * 1024 * 1024  # 2 MB
    MAX_DOCUMENT_BYTES = 10 * 1024 * 1024  # 10 MB per report/prescription
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-jwt-secret")
    SQLALCHEMY_DATABASE_URI = _database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=2)
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
    MAX_CONTENT_LENGTH = 12 * 1024 * 1024  # whole request (file + form overhead)


class TestConfig(Config):
    TESTING = True
    ENV_NAME = "testing"
    ANALYSIS_SYNC = True
    MONITOR_SIM_SYNC = True
    DOCUMENT_ENCRYPTION_KEY = ""
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    UPLOAD_FOLDER = tempfile.mkdtemp(prefix="hb_test_uploads_")
