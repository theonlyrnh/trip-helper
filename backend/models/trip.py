"""Trip model – the central entity representing one business trip."""

from datetime import datetime, date
from decimal import Decimal
from sqlalchemy import String, Integer, Date, Numeric, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from database import Base
from enums import TripStatus


class Trip(Base):
    __tablename__ = "trips"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    title: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    folder_path: Mapped[str] = mapped_column(String(1024), nullable=False, default="")
    folder_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")

    traveler_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    company_tax_id: Mapped[str | None] = mapped_column(String(50), nullable=True)

    folder_date_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    folder_date_end: Mapped[date | None] = mapped_column(Date, nullable=True)

    inferred_start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    inferred_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    confirmed_start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    confirmed_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    trip_days: Mapped[int | None] = mapped_column(Integer, nullable=True)

    origin_city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    destination_cities: Mapped[str | None] = mapped_column(String(500), nullable=True)
    route_text: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    daily_allowance: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    allowance_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )

    invoice_total_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    transport_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    intercity_transport_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    local_transport_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    lodging_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    meal_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    other_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    grand_total_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )

    document_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    recognized_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    review_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    issue_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default=TripStatus.CREATED
    )

    reimbursement_status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="NOT_REIMBURSED"
    )

    project_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="TRAVEL"
    )

    last_opened_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_analyzed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )