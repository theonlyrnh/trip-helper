"""Document service – scan, preprocess, and manage Document records."""

import os
import fitz  # PyMuPDF
from PIL import Image
from sqlalchemy.orm import Session

from config import settings
from models.trip import Trip
from models.document import Document
from enums import TripStatus, DocumentType, OCRStatus
from services.folder_scanner import scan_folder
from utils.file_hash import compute_file_hash

# Preprocessing constants
THUMBNAIL_MAX_SIZE = (300, 400)
PDF_RENDER_DPI = 200
PDF_RENDER_MAX_EDGE = 2560
TEXT_EXTRACTION_MIN_LENGTH = 80


class DocumentService:

    @staticmethod
    def scan_trip_folder(db: Session, trip: Trip) -> list[Document]:
        """
        Scan the trip's folder for invoice files and create Document records.

        Skips files that already exist (matched by file_hash).
        Returns the list of newly created Document records.
        """
        scanned = scan_folder(trip.folder_path)

        # Get existing hashes for this trip to avoid duplicates
        existing_hashes = {
            d.file_hash
            for d in db.query(Document).filter(Document.trip_id == trip.id).all()
        }

        new_docs: list[Document] = []

        for sf in scanned:
            file_hash = compute_file_hash(sf.file_path)

            if file_hash in existing_hashes:
                continue

            doc_type = DocumentType.PDF if sf.file_ext == ".pdf" else DocumentType.IMAGE

            doc = Document(
                trip_id=trip.id,
                file_name=sf.file_name,
                file_path=sf.file_path,
                file_ext=sf.file_ext,
                file_hash=file_hash,
                file_size=sf.file_size,
                page_count=1,
                document_type=doc_type,
                scan_status="SCANNED",
                ocr_status=OCRStatus.PENDING,
            )
            db.add(doc)
            new_docs.append(doc)
            existing_hashes.add(file_hash)

        if new_docs:
            # Update trip counters and status
            trip.document_count = (
                db.query(Document)
                .filter(Document.trip_id == trip.id)
                .count()
            )
            if trip.status == TripStatus.CREATED:
                trip.status = TripStatus.SCANNED

            db.commit()

            # Refresh all new docs to get their IDs
            for doc in new_docs:
                db.refresh(doc)

        return new_docs

    # ── Preprocessing methods ──────────────────────────────────────

    @staticmethod
    def extract_pdf_text(file_path: str) -> tuple[str, bool]:
        """
        Extract native text from a PDF using PyMuPDF.

        Returns (text, has_enough_text).
        has_enough_text is True when the extracted text is long enough
        to skip OCR and go directly to parsing.
        """
        text_parts: list[str] = []
        try:
            doc = fitz.open(file_path)
            for page in doc:
                page_text = page.get_text()
                if page_text:
                    text_parts.append(page_text)
            doc.close()
        except Exception:
            return "", False

        full_text = "\n".join(text_parts).strip()
        has_enough = len(full_text) > TEXT_EXTRACTION_MIN_LENGTH
        return full_text, has_enough

    @staticmethod
    def render_pdf_page_to_image(
        file_path: str, page_index: int = 0, output_dir: str | None = None
    ) -> str | None:
        """
        Render a PDF page to a PNG image.

        Returns the path to the generated image, or None on failure.
        """
        if output_dir is None:
            output_dir = settings.CACHE_DIR

        os.makedirs(output_dir, exist_ok=True)

        base_name = os.path.splitext(os.path.basename(file_path))[0]
        output_path = os.path.join(
            output_dir, f"{base_name}_p{page_index}.png"
        )

        try:
            doc = fitz.open(file_path)
            if page_index >= len(doc):
                doc.close()
                return None

            page = doc[page_index]
            # Calculate zoom to fit within max edge while maintaining DPI
            rect = page.rect
            zoom = PDF_RENDER_DPI / 72.0
            max_dim = max(rect.width, rect.height) * zoom
            if max_dim > PDF_RENDER_MAX_EDGE:
                zoom = PDF_RENDER_MAX_EDGE / max(rect.width, rect.height)

            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat)
            pix.save(output_path)
            doc.close()
            return output_path
        except Exception:
            return None

    @staticmethod
    def generate_thumbnail(
        image_path: str, output_dir: str | None = None
    ) -> str | None:
        """
        Generate a thumbnail for an image or rendered PDF page.

        Returns the path to the thumbnail, or None on failure.
        """
        if output_dir is None:
            output_dir = settings.THUMBNAIL_DIR

        os.makedirs(output_dir, exist_ok=True)

        base_name = os.path.splitext(os.path.basename(image_path))[0]
        thumb_path = os.path.join(output_dir, f"{base_name}_thumb.png")

        try:
            img = Image.open(image_path)
            img.thumbnail(THUMBNAIL_MAX_SIZE, Image.LANCZOS)
            img.save(thumb_path, "PNG")
            return thumb_path
        except Exception:
            return None

    @staticmethod
    def preprocess_document(db: Session, document: Document) -> Document:
        """
        Preprocess a single document:
        - For PDFs: extract text, render first page to image, generate thumbnail.
        - For images: generate thumbnail directly.

        Updates the document record in-place and commits.
        """
        if document.document_type == DocumentType.PDF:
            # Try text extraction first
            text, has_enough = DocumentService.extract_pdf_text(document.file_path)

            # Always render first page for preview/thumbnail (UI needs it)
            preview_path = DocumentService.render_pdf_page_to_image(
                document.file_path, page_index=0
            )
            if preview_path:
                document.preview_image_path = preview_path
                document.page_count = DocumentService._count_pdf_pages(
                    document.file_path
                )

                # Generate thumbnail from preview
                thumb_path = DocumentService.generate_thumbnail(preview_path)
                if thumb_path:
                    document.thumbnail_path = thumb_path

            # Set scan status based on text extraction result
            if has_enough:
                document.scan_status = "TEXT_EXTRACTED"
            elif preview_path:
                document.scan_status = "PREPROCESSED"
            else:
                document.scan_status = "RENDER_FAILED"
                document.error_message = "Failed to render PDF page to image"

        elif document.document_type == DocumentType.IMAGE:
            # Generate thumbnail directly from image
            thumb_path = DocumentService.generate_thumbnail(document.file_path)
            if thumb_path:
                document.thumbnail_path = thumb_path
                document.scan_status = "PREPROCESSED"
            else:
                document.scan_status = "PREPROCESS_FAILED"
                document.error_message = "Failed to generate thumbnail"

        db.commit()
        db.refresh(document)
        return document

    @staticmethod
    def preprocess_trip_documents(db: Session, trip_id: int) -> list[Document]:
        """Preprocess all documents in a trip."""
        docs = (
            db.query(Document)
            .filter(Document.trip_id == trip_id)
            .all()
        )
        results: list[Document] = []
        for doc in docs:
            result = DocumentService.preprocess_document(db, doc)
            results.append(result)
        return results

    @staticmethod
    def _count_pdf_pages(file_path: str) -> int:
        """Count the number of pages in a PDF."""
        try:
            doc = fitz.open(file_path)
            count = len(doc)
            doc.close()
            return count
        except Exception:
            return 1