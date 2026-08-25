from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest


class _Response:
    def __init__(self, body: dict, status_code: int = 200, headers: dict[str, str] | None = None) -> None:
        self.body = body
        self.status_code = status_code
        self.headers = headers or {}

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self.body


def _success_body(text: str) -> dict:
    return {"choices": [{"message": {"content": text}}]}


def test_existing_remote_api_environment_aliases_enable_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import Settings

    monkeypatch.setenv("REMOTE_API_BASE_URL", "https://legacy-ocr.example/v1")
    monkeypatch.setenv("REMOTE_API_KEY", "legacy-token")
    monkeypatch.setenv("REMOTE_MODEL_NAME", "legacy-vl")
    monkeypatch.delenv("REMOTE_OCR_ENABLED", raising=False)

    settings = Settings()

    assert settings.remote_ocr_api_url == "https://legacy-ocr.example/v1"
    assert settings.remote_ocr_api_key is not None
    assert settings.remote_ocr_api_key.get_secret_value() == "legacy-token"
    assert settings.remote_ocr_model == "legacy-vl"
    assert settings.remote_ocr_available is True


def test_local_ocr_failure_uses_configured_server_side_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core.config import Settings
    from app.infrastructure.ocr.paddle import PaddleOcrClient

    image = tmp_path / "receipt.png"
    image.write_bytes(b"fixture-image")
    calls: list[tuple[str, dict, dict[str, str] | None]] = []

    class Client:
        responses: list[object] = [httpx.ConnectError("local unavailable"), _Response(_success_body("远程识别文本"))]

        def __init__(self, **_: object) -> None:
            pass

        def __enter__(self) -> "Client":
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def post(self, url: str, *, json: dict, headers: dict[str, str] | None = None) -> _Response:
            calls.append((url, json, headers))
            response = self.responses.pop(0)
            if isinstance(response, Exception):
                raise response
            return response  # type: ignore[return-value]

    monkeypatch.setattr("app.infrastructure.ocr.paddle.httpx.Client", Client)
    settings = Settings(
        paddleocr_api_url="http://paddle.internal/v1",
        paddleocr_model="local-model",
        remote_ocr_api_url="https://remote.example/v1",
        remote_ocr_api_key="server-only-token",
        remote_ocr_model="remote-model",
        remote_ocr_enabled=True,
    )

    result = PaddleOcrClient(settings).recognize_image(image, "image/png")

    assert result.raw_text == "远程识别文本"
    assert result.provider == "remote_vl"
    assert result.model == "remote-model"
    assert [url for url, _, _ in calls] == [
        "http://paddle.internal/v1/chat/completions",
        "https://remote.example/v1/chat/completions",
    ]
    assert calls[1][1]["model"] == "remote-model"
    assert calls[1][2] == {"Authorization": "Bearer server-only-token"}


def test_ocr_replays_a_legacy_remote_gateway_redirect_with_the_original_api_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core.config import Settings
    from app.infrastructure.ocr.paddle import PaddleOcrClient

    image = tmp_path / "receipt.png"
    image.write_bytes(b"fixture-image")
    calls: list[tuple[str, dict[str, str] | None]] = []

    class Client:
        def __init__(self, **kwargs: object) -> None:
            assert kwargs == {"timeout": 120}

        def __enter__(self) -> "Client":
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def post(self, url: str, *, headers: dict[str, str] | None = None, **_: object) -> _Response:
            calls.append((url, headers))
            if len(calls) == 1:
                return _Response({}, 302, {"location": "https://gateway.example"})
            return _Response(_success_body("本地识别文本"))

    monkeypatch.setattr("app.infrastructure.ocr.paddle.httpx.Client", Client)
    settings = Settings(paddleocr_api_url="https://legacy.example/v1")

    PaddleOcrClient(settings).recognize_image(image, "image/png")

    assert calls == [
        ("https://legacy.example/v1/chat/completions", None),
        ("https://gateway.example/v1/chat/completions", None),
    ]


def test_ocr_uses_the_current_v1_gateway_after_legacy_api_v1_reports_not_found(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core.config import Settings
    from app.infrastructure.ocr.paddle import PaddleOcrClient

    image = tmp_path / "receipt.png"
    image.write_bytes(b"fixture-image")
    calls: list[str] = []

    class Client:
        def __init__(self, **_: object) -> None:
            pass

        def __enter__(self) -> "Client":
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def post(self, url: str, **_: object) -> _Response:
            calls.append(url)
            if len(calls) == 1:
                return _Response({}, 302, {"location": "https://gateway.example"})
            if len(calls) == 2:
                return _Response({}, 404)
            return _Response(_success_body("网关识别文本"))

    monkeypatch.setattr("app.infrastructure.ocr.paddle.httpx.Client", Client)
    settings = Settings(paddleocr_api_url="https://legacy.example/api/v1")

    result = PaddleOcrClient(settings).recognize_image(image, "image/png")

    assert result.raw_text == "网关识别文本"
    assert calls == [
        "https://legacy.example/api/v1/chat/completions",
        "https://gateway.example/api/v1/chat/completions",
        "https://gateway.example/v1/chat/completions",
    ]


def test_remote_ocr_is_not_called_when_disabled(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import Settings
    from app.infrastructure.ocr.paddle import OcrProviderError, PaddleOcrClient

    image = tmp_path / "receipt.png"
    image.write_bytes(b"fixture-image")
    calls: list[str] = []

    class Client:
        def __init__(self, **_: object) -> None:
            pass

        def __enter__(self) -> "Client":
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def post(self, url: str, **_: object) -> _Response:
            calls.append(url)
            raise httpx.ConnectError("local unavailable")

    monkeypatch.setattr("app.infrastructure.ocr.paddle.httpx.Client", Client)
    settings = Settings(
        paddleocr_api_url="http://paddle.internal/v1",
        remote_ocr_api_url="https://remote.example/v1",
        remote_ocr_api_key="server-only-token",
        remote_ocr_enabled=False,
        tesseract_fallback_enabled=False,
    )

    with pytest.raises(OcrProviderError):
        PaddleOcrClient(settings).recognize_image(image, "image/png")

    assert calls == ["http://paddle.internal/v1/chat/completions"]


def test_native_tesseract_is_used_after_configured_network_ocr_is_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core.config import Settings
    from app.infrastructure.ocr.paddle import PaddleOcrClient

    image = tmp_path / "receipt.png"
    image.write_bytes(b"fixture-image")

    class Client:
        def __init__(self, **_: object) -> None:
            pass

        def __enter__(self) -> "Client":
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def post(self, *_: object, **__: object) -> _Response:
            raise httpx.ConnectError("local unavailable")

    commands: list[list[str]] = []

    def native_ocr(command: list[str], **_: object) -> SimpleNamespace:
        commands.append(command)
        return SimpleNamespace(returncode=0, stdout="\u7535\u5b50\u53d1\u7968\n\u5408\u8ba1 123.45\n", stderr="")

    monkeypatch.setattr("app.infrastructure.ocr.paddle.httpx.Client", Client)
    monkeypatch.setattr("app.infrastructure.ocr.tesseract.subprocess.run", native_ocr)
    settings = Settings(
        paddleocr_api_url="http://paddle.internal/v1",
        remote_ocr_enabled=False,
        tesseract_fallback_enabled=True,
        tesseract_command="tesseract",
        tesseract_languages="chi_sim+eng",
    )

    result = PaddleOcrClient(settings).recognize_image(image, "image/png")

    assert result.provider == "tesseract"
    assert result.model == "chi_sim+eng"
    assert result.raw_text == "\u7535\u5b50\u53d1\u7968\n\u5408\u8ba1 123.45"
    assert commands == [["tesseract", str(image), "stdout", "-l", "chi_sim+eng", "--psm", "6"]]


def test_mineru_provider_parses_native_file_parse_response(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core.config import Settings
    from app.infrastructure.ocr.paddle import PaddleOcrClient

    image = tmp_path / "ticket.png"
    image.write_bytes(b"fixture-image")
    calls: list[tuple[str, dict, dict]] = []

    class Client:
        def __init__(self, **kwargs: object) -> None:
            assert kwargs == {"timeout": 120}

        def __enter__(self) -> "Client":
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def post(self, url: str, *, files: dict, data: dict) -> _Response:
            calls.append((url, files, data))
            return _Response(
                {
                    "version": "3.3.1",
                    "results": {"ticket": {"md_content": "![](images/ticket.png)\n\n# 北京南\nG1234  ¥123.00"}},
                }
            )

    monkeypatch.setattr("app.infrastructure.ocr.mineru.httpx.Client", Client)
    settings = Settings(
        ocr_provider="mineru",
        mineru_api_url="http://127.0.0.1:8888",
        tesseract_fallback_enabled=False,
    )

    result = PaddleOcrClient(settings).recognize_image(image, "image/png")

    assert result.provider == "mineru"
    assert result.model == "hybrid-engine-3.3.1"
    assert result.raw_text == "北京南\nG1234 ¥123.00"
    assert calls[0][0] == "http://127.0.0.1:8888/file_parse"
    assert calls[0][2]["backend"] == "hybrid-engine"
    assert calls[0][2]["parse_method"] == "auto"


def test_mineru_is_used_after_paddle_service_is_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core.config import Settings
    from app.infrastructure.ocr.paddle import PaddleOcrClient

    image = tmp_path / "ticket.png"
    image.write_bytes(b"fixture-image")

    class PaddleClient:
        def __init__(self, **_: object) -> None:
            pass

        def __enter__(self) -> "PaddleClient":
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def post(self, *_: object, **__: object) -> _Response:
            raise httpx.ConnectError("paddle unavailable")

    class MineruClient:
        def __init__(self, **_: object) -> None:
            pass

        def __enter__(self) -> "MineruClient":
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def post(self, *_: object, **__: object) -> _Response:
            return _Response({"results": {"ticket": {"md_content": "南京南 -> 北京南"}}})

    monkeypatch.setattr("app.infrastructure.ocr.paddle.httpx.Client", PaddleClient)
    monkeypatch.setattr("app.infrastructure.ocr.mineru.httpx.Client", MineruClient)
    settings = Settings(
        ocr_provider="local_paddle",
        paddleocr_api_url="http://paddle.internal/v1",
        mineru_api_url="http://mineru.internal:8888",
        remote_ocr_enabled=False,
        tesseract_fallback_enabled=False,
    )

    result = PaddleOcrClient(settings).recognize_image(image, "image/png")

    assert result.provider == "mineru"
    assert result.raw_text == "南京南 -> 北京南"
