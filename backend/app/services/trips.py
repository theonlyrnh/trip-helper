"""Trip queries and rebuilds with ownership-aware callers."""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from collections.abc import Iterable
from datetime import date
from decimal import Decimal

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.domain.reporting.summary import calculate_summary, calculate_trip_days
from app.infrastructure.db.models import (
    Document,
    Invoice,
    LodgingStay,
    ReviewIssue,
    TravelSegment,
    Trip,
    UserSettings,
)
from app.schemas import IssueRead, SummaryRead, TripRead, TripSummaryCompact


_COMPACT_DATE_RANGE = re.compile(r"(?<!\d)(\d{8})\D+(\d{8})(?!\d)")
_FULL_DATE_RANGE = re.compile(
    r"(?<!\d)(\d{4})[.\-/_\u5e74](\d{1,2})[.\-/_\u6708](\d{1,2})(?:\u65e5)?\D+"
    r"(\d{4})[.\-/_\u5e74](\d{1,2})[.\-/_\u6708](\d{1,2})(?:\u65e5)?(?!\d)"
)
_SHORT_DATE_RANGE = re.compile(
    r"(?<!\d)(\d{2})[.\-/](\d{1,2})[.\-/](\d{1,2})\D+"
    r"(\d{2})[.\-/](\d{1,2})[.\-/](\d{1,2})(?!\d)"
)
_DEPART_TIME = re.compile(r"^\s*(\d{1,2}):(\d{2})(?::\d{2})?\s*$")
_AUXILIARY_DOCUMENT_ROLES = frozenset({"ORDER_SCREENSHOT", "BOOKING_SCREENSHOT", "SUPPORTING_DOC"})


def ordered_route_segments(segments: Iterable[TravelSegment]) -> list[TravelSegment]:
    """Return transport segments in the same order used by route summaries.

    A date alone is not enough to order connecting tickets.  OCR jobs can finish
    in any order, so relying on database insertion order makes a same-day trip
    appear to start from a later transfer station.
    """

    def sort_key(segment: TravelSegment) -> tuple[bool, date, bool, int, str, str]:
        minutes = _departure_minutes(segment.depart_time)
        return (
            segment.depart_date is None,
            segment.depart_date or date.max,
            minutes is None,
            minutes if minutes is not None else 24 * 60,
            str(segment.created_at or ""),
            segment.id or "",
        )

    return sorted(segments, key=sort_key)


def route_text_from_segments(segments: Iterable[TravelSegment]) -> str | None:
    """Build a compact route from chronologically ordered transport segments."""
    cities: list[str] = []
    for segment in ordered_route_segments(segments):
        for city in (segment.from_city, segment.to_city):
            if city and (not cities or cities[-1] != city):
                cities.append(city)
    return " -> ".join(cities) if cities else None


def is_reimbursable_invoice(invoice: Invoice) -> bool:
    """Whether an invoice contributes to the project-level reimbursement state."""
    return invoice.document_role not in _AUXILIARY_DOCUMENT_ROLES


def project_reimbursement_status(invoices: Iterable[Invoice]) -> str:
    """Derive one stable reimbursement state for a project from its invoices."""
    statuses = {
        invoice.reimbursement_status
        for invoice in invoices
        if is_reimbursable_invoice(invoice)
    }
    if not statuses:
        return "PENDING"
    if statuses == {"ALREADY_REIMBURSED"}:
        return "ALREADY_REIMBURSED"
    if "ALREADY_REIMBURSED" in statuses and len(statuses) > 1:
        return "PARTIAL_REIMBURSED"
    if "THIS_TRIP" in statuses:
        return "THIS_TRIP"
    if statuses == {"NOT_REIMBURSED"}:
        return "NOT_REIMBURSED"
    return "PENDING"


def _departure_minutes(value: str | None) -> int | None:
    if not value:
        return None
    match = _DEPART_TIME.match(value)
    if not match:
        return None
    hour, minute = (int(part) for part in match.groups())
    if hour > 23 or minute > 59:
        return None
    return hour * 60 + minute


def serialize_trip(db: Session, trip: Trip) -> TripRead:
    invoices = list(db.scalars(select(Invoice).where(Invoice.trip_id == trip.id)))
    summary_result = calculate_summary(trip, invoices)
    document_count = db.scalar(select(func.count()).select_from(Document).where(Document.trip_id == trip.id)) or 0
    issue_count = db.scalar(
        select(func.count()).select_from(ReviewIssue).where(
            ReviewIssue.trip_id == trip.id, ReviewIssue.resolution_status == "OPEN"
        )
    ) or 0
    review_count = db.scalar(
        select(func.count()).select_from(Invoice).where(
            Invoice.trip_id == trip.id, Invoice.review_status == "NEEDS_REVIEW"
        )
    ) or 0
    summary = TripSummaryCompact(
        invoice_total_amount=summary_result["invoice_total_amount"],
        allowance_amount=summary_result["allowance_amount"],
        grand_total_amount=summary_result["grand_total_amount"],
        reimbursement_total_amount=summary_result["reimbursement_total_amount"],
        reimbursed_total_amount=summary_result["reimbursed_total_amount"],
        unallocated_total_amount=summary_result["unallocated_total_amount"],
        document_count=document_count,
        review_count=review_count,
        issue_count=issue_count,
    )
    # Keep existing projects accurate after a route-ordering fix.  `route_text`
    # is a derived projection, while travel_segments remain the source of truth.
    route_text = route_text_from_segments(
        db.scalars(select(TravelSegment).where(TravelSegment.trip_id == trip.id))
    )
    return TripRead(
        id=trip.id,
        title=trip.title,
        source_label=trip.source_label,
        traveler_name=trip.traveler_name,
        company_name=trip.company_name,
        company_tax_id=trip.company_tax_id,
        project_type=trip.project_type,
        status=trip.status,
        reimbursement_status=project_reimbursement_status(invoices),
        input_start_date=trip.input_start_date,
        input_end_date=trip.input_end_date,
        inferred_start_date=trip.inferred_start_date,
        inferred_end_date=trip.inferred_end_date,
        confirmed_start_date=trip.confirmed_start_date,
        confirmed_end_date=trip.confirmed_end_date,
        trip_days=trip.trip_days,
        date_confidence=float(trip.date_confidence or 0),
        date_evidence=trip.date_evidence,
        route_text=route_text,
        start_date=trip.confirmed_start_date or trip.inferred_start_date,
        end_date=trip.confirmed_end_date or trip.inferred_end_date,
        daily_allowance=trip.daily_allowance,
        invoice_total_amount=summary_result["invoice_total_amount"],
        allowance_amount=summary_result["allowance_amount"],
        grand_total_amount=summary_result["grand_total_amount"],
        document_count=document_count,
        issue_count=issue_count,
        summary=summary,
        created_at=trip.created_at,
        updated_at=trip.updated_at,
    )


def get_summary(db: Session, trip: Trip) -> SummaryRead:
    invoices = db.scalars(select(Invoice).where(Invoice.trip_id == trip.id)).all()
    result = calculate_summary(trip, invoices)
    return SummaryRead(trip_id=trip.id, **result)


def refresh_trip_summary(db: Session, trip: Trip) -> None:
    """Refresh only the reimbursement total when itinerary data is unchanged."""
    invoices = list(db.scalars(select(Invoice).where(Invoice.trip_id == trip.id)))
    _update_summary(trip, invoices)


def rebuild_trip_projections(db: Session, trip: Trip, *, sync_settings: bool = False) -> None:
    """Regenerate derived records idempotently from structured invoices."""
    if sync_settings:
        _apply_user_settings_snapshot(db, trip)
    invoices = list(db.scalars(select(Invoice).where(Invoice.trip_id == trip.id)))
    supplemental_flights = {
        _normalized_transport_no(invoice.transport_no)
        for invoice in invoices
        if invoice.invoice_type == "FLIGHT_ORDER_PROOF"
        and _has_flight_itinerary(invoice)
        and _normalized_transport_no(invoice.transport_no)
    }
    existing_segments = {
        item.invoice_id: item
        for item in db.scalars(select(TravelSegment).where(TravelSegment.trip_id == trip.id))
    }
    existing_lodging = {
        item.invoice_id: item
        for item in db.scalars(select(LodgingStay).where(LodgingStay.trip_id == trip.id))
    }
    desired_segment_ids: set[str] = set()
    desired_lodging_ids: set[str] = set()

    for invoice in invoices:
        if (
            invoice.invoice_type == "FLIGHT_TICKET"
            and _normalized_transport_no(invoice.transport_no) in supplemental_flights
            and not _has_flight_itinerary(invoice)
        ):
            # An order screenshot contains the actual itinerary while the
            # formal invoice commonly only carries its issue date and flight no.
            continue
        if invoice.invoice_type in {"TRAIN_TICKET", "FLIGHT_TICKET", "FLIGHT_ORDER_PROOF", "BUS_TICKET", "TAXI_INVOICE", "RIDE_HAILING_INVOICE"}:
            if invoice.expense_category != "REFUND_CHANGE_FEE":
                transport_type = {
                    "TRAIN_TICKET": "TRAIN",
                    "FLIGHT_TICKET": "FLIGHT",
                    "FLIGHT_ORDER_PROOF": "FLIGHT",
                    "BUS_TICKET": "BUS",
                    "TAXI_INVOICE": "TAXI",
                    "RIDE_HAILING_INVOICE": "RIDE_HAILING",
                }.get(invoice.invoice_type, "OTHER")
                desired_segment_ids.add(invoice.id)
                segment = existing_segments.get(invoice.id) or TravelSegment(trip_id=trip.id, invoice_id=invoice.id)
                segment.transport_type = transport_type
                segment.depart_date = invoice.flight_date or invoice.business_date
                segment.depart_time = invoice.depart_time_str
                segment.from_city = invoice.from_city
                segment.to_city = invoice.to_city
                segment.from_place = invoice.depart_airport or invoice.from_place
                segment.to_place = invoice.arrive_airport or invoice.to_place
                segment.transport_no = invoice.transport_no
                segment.seat_class = invoice.seat_class or invoice.cabin_class
                segment.amount = invoice.confirmed_amount if invoice.confirmed_amount is not None else invoice.total_amount
                segment.confidence = invoice.confidence
                if segment.id is None:
                    db.add(segment)
        if invoice.invoice_type == "HOTEL_INVOICE":
            desired_lodging_ids.add(invoice.id)
            stay = existing_lodging.get(invoice.id) or LodgingStay(trip_id=trip.id, invoice_id=invoice.id)
            stay.hotel_name = invoice.hotel_name or invoice.seller_name
            stay.city = invoice.to_city
            stay.checkin_date = invoice.checkin_date
            stay.checkout_date = invoice.checkout_date
            stay.nights = invoice.nights
            stay.amount = invoice.confirmed_amount if invoice.confirmed_amount is not None else invoice.total_amount
            stay.confidence = invoice.confidence
            if stay.id is None:
                db.add(stay)
    for invoice_id, segment in existing_segments.items():
        if invoice_id not in desired_segment_ids:
            db.delete(segment)
    for invoice_id, stay in existing_lodging.items():
        if invoice_id not in desired_lodging_ids:
            db.delete(stay)
    db.flush()

    _infer_dates_and_route(db, trip, invoices)
    _update_summary(trip, invoices)
    _detect_issues(db, trip, invoices)
    trip.status = "READY_FOR_REVIEW" if invoices else "PENDING"


def _normalized_transport_no(value: str | None) -> str | None:
    return value.strip().upper() if value and value.strip() else None


def _has_flight_itinerary(invoice: Invoice) -> bool:
    return bool(
        invoice.from_city
        and invoice.to_city
        and (invoice.flight_date or invoice.business_date)
    )


def _infer_dates_and_route(db: Session, trip: Trip, invoices: list[Invoice]) -> None:
    segments = list(db.scalars(select(TravelSegment).where(TravelSegment.trip_id == trip.id)))
    intercity_dates = [segment.depart_date for segment in segments if segment.transport_type in {"TRAIN", "FLIGHT"} and segment.depart_date]
    lodging = list(db.scalars(select(LodgingStay).where(LodgingStay.trip_id == trip.id)))
    checkins = [stay.checkin_date for stay in lodging if stay.checkin_date]
    checkouts = [stay.checkout_date for stay in lodging if stay.checkout_date]
    business_dates = [invoice.business_date for invoice in invoices if invoice.business_date]
    invoice_dates = [invoice.invoice_date for invoice in invoices if invoice.invoice_date]

    start: date | None
    end: date | None
    confidence: float
    evidence: list[str]
    if intercity_dates:
        start, end, confidence, evidence = min(intercity_dates), max(intercity_dates), 0.95, ["使用城际交通票据的最早和最晚日期"]
    elif checkins and checkouts:
        start, end, confidence, evidence = min(checkins), max(checkouts), 0.85, ["使用住宿记录的入住和离店日期"]
    elif trip.input_start_date and trip.input_end_date:
        start, end, confidence, evidence = trip.input_start_date, trip.input_end_date, 0.75, ["使用项目输入日期"]
    elif metadata_range := _date_range_from_trip_metadata(db, trip):
        start, end, confidence, evidence = metadata_range
    elif business_dates:
        start, end, confidence, evidence = min(business_dates), max(business_dates), 0.60, ["使用票据业务日期"]
    elif invoice_dates:
        start, end, confidence, evidence = min(invoice_dates), max(invoice_dates), 0.40, ["使用开票日期，仅供参考"]
    else:
        start, end, confidence, evidence = None, None, 0.0, ["无法自动推断出差日期"]
    trip.inferred_start_date = start
    trip.inferred_end_date = end
    trip.date_confidence = confidence
    trip.date_evidence = evidence
    effective_start = trip.confirmed_start_date or start
    effective_end = trip.confirmed_end_date or end
    if effective_start and effective_end and effective_end < effective_start:
        raise ValueError("Trip end date must be on or after start date")
    trip.trip_days = (
        calculate_trip_days(
            effective_start,
            effective_end,
            include_start_day=getattr(trip, "include_start_day", True),
            include_end_day=getattr(trip, "include_end_day", True),
        )
        if effective_start and effective_end
        else None
    )

    trip.route_text = route_text_from_segments(segments)


def _date_range_from_trip_metadata(db: Session, trip: Trip) -> tuple[date, date, float, list[str]] | None:
    """Recover the old folder-date fallback from browser-safe metadata only."""
    for label, value in (("项目来源标签", trip.source_label), ("项目名称", trip.title)):
        date_range = _parse_date_range(value)
        if date_range:
            return (*date_range, 0.75, [f"使用{label}中的日期"])

    ranges = [
        date_range
        for value in db.scalars(
            select(Document.relative_path).where(
                Document.trip_id == trip.id,
                Document.relative_path.is_not(None),
            )
        )
        if (date_range := _parse_date_range(value)) is not None
    ]
    if not ranges:
        return None
    counts = Counter(ranges)
    start, end = sorted(
        counts,
        key=lambda item: (-counts[item], -(item[1] - item[0]).days, item[0], item[1]),
    )[0]
    return start, end, 0.75, ["使用上传目录中的日期"]


def _parse_date_range(value: str | None) -> tuple[date, date] | None:
    """Parse the date-range formats accepted by the legacy folder workflow."""
    if not value:
        return None
    match = _COMPACT_DATE_RANGE.search(value)
    if match:
        result = _make_date_range(
            int(match.group(1)[:4]), int(match.group(1)[4:6]), int(match.group(1)[6:8]),
            int(match.group(2)[:4]), int(match.group(2)[4:6]), int(match.group(2)[6:8]),
        )
        if result:
            return result
    match = _FULL_DATE_RANGE.search(value)
    if match:
        result = _make_date_range(*(int(part) for part in match.groups()))
        if result:
            return result
    match = _SHORT_DATE_RANGE.search(value)
    if match:
        values = [int(part) for part in match.groups()]
        return _make_date_range(2000 + values[0], values[1], values[2], 2000 + values[3], values[4], values[5])
    return None


def _make_date_range(year_one: int, month_one: int, day_one: int, year_two: int, month_two: int, day_two: int) -> tuple[date, date] | None:
    try:
        first = date(year_one, month_one, day_one)
        second = date(year_two, month_two, day_two)
    except ValueError:
        return None
    return (first, second) if first <= second else (second, first)


def _update_summary(trip: Trip, invoices: Iterable[Invoice]) -> None:
    result = calculate_summary(trip, invoices)
    for field in (
        "intercity_transport_amount",
        "local_transport_amount",
        "lodging_amount",
        "meal_amount",
        "other_amount",
        "invoice_total_amount",
        "allowance_amount",
        "grand_total_amount",
    ):
        setattr(trip, field, result[field])
    trip.trip_days = int(result["trip_days"])


def _issue_fingerprint(issue_type: str, document_id: str | None, invoice_id: str | None) -> str:
    raw = "|".join((issue_type, document_id or "", invoice_id or ""))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _detect_issues(db: Session, trip: Trip, invoices: Iterable[Invoice]) -> None:
    """Upsert rule findings without erasing a prior resolve/ignore decision."""
    candidates: list[tuple[str, str | None, str | None, str, str, str | None]] = []
    for invoice in invoices:
        if float(invoice.confidence or 0) < 0.7:
            candidates.append(("LOW_CONFIDENCE", invoice.document_id, invoice.id, "WARNING", "识别置信度较低，请人工复核", "请检查并修正识别结果"))
        amount = invoice.confirmed_amount if invoice.confirmed_amount is not None else invoice.total_amount
        if invoice.document_role not in {"ORDER_SCREENSHOT", "BOOKING_SCREENSHOT", "SUPPORTING_DOC"} and (amount is None or amount <= 0):
            candidates.append(("MISSING_AMOUNT", invoice.document_id, invoice.id, "ERROR", "未识别到有效金额", "请手动填写发票金额"))
        if amount is not None and invoice.confirmed_amount is None and amount > Decimal("100000"):
            candidates.append(("INVALID_AMOUNT", invoice.document_id, invoice.id, "ERROR", "识别金额异常，疑似误识别为发票代码", "请人工确认正确金额"))
        lodging_limit = getattr(trip, "lodging_limit_per_day", None)
        if (
            invoice.expense_category == "LODGING"
            and lodging_limit is not None
            and amount is not None
            and amount > Decimal(str(lodging_limit)) * Decimal(max(1, invoice.nights or 1))
        ):
            candidates.append(("LODGING_LIMIT_EXCEEDED", invoice.document_id, invoice.id, "WARNING", "住宿金额超过设置的每日限额", "请确认住宿标准或人工调整金额"))
    if not ((trip.confirmed_start_date and trip.confirmed_end_date) or (trip.inferred_start_date and trip.inferred_end_date)):
        candidates.append(("CANNOT_INFER_DATES", None, None, "WARNING", "无法自动推断出差日期", "请手动设置出差起止日期"))
    effective_start = trip.confirmed_start_date or trip.inferred_start_date
    effective_end = trip.confirmed_end_date or trip.inferred_end_date
    if (
        trip.confirmed_start_date
        and trip.confirmed_end_date
        and trip.inferred_start_date
        and trip.inferred_end_date
        and (trip.confirmed_start_date, trip.confirmed_end_date)
        != (trip.inferred_start_date, trip.inferred_end_date)
    ):
        candidates.append(
            (
                "DATE_CONFLICT",
                None,
                None,
                "WARNING",
                "人工确认日期与票据推断日期不一致，已按人工确认日期计算",
                "请核对票据日期；人工确认值会覆盖自动推断",
            )
        )
    if invoices and getattr(trip, "require_lodging_invoice", True) and effective_start and effective_end and effective_end > effective_start:
        lodging_invoices = [item for item in invoices if item.expense_category == "LODGING" and item.include_in_summary]
        if not lodging_invoices:
            candidates.append(("MISSING_LODGING_INVOICE", None, None, "WARNING", "项目缺少住宿发票", "请上传住宿发票或关闭住宿发票校验"))
    if invoices and getattr(trip, "require_return_ticket", True):
        segments = list(db.scalars(select(TravelSegment).where(TravelSegment.trip_id == trip.id)))
        intercity = [item for item in segments if item.transport_type in {"TRAIN", "FLIGHT", "BUS"}]
        if intercity and effective_start and effective_end and len(intercity) < 2 and effective_end > effective_start:
            candidates.append(("MISSING_RETURN_TICKET", None, None, "WARNING", "未发现返程交通票据", "请上传返程票据或关闭返程票校验"))

    existing_by_fingerprint = {
        issue.rule_fingerprint: issue
        for issue in db.scalars(select(ReviewIssue).where(ReviewIssue.trip_id == trip.id))
    }
    candidate_fingerprints: set[str] = set()
    for issue_type, document_id, invoice_id, severity, message, suggestion in candidates:
        fingerprint = _issue_fingerprint(issue_type, document_id, invoice_id)
        candidate_fingerprints.add(fingerprint)
        existing = existing_by_fingerprint.get(fingerprint)
        if existing:
            if existing.resolution_status == "OPEN":
                existing.severity = severity
                existing.message = message
                existing.suggestion = suggestion
            elif existing.resolution_status == "AUTO_CLEARED":
                existing.resolution_status = "OPEN"
                existing.resolution_note = None
                existing.resolved_at = None
                existing.severity = severity
                existing.message = message
                existing.suggestion = suggestion
            continue
        db.add(
            ReviewIssue(
                trip_id=trip.id,
                document_id=document_id,
                invoice_id=invoice_id,
                issue_type=issue_type,
                rule_fingerprint=fingerprint,
                severity=severity,
                message=message,
                suggestion=suggestion,
            )
        )
    for fingerprint, issue in existing_by_fingerprint.items():
        if issue.resolution_status == "OPEN" and fingerprint not in candidate_fingerprints:
            issue.resolution_status = "AUTO_CLEARED"
            issue.resolution_note = "规则已不再满足，系统自动关闭"


def serialize_issue(db: Session, issue: ReviewIssue) -> IssueRead:
    filename = None
    if issue.document_id:
        document = db.get(Document, issue.document_id)
        filename = document.original_filename if document else None
    return IssueRead(
        id=issue.id,
        trip_id=issue.trip_id,
        document_id=issue.document_id,
        invoice_id=issue.invoice_id,
        issue_type=issue.issue_type,
        severity=issue.severity,
        message=issue.message,
        suggestion=issue.suggestion,
        resolution_status=issue.resolution_status,
        resolved=issue.resolution_status != "OPEN",
        ignored=issue.resolution_status == "IGNORED",
        resolution_note=issue.resolution_note,
        resolved_at=issue.resolved_at,
        created_at=issue.created_at,
        file_name=filename,
    )


def default_settings_for_user(db: Session, user_id: str) -> UserSettings:
    runtime = get_settings()
    remote_configured = runtime.remote_ocr_configured
    setting = db.scalar(select(UserSettings).where(UserSettings.user_id == user_id))
    if setting:
        # Existing users created before the Web migration had no remote OCR
        # configuration state. Enable their existing server-side fallback once,
        # while preserving a later explicit user opt-out.
        was_configured = setting.remote_provider_configured
        setting.remote_provider_configured = remote_configured
        if remote_configured and not was_configured:
            setting.remote_provider_enabled = runtime.remote_ocr_available
        elif not remote_configured:
            setting.remote_provider_enabled = False
        return setting
    setting = UserSettings(
        user_id=user_id,
        remote_provider_configured=remote_configured,
        remote_provider_enabled=runtime.remote_ocr_available,
    )
    db.add(setting)
    db.flush()
    return setting


def _apply_user_settings_snapshot(db: Session, trip: Trip) -> None:
    """Keep the domain calculation sourced from the owner's current rules."""
    if not getattr(trip, "owner_id", None):
        return
    setting = db.scalar(select(UserSettings).where(UserSettings.user_id == trip.owner_id))
    if not setting:
        return
    trip.daily_allowance = setting.daily_allowance
    trip.include_start_day = setting.include_start_day
    trip.include_end_day = setting.include_end_day
    trip.lodging_limit_per_day = setting.lodging_limit_per_day
    trip.require_return_ticket = setting.require_return_ticket
    trip.require_lodging_invoice = setting.require_lodging_invoice
