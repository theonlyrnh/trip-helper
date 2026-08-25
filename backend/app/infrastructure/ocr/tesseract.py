"""Native OCR fallback used when the configured A100 services are unavailable."""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from pathlib import Path


class TesseractError(RuntimeError):
    pass


@dataclass(frozen=True)
class TesseractResult:
    raw_text: str
    raw_json: dict[str, str]
    duration_ms: int


class TesseractOcrClient:
    """Run the native binary without shells or host paths in API responses."""

    def __init__(self, command: str, languages: str, timeout_seconds: int) -> None:
        self.command = command
        self.languages = languages
        self.timeout_seconds = timeout_seconds

    def recognize_image(self, path: Path) -> TesseractResult:
        started = time.monotonic()
        try:
            completed = subprocess.run(
                [self.command, str(path), "stdout", "-l", self.languages, "--psm", "6"],
                check=False,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise TesseractError("Native OCR service is unavailable") from exc
        if completed.returncode != 0 or not completed.stdout.strip():
            raise TesseractError("Native OCR service returned no text")
        return TesseractResult(
            raw_text=completed.stdout.strip(),
            raw_json={"engine": "tesseract", "languages": self.languages},
            duration_ms=int((time.monotonic() - started) * 1000),
        )
