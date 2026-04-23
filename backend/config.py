import os
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parent
BASE_DIR = BACKEND_DIR.parent
FRONTEND_DIR = BASE_DIR / "frontend"
UPLOAD_DIR = BASE_DIR / "uploads"
RESULTS_DIR = BASE_DIR / "results"
DATA_DIR = BASE_DIR / "data"
TEMP_DIR = BASE_DIR / "temp"

for directory in (UPLOAD_DIR, RESULTS_DIR, DATA_DIR, TEMP_DIR):
    directory.mkdir(parents=True, exist_ok=True)


class AppConfig:
    DOUBAO_API_URL = os.getenv(
        "DOUBAO_API_URL",
        "http://aigw.primeinnos.com/backend_seedream_cn/api/v3/contents/generations/tasks",
    )
    DOUBAO_MODEL = os.getenv("DOUBAO_MODEL", "doubao-seedance-2-0-260128")
    DOUBAO_API_TOKEN = os.getenv(
        "DOUBAO_API_TOKEN",
        "",
    )

    GEMINI_API_URL = os.getenv(
        "GEMINI_API_URL",
        "http://aigw.primeinnos.com/marketing_center/v1/chat/completions",
    )
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.1-pro-preview")
    GEMINI_API_TOKEN = os.getenv(
        "GEMINI_API_TOKEN",
        "",
    )

    APIFY_API_TOKEN = os.getenv(
        "APIFY_API_TOKEN",
        "",
    )

    R2_ENDPOINT = os.getenv(
        "R2_ENDPOINT",
        "https://a735435b6cf8bb51684485e2541e8cd2.r2.cloudflarestorage.com",
    )
    R2_BUCKET = os.getenv("R2_BUCKET", "video-share-2026")
    R2_PUBLIC_BASE_URL = os.getenv(
        "R2_PUBLIC_BASE_URL",
        "https://pub-5a97ce19576c4e2fbe50df2e8b452f2c.r2.dev",
    )
    R2_REGION = os.getenv("R2_REGION", "auto")
    R2_ACCESS_KEY_ID = os.getenv(
        "R2_ACCESS_KEY_ID",
        "YOUR_R2_ACCESS_KEY_ID",
    )
    R2_SECRET_ACCESS_KEY = os.getenv(
        "R2_SECRET_ACCESS_KEY",
        "YOUR_R2_SECRET_ACCESS_KEY",
    )
