"""Lodging builder – generates LodgingStay records from hotel invoices."""

from sqlalchemy.orm import Session

from models.invoice import Invoice
from models.lodging_stay import LodgingStay
from enums import InvoiceType


class LodgingBuilder:

    @staticmethod
    def build_from_invoice(db: Session, invoice: Invoice) -> LodgingStay | None:
        """Create a LodgingStay from a hotel invoice."""
        if invoice.invoice_type != InvoiceType.HOTEL_INVOICE:
            return None

        stay = LodgingStay(
            trip_id=invoice.trip_id,
            invoice_id=invoice.id,
            hotel_name=invoice.hotel_name or invoice.seller_name,
            city=invoice.to_city,
            checkin_date=invoice.checkin_date,
            checkout_date=invoice.checkout_date,
            nights=invoice.nights,
            amount=invoice.total_amount,
            source_document_id=invoice.document_id,
            confidence=invoice.confidence,
        )
        db.add(stay)
        db.commit()
        db.refresh(stay)
        return stay

    @staticmethod
    def build_for_trip(db: Session, trip_id: int) -> list[LodgingStay]:
        """Generate LodgingStays for all hotel invoices in a trip."""
        invoices = (
            db.query(Invoice)
            .filter(Invoice.trip_id == trip_id)
            .all()
        )

        stays: list[LodgingStay] = []
        for inv in invoices:
            existing = (
                db.query(LodgingStay)
                .filter(LodgingStay.invoice_id == inv.id)
                .first()
            )
            if existing:
                stays.append(existing)
                continue

            stay = LodgingBuilder.build_from_invoice(db, inv)
            if stay:
                stays.append(stay)

        return stays