from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import pytest
from fastapi.testclient import TestClient


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


@dataclass
class WebRuntime:
    client: TestClient
    session_factory: object
    storage_root: Path


@pytest.fixture()
def web_runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[WebRuntime]:
    """Run the API against isolated SQLite, storage, and in-process Celery tasks."""
    database_path = tmp_path / "trip-helper-test.db"
    storage_root = tmp_path / "storage"
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("APP_DOMAIN", "testserver")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path}")
    monkeypatch.setenv("STORAGE_ROOT", str(storage_root))
    monkeypatch.setenv("REDIS_URL", "memory://")
    monkeypatch.setenv("TASKS_EAGER", "true")
    monkeypatch.setenv("CELERY_TASK_ALWAYS_EAGER", "true")
    monkeypatch.setenv("CELERY_RESULT_BACKEND", "cache+memory://")

    from app.core.config import get_settings
    from app.infrastructure.db.session import get_engine, get_session_factory

    get_settings.cache_clear()
    get_session_factory.cache_clear()
    get_engine.cache_clear()

    from app.core.rate_limit import login_rate_limiter
    from app.infrastructure.queue.celery import celery_app
    from app.main import app

    login_rate_limiter.clear()
    celery_app.conf.update(
        broker_url="memory://",
        result_backend="cache+memory://",
        task_always_eager=True,
        task_eager_propagates=True,
    )

    with TestClient(app, raise_server_exceptions=True) as client:
        yield WebRuntime(
            client=client,
            session_factory=get_session_factory(),
            storage_root=storage_root,
        )

    get_engine().dispose()
    get_session_factory.cache_clear()
    get_engine.cache_clear()
    get_settings.cache_clear()
