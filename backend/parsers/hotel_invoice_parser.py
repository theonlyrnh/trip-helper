"""Hotel invoice parser – extracts fields from hotel invoice OCR text."""

import re
from decimal import Decimal
from datetime import date
from parsers.base_parser import BaseParser, ParsedInvoice
from enums import InvoiceType, ExpenseCategory


class HotelInvoiceParser(BaseParser):
    invoice_type = InvoiceType.HOTEL_INVOICE

    DATE_RE = re.compile(r"(\d{4})[年\-\/](\d{1,2})[月\-\/](\d{1,2})[日]?")
    # Require ¥ prefix OR 元 suffix – prevents matching invoice codes as amounts
    AMOUNT_RE = re.compile(r"[¥￥]\s*(\d+\.?\d{0,2})(?:\s*[元]?)|(\d+\.\d{2})\s*元")

    def can_parse(self, raw_text: str) -> bool:
        keywords = ["住宿", "酒店", "宾馆", "客房", "房费", "入住", "离店"]
        return any(kw in raw_text for kw in keywords)

    def parse(self, raw_text: str) -> ParsedInvoice:
        result = ParsedInvoice(
            invoice_type=InvoiceType.HOTEL_INVOICE,
            expense_category=ExpenseCategory.LODGING,
            parser_name="HotelInvoiceParser",
            confidence=0.85,
        )

        # Hotel name
        name_match = re.search(r"(?:酒店名称|名称)[：:]\s*(\S+)", raw_text)
        if name_match:
            result.hotel_name = name_match.group(1)
        else:
            # Try to find seller name as hotel name
            seller_match = re.search(r"(?:销售方|销货方)[：:]\s*(\S+)", raw_text)
            if seller_match:
                result.seller_name = seller_match.group(1)
                result.hotel_name = seller_match.group(1)

        # Invoice number
        inv_match = re.search(r"(?:发票号码|发票代码)[：:]\s*(\S+)", raw_text)
        if inv_match:
            result.invoice_number = inv_match.group(1)

        # Dates
        dates = self.DATE_RE.findall(raw_text)
        date_objs = []
        for d in dates:
            try:
                date_objs.append(date(int(d[0]), int(d[1]), int(d[2])))
            except ValueError:
                pass

        if date_objs:
            result.invoice_date = date_objs[0] if date_objs else None
            if len(date_objs) >= 2:
                result.checkin_date = min(date_objs)
                result.checkout_date = max(date_objs)
                delta = (result.checkout_date - result.checkin_date).days
                result.nights = max(delta, 1)

        # Amount – prefer 价税合计, fallback to ¥/元 patterns
        total_match = re.search(r"(?:价税合计|合计金额|合计)[^¥]*(?:[¥￥]\s*(\d+\.?\d*))", raw_text, re.DOTALL)
        if total_match:
            amt = Decimal(total_match.group(1))
            if 0 < amt < 100000:
                result.total_amount = amt
        if result.total_amount is None:
            amounts = self.AMOUNT_RE.findall(raw_text)
            if amounts:
                nums = []
                for t in amounts:
                    for val in t:
                        if val:
                            try:
                                n = Decimal(val)
                                if 0 < n < 100000:
                                    nums.append(n)
                            except: pass
                if nums:
                    result.total_amount = max(nums)

        # Buyer
        buyer_match = re.search(r"(?:购买方|购货方)[：:]\s*(\S+)", raw_text)
        if buyer_match:
            result.buyer_name = buyer_match.group(1)

        return result