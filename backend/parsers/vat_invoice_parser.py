"""VAT invoice parser – extracts fields from general VAT invoice OCR text."""

import re
from decimal import Decimal
from datetime import date
from parsers.base_parser import BaseParser, ParsedInvoice
from enums import InvoiceType, ExpenseCategory


class VATInvoiceParser(BaseParser):
    invoice_type = InvoiceType.VAT_INVOICE

    DATE_RE = re.compile(r"(\d{4})[年\-\/](\d{1,2})[月\-\/](\d{1,2})[日]?")
    # Require ¥ prefix OR 元 suffix – prevents matching invoice codes as amounts
    AMOUNT_RE = re.compile(r"[¥￥]\s*(\d+\.?\d{0,2})(?:\s*[元]?)|(\d+\.\d{2})\s*元")

    # Service name → expense category mapping
    SERVICE_CATEGORY_MAP = {
        "住宿": ExpenseCategory.LODGING,
        "餐饮": ExpenseCategory.MEAL,
        "客运": ExpenseCategory.LOCAL_TRANSPORT,
        "运输": ExpenseCategory.INTERCITY_TRANSPORT,
        "交通": ExpenseCategory.LOCAL_TRANSPORT,
    }

    def can_parse(self, raw_text: str) -> bool:
        # VAT invoices typically have invoice code/number and tax info
        has_code = bool(re.search(r"发票代码", raw_text))
        has_tax = bool(re.search(r"(?:税额|税率)", raw_text))
        return has_code or has_tax

    def parse(self, raw_text: str) -> ParsedInvoice:
        result = ParsedInvoice(
            invoice_type=InvoiceType.VAT_INVOICE,
            expense_category=ExpenseCategory.OTHER,
            parser_name="VATInvoiceParser",
            confidence=0.80,
        )

        # Invoice code/number
        code_match = re.search(r"发票代码[：:]\s*(\S+)", raw_text)
        num_match = re.search(r"发票号码[：:]\s*(\S+)", raw_text)
        if code_match:
            result.invoice_code = code_match.group(1)
        if num_match:
            result.invoice_number = num_match.group(1)

        # Date
        m = self.DATE_RE.search(raw_text)
        if m:
            try:
                result.invoice_date = date(
                    int(m.group(1)), int(m.group(2)), int(m.group(3))
                )
            except ValueError:
                pass

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

        # Tax amount
        tax_match = re.search(r"税额[：:]\s*[¥￥]?\s*(\d+\.?\d*)", raw_text)
        if tax_match:
            result.tax_amount = Decimal(tax_match.group(1))

        # Buyer
        buyer_match = re.search(r"(?:购买方名称|名称)[：:]\s*(\S+)", raw_text)
        if buyer_match:
            result.buyer_name = buyer_match.group(1)

        # Seller
        seller_match = re.search(r"(?:销售方名称|销售方)[：:]\s*(\S+)", raw_text)
        if seller_match:
            result.seller_name = seller_match.group(1)

        # Service/item name → determine expense category
        service_match = re.search(r"(?:项目名称|货物或应税劳务|服务名称)[：:]?\s*[\*]?(\S+)", raw_text)
        if service_match:
            service = service_match.group(1)
            result.service_name = service
            for keyword, category in self.SERVICE_CATEGORY_MAP.items():
                if keyword in service:
                    result.expense_category = category
                    break

        return result