"""Document model – a PDF or image file on disk."""

from datetime import datetime
from sqlalchemy import String, Integer, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from database import Base
from enums import DocumentType, OCRStatus


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trip_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("trips.id", ondelete="CASCADE"), nullable=False
    )

    file_name: Mapped[str] = mapped_column(String(500), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    file_ext: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    file_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    page_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    selected_pages: Mapped[str | None] = mapped_column(String(200), nullable=True)

    document_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default=DocumentType.UNKNOWN
    )
    scan_status: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDING")
    ocr_status: Mapped[str] = mapped_column(
        String(50), nullable=False, default=OCRStatus.PENDING
    )

    thumbnail_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    preview_image_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    error_message: Mapped[str | None] = mapped_column(String(2000), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )