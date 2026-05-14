"""PaddleOCR-VL provider – calls local PaddleOCR API via OpenAI-compatible endpoint."""

import time
import base64
import requests
from providers.base_ocr_provider import BaseOCRProvider, OCRResultDTO


class PaddleOCRVLProvider(BaseOCRProvider):
    """Calls a local PaddleOCR-VL server via OpenAI-compatible chat API."""

    name = "paddleocr_vl"

    def __init__(
        self,
        api_url: str = "http://localhost:8118/v1",
        model_name: str = "PaddleOCR-VL-1.5-0.9B",
        timeout: int = 60,
    ):
        self.api_url = api_url.rstrip("/")
        self.model_name = model_name
        self.timeout = timeout

    def _call_api(self, image_path: str, prompt: str) -> OCRResultDTO:
        """Send image to PaddleOCR-VL and return structured result."""
        start = time.time()

        try:
            with open(image_path, "rb") as f:
                image_data = base64.b64encode(f.read()).decode("utf-8")

            ext = image_path.rsplit(".", 1)[-1].lower()
            mime = f"image/{ext}" if ext in ("png", "jpg", "jpeg") else "image/png"

            payload = {
                "model": self.model_name,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{mime};base64,{image_data}"
                                },
                            },
                            {"type": "text", "text": prompt or "请识别这张图片中的所有文字内容。"},
                        ],
                    }
                ],
                "max_tokens": 2048,
            }

            resp = requests.post(
                f"{self.api_url}/chat/completions",
                json=payload,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()

            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            duration_ms = int((time.time() - start) * 1000)

            return OCRResultDTO(
                success=True,
                raw_text=content.strip(),
                raw_json=data,
                confidence=None,
                provider=self.name,
                model_name=self.model_name,
                duration_ms=duration_ms,
            )

        except requests.exceptions.ConnectionError:
            duration_ms = int((time.time() - start) * 1000)
            return OCRResultDTO(
                success=False,
                raw_text="",
                provider=self.name,
                model_name=self.model_name,
                duration_ms=duration_ms,
                error_message="Cannot connect to PaddleOCR-VL server",
            )
        except Exception as e:
            duration_ms = int((time.time() - start) * 1000)
            return OCRResultDTO(
                success=False,
                raw_text="",
                provider=self.name,
                model_name=self.model_name,
                duration_ms=duration_ms,
                error_message=str(e),
            )

    def recognize_image(self, image_path: str, prompt: str = "") -> OCRResultDTO:
        return self._call_api(image_path, prompt)

    def recognize_pdf_page(
        self, pdf_path: str, page_index: int, prompt: str = ""
    ) -> OCRResultDTO:
        # For PDF, we expect the page to already be rendered as an image
        return self._call_api(pdf_path, prompt)