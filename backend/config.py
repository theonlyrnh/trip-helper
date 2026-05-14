"""Application configuration loaded from environment variables."""

import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    APP_NAME: str = os.getenv("APP_NAME", "Travel Invoice Assistant")
    APP_ENV: str = os.getenv("APP_ENV", "local")

    BACKEND_HOST: str = os.getenv("BACKEND_HOST", "127.0.0.1")
    BACKEND_PORT: int = int(os.getenv("BACKEND_PORT", "8000"))

    DB_PATH: str = os.getenv("DB_PATH", "data/app.db")
    EXPORT_DIR: str = os.getenv("EXPORT_DIR", "data/exports")
    CACHE_DIR: str = os.getenv("CACHE_DIR", "data/cache")
    THUMBNAIL_DIR: str = os.getenv("THUMBNAIL_DIR", "data/thumbnails")

    OCR_PROVIDER_MODE: str = os.getenv("OCR_PROVIDER_MODE", "local_first")
    PADDLEOCR_API_URL: str = os.getenv("PADDLEOCR_API_URL", "http://localhost:8118/v1")
    PADDLEOCR_MODEL: str = os.getenv("PADDLEOCR_MODEL", "PaddleOCR-VL-1.5-0.9B")

    REMOTE_API_BASE_URL: str | None = os.getenv("REMOTE_API_BASE_URL")
    REMOTE_API_KEY: str | None = os.getenv("REMOTE_API_KEY")
    REMOTE_MODEL_NAME: str | None = os.getenv("REMOTE_MODEL_NAME")


settings = Settings()