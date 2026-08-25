"""Typed runtime configuration for the A100 API and local development."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration kept outside the database so secrets never reach clients."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        # Validation aliases keep the legacy REMOTE_API_* variables working;
        # this also keeps explicit Settings(...) construction useful in tests
        # and internal tooling.
        populate_by_name=True,
    )

    app_name: str = "Trip Helper"
    app_env: str = "development"
    app_domain: str = "localhost"
    public_api_prefix: str = "/api/v1"

    database_url: str = "sqlite:///./data/trip-helper-web.db"
    redis_url: str = "redis://localhost:6379/0"
    storage_root: Path = Path("./data/web-storage")

    session_secret: str = "local-development-session-secret-change-me"
    session_days: int = Field(default=14, ge=1, le=90)
    cookie_secure: bool = False
    cookie_name: str = "trip_helper_session"
    csrf_header_name: str = "X-CSRF-Token"
    trusted_proxy_cidrs: str = ""

    max_upload_bytes: int = Field(default=104_857_600, ge=1)
    max_pdf_pages: int = Field(default=100, ge=1)
    max_image_pixels: int = Field(default=40_000_000, ge=1)
    max_documents_per_trip: int = Field(default=2_000, ge=1)
    upload_chunk_bytes: int = Field(default=1_048_576, ge=65_536)
    export_retention_hours: int = Field(default=72, ge=1, le=24 * 365)
    export_cleanup_grace_seconds: int = Field(default=300, ge=0, le=86_400)
    pdf_font_path: str | None = None

    tasks_eager: bool = False
    celery_task_always_eager: bool = False
    celery_result_backend: str | None = None
    ocr_provider: str = "local_paddle"
    paddleocr_api_url: str = "http://ocr:8118/v1"
    paddleocr_model: str = "PaddleOCR-VL-1.5-0.9B"
    # MinerU is an optional native A100 service.  Its API is multipart
    # `/file_parse`, not the OpenAI-compatible PaddleOCR contract above.
    mineru_api_url: str | None = Field(default=None, validation_alias="MINERU_API_URL")
    mineru_enabled: bool | None = Field(default=None, validation_alias="MINERU_ENABLED")
    mineru_backend: str = Field(default="hybrid-engine", validation_alias="MINERU_BACKEND")
    mineru_parse_method: str = Field(default="auto", validation_alias="MINERU_PARSE_METHOD")
    ocr_timeout_seconds: int = Field(default=120, ge=5, le=3600)
    tesseract_fallback_enabled: bool = True
    tesseract_command: str = "tesseract"
    tesseract_languages: str = "chi_sim+eng"
    # Keep the previous local configuration names as aliases so an existing
    # A100/local .env keeps its working OCR fallback after the web migration.
    # Secrets remain server-side and are never part of API DTOs.
    remote_ocr_api_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("REMOTE_OCR_API_URL", "REMOTE_API_BASE_URL"),
    )
    remote_ocr_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("REMOTE_OCR_API_KEY", "REMOTE_API_KEY"),
    )
    remote_ocr_model: str = Field(
        default="Qwen3-VL-30B-A3B-Instruct",
        validation_alias=AliasChoices("REMOTE_OCR_MODEL", "REMOTE_MODEL_NAME"),
    )
    # None means: use the configured legacy fallback. Explicit false disables
    # it for deployments that must keep OCR entirely on the A100.
    remote_ocr_enabled: bool | None = None

    bootstrap_token: str | None = None
    log_level: str = "INFO"

    @field_validator("public_api_prefix")
    @classmethod
    def normalize_prefix(cls, value: str) -> str:
        value = "/" + value.strip("/")
        return value

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    @property
    def is_tunnel(self) -> bool:
        """Whether the API is published through the private SSH backhaul."""
        return self.app_env.lower() == "tunnel"

    @property
    def is_deployed(self) -> bool:
        """Whether the API has an Internet-facing HTTPS entry point."""
        return self.is_production or self.is_tunnel

    @property
    def remote_ocr_configured(self) -> bool:
        return bool(self.remote_ocr_api_url and self.remote_ocr_api_key)

    @property
    def remote_ocr_available(self) -> bool:
        return self.remote_ocr_configured and self.remote_ocr_enabled is not False

    @property
    def mineru_available(self) -> bool:
        """A URL is enough to opt in unless the deployment explicitly disables MinerU."""
        return bool(self.mineru_api_url and self.mineru_enabled is not False)

    @property
    def allowed_hosts(self) -> list[str]:
        if self.is_deployed:
            return [self.app_domain]
        return ["localhost", "127.0.0.1", "testserver", self.app_domain]

    @model_validator(mode="after")
    def validate_deployment(self) -> "Settings":
        if not self.is_deployed:
            return self
        missing: list[str] = []
        if self.app_domain in {"", "localhost", "APP_DOMAIN"}:
            missing.append("APP_DOMAIN")
        if self.session_secret in {"", "local-development-session-secret-change-me", "SESSION_SECRET"}:
            missing.append("SESSION_SECRET")
        if not self.bootstrap_token or self.bootstrap_token == "BOOTSTRAP_TOKEN":
            missing.append("BOOTSTRAP_TOKEN")
        if self.is_production and self.database_url.startswith("sqlite"):
            missing.append("DATABASE_URL (PostgreSQL required)")
        if not self.cookie_secure:
            missing.append("COOKIE_SECURE=true")
        if missing:
            raise ValueError("Missing or unsafe deployment configuration: " + ", ".join(missing))
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
