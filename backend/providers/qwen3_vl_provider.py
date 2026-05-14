"""Qwen3-VL provider – calls remote Qwen3-VL API via OpenAI-compatible endpoint."""

import time
import base64
import requests
from providers.base_ocr_provider import BaseOCRProvider, OCRResultDTO


class Qwen3VLProvider(BaseOCRProvider):
    """Calls a remote Qwen3-VL API via OpenAI-compatible chat endpoint."""

    name = "qwen3_vl"

    def __init__(
        self,
        api_url: str = "https://chatbox.isrc.ac.cn/api/v1",
        api_key: str = "",
        model_name: str = "Qwen3-VL-30B-A3B-Instruct",
        timeout: int = 120,
    ):
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self.model_name = model_name
        self.timeout = timeout

    def _call_api(self, image_path: str, prompt: str) -> OCRResultDTO:
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
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
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
                error_message="Cannot connect to Qwen3-VL server",
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
        return self._call_api(pdf_path, prompt)