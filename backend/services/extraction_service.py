"""Extraction service – classifies OCR text and runs the appropriate parser."""

import fitz
from sqlalchemy.orm import Session

from models.ocr_result import OCRResult
from models.document import Document
from models.invoice import Invoice
from enums import InvoiceType, ReviewStatus, ReimbursementStatus
from services.classification_service import classify_invoice
from parsers.train_ticket_parser import TrainTicketParser
from parsers.flight_ticket_parser import FlightTicketParser
from parsers.hotel_invoice_parser import HotelInvoiceParser
from parsers.vat_invoice_parser import VATInvoiceParser
from parsers.train_ticket_coord_parser import parse_train_ticket_words, TrainTicketResult


# Parser registry – ordered by specificity
PARSERS = [
    TrainTicketParser(),
    FlightTicketParser(),
    HotelInvoiceParser(),
    VATInvoiceParser(),
]


class ExtractionService:

    @staticmethod
    def extract_from_ocr_result(
        db: Session, ocr_result: OCRResult
    ) -> Invoice | None:
        """
        Classify OCR text and run the matching parser to produce an Invoice.

        For PyMuPDF results on train tickets, uses coordinate-based parsing.
        """
        raw_text = ocr_result.raw_text
        if not raw_text or not raw_text.strip():
            return None

        # ── Try coordinate-based parsing for PyMuPDF train tickets ──
        if ocr_result.provider == "pymupdf" and ocr_result.document_id:
            doc = db.query(Document).filter(Document.id == ocr_result.document_id).first()
            if doc and doc.file_path.lower().endswith(".pdf"):
                try:
                    pdf_doc = fitz.open(doc.file_path)
                    words = pdf_doc[0].get_text("words")
                    page_w = pdf_doc[0].rect.width
                    pdf_doc.close()

                    coord_result = parse_train_ticket_words(words, page_w)
                    if coord_result.train_no:
                        return ExtractionService._create_invoice_from_coord(
                            db, ocr_result, coord_result
                        )
                except Exception:
                    pass  # Fall through to text-based parsing

        # Step 1: Classify
        classification = classify_invoice(raw_text)

        # Step 2: Find matching parser
        parser = None
        for p in PARSERS:
            if p.invoice_type == classification.invoice_type:
                parser = p
                break

        # If no exact match, try can_parse on each
        if parser is None:
            for p in PARSERS:
                if p.can_parse(raw_text):
                    parser = p
                    break

        # Step 3: Parse
        if parser is not None:
            parsed = parser.parse(raw_text)
        else:
            # Use classification result as-is
            from parsers.base_parser import ParsedInvoice
            parsed = ParsedInvoice(
                invoice_type=classification.invoice_type,
                expense_category=classification.expense_category,
                confidence=classification.confidence,
                parser_name="ClassificationOnly",
            )

        # Step 4: Create Invoice record
        invoice = Invoice(
            trip_id=ocr_result.trip_id,
            document_id=ocr_result.document_id,
            ocr_result_id=ocr_result.id,
            invoice_type=parsed.invoice_type,
            expense_category=parsed.expense_category,
            invoice_code=parsed.invoice_code,
            invoice_number=parsed.invoice_number,
            invoice_date=parsed.invoice_date,
            seller_name=parsed.seller_name,
            buyer_name=parsed.buyer_name,
            total_amount=parsed.total_amount,
            tax_amount=parsed.tax_amount,
            business_date=parsed.business_date,
            person_name=parsed.person_name,
            from_city=parsed.from_city,
            to_city=parsed.to_city,
            from_place=parsed.from_place,
            to_place=parsed.to_place,
            transport_no=parsed.transport_no,
            seat_class=parsed.seat_class,
            hotel_name=parsed.hotel_name,
            checkin_date=parsed.checkin_date,
            checkout_date=parsed.checkout_date,
            nights=parsed.nights,
            confidence=parsed.confidence,
            parser_name=parsed.parser_name,
            review_status=ReviewStatus.NEEDS_REVIEW,
            reimbursement_status=ReimbursementStatus.THIS_TRIP,
        )
        db.add(invoice)
        db.commit()
        db.refresh(invoice)
        return invoice

    @staticmethod
    def _create_invoice_from_coord(
        db: Session, ocr_result: OCRResult, cr: TrainTicketResult
    ) -> Invoice:
        """Create an Invoice from coordinate-parsed train ticket result."""
        # Determine total_amount: fare takes priority, fallback to change fee
        total = cr.fare_amount or cr.change_fee_amount

        # Build business_date with time if available
        business_dt = cr.travel_date

        invoice = Invoice(
            trip_id=ocr_result.trip_id,
            document_id=ocr_result.document_id,
            ocr_result_id=ocr_result.id,
            invoice_type=cr.invoice_type,
            expense_category=cr.expense_category,
            invoice_date=cr.invoice_date,
            total_amount=total,
            business_date=business_dt,
            person_name=cr.person_name,
            from_place=cr.departure_station,
            to_place=cr.arrival_station,
            transport_no=cr.train_no,
            seat_class=cr.seat_class,
            buyer_name=cr.buyer_name,
            confidence=cr.confidence,
            parser_name="TrainTicketCoordParser",
            review_status=ReviewStatus.NEEDS_REVIEW if cr.needs_review else ReviewStatus.AUTO_CONFIRMED,
            reimbursement_status=ReimbursementStatus.THIS_TRIP,
        )
        db.add(invoice)
        db.commit()
        db.refresh(invoice)
        return invoice

    @staticmethod
    def extract_trip_invoices(db: Session, trip_id: int) -> list[Invoice]:
        """Run extraction on all OCR results for a trip."""
        ocr_results = (
            db.query(OCRResult)
            .filter(OCRResult.trip_id == trip_id, OCRResult.success == True)
            .all()
        )

        invoices: list[Invoice] = []
        for ocr in ocr_results:
            # Skip if already has an invoice
            existing = (
                db.query(Invoice)
                .filter(Invoice.ocr_result_id == ocr.id)
                .first()
            )
            if existing:
                invoices.append(existing)
                continue

            inv = ExtractionService.extract_from_ocr_result(db, ocr)
            if inv:
                invoices.append(inv)

        # ── Deduplicate: same train/flight + date + amount → keep PDF over image ──
        invoices = ExtractionService._deduplicate_invoices(db, invoices)

        return invoices

    @staticmethod
    def _deduplicate_invoices(db: Session, invoices: list[Invoice]) -> list[Invoice]:
        """Remove duplicate invoices where PDF and screenshot produce same result."""
        from models.document import Document

        seen: dict[tuple, Invoice] = {}
        to_remove: list[Invoice] = []

        for inv in invoices:
            if not inv.transport_no or not inv.business_date:
                continue
            key = (inv.transport_no, str(inv.business_date), str(inv.total_amount))

            if key in seen:
                existing = seen[key]
                # Prefer PDF over image
                existing_doc = db.query(Document).filter(Document.id == existing.document_id).first()
                current_doc = db.query(Document).filter(Document.id == inv.document_id).first()

                existing_is_pdf = existing_doc and existing_doc.file_ext == ".pdf"
                current_is_pdf = current_doc and current_doc.file_ext == ".pdf"

                if current_is_pdf and not existing_is_pdf:
                    # Current is PDF, replace existing
                    to_remove.append(existing)
                    seen[key] = inv
                else:
                    # Keep existing (either PDF or first seen)
                    to_remove.append(inv)
            else:
                seen[key] = inv

        # Delete duplicate invoices
        for inv in to_remove:
            db.delete(inv)
        if to_remove:
            db.commit()

        return [inv for inv in invoices if inv not in to_remove]