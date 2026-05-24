"""ReviewIssue model – structured anomaly/issue records."""

from datetime import datetime
from sqlalchemy import String, Integer, Boolean, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from database import Base
from enums import IssueSeverity


class ReviewIssue(Base):
    __tablename__ = "review_issues"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trip_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("trips.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )
    invoice_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("invoices.id", ondelete="SET NULL"), nullable=True
    )

    issue_type: Mapped[str] = mapped_column(String(100), nullable=False)
    severity: Mapped[str] = mapped_column(
        String(20), nullable=False, default=IssueSeverity.WARNING
    )
    message: Mapped[str] = mapped_column(String(2000), nullable=False)

    suggestion: Mapped[str | None] = mapped_column(String(2000), nullable=True)

    auto_generated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    resolved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    resolution_status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="OPEN"
    )
    resolution_note: Mapped[str | None] = mapped_column(String(2000), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
