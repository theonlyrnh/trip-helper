"""Internal OCR provider adapter."""

from .base import OcrProviderError, RecognitionResult
from .mineru import MineruOcrClient
from .paddle import PaddleOcrClient

__all__ = ["MineruOcrClient", "OcrProviderError", "PaddleOcrClient", "RecognitionResult"]
