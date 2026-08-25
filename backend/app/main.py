"""Production FastAPI entry point for the A100 private API."""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import router as v1_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.infrastructure.db.session import init_database
from app.infrastructure.storage.local import LocalStorage


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    LocalStorage()
    # Native production setup runs Alembic in ExecStartPre. Local/test starts
    # can create isolated development tables without touching legacy SQLite.
    init_database()
    logger.info("application_started", extra={"event": "application_started"})
    yield
    logger.info("application_stopped", extra={"event": "application_stopped"})


settings = get_settings()
app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    docs_url=None if settings.is_deployed else "/docs",
    redoc_url=None if settings.is_deployed else "/redoc",
    openapi_url=None if settings.is_deployed else "/openapi.json",
    lifespan=lifespan,
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)

if not settings.is_deployed:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:4173"],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Content-Type", settings.csrf_header_name],
    )


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", "")[:64] or uuid4().hex
    request.state.request_id = request_id
    started = time.monotonic()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception(
            "Unhandled request failure",
            extra={"request_id": request_id, "event": "request_failed"},
        )
        response = JSONResponse(status_code=500, content={"detail": "Internal server error"})
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "request_complete",
        extra={"request_id": request_id, "event": "request_complete", "duration_ms": int((time.monotonic() - started) * 1000)},
    )
    return response


app.include_router(v1_router, prefix=settings.public_api_prefix)
