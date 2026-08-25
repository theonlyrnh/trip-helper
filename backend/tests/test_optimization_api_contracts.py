from __future__ import annotations

from hashlib import sha256

from sqlalchemy import select


API = "/api/v1"
LOGIN_VALUE = "correct-horse-battery-staple"


def _bootstrap(client, email: str = "contract@example.test") -> str:
    response = client.post(
        f"{API}/auth/bootstrap",
        json={"email": email, "password": LOGIN_VALUE},
    )
    assert response.status_code == 201, response.text
    return response.json()["csrf_token"]


def _headers(csrf_value: str) -> dict[str, str]:
    return {"X-CSRF-Token": csrf_value}


def _trip(client, csrf_value: str) -> dict:
    response = client.post(f"{API}/trips", headers=_headers(csrf_value), json={"title": "API contract trip"})
    assert response.status_code == 201, response.text
    return response.json()


def test_private_streams_and_exports_set_no_store_headers(web_runtime) -> None:
    from app.infrastructure.db.models import Document, DocumentPage, OcrRun, User
    from app.infrastructure.storage.local import LocalStorage

    client = web_runtime.client
    csrf_value = _bootstrap(client)
    trip = _trip(client, csrf_value)
    db = web_runtime.session_factory()
    try:
        owner = db.scalar(select(User).where(User.email == "contract@example.test"))
        assert owner is not None
        storage = LocalStorage(root=web_runtime.storage_root)
        document = Document(
            trip_id=trip["id"],
            storage_key="originals/private.bin",
            original_filename="private.bin",
            sha256=sha256(b"private").hexdigest(),
            size_bytes=7,
            mime_type="application/octet-stream",
            file_extension=".bin",
            document_type="UNKNOWN",
        )
        db.add(document)
        db.flush()
        page = DocumentPage(document_id=document.id, page_index=0, preview_key="previews/private.png")
        run = OcrRun(document_id=document.id, provider="fixture", raw_text="private OCR", status="SUCCEEDED")
        db.add_all((page, run))
        db.commit()
        storage.put_bytes(b"private", document.storage_key)
        storage.put_bytes(b"preview", page.preview_key)
        document_id = document.id
    finally:
        db.close()

    content = client.get(f"{API}/documents/{document_id}/content")
    preview = client.get(f"{API}/documents/{document_id}/preview")
    ocr = client.get(f"{API}/documents/{document_id}/ocr")
    assert content.status_code == preview.status_code == ocr.status_code == 200
    assert content.headers["cache-control"] == "no-store"
    assert preview.headers["cache-control"] == "no-store"
    assert ocr.headers["cache-control"] == "no-store"
    assert "attachment" not in content.headers.get("content-disposition", "").lower()

    created = client.post(f"{API}/trips/{trip['id']}/exports", headers=_headers(csrf_value), json={"format": "PDF"})
    assert created.status_code == 202, created.text
    export_id = created.json()["id"]
    downloaded = client.get(f"{API}/exports/{export_id}/download")
    assert downloaded.status_code == 200, downloaded.text
    assert downloaded.headers["cache-control"] == "no-store"
    assert "attachment" in downloaded.headers["content-disposition"].lower()


def test_documents_are_paginated_with_total_count(web_runtime) -> None:
    from app.infrastructure.db.models import Document, User

    client = web_runtime.client
    csrf_value = _bootstrap(client)
    trip = _trip(client, csrf_value)
    db = web_runtime.session_factory()
    try:
        owner = db.scalar(select(User).where(User.email == "contract@example.test"))
        assert owner is not None
        for index in range(205):
            db.add(
                Document(
                    trip_id=trip["id"],
                    storage_key=f"originals/page-{index}.bin",
                    original_filename=f"page-{index}.bin",
                    sha256=sha256(f"page-{index}".encode()).hexdigest(),
                    size_bytes=1,
                    mime_type="application/octet-stream",
                    file_extension=".bin",
                    document_type="UNKNOWN",
                )
            )
        db.commit()
    finally:
        db.close()

    response = client.get(f"{API}/trips/{trip['id']}/documents?page=2&page_size=100")
    assert response.status_code == 200, response.text
    assert len(response.json()) == 100
    assert response.headers["x-total-count"] == "205"
    assert response.headers["x-page"] == "2"
    assert response.headers["x-page-size"] == "100"
    assert response.headers["cache-control"] == "no-store"


def test_health_readiness_and_session_lifecycle(web_runtime) -> None:
    client = web_runtime.client
    assert client.get(f"{API}/health/live").json()["status"] == "ok"
    ready = client.get(f"{API}/health/ready")
    assert ready.status_code == 200
    assert ready.json()["status"] == "ready"
    assert ready.json()["checks"]["database"] == "ok"
    assert ready.json()["checks"]["queue"] == "eager"

    _bootstrap(client)
    second_login = client.post(
        f"{API}/auth/login",
        json={"email": "contract@example.test", "password": LOGIN_VALUE},
    )
    assert second_login.status_code == 200, second_login.text
    second_csrf = second_login.json()["csrf_token"]
    sessions = client.get(f"{API}/auth/sessions")
    assert sessions.status_code == 200
    assert len(sessions.json()) == 2
    assert sum(1 for item in sessions.json() if item["current"]) == 1

    changed = client.post(
        f"{API}/auth/change-password",
        headers=_headers(second_csrf),
        json={"current_password": LOGIN_VALUE, "new_password": "new-correct-horse-battery"},
    )
    assert changed.status_code == 204, changed.text
    assert len(client.get(f"{API}/auth/sessions").json()) == 1

    revoked = client.post(f"{API}/auth/revoke-all", headers=_headers(second_csrf))
    assert revoked.status_code == 204, revoked.text
    assert client.get(f"{API}/auth/me").status_code == 401


def test_login_limiter_uses_shared_counter_and_bounded_fallback() -> None:
    from app.core.rate_limit import LoginRateLimiter

    class Pipeline:
        def __init__(self, store: dict[str, int]) -> None:
            self.store = store
            self.key = ""

        def __enter__(self):
            return self

        def __exit__(self, *_args) -> None:
            return None

        def incr(self, key: str) -> None:
            self.key = key
            self.store[key] = self.store.get(key, 0) + 1

        def expire(self, _key: str, _seconds: int) -> None:
            return None

        def execute(self) -> tuple[int, bool]:
            return self.store[self.key], True

    class RedisFixture:
        def __init__(self) -> None:
            self.store: dict[str, int] = {}

        def pipeline(self, **_kwargs):
            return Pipeline(self.store)

    limiter = LoginRateLimiter(attempts=2, max_local_keys=2)
    redis_fixture = RedisFixture()
    limiter._redis_client = lambda: redis_fixture
    assert limiter.allowed("client@example.test") is True
    assert limiter.allowed("client@example.test") is True
    assert limiter.allowed("client@example.test") is False
    assert limiter._records == {}

    limiter._redis_client = lambda: None
    for index in range(5):
        limiter.allowed(f"fallback-{index}")
    assert len(limiter._records) <= 2
