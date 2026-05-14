"""OCR service – tiered recognition: PyMuPDF → PaddleOCR → Qwen3."""

import time
from sqlalchemy.orm import Session

from models.document import Document
from models.ocr_result import OCRResult
from enums import OCRStatus
from providers.base_ocr_provider import OCRResultDTO
from providers.paddleocr_vl_provider import PaddleOCRVLProvider
from providers.qwen3_vl_provider import Qwen3VLProvider
from config import settings


class OCRService:

    def __init__(self):
        self._paddle = None
        self._qwen = None

    @property
    def paddle(self):
        if self._paddle is None:
            self._paddle = PaddleOCRVLProvider(
                api_url=settings.PADDLEOCR_API_URL or "http://localhost:8118/v1",
                model_name=settings.PADDLEOCR_MODEL or "PaddleOCR-VL-1.5-0.9B",
            )
        return self._paddle

    @property
    def qwen(self):
        if self._qwen is None:
            self._qwen = Qwen3VLProvider(
                api_url=settings.REMOTE_API_BASE_URL or "",
                api_key=settings.REMOTE_API_KEY or "",
                model_name=settings.REMOTE_MODEL_NAME or "Qwen3-VL-30B-A3B-Instruct",
            )
        return self._qwen

    def recognize_document(self, db: Session, document: Document) -> OCRResult:
        """
        Tiered recognition strategy:

        1. PDF with embedded text (TEXT_EXTRACTED) → use PyMuPDF directly
        2. Image / scanned PDF → PaddleOCR (local, fast)
        3. PaddleOCR failed → Qwen3 (remote, accurate)
        """
        document.ocr_status = OCRStatus.PROCESSING
        db.commit()

        # ── Tier 1: PyMuPDF for electronic PDFs ──
        if document.scan_status == "TEXT_EXTRACTED":
            dto = self._recognize_pymupdf(document)
            return self._save_result(db, document, dto)

        # ── Tier 2: PaddleOCR ──
        image_path = document.preview_image_path or document.file_path
        dto = self.paddle.recognize_image(image_path)

        if dto.success and dto.raw_text.strip():
            return self._save_result(db, document, dto)

        # ── Tier 3: Qwen3 fallback ──
        if settings.REMOTE_API_KEY:
            dto = self.qwen.recognize_image(image_path)
            return self._save_result(db, document, dto)

        # All failed
        return self._save_result(db, document, dto)

    def recognize_trip_documents(
        self, db: Session, trip_id: int
    ) -> list[OCRResult]:
        """Run tiered recognition on all pending documents in a trip."""
        from models.trip import Trip
        from enums import TripStatus

        docs = (
            db.query(Document)
            .filter(
                Document.trip_id == trip_id,
                Document.ocr_status.in_([OCRStatus.PENDING, OCRStatus.FAILED]),
            )
            .all()
        )

        results: list[OCRResult] = []
        for doc in docs:
            result = self.recognize_document(db, doc)
            results.append(result)

        # Update trip counters
        trip = db.query(Trip).filter(Trip.id == trip_id).first()
        if trip:
            trip.recognized_count = (
                db.query(OCRResult)
                .filter(
                    OCRResult.trip_id == trip_id,
                    OCRResult.success == True,
                )
                .count()
            )
            if trip.status in (TripStatus.SCANNED, TripStatus.RECOGNIZING):
                trip.status = TripStatus.RECOGNIZED
            db.commit()

        return results

    # ── Private helpers ──────────────────────────────────────────

    def _recognize_pymupdf(self, document: Document) -> OCRResultDTO:
        """Extract text from electronic PDF using PyMuPDF."""
        import fitz
        t0 = time.time()
        try:
            doc = fitz.open(document.file_path)
            text_parts = []
            for page in doc:
                t = page.get_text()
                if t:
                    text_parts.append(t)
            doc.close()
            full_text = "\n".join(text_parts).strip()
            return OCRResultDTO(
                success=True,
                raw_text=full_text,
                confidence=1.0,
                provider="pymupdf",
                model_name="PyMuPDF",
                duration_ms=int((time.time() - t0) * 1000),
            )
        except Exception as e:
            return OCRResultDTO(
                success=False,
                raw_text="",
                provider="pymupdf",
                model_name="PyMuPDF",
                error_message=str(e),
            )

    def _save_result(
        self, db: Session, document: Document, dto: OCRResultDTO
    ) -> OCRResult:
        ocr_result = OCRResult(
            document_id=document.id,
            trip_id=document.trip_id,
            provider=dto.provider,
            model_name=dto.model_name,
            raw_text=dto.raw_text,
            raw_json=str(dto.raw_json) if dto.raw_json else None,
            confidence=dto.confidence,
            duration_ms=dto.duration_ms,
            image_path=document.preview_image_path or document.file_path,
            success=dto.success,
            error_message=dto.error_message,
        )
        db.add(ocr_result)

        if dto.success:
            document.ocr_status = OCRStatus.SUCCESS
        else:
            document.ocr_status = OCRStatus.FAILED
            document.error_message = dto.error_message

        db.commit()
        db.refresh(ocr_result)
        return ocr_result