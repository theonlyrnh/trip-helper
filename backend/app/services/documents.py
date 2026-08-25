"""Upload validation, document metadata, and private previews."""

from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.infrastructure.db.models import Document, DocumentPage, Invoice, ReviewIssue
from app.infrastructure.storage.local import LocalStorage, StorageError, sanitize_filename
from app.schemas import DocumentInvoiceRead, DocumentRead


class FileValidationError(ValueError):
    pass


def inspect_stored_object(storage: LocalStorage, key: str, filename: str) -> tuple[str, str, int]:
    """Verify file signatures and bounded parser metadata, never trust MIME alone."""
    path = storage.path_for_internal_use(key)
    with path.open("rb") as source:
        signature = source.read(32)
    suffix = Path(filename).suffix.lower()
    if signature.startswith(b"%PDF-"):
        try:
            import fitz

            pdf = fitz.open(path)
            page_count = len(pdf)
            pdf.close()
        except Exception as exc:
            raise FileValidationError("The PDF cannot be opened") from exc
        if page_count < 1 or page_count > get_settings().max_pdf_pages:
            raise FileValidationError("The PDF page count exceeds the configured limit")
        return "application/pdf", "PDF", page_count
    if signature.startswith(b"\x89PNG\r\n\x1a\n") or signature.startswith(b"\xff\xd8\xff"):
        try:
            from PIL import Image

            with Image.open(path) as image:
                width, height = image.size
                image.verify()
        except Exception as exc:
            raise FileValidationError("The image cannot be opened") from exc
        if width * height > get_settings().max_image_pixels:
            raise FileValidationError("The image dimensions exceed the configured limit")
        mime_type = "image/png" if signature.startswith(b"\x89PNG") else "image/jpeg"
        return mime_type, "IMAGE", 1
    if suffix in {".pdf", ".png", ".jpg", ".jpeg"}:
        raise FileValidationError("File contents do not match the selected file type")
    raise FileValidationError("Only PDF, PNG, and JPEG uploads are supported")


def serialize_document(db: Session, document: Document) -> DocumentRead:
    invoice = db.scalar(select(Invoice).where(Invoice.document_id == document.id))
    issue_count = db.scalar(
        select(func.count()).select_from(ReviewIssue).where(
            ReviewIssue.document_id == document.id,
            ReviewIssue.resolution_status == "OPEN",
        )
    ) or 0
    return _document_read(document, invoice, issue_count)


def serialize_documents(db: Session, documents: list[Document]) -> list[DocumentRead]:
    """Serialize a page with two batched relationship queries (no N+1)."""
    if not documents:
        return []
    ids = [item.id for item in documents]
    invoices = {
        item.document_id: item
        for item in db.scalars(select(Invoice).where(Invoice.document_id.in_(ids)))
    }
    issue_counts = dict(
        db.execute(
            select(ReviewIssue.document_id, func.count())
            .where(ReviewIssue.document_id.in_(ids), ReviewIssue.resolution_status == "OPEN")
            .group_by(ReviewIssue.document_id)
        ).all()
    )
    return [_document_read(document, invoices.get(document.id), issue_counts.get(document.id, 0)) for document in documents]


def _document_read(document: Document, invoice: Invoice | None, issue_count: int) -> DocumentRead:
    return DocumentRead(
        id=document.id,
        trip_id=document.trip_id,
        original_filename=document.original_filename,
        relative_path=document.relative_path,
        sha256=document.sha256,
        size_bytes=document.size_bytes,
        mime_type=document.mime_type,
        page_count=document.page_count,
        document_type=document.document_type,
        upload_status=document.upload_status,
        processing_status=document.processing_status,
        ocr_status=document.ocr_status,
        error_code=document.error_code,
        error_message=document.error_message,
        created_at=document.created_at,
        updated_at=document.updated_at,
        invoice_id=invoice.id if invoice else None,
        invoice=(
            DocumentInvoiceRead(
                id=invoice.id,
                invoice_type=invoice.invoice_type,
                expense_category=invoice.expense_category,
                total_amount=invoice.total_amount,
                confirmed_amount=invoice.confirmed_amount,
                reimbursement_status=invoice.reimbursement_status,
                include_in_summary=invoice.include_in_summary,
                review_status=invoice.review_status,
                document_role=invoice.document_role,
                invoice_number=invoice.invoice_number,
                invoice_date=invoice.invoice_date,
                business_date=invoice.business_date,
                seller_name=invoice.seller_name,
                buyer_name=invoice.buyer_name,
                from_city=invoice.from_city,
                to_city=invoice.to_city,
                from_place=invoice.from_place,
                to_place=invoice.to_place,
                transport_no=invoice.transport_no,
                depart_time_str=invoice.depart_time_str,
                seat_class=invoice.seat_class,
                hotel_name=invoice.hotel_name,
                checkin_date=invoice.checkin_date,
                checkout_date=invoice.checkout_date,
                nights=invoice.nights,
                note=invoice.note,
            )
            if invoice
            else None
        ),
        issue_count=issue_count,
    )


def remove_document_objects(storage: LocalStorage, document: Document, pages: list[DocumentPage]) -> None:
    storage.delete(document.storage_key)
    for page in pages:
        storage.delete(page.preview_key)
        storage.delete(page.thumbnail_key)


def generate_previews_and_text(db: Session, storage: LocalStorage, document: Document) -> str:
    """Create per-page previews and return native PDF text when available."""
    old_pages = list(db.scalars(select(DocumentPage).where(DocumentPage.document_id == document.id)))
    for old_page in old_pages:
        storage.delete(old_page.preview_key)
        if old_page.thumbnail_key and old_page.thumbnail_key != old_page.preview_key:
            storage.delete(old_page.thumbnail_key)
    db.query(DocumentPage).filter(DocumentPage.document_id == document.id).delete()
    native_text = ""
    if document.document_type == "PDF":
        import fitz

        pdf = fitz.open(storage.path_for_internal_use(document.storage_key))
        try:
            for index, page in enumerate(pdf):
                text = page.get_text("text") or ""
                native_text += text + "\n"
                preview_key = storage.new_key("previews", ".png")
                thumbnail_key = storage.new_key("thumbnails", ".png")
                pixmap = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
                preview_bytes = pixmap.tobytes("png")
                storage.put_bytes(preview_bytes, preview_key)
                try:
                    from PIL import Image
                    from io import BytesIO

                    with Image.open(BytesIO(preview_bytes)) as image:
                        image.thumbnail((480, 480))
                        output = BytesIO()
                        image.save(output, format="PNG")
                        storage.put_bytes(output.getvalue(), thumbnail_key)
                except Exception:
                    thumbnail_key = preview_key
                db.add(
                    DocumentPage(
                        document_id=document.id,
                        page_index=index,
                        preview_key=preview_key,
                        thumbnail_key=thumbnail_key,
                        extracted_text=text or None,
                        text_status="SUCCEEDED" if text.strip() else "EMPTY",
                    )
                )
        finally:
            pdf.close()
    else:
        db.add(DocumentPage(document_id=document.id, page_index=0, text_status="PENDING"))
    document.processing_status = "PREPROCESSED"
    document.page_count = max(document.page_count, 1)
    return native_text.strip()


def get_preview_key(db: Session, document: Document, page_index: int = 0) -> tuple[str, str]:
    page = db.scalar(
        select(DocumentPage).where(DocumentPage.document_id == document.id, DocumentPage.page_index == page_index)
    )
    if page and page.preview_key:
        return page.preview_key, "image/png"
    if document.document_type == "IMAGE":
        return document.storage_key, document.mime_type
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Preview is not available")
