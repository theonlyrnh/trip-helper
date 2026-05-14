"""Coordinate-based train ticket parser using PyMuPDF words output.

Key design:
- Uses page.get_text("words") for (x,y) coordinates
- Separates 开票日期 (invoice_date) from 乘车日期 (travel_date) by checking for "开" suffix
- Determines departure/arrival station by x-position relative to train number
- Separates 票价 (fare) from 改签费/退票费 (change/refund fee)
"""

import re
from decimal import Decimal
from datetime import date, time
from dataclasses import dataclass, field


@dataclass
class TrainTicketResult:
    invoice_type: str = "TRAIN_TICKET"
    expense_category: str = "INTERCITY_TRANSPORT"

    invoice_date: date | None = None
    travel_date: date | None = None
    depart_time: str | None = None

    train_no: str | None = None
    departure_station: str | None = None
    arrival_station: str | None = None

    fare_amount: Decimal | None = None
    change_fee_amount: Decimal | None = None

    seat_class: str | None = None
    person_name: str | None = None
    buyer_name: str | None = None

    should_create_travel_segment: bool = False
    needs_review: bool = False
    issues: list[str] = field(default_factory=list)
    confidence: float = 0.85


def parse_train_ticket_words(words: list, page_width: float = 595) -> TrainTicketResult:
    """
    Parse a train e-ticket from PyMuPDF words list.

    Each word: (x0, y0, x1, y1, text, block_no, line_no, word_no)
    """
    result = TrainTicketResult()
    center_x = page_width / 2

    # ── Group words by approximate y-line ──
    lines: dict[int, list] = {}
    for w in words:
        y_key = round(w[1] / 5) * 5  # group by 5px y-bands
        if y_key not in lines:
            lines[y_key] = []
        lines[y_key].append(w)

    # ── Extract train number (center, middle area) ──
    train_no_re = re.compile(r"^[GDCZTK]\d{1,4}$")
    for w in words:
        if train_no_re.match(w[4]) and abs(w[0] + w[2] / 2 - center_x) < 150:
            result.train_no = w[4]
            break

    # ── Extract stations: left of train_no = departure, right = arrival ──
    if result.train_no:
        train_x = 0
        for w in words:
            if w[4] == result.train_no:
                train_x = (w[0] + w[2]) / 2
                break

        # Find station words near train_no's y-coordinate
        train_y = 0
        for w in words:
            if w[4] == result.train_no:
                train_y = w[1]
                break

        left_station_parts = []
        right_station_parts = []
        for w in words:
            if abs(w[1] - train_y) > 15:
                continue
            if not re.search(r"[\u4e00-\u9fff]", w[4]):
                continue
            if w[0] < train_x - 20:
                left_station_parts.append((w[0], w[4]))
            elif w[0] > train_x + 20:
                right_station_parts.append((w[0], w[4]))

        left_station_parts.sort()
        right_station_parts.sort()

        if left_station_parts:
            result.departure_station = "".join(t[1] for t in left_station_parts)
        if right_station_parts:
            result.arrival_station = "".join(t[1] for t in right_station_parts)

    # ── Extract dates ──
    date_re = re.compile(r"(\d{4})[年\-\/\.](\d{1,2})[月\-\/\.](\d{1,2})[日]?")
    time_re = re.compile(r"(\d{1,2}:\d{2})")

    all_dates = []
    for w in words:
        m = date_re.search(w[4])
        if m:
            try:
                d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
                all_dates.append((w, d))
            except ValueError:
                pass

    # Find 开票日期 (invoice date) - has "开票日期" label, top-right area
    for w, d in all_dates:
        if "开票日期" in w[4] or (w[0] > center_x + 50 and w[1] < 80):
            result.invoice_date = d
            break

    # Find 乘车日期 (travel date) - has "开" suffix with time, middle-left area
    # Don't skip by date value (same-day tickets have same invoice & travel date)
    invoice_word = None
    for w, d in all_dates:
        if d == result.invoice_date and ("开票日期" in w[4] or w[0] > 300):
            invoice_word = w
            break

    for w, d in all_dates:
        if w is invoice_word:
            continue  # Skip the invoice date word itself
        # Check if nearby words contain time + "开"
        has_time_nearby = False
        for w2 in words:
            if abs(w2[1] - w[1]) < 12 and time_re.search(w2[4]) and "开" in w2[4]:
                has_time_nearby = True
                tm = time_re.search(w2[4])
                if tm:
                    result.depart_time = tm.group(1)
                break
        if has_time_nearby:
            result.travel_date = d
            break

    # Fallback: any date below header area (not the invoice date word)
    if result.travel_date is None:
        for w, d in all_dates:
            if w is invoice_word:
                continue
            if w[1] > 100:
                result.travel_date = d
                # Also try to find time nearby
                for w2 in words:
                    if abs(w2[1] - w[1]) < 12 and time_re.search(w2[4]):
                        tm = time_re.search(w2[4])
                        if tm:
                            result.depart_time = tm.group(1)
                        break
                break

    # ── Extract amounts ──
    amount_re = re.compile(r"[¥￥]\s*(\d+\.?\d{0,2})")
    for w in words:
        text = w[4]
        m = amount_re.search(text)
        if not m:
            continue
        amt = Decimal(m.group(1))
        if amt <= 0 or amt > 100000:
            continue

        # Check nearby label words
        nearby_texts = []
        for w2 in words:
            if abs(w2[1] - w[1]) < 15 and abs(w2[0] - w[0]) < 200:
                nearby_texts.append(w2[4])
        context = " ".join(nearby_texts)

        if any(kw in context for kw in ["改签费", "退票费", "退票手续费", "改签手续费", "变更费"]):
            result.change_fee_amount = amt
        elif any(kw in context for kw in ["票价", "票 价"]) or "票价" in text:
            result.fare_amount = amt
        elif result.fare_amount is None and "改签" not in context and "退票" not in context:
            result.fare_amount = amt

    # ── Extract other fields ──
    seat_re = re.compile(r"(二等座|一等座|商务座|硬座|硬卧|软卧|无座|特等座)")
    for w in words:
        if seat_re.search(w[4]):
            result.seat_class = w[4]
            break

    name_re = re.compile(r"^([\u4e00-\u9fff]{2,4})$")
    for w in words:
        if name_re.match(w[4]) and w[1] > 200 and w[1] < 280:
            # Check it's near an ID number
            for w2 in words:
                if abs(w2[1] - w[1]) < 12 and re.search(r"\*{4}\d{4}", w2[4]):
                    result.person_name = w[4]
                    break
            if result.person_name:
                break

    # ── Classification ──
    has_refund_keywords = any(
        kw in " ".join(w[4] for w in words)
        for kw in ["退票费", "退票手续费", "改签费", "改签手续费", "变更费", "退改签费用"]
    )
    has_valid_trip = bool(
        result.train_no and result.travel_date
        and result.departure_station and result.arrival_station
        and result.fare_amount
    )

    if has_refund_keywords and not result.fare_amount:
        # Pure refund/change fee ticket
        result.invoice_type = "OTHER"
        result.expense_category = "REFUND_CHANGE_FEE"
        result.should_create_travel_segment = False
        if result.change_fee_amount is None:
            # Try to find any amount as the fee
            for w in words:
                m = amount_re.search(w[4])
                if m:
                    result.change_fee_amount = Decimal(m.group(1))
                    break
    elif has_valid_trip:
        # Valid travel ticket (even if it says 始发改签)
        result.invoice_type = "TRAIN_TICKET"
        result.expense_category = "INTERCITY_TRANSPORT"
        result.should_create_travel_segment = True
    elif result.train_no and not result.travel_date:
        result.should_create_travel_segment = False
        result.needs_review = True
        result.issues.append("MISSING_TRAVEL_DATE")
    else:
        result.should_create_travel_segment = False
        result.needs_review = True

    # Missing station check
    if result.should_create_travel_segment:
        if not result.departure_station or not result.arrival_station:
            result.issues.append("MISSING_STATION")
            result.needs_review = True

    return result