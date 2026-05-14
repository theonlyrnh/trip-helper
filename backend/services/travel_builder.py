"""Travel builder – generates TravelSegment records from transport invoices."""

from sqlalchemy.orm import Session

from models.invoice import Invoice
from models.travel_segment import TravelSegment
from enums import InvoiceType, TransportType


class TravelBuilder:

    @staticmethod
    def build_from_invoice(db: Session, invoice: Invoice) -> TravelSegment | None:
        """Create a TravelSegment from a transport invoice."""
        if invoice.invoice_type not in (
            InvoiceType.TRAIN_TICKET,
            InvoiceType.FLIGHT_TICKET,
            InvoiceType.BUS_TICKET,
            InvoiceType.TAXI_INVOICE,
            InvoiceType.RIDE_HAILING_INVOICE,
        ):
            return None

        # Skip refund/change fee invoices
        if invoice.expense_category == "REFUND_CHANGE_FEE":
            return None

        # Map invoice type to transport type
        transport_map = {
            InvoiceType.TRAIN_TICKET: TransportType.TRAIN,
            InvoiceType.FLIGHT_TICKET: TransportType.FLIGHT,
            InvoiceType.BUS_TICKET: TransportType.BUS,
            InvoiceType.TAXI_INVOICE: TransportType.TAXI,
            InvoiceType.RIDE_HAILING_INVOICE: TransportType.RIDE_HAILING,
        }

        # Try to parse depart_time from invoice if available
        depart_time = None
        if invoice.business_date:
            import re as _re
            tm = _re.search(r"(\d{1,2}:\d{2})", str(invoice.business_date))

        segment = TravelSegment(
            trip_id=invoice.trip_id,
            invoice_id=invoice.id,
            transport_type=transport_map.get(invoice.invoice_type, TransportType.OTHER),
            depart_date=invoice.business_date,
            depart_time=depart_time,
            from_city=invoice.from_city,
            to_city=invoice.to_city,
            from_place=invoice.from_place,
            to_place=invoice.to_place,
            transport_no=invoice.transport_no,
            seat_class=invoice.seat_class,
            amount=invoice.total_amount,
            source_document_id=invoice.document_id,
            confidence=invoice.confidence,
        )
        db.add(segment)
        db.commit()
        db.refresh(segment)
        return segment

    @staticmethod
    def build_for_trip(db: Session, trip_id: int) -> list[TravelSegment]:
        """Generate TravelSegments for all transport invoices in a trip."""
        invoices = (
            db.query(Invoice)
            .filter(Invoice.trip_id == trip_id)
            .all()
        )

        segments: list[TravelSegment] = []
        for inv in invoices:
            # Skip if already has a segment
            existing = (
                db.query(TravelSegment)
                .filter(TravelSegment.invoice_id == inv.id)
                .first()
            )
            if existing:
                segments.append(existing)
                continue

            seg = TravelBuilder.build_from_invoice(db, inv)
            if seg:
                segments.append(seg)

        return segments