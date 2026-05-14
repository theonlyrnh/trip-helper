"""AppSetting model – system-wide configuration (singleton row)."""

from datetime import datetime
from decimal import Decimal
from sqlalchemy import String, Integer, Boolean, Numeric, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class AppSetting(Base):
    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    default_invoice_root_dir: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    default_company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    default_company_tax_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    default_traveler_name: Mapped[str | None] = mapped_column(String(100), nullable=True)

    daily_allowance: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("180.00")
    )
    include_start_day: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    include_end_day: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    lodging_limit_per_day: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    require_return_ticket: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    require_lodging_invoice: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    ocr_provider_mode: Mapped[str] = mapped_column(
        String(50), nullable=False, default="local_first"
    )
    paddleocr_api_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    remote_api_base_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    remote_api_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    remote_model_name: Mapped[str | None] = mapped_column(String(100), nullable=True)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )