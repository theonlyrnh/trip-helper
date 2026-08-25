"""Production data model with explicit user ownership and opaque public IDs."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base


def new_id() -> str:
    return str(uuid4())


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class UserSession(Base):
    __tablename__ = "user_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    csrf_token: Mapped[str] = mapped_column(String(128), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class UserSettings(Base):
    __tablename__ = "user_settings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    default_company_name: Mapped[str | None] = mapped_column(String(255))
    default_company_tax_id: Mapped[str | None] = mapped_column(String(64))
    default_traveler_name: Mapped[str | None] = mapped_column(String(128))
    daily_allowance: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("180.00"))
    include_start_day: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    include_end_day: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    lodging_limit_per_day: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    require_return_ticket: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    require_lodging_invoice: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    remote_provider_configured: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    remote_provider_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class Trip(Base):
    __tablename__ = "trips"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    source_label: Mapped[str | None] = mapped_column(String(255))
    traveler_name: Mapped[str | None] = mapped_column(String(128))
    company_name: Mapped[str | None] = mapped_column(String(255))
    company_tax_id: Mapped[str | None] = mapped_column(String(64))
    project_type: Mapped[str] = mapped_column(String(32), nullable=False, default="TRAVEL")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")

    input_start_date: Mapped[datetime | None] = mapped_column(Date)
    input_end_date: Mapped[datetime | None] = mapped_column(Date)
    inferred_start_date: Mapped[datetime | None] = mapped_column(Date)
    inferred_end_date: Mapped[datetime | None] = mapped_column(Date)
    confirmed_start_date: Mapped[datetime | None] = mapped_column(Date)
    confirmed_end_date: Mapped[datetime | None] = mapped_column(Date)
    trip_days: Mapped[int | None] = mapped_column(Integer)
    date_confidence: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False, default=0)
    date_evidence: Mapped[list[str] | None] = mapped_column(JSON)
    route_text: Mapped[str | None] = mapped_column(String(2000))

    daily_allowance: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("180.00"))
    include_start_day: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    include_end_day: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    lodging_limit_per_day: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    require_return_ticket: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    require_lodging_invoice: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    intercity_transport_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    local_transport_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    lodging_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    meal_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    other_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    invoice_total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    allowance_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    grand_total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint("trip_id", "sha256", name="uq_documents_trip_sha256"),
        Index("ix_documents_trip_created", "trip_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    trip_id: Mapped[str] = mapped_column(ForeignKey("trips.id", ondelete="CASCADE"), index=True, nullable=False)
    storage_key: Mapped[str] = mapped_column(String(512), unique=True, nullable=False)
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    relative_path: Mapped[str | None] = mapped_column(String(1024))
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    file_extension: Mapped[str] = mapped_column(String(16), nullable=False)
    page_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    document_type: Mapped[str] = mapped_column(String(64), nullable=False, default="UNKNOWN")
    upload_status: Mapped[str] = mapped_column(String(32), nullable=False, default="SUCCEEDED")
    processing_status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")
    ocr_status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(String(1000))
    processing_version: Mapped[str] = mapped_column(String(64), nullable=False, default="v1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class DocumentPage(Base):
    __tablename__ = "document_pages"
    __table_args__ = (UniqueConstraint("document_id", "page_index", name="uq_document_pages_index"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True, nullable=False)
    page_index: Mapped[int] = mapped_column(Integer, nullable=False)
    preview_key: Mapped[str | None] = mapped_column(String(512))
    thumbnail_key: Mapped[str | None] = mapped_column(String(512))
    extracted_text: Mapped[str | None] = mapped_column(Text)
    text_status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class OcrRun(Base):
    __tablename__ = "ocr_runs"
    __table_args__ = (Index("ix_ocr_runs_document_attempt", "document_id", "attempt"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True, nullable=False)
    page_index: Mapped[int | None] = mapped_column(Integer)
    provider: Mapped[str] = mapped_column(String(128), nullable=False)
    model: Mapped[str | None] = mapped_column(String(256))
    raw_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    raw_json: Mapped[dict | list | None] = mapped_column(JSON)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Invoice(Base):
    __tablename__ = "invoices"
    __table_args__ = (UniqueConstraint("document_id", name="uq_invoices_document"), Index("ix_invoices_trip_status", "trip_id", "reimbursement_status"))

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    trip_id: Mapped[str] = mapped_column(ForeignKey("trips.id", ondelete="CASCADE"), index=True, nullable=False)
    document_id: Mapped[str | None] = mapped_column(ForeignKey("documents.id", ondelete="SET NULL"), index=True)
    ocr_run_id: Mapped[str | None] = mapped_column(ForeignKey("ocr_runs.id", ondelete="SET NULL"))
    invoice_type: Mapped[str] = mapped_column(String(64), nullable=False, default="UNKNOWN")
    expense_category: Mapped[str] = mapped_column(String(64), nullable=False, default="OTHER")
    invoice_code: Mapped[str | None] = mapped_column(String(64))
    invoice_number: Mapped[str | None] = mapped_column(String(64))
    invoice_date: Mapped[datetime | None] = mapped_column(Date)
    seller_name: Mapped[str | None] = mapped_column(String(512))
    seller_tax_id: Mapped[str | None] = mapped_column(String(64))
    buyer_name: Mapped[str | None] = mapped_column(String(512))
    buyer_tax_id: Mapped[str | None] = mapped_column(String(64))
    item_name: Mapped[str | None] = mapped_column(String(512))
    service_name: Mapped[str | None] = mapped_column(String(512))
    amount_without_tax: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    tax_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    total_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    confirmed_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    business_date: Mapped[datetime | None] = mapped_column(Date)
    business_start_date: Mapped[datetime | None] = mapped_column(Date)
    business_end_date: Mapped[datetime | None] = mapped_column(Date)
    person_name: Mapped[str | None] = mapped_column(String(128))
    from_city: Mapped[str | None] = mapped_column(String(128))
    to_city: Mapped[str | None] = mapped_column(String(128))
    from_place: Mapped[str | None] = mapped_column(String(255))
    to_place: Mapped[str | None] = mapped_column(String(255))
    transport_no: Mapped[str | None] = mapped_column(String(64))
    depart_time_str: Mapped[str | None] = mapped_column(String(16))
    seat_class: Mapped[str | None] = mapped_column(String(64))
    hotel_name: Mapped[str | None] = mapped_column(String(512))
    checkin_date: Mapped[datetime | None] = mapped_column(Date)
    checkout_date: Mapped[datetime | None] = mapped_column(Date)
    nights: Mapped[int | None] = mapped_column(Integer)
    confidence: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False, default=0)
    parser_name: Mapped[str | None] = mapped_column(String(128))
    review_status: Mapped[str] = mapped_column(String(32), nullable=False, default="NEEDS_REVIEW")
    reimbursement_status: Mapped[str] = mapped_column(String(32), nullable=False, default="THIS_TRIP")
    document_role: Mapped[str] = mapped_column(String(64), nullable=False, default="OFFICIAL_INVOICE")
    include_in_summary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    platform_name: Mapped[str | None] = mapped_column(String(128))
    booking_order_no: Mapped[str | None] = mapped_column(String(128))
    actual_hotel_name: Mapped[str | None] = mapped_column(String(512))
    order_total_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    insurance_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    ancillary_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    flight_date: Mapped[datetime | None] = mapped_column(Date)
    depart_airport: Mapped[str | None] = mapped_column(String(255))
    arrive_airport: Mapped[str | None] = mapped_column(String(255))
    airline_name: Mapped[str | None] = mapped_column(String(128))
    cabin_class: Mapped[str | None] = mapped_column(String(64))
    linked_invoice_id: Mapped[str | None] = mapped_column(String(36))
    note: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class TravelSegment(Base):
    __tablename__ = "travel_segments"
    __table_args__ = (UniqueConstraint("invoice_id", name="uq_travel_segments_invoice"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    trip_id: Mapped[str] = mapped_column(ForeignKey("trips.id", ondelete="CASCADE"), index=True, nullable=False)
    invoice_id: Mapped[str] = mapped_column(ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False)
    transport_type: Mapped[str] = mapped_column(String(64), nullable=False, default="OTHER")
    depart_date: Mapped[datetime | None] = mapped_column(Date)
    depart_time: Mapped[str | None] = mapped_column(String(16))
    from_city: Mapped[str | None] = mapped_column(String(128))
    to_city: Mapped[str | None] = mapped_column(String(128))
    from_place: Mapped[str | None] = mapped_column(String(255))
    to_place: Mapped[str | None] = mapped_column(String(255))
    transport_no: Mapped[str | None] = mapped_column(String(64))
    seat_class: Mapped[str | None] = mapped_column(String(64))
    amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    confidence: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class LodgingStay(Base):
    __tablename__ = "lodging_stays"
    __table_args__ = (UniqueConstraint("invoice_id", name="uq_lodging_stays_invoice"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    trip_id: Mapped[str] = mapped_column(ForeignKey("trips.id", ondelete="CASCADE"), index=True, nullable=False)
    invoice_id: Mapped[str] = mapped_column(ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False)
    hotel_name: Mapped[str | None] = mapped_column(String(512))
    city: Mapped[str | None] = mapped_column(String(128))
    checkin_date: Mapped[datetime | None] = mapped_column(Date)
    checkout_date: Mapped[datetime | None] = mapped_column(Date)
    nights: Mapped[int | None] = mapped_column(Integer)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    confidence: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ReviewIssue(Base):
    __tablename__ = "review_issues"
    __table_args__ = (UniqueConstraint("trip_id", "rule_fingerprint", name="uq_review_issues_rule"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    trip_id: Mapped[str] = mapped_column(ForeignKey("trips.id", ondelete="CASCADE"), index=True, nullable=False)
    document_id: Mapped[str | None] = mapped_column(ForeignKey("documents.id", ondelete="SET NULL"))
    invoice_id: Mapped[str | None] = mapped_column(ForeignKey("invoices.id", ondelete="SET NULL"))
    issue_type: Mapped[str] = mapped_column(String(128), nullable=False)
    rule_fingerprint: Mapped[str] = mapped_column(String(128), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False, default="WARNING")
    message: Mapped[str] = mapped_column(String(2000), nullable=False)
    suggestion: Mapped[str | None] = mapped_column(String(2000))
    auto_generated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    resolution_status: Mapped[str] = mapped_column(String(32), nullable=False, default="OPEN")
    resolution_note: Mapped[str | None] = mapped_column(String(2000))
    resolved_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint("owner_id", "idempotency_key", name="uq_jobs_owner_idempotency"),
        Index("ix_jobs_owner_state", "owner_id", "state"),
        Index("ix_jobs_trip_created", "trip_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    trip_id: Mapped[str | None] = mapped_column(ForeignKey("trips.id", ondelete="CASCADE"), index=True)
    document_id: Mapped[str | None] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    queue: Mapped[str] = mapped_column(String(32), nullable=False, default="default")
    idempotency_key: Mapped[str | None] = mapped_column(String(256), index=True)
    celery_task_id: Mapped[str | None] = mapped_column(String(128), index=True)
    trace_id: Mapped[str] = mapped_column(String(64), nullable=False, default=new_id)
    message: Mapped[str | None] = mapped_column(String(512))
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(String(2000))
    result_ref: Mapped[str | None] = mapped_column(String(512))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    @property
    def progress_message(self) -> str | None:
        return self.message

    @property
    def retryable(self) -> bool:
        return self.state in {"FAILED", "RETRYING"} and self.attempt < self.max_attempts


class Export(Base):
    __tablename__ = "exports"
    __table_args__ = (Index("ix_exports_trip_status", "trip_id", "status"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    trip_id: Mapped[str] = mapped_column(ForeignKey("trips.id", ondelete="CASCADE"), index=True, nullable=False)
    job_id: Mapped[str | None] = mapped_column(ForeignKey("jobs.id", ondelete="SET NULL"), index=True)
    storage_key: Mapped[str | None] = mapped_column(String(512), unique=True)
    original_filename: Mapped[str | None] = mapped_column(String(512))
    format: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_accessed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(String(2000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (Index("ix_audit_events_actor_created", "actor_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(36))
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    trace_id: Mapped[str | None] = mapped_column(String(64))
    metadata_json: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
