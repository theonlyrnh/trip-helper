"""Map immutable OCR output to a replaceable structured invoice projection."""

from __future__ import annotations

import re
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.db.models import Document, Invoice, OcrRun


def ensure_manual_review_invoice(
    db: Session,
    document: Document,
    *,
    reason: str = "OCR 未返回可用文字，请人工录入。",
) -> Invoice:
    """Create or retain a reviewable invoice for an empty/failed OCR result."""
    existing = db.scalar(select(Invoice).where(Invoice.document_id == document.id))
    if existing:
        if existing.review_status != "MANUALLY_CONFIRMED":
            existing.review_status = "NEEDS_REVIEW"
            existing.include_in_summary = False
            existing.note = reason
        return existing
    invoice = Invoice(
        trip_id=document.trip_id,
        document_id=document.id,
        invoice_type="UNKNOWN",
        expense_category="OTHER",
        confidence=0,
        parser_name="ManualFallback",
        review_status="NEEDS_REVIEW",
        reimbursement_status="PENDING",
        document_role="OFFICIAL_INVOICE",
        include_in_summary=False,
        note=reason,
    )
    db.add(invoice)
    db.flush()
    return invoice


def extract_invoice_from_ocr(
    db: Session,
    document: Document,
    ocr_run: OcrRun,
    *,
    coordinate_words: list | None = None,
    page_width: float | None = None,
) -> Invoice | None:
    """Use the established parsers without coupling them to old ORM models."""
    raw_text = re.sub(r"<\|LOC_\d+\|>", "", ocr_run.raw_text or "").strip()
    if not raw_text:
        return None

    # Existing parsers are pure text/coordinate code and remain the domain source.
    from parsers.flight_ticket_parser import FlightTicketParser
    from parsers.hotel_invoice_parser import HotelInvoiceParser
    from parsers.train_ticket_parser import TrainTicketParser
    from parsers.vat_invoice_parser import VATInvoiceParser
    from services.classification_service import classify_invoice

    classification = classify_invoice(raw_text)
    existing = db.scalar(select(Invoice).where(Invoice.document_id == document.id))
    if existing and existing.review_status == "MANUALLY_CONFIRMED":
        return existing
    invoice = existing or Invoice(trip_id=document.trip_id, document_id=document.id)

    role = "OFFICIAL_INVOICE"
    include = True
    parser_name = "ClassificationOnly"
    confidence = classification.confidence
    fields: dict[str, object] = {
        "invoice_type": classification.invoice_type,
        "expense_category": classification.expense_category,
        "ocr_run_id": ocr_run.id,
        "review_status": "NEEDS_REVIEW",
        "reimbursement_status": "THIS_TRIP",
    }

    coordinate_fields = _coordinate_train_fields(coordinate_words, page_width)
    if coordinate_fields:
        parser_name = "TrainTicketCoordParser"
        confidence = float(coordinate_fields.pop("confidence"))
        fields.update(coordinate_fields)
    elif classification.invoice_type == "HOTEL_BOOKING_PROOF":
        role, include, parser_name = "BOOKING_SCREENSHOT", False, "PlatformBookingDetector"
        fields.update(_booking_fields(raw_text))
    elif classification.invoice_type == "FLIGHT_ORDER_PROOF":
        role, include, parser_name = "ORDER_SCREENSHOT", False, "FlightOrderDetector"
        fields.update(_flight_order_fields(raw_text, reference_date=_document_reference_date(document)))
    elif classification.invoice_type == "TRAVEL_INSURANCE_INVOICE":
        parser_name = "TravelInsuranceDetector"
        fields.update(_insurance_fields(raw_text))
    elif classification.expense_category == "REFUND_CHANGE_FEE":
        parser_name = "RefundChangeDetector"
        fields.update(_refund_fields(raw_text))
    elif classification.invoice_type == "GENERAL_INVOICE":
        parser_name = "GeneralInvoiceDetector"
        fields.update(_general_invoice_fields(raw_text, classification.expense_category))
    else:
        parser = next(
            (
                parser
                for parser in (TrainTicketParser(), FlightTicketParser(), HotelInvoiceParser(), VATInvoiceParser())
                if parser.invoice_type == classification.invoice_type
            ),
            None,
        )
        if parser is None:
            parser = next(
                (parser for parser in (TrainTicketParser(), FlightTicketParser(), HotelInvoiceParser(), VATInvoiceParser()) if parser.can_parse(raw_text)),
                None,
            )
        if parser:
            parsed = parser.parse(raw_text)
            parser_name = parsed.parser_name
            confidence = parsed.confidence
            fields.update(
                {
                    "invoice_type": parsed.invoice_type,
                    "expense_category": parsed.expense_category,
                    "invoice_code": parsed.invoice_code,
                    "invoice_number": parsed.invoice_number,
                    "invoice_date": parsed.invoice_date,
                    "seller_name": parsed.seller_name,
                    "buyer_name": parsed.buyer_name,
                    "total_amount": parsed.total_amount,
                    "tax_amount": parsed.tax_amount,
                    "business_date": parsed.business_date,
                    "person_name": parsed.person_name,
                    "from_city": parsed.from_city,
                    "to_city": parsed.to_city,
                    "from_place": parsed.from_place,
                    "to_place": parsed.to_place,
                    "transport_no": parsed.transport_no,
                    "seat_class": parsed.seat_class,
                    "depart_time_str": parsed.depart_time,
                    "hotel_name": parsed.hotel_name,
                    "checkin_date": parsed.checkin_date,
                    "checkout_date": parsed.checkout_date,
                    "nights": parsed.nights,
                }
            )
    fields.update({"document_role": role, "include_in_summary": include, "parser_name": parser_name, "confidence": confidence})
    for name, value in fields.items():
        setattr(invoice, name, value)
    if not existing:
        db.add(invoice)
    db.flush()
    return invoice


def _coordinate_train_fields(words: list | None, page_width: float | None) -> dict[str, object] | None:
    """Use the retained PyMuPDF coordinate parser before text-order heuristics."""
    if not words:
        return None
    from parsers.train_ticket_coord_parser import parse_train_ticket_words

    result = parse_train_ticket_words(words, page_width or 595)
    if not result.train_no:
        return None
    amount = result.fare_amount or result.change_fee_amount
    return {
        "invoice_type": result.invoice_type,
        "expense_category": result.expense_category,
        "invoice_date": result.invoice_date,
        "business_date": result.travel_date,
        "total_amount": amount,
        "depart_time_str": result.depart_time,
        "person_name": result.person_name,
        "from_place": result.departure_station,
        "to_place": result.arrival_station,
        "from_city": _station_city(result.departure_station),
        "to_city": _station_city(result.arrival_station),
        "transport_no": result.train_no,
        "seat_class": result.seat_class,
        "buyer_name": result.buyer_name,
        "review_status": "NEEDS_REVIEW" if result.needs_review else "AUTO_CONFIRMED",
        "confidence": result.confidence,
    }


def _station_city(value: str | None) -> str | None:
    if not value:
        return None
    for suffix in ("南", "北", "东", "西", "站"):
        if value.endswith(suffix) and len(value) > 2:
            return value[:-1]
    return value


def _booking_fields(raw_text: str) -> dict[str, object]:
    dates = _find_dates(raw_text)
    hotel = _find_first(raw_text, r"([\u4e00-\u9fff]{3,30}(?:酒店|宾馆|民宿|旅馆))")
    amount = _find_amount(raw_text)
    return {
        "expense_category": "LODGING",
        "total_amount": amount,
        "hotel_name": hotel,
        "actual_hotel_name": hotel,
        "checkin_date": min(dates) if len(dates) >= 2 else None,
        "checkout_date": max(dates) if len(dates) >= 2 else None,
        "nights": (max(dates) - min(dates)).days if len(dates) >= 2 else None,
        "platform_name": next((name for name in ("携程", "飞猪", "美团", "同程", "去哪儿", "艺龙") if name in raw_text), None),
        "booking_order_no": _find_first(raw_text, r"订单号[：:]?\s*([A-Za-z0-9-]+)"),
    }


_FLIGHT_NUMBER = re.compile(r"(?<![A-Z0-9])([A-Z]{2}\d{3,4})(?!\d)", re.IGNORECASE)
_MONTH_DAY = re.compile(
    r"(?:(?P<year>\d{4})\s*年\s*)?(?P<month>1[0-2]|0?\d)\s*月\s*(?P<day>3[01]|[12]?\d)\s*日?"
)
_WEEKDAY = re.compile(r"(?:周|星期)[一二三四五六日天]")
_FLIGHT_ROUTE = re.compile(r"(?P<from>[\u4e00-\u9fff]{2,8})\s*(?:[-－—–→]|至|到)\s*(?P<to>[\u4e00-\u9fff]{2,8})")
_TIME = re.compile(r"\b([01]?\d|2[0-3]):[0-5]\d\b")
_AIRPORT = re.compile(r"([\u4e00-\u9fff]{2,30}(?:国际)?机场(?:[Tt]\d)?)")


def _flight_order_fields(raw_text: str, *, reference_date: date | None = None) -> dict[str, object]:
    route_line, route_index, from_city, to_city = _find_flight_route(raw_text)
    flight_date = _find_flight_date(route_line, reference_date)
    depart_time, depart_airport, arrive_airport = _find_flight_schedule(raw_text, route_index)
    transport_no = _find_flight_number(raw_text)
    return {
        "expense_category": "INTERCITY_TRANSPORT",
        "order_total_amount": _find_amount(raw_text),
        # The itinerary date is the business date shown in review/export views;
        # flight_date remains the dedicated transport projection source.
        "flight_date": flight_date,
        "business_date": flight_date,
        "from_city": from_city,
        "to_city": to_city,
        "from_place": depart_airport,
        "to_place": arrive_airport,
        "depart_airport": depart_airport,
        "arrive_airport": arrive_airport,
        "depart_time_str": depart_time,
        "transport_no": transport_no,
        "airline_name": _find_airline(raw_text, transport_no),
        "seat_class": _find_first(raw_text, r"(?:[|｜]\s*)?([^\s|｜]{1,16}舱)(?:\s*[|｜]|$)"),
        "booking_order_no": _find_first(raw_text, r"订单号[：:]?\s*([A-Za-z0-9-]+)"),
        "platform_name": next((name for name in ("携程", "飞猪", "美团", "同程", "去哪儿") if name in raw_text), None),
    }


def _document_reference_date(document: Document) -> date | None:
    created_at = getattr(document, "created_at", None)
    if isinstance(created_at, date):
        return created_at.date() if hasattr(created_at, "date") else created_at
    return None


def _find_flight_route(raw_text: str) -> tuple[str | None, int | None, str | None, str | None]:
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    candidates: list[tuple[int, int, str, str, str]] = []
    for index, line in enumerate(lines):
        cleaned = _MONTH_DAY.sub(" ", line)
        cleaned = _WEEKDAY.sub(" ", cleaned)
        match = _FLIGHT_ROUTE.search(cleaned)
        if not match:
            continue
        from_city = _normalize_city(match.group("from"))
        to_city = _normalize_city(match.group("to"))
        if not from_city or not to_city or from_city == to_city:
            continue
        is_itinerary = any(marker in line for marker in ("单程", "去程", "行程", "航班"))
        candidates.append((0 if is_itinerary else 1, index, line, from_city, to_city))
    if not candidates:
        return None, None, None, None
    _, index, line, from_city, to_city = min(candidates, key=lambda item: (item[0], item[1]))
    return line, index, from_city, to_city


def _normalize_city(value: str) -> str | None:
    result = value.strip().removesuffix("市")
    return result or None


def _find_flight_date(route_line: str | None, reference_date: date | None) -> date | None:
    if not route_line:
        return None
    match = _MONTH_DAY.search(route_line)
    if not match:
        return None
    try:
        month = int(match.group("month"))
        day = int(match.group("day"))
        if match.group("year"):
            return date(int(match.group("year")), month, day)
        reference = reference_date or date.today()
        candidate = date(reference.year, month, day)
        if candidate - reference > timedelta(days=200):
            return date(reference.year - 1, month, day)
        if reference - candidate > timedelta(days=200):
            return date(reference.year + 1, month, day)
        return candidate
    except ValueError:
        return None


def _find_flight_schedule(raw_text: str, route_index: int | None) -> tuple[str | None, str | None, str | None]:
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    window = lines[(route_index + 1) if route_index is not None else 0 : (route_index + 12) if route_index is not None else 12]
    times = [match.group(0) for line in window for match in _TIME.finditer(line)]
    airports = [_airport_from_line(line) for line in window if "机场" in line]
    airports = [airport for airport in airports if airport]
    return (times[0] if times else None, airports[0] if airports else None, airports[1] if len(airports) > 1 else None)


def _airport_from_line(line: str) -> str | None:
    match = _AIRPORT.search(line)
    return match.group(1).strip() if match else None


def _find_flight_number(raw_text: str) -> str | None:
    match = _FLIGHT_NUMBER.search(raw_text)
    return match.group(1).upper() if match else None


def _find_airline(raw_text: str, flight_no: str | None) -> str | None:
    if not flight_no:
        return None
    match = re.search(rf"([\u4e00-\u9fffA-Za-z]{{2,16}})\s*{re.escape(flight_no)}", raw_text, re.IGNORECASE)
    return match.group(1).strip() if match else None


def _insurance_fields(raw_text: str) -> dict[str, object]:
    return {
        "expense_category": "TRAVEL_INSURANCE",
        "total_amount": _find_amount(raw_text),
        "invoice_number": _find_first(raw_text, r"发票号码[：:]?\s*([A-Za-z0-9-]+)"),
        "booking_order_no": _find_first(raw_text, r"保单号[：:]?\s*([A-Za-z0-9-]+)"),
        "invoice_date": _find_dates(raw_text)[0] if _find_dates(raw_text) else None,
    }


def _refund_fields(raw_text: str) -> dict[str, object]:
    return {
        "invoice_type": "OTHER",
        "expense_category": "REFUND_CHANGE_FEE",
        "total_amount": _find_amount(raw_text),
        "transport_no": _find_first(raw_text, r"\b([A-Z]{2}\d{3,4}|[GDCZTK]\d{1,4})\b"),
        "business_date": _find_dates(raw_text)[0] if _find_dates(raw_text) else None,
    }


def _general_invoice_fields(raw_text: str, expense_category: str) -> dict[str, object]:
    dates = _find_dates(raw_text)
    return {
        "invoice_type": "GENERAL_INVOICE",
        "expense_category": expense_category,
        "total_amount": _find_amount(raw_text),
        "invoice_number": _find_first(raw_text, r"发票号码[：:]?\s*([A-Za-z0-9-]+)"),
        "invoice_code": _find_first(raw_text, r"发票代码[：:]?\s*([A-Za-z0-9-]+)"),
        "invoice_date": dates[0] if dates else None,
        "seller_name": _find_first(raw_text, r"(?:销售方名称|销售方)[：:]?\s*([^\n\s]+)"),
        "buyer_name": _find_first(raw_text, r"(?:购买方名称|购买方)[：:]?\s*([^\n\s]+)"),
    }


def _find_dates(raw_text: str) -> list[date]:
    matches = re.findall(r"(\d{4})[年\-/.](\d{1,2})[月\-/.](\d{1,2})", raw_text)
    values: list[date] = []
    for year, month, day in matches:
        try:
            values.append(date(int(year), int(month), int(day)))
        except ValueError:
            continue
    return values


def _find_amount(raw_text: str) -> Decimal | None:
    values = [Decimal(value) for value in re.findall(r"[¥￥]\s*(\d+(?:\.\d{1,2})?)", raw_text)]
    values = [value for value in values if Decimal("0") < value < Decimal("100000")]
    return max(values) if values else None


def _find_first(raw_text: str, pattern: str) -> str | None:
    match = re.search(pattern, raw_text)
    return match.group(1) if match else None
