import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
PROJECT_DIR = BASE_DIR.parent
STORAGE_DIR = BASE_DIR / "storage"
UPLOAD_DIR = STORAGE_DIR / "uploads"
PROCESSED_DIR = STORAGE_DIR / "processed"
REPORTS_DIR = STORAGE_DIR / "reports"
TEMP_DIR = STORAGE_DIR / "temp"

DATA_DIR = Path(os.environ.get("CRICPOSE_DATA_DIR", PROJECT_DIR / "data")).resolve()
RAW_VIDEOS_DIR = DATA_DIR / "raw_videos"
PRO_BOWLERS_DIR = RAW_VIDEOS_DIR / "pro_bowlers"
USER_RAW_VIDEOS_DIR = RAW_VIDEOS_DIR / "users"
PROCESSED_FRAMES_DIR = DATA_DIR / "processed_frames"
KEYPOINTS_DIR = DATA_DIR / "keypoints"
DATASETS_DIR = DATA_DIR / "datasets"
PROFILES_DIR = DATA_DIR / "profiles"
STATIC_DIR = DATA_DIR / "static"
STATIC_VIDEOS_DIR = STATIC_DIR / "videos"

for directory in (
    UPLOAD_DIR,
    PROCESSED_DIR,
    REPORTS_DIR,
    TEMP_DIR,
    RAW_VIDEOS_DIR,
    PRO_BOWLERS_DIR,
    USER_RAW_VIDEOS_DIR,
    PROCESSED_FRAMES_DIR,
    KEYPOINTS_DIR,
    DATASETS_DIR,
    PROFILES_DIR,
    STATIC_VIDEOS_DIR,
):
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
