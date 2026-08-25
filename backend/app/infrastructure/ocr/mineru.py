"""Client for the native MinerU FastAPI service running on the A100."""

from __future__ import annotations

import re
import time
from pathlib import Path

import httpx

from app.core.config import Settings
from app.infrastructure.ocr.base import OcrProviderError, RecognitionResult


class MineruOcrClient:
    """Submit one image to MinerU and flatten its markdown result to OCR text."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def recognize_image(self, path: Path, mime_type: str) -> RecognitionResult:
        if not self.settings.mineru_api_url:
            raise OcrProviderError("MinerU OCR is not configured")
        started = time.monotonic()
        endpoint = self._endpoint(self.settings.mineru_api_url)
        data = {
            "backend": self.settings.mineru_backend,
            "parse_method": self.settings.mineru_parse_method,
            "lang_list": "ch",
            "return_md": "true",
            "return_middle_json": "false",
            "return_model_output": "false",
            "return_content_list": "false",
            "return_images": "false",
        }
        try:
            with (
                path.open("rb") as source,
                httpx.Client(timeout=self.settings.ocr_timeout_seconds) as client,
            ):
                response = client.post(
                    endpoint,
                    files={"files": (path.name, source, mime_type)},
                    data=data,
                )
                response.raise_for_status()
                body = response.json()
        except (OSError, httpx.HTTPError, ValueError) as exc:
            raise OcrProviderError("MinerU OCR service is unavailable") from exc

        raw_text = self._extract_text(body)
        if not raw_text:
            raise OcrProviderError("MinerU OCR service returned no text")
        version = body.get("version") if isinstance(body, dict) else None
        model = f"{self.settings.mineru_backend}{('-' + str(version)) if version else ''}"
        return RecognitionResult(
            raw_text=raw_text,
            raw_json=body if isinstance(body, dict) else {"response": body},
            duration_ms=int((time.monotonic() - started) * 1000),
            provider="mineru",
            model=model,
        )

    @staticmethod
    def _endpoint(url: str) -> str:
        normalized = url.rstrip("/")
        return normalized if normalized.endswith("/file_parse") else f"{normalized}/file_parse"

    @classmethod
    def _extract_text(cls, body: object) -> str:
        if not isinstance(body, dict):
            return ""
        results = body.get("results")
        if not isinstance(results, dict):
            return ""
        chunks: list[str] = []
        for result in results.values():
            if not isinstance(result, dict):
                continue
            content = result.get("md_content")
            if isinstance(content, str) and content.strip():
                chunks.append(cls._clean_markdown(content))
        return "\n\n".join(chunk for chunk in chunks if chunk)

    @staticmethod
    def _clean_markdown(value: str) -> str:
        # Extractors consume plain text; image references only add noise and
        # may point at the temporary output directory of the OCR service.
        value = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", value)
        value = re.sub(r"<[^>]+>", " ", value)
        value = re.sub(r"^\s{0,3}#{1,6}\s*", "", value, flags=re.MULTILINE)
        value = re.sub(r"[ \t]+", " ", value)
        value = re.sub(r"\n{3,}", "\n\n", value)
        return value.strip()
