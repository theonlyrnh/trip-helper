"""TravelSegment model – transportation segment extracted from tickets."""

from datetime import datetime, date, time
from decimal import Decimal
from sqlalchemy import String, Integer, Float, Date, Time, Numeric, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class TravelSegment(Base):
    __tablename__ = "travel_segments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trip_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("trips.id", ondelete="CASCADE"), nullable=False
    )
    invoice_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("invoices.id", ondelete="SET NULL"), nullable=True
    )

    transport_type: Mapped[str] = mapped_column(String(50), nullable=False, default="OTHER")

    depart_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    depart_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    arrive_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    arrive_time: Mapped[time | None] = mapped_column(Time, nullable=True)

    from_city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    to_city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    from_place: Mapped[str | None] = mapped_column(String(200), nullable=True)
    to_place: Mapped[str | None] = mapped_column(String(200), nullable=True)

    transport_no: Mapped[str | None] = mapped_column(String(50), nullable=True)
    seat_class: Mapped[str | None] = mapped_column(String(50), nullable=True)

    amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    source_document_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )