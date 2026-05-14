"""Invoice model – structured invoice data parsed from OCR results."""

from datetime import datetime, date
from decimal import Decimal
from sqlalchemy import String, Integer, Float, Boolean, Date, Numeric, DateTime, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from database import Base
from enums import ReviewStatus, ReimbursementStatus


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trip_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("trips.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )
    ocr_result_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("ocr_results.id", ondelete="SET NULL"), nullable=True
    )

    invoice_type: Mapped[str] = mapped_column(String(50), nullable=False, default="UNKNOWN")
    expense_category: Mapped[str] = mapped_column(String(50), nullable=False, default="OTHER")

    invoice_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    invoice_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    invoice_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    seller_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    seller_tax_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    buyer_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    buyer_tax_id: Mapped[str | None] = mapped_column(String(50), nullable=True)

    item_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    service_name: Mapped[str | None] = mapped_column(String(500), nullable=True)

    amount_without_tax: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    tax_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    total_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    confirmed_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)

    business_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    business_start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    business_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    person_name: Mapped[str | None] = mapped_column(String(100), nullable=True)

    from_city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    to_city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    from_place: Mapped[str | None] = mapped_column(String(200), nullable=True)
    to_place: Mapped[str | None] = mapped_column(String(200), nullable=True)

    transport_no: Mapped[str | None] = mapped_column(String(50), nullable=True)
    seat_class: Mapped[str | None] = mapped_column(String(50), nullable=True)

    hotel_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    checkin_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    checkout_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    nights: Mapped[int | None] = mapped_column(Integer, nullable=True)

    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    parser_name: Mapped[str | None] = mapped_column(String(100), nullable=True)

    review_status: Mapped[str] = mapped_column(
        String(50), nullable=False, default=ReviewStatus.NEEDS_REVIEW
    )
    reimbursement_status: Mapped[str] = mapped_column(
        String(50), nullable=False, default=ReimbursementStatus.THIS_TRIP
    )

    depart_time_str: Mapped[str | None] = mapped_column(String(10), nullable=True)

    document_role: Mapped[str] = mapped_column(
        String(50), nullable=False, default="OFFICIAL_INVOICE"
    )
    include_in_summary: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    platform_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    booking_order_no: Mapped[str | None] = mapped_column(String(100), nullable=True)
    actual_hotel_name: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Flight order fields
    order_total_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    insurance_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    ancillary_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    flight_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    depart_airport: Mapped[str | None] = mapped_column(String(200), nullable=True)
    arrive_airport: Mapped[str | None] = mapped_column(String(200), nullable=True)
    airline_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    cabin_class: Mapped[str | None] = mapped_column(String(50), nullable=True)
    linked_invoice_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )