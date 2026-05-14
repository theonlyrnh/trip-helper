"""Mock OCR provider – returns fixed text for testing without a real OCR server."""

import time
from providers.base_ocr_provider import BaseOCRProvider, OCRResultDTO


class MockOCRProvider(BaseOCRProvider):
    """Returns canned OCR text for testing purposes."""

    name = "mock"

    def __init__(self):
        self._call_count = 0

    def recognize_image(self, image_path: str, prompt: str = "") -> OCRResultDTO:
        self._call_count += 1
        return OCRResultDTO(
            success=True,
            raw_text=self._mock_text(),
            confidence=0.95,
            provider=self.name,
            model_name="mock-v1",
            duration_ms=10,
        )

    def recognize_pdf_page(
        self, pdf_path: str, page_index: int, prompt: str = ""
    ) -> OCRResultDTO:
        return self.recognize_image(pdf_path, prompt)

    @staticmethod
    def _mock_text() -> str:
        """Return a realistic Chinese invoice OCR text sample."""
        return (
            "电子客票行程单\n"
            "航班号：CA1234\n"
            "乘机人：张三\n"
            "出发城市：上海\n"
            "到达城市：北京\n"
            "起飞日期：2026-04-07\n"
            "票价：1060.00\n"
            "燃油附加费：120.00\n"
            "机场建设费：50.00\n"
            "合计金额：1230.00\n"
        )