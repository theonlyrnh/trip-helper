"""Train ticket parser – extracts fields from railway e-ticket OCR text."""

import re
from decimal import Decimal
from datetime import date
from parsers.base_parser import BaseParser, ParsedInvoice
from enums import InvoiceType, ExpenseCategory


class TrainTicketParser(BaseParser):
    invoice_type = InvoiceType.TRAIN_TICKET

    # Patterns – relaxed for noisy OCR output (handles concatenated text like "站G7925站")
    TRAIN_NO_RE = re.compile(r"[GDCZTK]\d{1,4}")
    DATE_RE = re.compile(r"(\d{4})[年\-\/\.](\d{1,2})[月\-\/\.](\d{1,2})[日]?")
    # Amount: ¥ prefix with at most 2 decimal places, or number followed by 元
    AMOUNT_RE = re.compile(r"[¥￥]\s*(\d+\.?\d{0,2})(?:\s*[元]?)|(\d+\.\d{2})\s*元")
    NAME_RE = re.compile(r"(?:乘车人|乘机人|姓名)[：:]\s*(\S+)")
    SEAT_RE = re.compile(r"(二等座|一等座|商务座|硬座|硬卧|软卧|无座|特等座)")
    # Station pattern: Chinese place name ending with 站
    STATION_SINGLE_RE = re.compile(r"([\u4e00-\u9fff]{2,6}站)")

    def can_parse(self, raw_text: str) -> bool:
        return bool(self.TRAIN_NO_RE.search(raw_text))

    def parse(self, raw_text: str) -> ParsedInvoice:
        result = ParsedInvoice(
            invoice_type=InvoiceType.TRAIN_TICKET,
            expense_category=ExpenseCategory.INTERCITY_TRANSPORT,
            parser_name="TrainTicketParser",
            confidence=0.85,
        )

        # ── Train number ──
        m = self.TRAIN_NO_RE.search(raw_text)
        if m:
            raw_match = m.group()
            # Extract just the train number from surrounding chars
            tn = re.search(r"[GDCZTK]\d{1,4}", raw_match)
            if tn:
                result.transport_no = tn.group()

        # ── Date ──
        m = self.DATE_RE.search(raw_text)
        if m:
            try:
                result.business_date = date(
                    int(m.group(1)), int(m.group(2)), int(m.group(3))
                )
            except ValueError:
                pass

        # ── Depart time (e.g. "15:18开") ──
        time_match = re.search(r"(\d{1,2}:\d{2})\s*开", raw_text)
        if time_match:
            result.depart_time = time_match.group(1)

        # ── Amount ──
        amounts = self.AMOUNT_RE.findall(raw_text)
        if amounts:
            nums = []
            for t in amounts:
                for val in t:
                    if val:
                        try:
                            n = Decimal(val)
                            if 0 < n < 10000:
                                nums.append(n)
                        except Exception:
                            pass
            if nums:
                result.total_amount = max(nums)

        # ── Person name ──
        m = self.NAME_RE.search(raw_text)
        if m:
            result.person_name = m.group(1)
        if not result.person_name:
            # Fallback: Chinese name after masked ID (e.g. "4128282001****2510 任宁辉")
            m = re.search(r"\*{4}\d{4}\s+([\u4e00-\u9fff]{2,4})", raw_text)
            if m:
                result.person_name = m.group(1)

        # ── Seat class ──
        m = self.SEAT_RE.search(raw_text)
        if m:
            result.seat_class = m.group(1)

        # ── Stations ──
        # Strategy: find all "XX站" patterns, pick the two near the train number
        stations = self.STATION_SINGLE_RE.findall(raw_text)
        if len(stations) >= 2:
            # Filter out non-station matches (like 网站, 站台 etc.)
            real_stations = [
                s for s in stations
                if not any(kw in s for kw in ["网站", "站台", "站内"])
            ]
            if len(real_stations) >= 2:
                result.from_place = real_stations[0]
                result.to_place = real_stations[1]
                result.from_city = _extract_city(real_stations[0])
                result.to_city = _extract_city(real_stations[1])
            elif len(real_stations) == 1:
                result.from_place = real_stations[0]

        # Fallback: try arrow/to pattern
        if not result.from_place:
            station_pattern = re.compile(
                r"([\u4e00-\u9fff]{2,4}(?:站|南|北|东|西)?)\s*[→\-—>至到]\s*([\u4e00-\u9fff]{2,4}(?:站|南|北|东|西)?)"
            )
            m = station_pattern.search(raw_text)
            if m:
                result.from_place = m.group(1)
                result.to_place = m.group(2)
                result.from_city = _extract_city(m.group(1))
                result.to_city = _extract_city(m.group(2))

        return result


def _extract_city(place: str) -> str:
    """Extract city name from a station name like '北京南' → '北京'."""
    for suffix in ["南", "北", "东", "西", "站"]:
        if place.endswith(suffix) and len(place) > 2:
            return place[:-1]
    return place