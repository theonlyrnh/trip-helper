"""Provider factory – selects the appropriate OCR provider based on config."""

from providers.base_ocr_provider import BaseOCRProvider
from providers.paddleocr_vl_provider import PaddleOCRVLProvider
from providers.mock_ocr_provider import MockOCRProvider
from config import settings


def get_ocr_provider(mode: str | None = None) -> BaseOCRProvider:
    """
    Return an OCR provider instance based on the configured mode.

    Modes:
      - local_first: try PaddleOCR, fall back to mock
      - local_only: PaddleOCR only
      - mock: mock provider for testing
    """
    mode = mode or settings.OCR_PROVIDER_MODE

    if mode == "mock":
        return MockOCRProvider()

    if mode in ("local_first", "local_only"):
        return PaddleOCRVLProvider(
            api_url=settings.PADDLEOCR_API_URL or "http://localhost:8118/v1",
            model_name=settings.PADDLEOCR_MODEL or "PaddleOCR-VL-1.5-0.9B",
        )

    # Default fallback
    return MockOCRProvider()