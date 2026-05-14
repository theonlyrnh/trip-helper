"""Base OCR provider interface and DTO."""

from dataclasses import dataclass, field


@dataclass
class OCRResultDTO:
    success: bool
    raw_text: str
    raw_json: dict | None = None
    confidence: float | None = None
    provider: str = ""
    model_name: str = ""
    duration_ms: int = 0
    error_message: str | None = None


class BaseOCRProvider:
    """Abstract base for OCR providers."""

    name: str = "base"

    def recognize_image(self, image_path: str, prompt: str = "") -> OCRResultDTO:
        raise NotImplementedError

    def recognize_pdf_page(
        self, pdf_path: str, page_index: int, prompt: str = ""
    ) -> OCRResultDTO:
        raise NotImplementedError