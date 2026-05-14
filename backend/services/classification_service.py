"""Invoice classification service – rule-based classification of OCR text."""

import re
from dataclasses import dataclass
from enums import InvoiceType, ExpenseCategory


@dataclass
class ClassificationResult:
    invoice_type: str
    expense_category: str
    confidence: float
    reason: str = ""


# ── Strong keyword rules ──────────────────────────────────────────

TRAIN_KEYWORDS = [
    "电子客票", "铁路", "中国铁路", "乘车日期", "车次", "检票口",
    "出发站", "到达站", "二等座", "一等座", "商务座", "硬座", "硬卧",
    "软卧", "无座", "高铁", "动车", "火车站",
]

FLIGHT_KEYWORDS = [
    "电子客票行程单", "航空运输电子客票", "航班号", "客票号",
    "乘机人", "起飞", "到达", "机场建设费", "燃油附加费",
    "民航发展基金", "登机", "值机",
]

HOTEL_KEYWORDS = [
    "住宿服务", "酒店", "宾馆", "客房", "房费", "入住", "离店",
    "住宿费", "民宿", "旅馆",
]

TAXI_KEYWORDS = [
    "出租汽车", "客运服务", "行程单", "滴滴", "高德打车",
    "T3出行", "曹操出行", "起点", "终点", "上车时间", "下车时间",
    "网约车", "出租车",
]

MEAL_KEYWORDS = [
    "餐饮服务", "餐费", "饭店", "餐厅", "食品", "饮品", "餐饮",
]

REFUND_CHANGE_KEYWORDS = [
    "退票费", "退票手续费", "改签费", "改签手续费",
    "变更费", "退改签费用", "退票", "改签",
]

# ── Regex patterns ─────────────────────────────────────────────────

TRAIN_NO_PATTERN = re.compile(r"\b[GDCZTK]\d{1,4}\b")
FLIGHT_NO_PATTERN = re.compile(r"\b[A-Z]{2}\d{3,4}\b")


def normalize_text(text: str) -> str:
    """Normalize OCR text: strip whitespace, normalize spaces."""
    return " ".join(text.split())


def classify_invoice(raw_text: str) -> ClassificationResult:
    """
    Classify an invoice by its OCR text using rule-based matching.

    Priority: strong keywords → field patterns → unknown.
    """
    text = normalize_text(raw_text)

    # ── Strong keyword matching ──
    result = _classify_by_keywords(text)
    if result.confidence >= 0.85:
        return result

    # ── Pattern matching ──
    result = _classify_by_patterns(text)
    if result.confidence >= 0.75:
        return result

    # ── Fallback ──
    return ClassificationResult(
        invoice_type=InvoiceType.UNKNOWN,
        expense_category=ExpenseCategory.OTHER,
        confidence=0.3,
        reason="无法根据规则判断票据类型",
    )


def _classify_by_keywords(text: str) -> ClassificationResult:
    """Match against strong keyword lists."""
    # Check refund/change fee first – only if NOT a valid travel ticket
    refund_hits = sum(1 for kw in REFUND_CHANGE_KEYWORDS if kw in text)
    has_train_no = bool(TRAIN_NO_PATTERN.search(text))
    has_flight_no = bool(FLIGHT_NO_PATTERN.search(text))
    has_station = bool(re.search(r"[\u4e00-\u9fff]{2,4}站", text))

    if refund_hits >= 1 and not (has_train_no and has_station) and not has_flight_no:
        return ClassificationResult(
            invoice_type=InvoiceType.OTHER,
            expense_category=ExpenseCategory.REFUND_CHANGE_FEE,
            confidence=0.85,
            reason=f"匹配退票/改签关键词 {refund_hits} 个，且非有效行程票据",
        )

    # Check train
    train_hits = sum(1 for kw in TRAIN_KEYWORDS if kw in text)
    if train_hits >= 2:
        return ClassificationResult(
            invoice_type=InvoiceType.TRAIN_TICKET,
            expense_category=ExpenseCategory.INTERCITY_TRANSPORT,
            confidence=min(0.95, 0.7 + train_hits * 0.05),
            reason=f"匹配高铁/火车关键词 {train_hits} 个",
        )

    # Check flight
    flight_hits = sum(1 for kw in FLIGHT_KEYWORDS if kw in text)
    if flight_hits >= 2:
        return ClassificationResult(
            invoice_type=InvoiceType.FLIGHT_TICKET,
            expense_category=ExpenseCategory.INTERCITY_TRANSPORT,
            confidence=min(0.95, 0.7 + flight_hits * 0.05),
            reason=f"匹配机票关键词 {flight_hits} 个",
        )

    # Check hotel
    hotel_hits = sum(1 for kw in HOTEL_KEYWORDS if kw in text)
    if hotel_hits >= 2:
        return ClassificationResult(
            invoice_type=InvoiceType.HOTEL_INVOICE,
            expense_category=ExpenseCategory.LODGING,
            confidence=min(0.95, 0.7 + hotel_hits * 0.05),
            reason=f"匹配酒店关键词 {hotel_hits} 个",
        )

    # Check taxi
    taxi_hits = sum(1 for kw in TAXI_KEYWORDS if kw in text)
    if taxi_hits >= 2:
        return ClassificationResult(
            invoice_type=InvoiceType.TAXI_INVOICE,
            expense_category=ExpenseCategory.LOCAL_TRANSPORT,
            confidence=min(0.95, 0.7 + taxi_hits * 0.05),
            reason=f"匹配出租车/网约车关键词 {taxi_hits} 个",
        )

    # Check meal
    meal_hits = sum(1 for kw in MEAL_KEYWORDS if kw in text)
    if meal_hits >= 2:
        return ClassificationResult(
            invoice_type=InvoiceType.MEAL_INVOICE,
            expense_category=ExpenseCategory.MEAL,
            confidence=min(0.95, 0.7 + meal_hits * 0.05),
            reason=f"匹配餐饮关键词 {meal_hits} 个",
        )

    return ClassificationResult(
        invoice_type=InvoiceType.UNKNOWN,
        expense_category=ExpenseCategory.OTHER,
        confidence=0.0,
        reason="无关键词匹配",
    )


def _classify_by_patterns(text: str) -> ClassificationResult:
    """Match against regex patterns."""
    # Train number pattern
    if TRAIN_NO_PATTERN.search(text):
        return ClassificationResult(
            invoice_type=InvoiceType.TRAIN_TICKET,
            expense_category=ExpenseCategory.INTERCITY_TRANSPORT,
            confidence=0.80,
            reason="匹配车次号正则",
        )

    # Flight number pattern
    if FLIGHT_NO_PATTERN.search(text):
        return ClassificationResult(
            invoice_type=InvoiceType.FLIGHT_TICKET,
            expense_category=ExpenseCategory.INTERCITY_TRANSPORT,
            confidence=0.80,
            reason="匹配航班号正则",
        )

    return ClassificationResult(
        invoice_type=InvoiceType.UNKNOWN,
        expense_category=ExpenseCategory.OTHER,
        confidence=0.0,
        reason="无正则匹配",
    )