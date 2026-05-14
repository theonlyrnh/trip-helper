"""LodgingStay model – hotel stay record."""

from datetime import datetime, date
from decimal import Decimal
from sqlalchemy import String, Integer, Float, Date, Numeric, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class LodgingStay(Base):
    __tablename__ = "lodging_stays"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trip_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("trips.id", ondelete="CASCADE"), nullable=False
    )
    invoice_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("invoices.id", ondelete="SET NULL"), nullable=True
    )

    hotel_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)

    checkin_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    checkout_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    nights: Mapped[int | None] = mapped_column(Integer, nullable=True)

    amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    source_document_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    platform_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    seller_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    booking_order_no: Mapped[str | None] = mapped_column(String(100), nullable=True)
    booking_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    official_invoice_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="INVOICE_ONLY")

    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )