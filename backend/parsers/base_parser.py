"""Base parser interface and parsed invoice DTO."""

from dataclasses import dataclass, field
from decimal import Decimal
from datetime import date


@dataclass
class ParsedInvoice:
    invoice_type: str
    expense_category: str

    invoice_code: str | None = None
    invoice_number: str | None = None
    invoice_date: date | None = None

    seller_name: str | None = None
    buyer_name: str | None = None

    total_amount: Decimal | None = None
    tax_amount: Decimal | None = None

    business_date: date | None = None

    person_name: str | None = None

    from_city: str | None = None
    to_city: str | None = None
    from_place: str | None = None
    to_place: str | None = None

    transport_no: str | None = None
    seat_class: str | None = None

    hotel_name: str | None = None
    checkin_date: date | None = None
    checkout_date: date | None = None
    nights: int | None = None

    confidence: float = 0.0
    parser_name: str = ""


class BaseParser:
    invoice_type: str = "UNKNOWN"

    def can_parse(self, raw_text: str) -> bool:
        raise NotImplementedError

    def parse(self, raw_text: str) -> ParsedInvoice:
        raise NotImplementedError