"""Shared result and error types for server-side OCR adapters."""

from __future__ import annotations

from dataclasses import dataclass


class OcrProviderError(RuntimeError):
    pass


@dataclass(frozen=True)
class RecognitionResult:
    raw_text: str
    raw_json: dict
    duration_ms: int
    provider: str
    model: str
