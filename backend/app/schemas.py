"""Safe API DTOs. None of these types expose host paths or server secrets."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.security import MIN_PASSWORD_LENGTH


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


class UserRead(ApiModel):
    id: str
    email: str
    display_name: str | None = None
    is_admin: bool


class AuthRequest(ApiModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=512)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class BootstrapRequest(AuthRequest):
    bootstrap_token: str | None = Field(default=None, max_length=512)


class AuthResponse(ApiModel):
    user: UserRead
    csrf_token: str


class PasswordChange(ApiModel):
    current_password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=512)
    new_password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=512)


class UserSessionRead(ApiModel):
    id: str
    created_at: datetime
    last_seen_at: datetime
    expires_at: datetime
    current: bool = False


class TripCreate(ApiModel):
    title: str = Field(min_length=1, max_length=255)
    source_label: str | None = Field(default=None, max_length=255)
    traveler_name: str | None = Field(default=None, max_length=128)
    company_name: str | None = Field(default=None, max_length=255)
    company_tax_id: str | None = Field(default=None, max_length=64)
    project_type: Literal["TRAVEL", "DAILY", "MIXED"] = "TRAVEL"
    input_start_date: date | None = None
    input_end_date: date | None = None

    @model_validator(mode="after")
    def validate_date_range(self) -> "TripCreate":
        if self.input_start_date and self.input_end_date and self.input_start_date > self.input_end_date:
            raise ValueError("input_start_date must be on or before input_end_date")
        return self


class TripUpdate(ApiModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    source_label: str | None = Field(default=None, max_length=255)
    traveler_name: str | None = Field(default=None, max_length=128)
    company_name: str | None = Field(default=None, max_length=255)
    company_tax_id: str | None = Field(default=None, max_length=64)
    project_type: Literal["TRAVEL", "DAILY", "MIXED"] | None = None
    input_start_date: date | None = None
    input_end_date: date | None = None
    confirmed_start_date: date | None = None
    confirmed_end_date: date | None = None
    # Compact browser DTO aliases. They map to manual/confirmed trip dates.
    start_date: date | None = None
    end_date: date | None = None
    daily_allowance: Decimal | None = Field(default=None, ge=0, le=100_000)

    @model_validator(mode="after")
    def validate_date_range(self) -> "TripUpdate":
        pairs = (
            (self.input_start_date, self.input_end_date, "input_start_date", "input_end_date"),
            (self.confirmed_start_date, self.confirmed_end_date, "confirmed_start_date", "confirmed_end_date"),
            (self.start_date, self.end_date, "start_date", "end_date"),
        )
        for start, end, start_name, end_name in pairs:
            if start and end and start > end:
                raise ValueError(f"{start_name} must be on or before {end_name}")
        return self


class TripSummaryCompact(ApiModel):
    invoice_total_amount: Decimal
    allowance_amount: Decimal
    grand_total_amount: Decimal
    reimbursement_total_amount: Decimal = Decimal("0.00")
    reimbursed_total_amount: Decimal = Decimal("0.00")
    unallocated_total_amount: Decimal = Decimal("0.00")
    document_count: int
    review_count: int
    issue_count: int


class TripRead(ApiModel):
    id: str
    title: str
    source_label: str | None
    traveler_name: str | None
    company_name: str | None
    company_tax_id: str | None
    project_type: str
    status: str
    reimbursement_status: str = "NOT_REIMBURSED"
    input_start_date: date | None
    input_end_date: date | None
    inferred_start_date: date | None
    inferred_end_date: date | None
    confirmed_start_date: date | None
    confirmed_end_date: date | None
    trip_days: int | None
    date_confidence: float
    date_evidence: list[str] | None
    route_text: str | None
    start_date: date | None = None
    end_date: date | None = None
    daily_allowance: Decimal
    invoice_total_amount: Decimal
    allowance_amount: Decimal
    grand_total_amount: Decimal
    document_count: int = 0
    issue_count: int = 0
    summary: TripSummaryCompact | None = None
    created_at: datetime
    updated_at: datetime


class RouteSegmentRead(ApiModel):
    id: str
    trip_id: str
    invoice_id: str
    transport_type: str
    depart_date: date | None
    depart_time: str | None
    from_city: str | None
    to_city: str | None
    from_place: str | None
    to_place: str | None
    transport_no: str | None
    seat_class: str | None
    amount: Decimal | None
    confidence: float


class SummaryRead(ApiModel):
    trip_id: str
    intercity_transport_amount: Decimal
    local_transport_amount: Decimal
    lodging_amount: Decimal
    meal_amount: Decimal
    refund_change_fee: Decimal
    travel_insurance_amount: Decimal
    other_amount: Decimal
    invoice_total_amount: Decimal
    trip_days: int
    daily_allowance: Decimal
    allowance_amount: Decimal
    grand_total_amount: Decimal
    reimbursement_invoice_total_amount: Decimal
    reimbursement_allowance_amount: Decimal
    reimbursement_total_amount: Decimal
    reimbursed_invoice_amount: Decimal
    reimbursed_allowance_amount: Decimal
    reimbursed_total_amount: Decimal
    unallocated_total_amount: Decimal


class MonthlyTrendRead(ApiModel):
    month: int
    project_count: int
    invoice_amount: Decimal
    allowance_amount: Decimal


class CitySummaryRead(ApiModel):
    city: str
    count: int


class AnnualProjectRead(ApiModel):
    id: str
    title: str
    project_type: str
    status: str
    reimbursement_status: str
    start_date: date | None
    end_date: date | None
    route_text: str | None
    document_count: int
    trip_days: int
    invoice_total_amount: Decimal
    allowance_amount: Decimal
    grand_total_amount: Decimal


class YearlyDashboardRead(ApiModel):
    year: int
    available_years: list[int]
    total_project_count: int
    travel_project_count: int
    daily_project_count: int
    total_trip_days: int
    total_invoice_amount: Decimal
    total_income_amount: Decimal
    reimbursed_amount: Decimal
    unreimbursed_amount: Decimal
    monthly_trends: list[MonthlyTrendRead]
    category_summary: dict[str, Decimal]
    city_summary: list[CitySummaryRead]
    reimbursement_summary: dict[str, int]
    recent_projects: list[AnnualProjectRead]


class DocumentInvoiceRead(ApiModel):
    id: str
    invoice_type: str | None
    expense_category: str | None
    total_amount: Decimal | None
    confirmed_amount: Decimal | None
    reimbursement_status: str
    include_in_summary: bool
    review_status: str
    document_role: str
    invoice_number: str | None
    invoice_date: date | None
    business_date: date | None
    seller_name: str | None
    buyer_name: str | None
    from_city: str | None
    to_city: str | None
    from_place: str | None
    to_place: str | None
    transport_no: str | None
    depart_time_str: str | None
    seat_class: str | None
    hotel_name: str | None
    checkin_date: date | None
    checkout_date: date | None
    nights: int | None
    note: str | None


class DocumentRead(ApiModel):
    id: str
    trip_id: str
    original_filename: str
    relative_path: str | None
    sha256: str | None = None
    size_bytes: int
    mime_type: str
    page_count: int
    document_type: str
    upload_status: str
    processing_status: str
    ocr_status: str
    error_code: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    invoice_id: str | None = None
    invoice: DocumentInvoiceRead | None = None
    issue_count: int = 0


class UploadResponse(ApiModel):
    document: DocumentRead
    job_id: str | None = None
    job: "JobRead | None" = None
    duplicate: bool = False


class JobCreate(ApiModel):
    kind: Literal["FULL_ANALYSIS", "EXPORT_XLSX", "EXPORT_PDF", "REPROCESS_DOCUMENT"]
    document_id: str | None = None


class JobRead(ApiModel):
    id: str
    trip_id: str | None
    document_id: str | None
    kind: str
    state: str
    progress: int
    attempt: int
    max_attempts: int
    message: str | None
    progress_message: str | None = None
    error_code: str | None
    error_message: str | None
    result_ref: str | None
    retryable: bool = False
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class InvoiceRead(ApiModel):
    id: str
    trip_id: str
    document_id: str | None
    invoice_type: str
    expense_category: str
    invoice_code: str | None
    invoice_number: str | None
    invoice_date: date | None
    seller_name: str | None
    buyer_name: str | None
    total_amount: Decimal | None
    confirmed_amount: Decimal | None
    business_date: date | None
    from_city: str | None
    to_city: str | None
    from_place: str | None
    to_place: str | None
    transport_no: str | None
    depart_time_str: str | None
    seat_class: str | None
    hotel_name: str | None
    checkin_date: date | None
    checkout_date: date | None
    nights: int | None
    confidence: float
    parser_name: str | None
    review_status: str
    reimbursement_status: str
    document_role: str
    include_in_summary: bool
    note: str | None
    version: int
    created_at: datetime
    updated_at: datetime


class InvoiceUpdate(ApiModel):
    invoice_type: str | None = Field(default=None, max_length=64)
    expense_category: str | None = Field(default=None, max_length=64)
    invoice_number: str | None = Field(default=None, max_length=64)
    invoice_date: date | None = None
    seller_name: str | None = Field(default=None, max_length=512)
    buyer_name: str | None = Field(default=None, max_length=512)
    total_amount: Decimal | None = Field(default=None, ge=0, le=10_000_000)
    confirmed_amount: Decimal | None = Field(default=None, ge=0, le=10_000_000)
    business_date: date | None = None
    from_city: str | None = Field(default=None, max_length=128)
    to_city: str | None = Field(default=None, max_length=128)
    from_place: str | None = Field(default=None, max_length=255)
    to_place: str | None = Field(default=None, max_length=255)
    transport_no: str | None = Field(default=None, max_length=64)
    depart_time_str: str | None = Field(default=None, max_length=16)
    seat_class: str | None = Field(default=None, max_length=64)
    hotel_name: str | None = Field(default=None, max_length=512)
    checkin_date: date | None = None
    checkout_date: date | None = None
    nights: int | None = Field(default=None, ge=0, le=366)
    review_status: str | None = Field(default=None, max_length=32)
    reimbursement_status: Literal["THIS_TRIP", "ALREADY_REIMBURSED", "NOT_REIMBURSED", "PENDING"] | None = None
    document_role: Literal["OFFICIAL_INVOICE", "ORDER_SCREENSHOT", "BOOKING_SCREENSHOT", "SUPPORTING_DOC"] | None = None
    include_in_summary: bool | None = None
    note: str | None = Field(default=None, max_length=10_000)
    version: int | None = Field(default=None, ge=1)


class InvoiceBulkUpdate(ApiModel):
    invoice_ids: list[str] = Field(min_length=1, max_length=500)
    updates: InvoiceUpdate


class IssueRead(ApiModel):
    id: str
    trip_id: str
    document_id: str | None
    invoice_id: str | None
    issue_type: str
    severity: str
    message: str
    suggestion: str | None
    resolution_status: str
    resolved: bool = False
    ignored: bool = False
    resolution_note: str | None
    resolved_at: datetime | None
    created_at: datetime
    file_name: str | None = None


class IssueResolution(ApiModel):
    resolution_status: Literal["RESOLVED", "IGNORED"] | None = None
    resolved: bool | None = None
    ignored: bool | None = None
    resolution_note: str | None = Field(default=None, max_length=2000)


class ExportRead(ApiModel):
    id: str
    trip_id: str
    job_id: str | None
    format: str
    status: str
    original_filename: str | None
    filename: str | None = None
    expires_at: datetime | None
    error_code: str | None
    error_message: str | None
    created_at: datetime


class ExportCreate(ApiModel):
    format: Literal["XLSX", "PDF"]


class UserSettingsRead(ApiModel):
    default_company_name: str | None
    default_company_tax_id: str | None
    default_traveler_name: str | None
    daily_allowance: Decimal
    include_start_day: bool
    include_end_day: bool
    lodging_limit_per_day: Decimal | None
    require_return_ticket: bool
    require_lodging_invoice: bool
    remote_provider_configured: bool
    remote_provider_enabled: bool


class UserSettingsUpdate(ApiModel):
    default_company_name: str | None = Field(default=None, max_length=255)
    default_company_tax_id: str | None = Field(default=None, max_length=64)
    default_traveler_name: str | None = Field(default=None, max_length=128)
    daily_allowance: Decimal | None = Field(default=None, ge=0, le=100_000)
    include_start_day: bool | None = None
    include_end_day: bool | None = None
    lodging_limit_per_day: Decimal | None = Field(default=None, ge=0, le=100_000)
    require_return_ticket: bool | None = None
    require_lodging_invoice: bool | None = None
    remote_provider_enabled: bool | None = None


class HealthRead(ApiModel):
    status: Literal["ok", "ready", "degraded", "unavailable"]
    service: str
    version: str
    checks: dict[str, str] = Field(default_factory=dict)


UploadResponse.model_rebuild()
