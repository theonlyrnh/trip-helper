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

PLATFORM_BOOKING_KEYWORDS = [
    "携程", "Trip.com", "飞猪", "美团", "同程", "去哪儿",
    "艺龙", "华住会", "锦江", "订单详情", "酒店订单",
    "已完成", "已在线付", "费用明细", "房型", "酒店位置",
]

PLATFORM_SELLER_KEYWORDS = [
    "携程", "赫程", "上海赫程国际旅行社", "美团", "飞猪",
    "阿里旅行", "同程", "艺龙", "去哪儿", "途牛", "驴妈妈",
    "商旅", "旅行社", "国际旅行社", "旅游服务", "票务代理",
    "经纪代理", "代订",
]

PLATFORM_HOTEL_ITEM_KEYWORDS = [
    "代订住宿费", "代订酒店", "酒店代订", "住宿服务",
    "经纪代理服务*代订住宿费", "旅游服务*代订住宿费",
    "商旅服务*住宿", "代理服务*住宿", "预订服务*住宿",
]

FLIGHT_ORDER_KEYWORDS = [
    "订单详情", "行程已结束", "总额", "订单号", "单程", "往返",
    "航班号", "航空公司", "经济舱", "商务舱", "头等舱",
    "起飞", "到达", "机场", "T1", "T2", "T3",
    "出行信息", "发票报销", "行李额", "选座", "保险",
    "出行保障", "服务包", "返现", "权益",
]

PLATFORM_FLIGHT_ITEM_KEYWORDS = [
    "代订机票费", "代订机票", "机票费", "航空运输服务",
    "客运服务", "经纪代理服务*代订机票费", "旅游服务*代订机票费",
    "商旅服务*机票", "票务代理服务", "机票代理服务",
]

INSURANCE_KEYWORDS = [
    "保险服务", "航空意外险", "机票航空意外险",
    "国内机票航空意外险", "交通意外险", "出行保险",
    "保险费", "保单号", "意外伤害保险",
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
    has_invoice_fields = bool(re.search(r"发票号码|发票代码|购买方名称|纳税人识别号|价税合计|税额", text))

    # ── Refund ticket with flight info in remarks: classify as refund, not travel ──
    has_refund_item = "退票费" in text or "改签费" in text
    has_broker_service = "经纪代理服务" in text or "经纪代理" in text
    if has_refund_item and has_broker_service:
        return ClassificationResult(
            invoice_type=InvoiceType.OTHER,
            expense_category=ExpenseCategory.REFUND_CHANGE_FEE,
            confidence=0.90,
            reason="项目含退票/改签费，归类为退改签费用",
        )

    # ── Order screenshots FIRST (before refund/train checks) ──
    flight_order_hits = sum(1 for kw in FLIGHT_ORDER_KEYWORDS if kw in text)
    if flight_order_hits >= 3 and not has_invoice_fields:
        return ClassificationResult(
            invoice_type="FLIGHT_ORDER_PROOF",
            expense_category=ExpenseCategory.INTERCITY_TRANSPORT,
            confidence=0.85,
            reason=f"匹配机票订单关键词 {flight_order_hits} 个",
        )

    platform_hits = sum(1 for kw in PLATFORM_BOOKING_KEYWORDS if kw in text)
    if platform_hits >= 2 and not has_invoice_fields:
        return ClassificationResult(
            invoice_type="HOTEL_BOOKING_PROOF",
            expense_category=ExpenseCategory.LODGING,
            confidence=0.85,
            reason=f"匹配平台订单关键词 {platform_hits} 个，无正式发票字段",
        )

    # ── Insurance invoice ──
    insurance_hits = sum(1 for kw in INSURANCE_KEYWORDS if kw in text)
    if insurance_hits >= 1 and has_invoice_fields:
        return ClassificationResult(
            invoice_type="TRAVEL_INSURANCE_INVOICE",
            expense_category="TRAVEL_INSURANCE",
            confidence=0.85,
            reason=f"匹配保险关键词 {insurance_hits} 个",
        )

    # ── Refund/change fee – only if NOT a valid travel ticket ──
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

    # Check hotel BEFORE train (住宿服务 is a stronger signal than ambiguous numbers)
    hotel_hits = sum(1 for kw in HOTEL_KEYWORDS if kw in text)
    # Strong hotel indicator: "住宿服务" alone is enough
    has_strong_hotel = "住宿服务" in text or "住宿费" in text
    if hotel_hits >= 2 or has_strong_hotel:
        conf = 0.90 if has_strong_hotel else min(0.95, 0.80 + hotel_hits * 0.05)
        return ClassificationResult(
            invoice_type=InvoiceType.HOTEL_INVOICE,
            expense_category=ExpenseCategory.LODGING,
            confidence=conf,
            reason=f"匹配酒店关键词 {hotel_hits} 个" + ("，含强特征'住宿服务'" if has_strong_hotel else ""),
        )

    # Check train – must have strong train signals
    train_hits = sum(1 for kw in TRAIN_KEYWORDS if kw in text)
    has_train_no = bool(TRAIN_NO_PATTERN.search(text))
    if train_hits >= 2 and has_train_no:
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