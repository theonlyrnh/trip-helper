"""Unauthenticated liveness/readiness endpoints for deployment probes."""

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.infrastructure.db.session import get_db
from app.infrastructure.storage.local import LocalStorage
from app.schemas import HealthRead


router = APIRouter(tags=["health"])


def _live() -> HealthRead:
    return HealthRead(status="ok", service="trip-helper-api", version="1")


@router.get("/health", response_model=HealthRead)
def health() -> HealthRead:
    return _live()


@router.get("/health/live", response_model=HealthRead)
def live() -> HealthRead:
    return _live()


@router.get("/health/ready", response_model=HealthRead)
def ready(response: Response, db: Session = Depends(get_db)) -> HealthRead:
    checks: dict[str, str] = {}
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "unavailable"
    try:
        LocalStorage()
        checks["storage"] = "ok"
    except Exception:
        checks["storage"] = "unavailable"
    settings = get_settings()
    if settings.redis_url.startswith("memory://") or settings.tasks_eager:
        checks["queue"] = "eager"
    else:
        try:
            import redis

            redis.Redis.from_url(settings.redis_url, socket_connect_timeout=0.5, socket_timeout=0.5).ping()
            checks["queue"] = "ok"
        except Exception:
            checks["queue"] = "unavailable"
    checks["ocr"] = "configured" if (
        settings.mineru_available or settings.remote_ocr_available or settings.tesseract_fallback_enabled
    ) else "unavailable"
    ready_state = all(value in {"ok", "eager", "configured"} for value in checks.values())
    if not ready_state:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return HealthRead(
        status="ready" if ready_state else "unavailable",
        service="trip-helper-api",
        version="1",
        checks=checks,
    )
