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


BASE_UPLOAD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "uploads"))


class Config:
    ENV_NAME = os.getenv("FLASK_ENV", "development").lower()
    DOCUMENT_ENCRYPTION_KEY = os.getenv("DOCUMENT_ENCRYPTION_KEY", "")
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
    DOCUMENT_ENCRYPTION_KEY = ""
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    UPLOAD_FOLDER = tempfile.mkdtemp(prefix="hb_test_uploads_")
