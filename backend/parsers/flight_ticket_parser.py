"""Flight ticket parser – extracts fields from flight e-ticket OCR text."""

import re
from decimal import Decimal
from datetime import date
from parsers.base_parser import BaseParser, ParsedInvoice
from enums import InvoiceType, ExpenseCategory


class FlightTicketParser(BaseParser):
    invoice_type = InvoiceType.FLIGHT_TICKET

    FLIGHT_NO_RE = re.compile(r"[A-Z]{2}\d{3,4}")
    DATE_RE = re.compile(r"(\d{4})[年\-\/](\d{1,2})[月\-\/](\d{1,2})[日]?")
    # Require ¥ prefix OR 元 suffix – prevents matching flight numbers like ZH8585
    AMOUNT_RE = re.compile(r"[¥￥]\s*(\d+\.?\d{0,2})(?:\s*[元]?)|(\d+\.\d{2})\s*元")
    NAME_RE = re.compile(r"(?:乘机人|乘车人|姓名|旅客)[：:]\s*(\S+)")
    CITY_RE = re.compile(r"(?:出发城市|到达城市)[：:]\s*(\S+)")

    def can_parse(self, raw_text: str) -> bool:
        return bool(self.FLIGHT_NO_RE.search(raw_text))

    def parse(self, raw_text: str) -> ParsedInvoice:
        result = ParsedInvoice(
            invoice_type=InvoiceType.FLIGHT_TICKET,
            expense_category=ExpenseCategory.INTERCITY_TRANSPORT,
            parser_name="FlightTicketParser",
            confidence=0.85,
        )

        # Flight number
        m = self.FLIGHT_NO_RE.search(raw_text)
        if m:
            result.transport_no = m.group()

        # Date
        m = self.DATE_RE.search(raw_text)
        if m:
            try:
                result.business_date = date(
                    int(m.group(1)), int(m.group(2)), int(m.group(3))
                )
            except ValueError:
                pass

        # Amount – search 价税合计 first (priority), then 合计金额, then bare 合计
        for label in ["价税合计", "合计金额", "合计"]:
            m = re.search(
                label + r"[^¥￥]*(?:[¥￥]\s*(\d+\.?\d*))",
                raw_text, re.DOTALL
            )
            if m:
                amt = Decimal(m.group(1))
                if 0 < amt < 100000:
                    result.total_amount = amt
                    break
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

        # Person name – multiple fallback strategies
        m = self.NAME_RE.search(raw_text)
        if m:
            result.person_name = m.group(1)
        if not result.person_name:
            # Strategy 1: "备注: 任宁辉" or "备注 任宁辉"
            m = re.search(r"备注[：:]\s*([\u4e00-\u9fff]{2,4})", raw_text)
            if m:
                result.person_name = m.group(1)
        if not result.person_name:
            # Strategy 2: "任宁辉 （1）ZH8585" pattern (name before flight info in remarks)
            m = re.search(r"([\u4e00-\u9fff]{2,4})\s*[（(]\d+[）)]\s*[A-Z]{2}\d+", raw_text)
            if m:
                result.person_name = m.group(1)
        if not result.person_name:
            # Strategy 3: Chinese name after ID number (e.g. "4128282001****2510 任宁辉")
            m = re.search(r"\*{4}\d{4}\s+([\u4e00-\u9fff]{2,4})", raw_text)
            if m:
                result.person_name = m.group(1)

        # Cities
        from_match = re.search(r"出发城市[：:]\s*(\S+)", raw_text)
        to_match = re.search(r"到达城市[：:]\s*(\S+)", raw_text)
        if from_match:
            result.from_city = from_match.group(1)
        if to_match:
            result.to_city = to_match.group(1)

        return result