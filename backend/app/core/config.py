import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
STORAGE_DIR = BASE_DIR / "storage"
UPLOAD_DIR = STORAGE_DIR / "uploads"
PROCESSED_DIR = STORAGE_DIR / "processed"
REPORTS_DIR = STORAGE_DIR / "reports"
TEMP_DIR = STORAGE_DIR / "temp"

for directory in (UPLOAD_DIR, PROCESSED_DIR, REPORTS_DIR, TEMP_DIR):
    directory.mkdir(parents=True, exist_ok=True)


def get_mongo_url() -> str:
    return os.environ["MONGO_URL"]


def get_db_name() -> str:
    return os.environ["DB_NAME"]


def get_jwt_secret() -> str:
    return os.environ["JWT_SECRET"]


JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 14
ALLOWED_CONTENT_TYPES = {"video/mp4", "video/quicktime", "video/webm", "video/x-m4v", "video/mpeg"}
