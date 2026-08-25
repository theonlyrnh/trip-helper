"""Tiered client for the A100-local OCR providers."""

from __future__ import annotations

import base64
import time
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx

from app.core.config import Settings, get_settings
from app.infrastructure.ocr.base import OcrProviderError, RecognitionResult
from app.infrastructure.ocr.mineru import MineruOcrClient
from app.infrastructure.ocr.tesseract import TesseractError, TesseractOcrClient


class PaddleOcrClient:
    """Route image recognition through PaddleOCR, MinerU, remote VL, or Tesseract."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def recognize_image(self, path: Path, mime_type: str, *, allow_remote: bool = True) -> RecognitionResult:
        started = time.monotonic()
        provider_mode = self.settings.ocr_provider.strip().lower()
        errors: list[OcrProviderError] = []
        mineru_only = provider_mode in {"mineru", "mineru_only", "local_mineru"}
        paddle_disabled_modes = {
            "remote",
            "remote_only",
            "tesseract",
            "local_tesseract",
            "mineru",
            "mineru_only",
            "local_mineru",
        }
        payload: dict | None = None
        if mineru_only:
            try:
                return MineruOcrClient(self.settings).recognize_image(path, mime_type)
            except OcrProviderError as error:
                errors.append(error)

        if provider_mode not in paddle_disabled_modes:
            payload = self._openai_payload(path, mime_type)
            try:
                return self._request(
                    url=self.settings.paddleocr_api_url,
                    payload=payload or {},
                    provider="paddleocr_vl",
                    model=self.settings.paddleocr_model,
                    started=started,
                )
            except OcrProviderError as error:
                errors.append(error)

            if self.settings.mineru_available:
                try:
                    return MineruOcrClient(self.settings).recognize_image(path, mime_type)
                except OcrProviderError as error:
                    errors.append(error)

        if (
            provider_mode not in {"tesseract", "local_tesseract"}
            and allow_remote
            and self.settings.remote_ocr_available
        ):
            provider_credential = self.settings.remote_ocr_api_key
            if provider_credential is not None:
                payload = payload or self._openai_payload(path, mime_type)
                try:
                    return self._request(
                        url=self.settings.remote_ocr_api_url or "",
                        payload={**payload, "model": self.settings.remote_ocr_model},
                        provider="remote_vl",
                        model=self.settings.remote_ocr_model,
                        started=started,
                        headers={"Authorization": f"Bearer {provider_credential.get_secret_value()}"},
                    )
                except OcrProviderError as error:
                    errors.append(error)

        if self.settings.tesseract_fallback_enabled or provider_mode in {"tesseract", "local_tesseract"}:
            try:
                fallback = TesseractOcrClient(
                    self.settings.tesseract_command,
                    self.settings.tesseract_languages,
                    self.settings.ocr_timeout_seconds,
                ).recognize_image(path)
                return RecognitionResult(
                    raw_text=fallback.raw_text,
                    raw_json=fallback.raw_json,
                    duration_ms=int((time.monotonic() - started) * 1000),
                    provider="tesseract",
                    model=self.settings.tesseract_languages,
                )
            except TesseractError as error:
                errors.append(OcrProviderError(str(error)))

        if errors:
            raise OcrProviderError(str(errors[-1])) from errors[-1]
        raise OcrProviderError("No OCR provider is enabled")

    def _openai_payload(self, path: Path, mime_type: str) -> dict:
        # Encode in bounded chunks rather than materialising the source file
        # with ``read_bytes``. The final provider payload is still bounded by
        # the upload limit and is released after the request completes.
        max_bytes = self.settings.max_upload_bytes
        if path.stat().st_size > max_bytes:
            raise OcrProviderError("OCR image exceeds the configured limit")
        encoded_parts: list[bytes] = []
        with path.open("rb") as source:
            remainder = b""
            while chunk := source.read(self.settings.upload_chunk_bytes):
                chunk = remainder + chunk
                usable = len(chunk) - (len(chunk) % 3)
                if usable:
                    encoded_parts.append(base64.b64encode(chunk[:usable]))
                remainder = chunk[usable:]
            if remainder:
                encoded_parts.append(base64.b64encode(remainder))
        encoded = b"".join(encoded_parts).decode("ascii")
        return {
            "model": self.settings.paddleocr_model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{encoded}"}},
                        {"type": "text", "text": "请识别图片中的全部文字，按阅读顺序输出。"},
                    ],
                }
            ],
            "max_tokens": 4096,
        }

    def _request(
        self,
        *,
        url: str,
        payload: dict,
        provider: str,
        model: str,
        started: float,
        headers: dict[str, str] | None = None,
    ) -> RecognitionResult:
        endpoint = f"{url.rstrip('/')}/chat/completions"
        try:
            with httpx.Client(timeout=self.settings.ocr_timeout_seconds) as client:
                response = self._post_with_legacy_gateway_redirect(client, endpoint, payload, headers)
                response.raise_for_status()
                body = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise OcrProviderError("OCR service is unavailable") from exc
        if not isinstance(body, dict):
            raise OcrProviderError("OCR service returned an invalid response")
        choices = body.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            raise OcrProviderError("OCR service returned an invalid response")
        message = choices[0].get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str) or not content.strip():
            raise OcrProviderError("OCR service returned no text")
        return RecognitionResult(
            raw_text=content.strip(),
            raw_json=body,
            duration_ms=int((time.monotonic() - started) * 1000),
            provider=provider,
            model=model,
        )

    @staticmethod
    def _post_with_legacy_gateway_redirect(
        client: httpx.Client,
        endpoint: str,
        payload: dict,
        headers: dict[str, str] | None,
    ) -> httpx.Response:
        """Repeat a POST at a trusted gateway without losing the API path or auth."""
        current_endpoint = endpoint
        fallback_endpoints: list[str] = []
        for _ in range(4):
            response = client.post(current_endpoint, json=payload, headers=headers)
            if response.status_code == 404 and fallback_endpoints:
                current_endpoint = fallback_endpoints.pop(0)
                continue
            if response.status_code not in {301, 302, 303, 307, 308}:
                return response
            location = response.headers.get("location")
            if not location:
                return response
            redirected_endpoints = PaddleOcrClient._gateway_endpoints(current_endpoint, location)
            if not redirected_endpoints or not all(
                PaddleOcrClient._is_trusted_gateway_redirect(current_endpoint, item)
                for item in redirected_endpoints
            ):
                raise OcrProviderError("OCR endpoint redirected to an untrusted gateway")
            current_endpoint, *fallback_endpoints = redirected_endpoints
        raise OcrProviderError("OCR endpoint redirected too many times")

    @staticmethod
    def _gateway_endpoints(endpoint: str, location: str) -> list[str]:
        redirected = urlsplit(urljoin(endpoint, location))
        original = urlsplit(endpoint)
        path = redirected.path
        if path in {"", "/"}:
            path = original.path
        endpoints = [urlunsplit((redirected.scheme, redirected.netloc, path, redirected.query, ""))]
        # The legacy Chatbox address used /api/v1, while its current gateway
        # exposes the same OpenAI contract at /v1. Try that compatible path
        # only after the preserved path explicitly reports 404.
        if path.startswith("/api/"):
            endpoints.append(urlunsplit((redirected.scheme, redirected.netloc, path.removeprefix("/api"), redirected.query, "")))
        return endpoints

    @staticmethod
    def _is_trusted_gateway_redirect(endpoint: str, redirected_endpoint: str) -> bool:
        source = urlsplit(endpoint)
        target = urlsplit(redirected_endpoint)
        if source.scheme != "https" or target.scheme != "https":
            return source.netloc == target.netloc
        source_host = (source.hostname or "").lower()
        target_host = (target.hostname or "").lower()
        if source_host == target_host:
            return True
        source_parent = source_host.split(".", 1)[1] if "." in source_host else ""
        target_parent = target_host.split(".", 1)[1] if "." in target_host else ""
        return bool(source_parent and source_parent == target_parent)
