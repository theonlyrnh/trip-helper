"""Extraction service – classifies OCR text and runs the appropriate parser."""

import fitz
from sqlalchemy.orm import Session

from models.ocr_result import OCRResult
from models.document import Document
from models.invoice import Invoice
from enums import InvoiceType, ExpenseCategory, ReviewStatus, ReimbursementStatus
from services.classification_service import classify_invoice
from parsers.train_ticket_parser import TrainTicketParser
from parsers.flight_ticket_parser import FlightTicketParser
from parsers.hotel_invoice_parser import HotelInvoiceParser
from parsers.vat_invoice_parser import VATInvoiceParser
from parsers.train_ticket_coord_parser import parse_train_ticket_words, TrainTicketResult


# Parser registry – ordered by specificity
PARSERS = [
    TrainTicketParser(),
    FlightTicketParser(),
    HotelInvoiceParser(),
    VATInvoiceParser(),
]


class ExtractionService:

    @staticmethod
    def extract_from_ocr_result(
        db: Session, ocr_result: OCRResult
    ) -> Invoice | None:
        """
        Classify OCR text and run the matching parser to produce an Invoice.

        For PyMuPDF results on train tickets, uses coordinate-based parsing.
        """
        raw_text = ocr_result.raw_text
        if not raw_text or not raw_text.strip():
            return None

        # Clean LOC tokens from PaddleOCR output
        import re as _re
        raw_text = _re.sub(r"<\|LOC_\d+\|>", "", raw_text)

        # ── Try coordinate-based parsing for PyMuPDF train tickets ──
        if ocr_result.provider == "pymupdf" and ocr_result.document_id:
            doc = db.query(Document).filter(Document.id == ocr_result.document_id).first()
            if doc and doc.file_path.lower().endswith(".pdf"):
                try:
                    pdf_doc = fitz.open(doc.file_path)
                    words = pdf_doc[0].get_text("words")
                    page_w = pdf_doc[0].rect.width
                    pdf_doc.close()

                    coord_result = parse_train_ticket_words(words, page_w)
                    if coord_result.train_no:
                        return ExtractionService._create_invoice_from_coord(
                            db, ocr_result, coord_result
                        )
                except Exception:
                    pass  # Fall through to text-based parsing

        # Step 1: Classify
        classification = classify_invoice(raw_text)

        # Handle platform booking screenshot
        if classification.invoice_type == "HOTEL_BOOKING_PROOF":
            return ExtractionService._create_booking_proof(db, ocr_result, raw_text, classification)

        # Handle flight order screenshot
        if classification.invoice_type == "FLIGHT_ORDER_PROOF":
            return ExtractionService._create_flight_order_proof(db, ocr_result, raw_text, classification)

        # Handle travel insurance invoice
        if classification.invoice_type == "TRAVEL_INSURANCE_INVOICE":
            return ExtractionService._create_insurance_invoice(db, ocr_result, raw_text, classification)

        # Handle general invoice (non-travel) – skip travel parsers
        if classification.invoice_type == "GENERAL_INVOICE":
            return ExtractionService._create_general_invoice(db, ocr_result, raw_text, classification)

        # Handle refund ticket – extract flight info from remarks for reference only
        if classification.expense_category == "REFUND_CHANGE_FEE":
            return ExtractionService._create_refund_ticket(db, ocr_result, raw_text, classification)

        # Handle platform hotel invoice (seller is platform agent)
        is_platform_hotel = ExtractionService._is_platform_hotel_invoice(raw_text, classification)

        # Step 2: Find matching parser
        parser = None
        for p in PARSERS:
            if p.invoice_type == classification.invoice_type:
                parser = p
                break

        # If no exact match, try can_parse on each
        if parser is None:
            for p in PARSERS:
                if p.can_parse(raw_text):
                    parser = p
                    break

        # Step 3: Parse
        if parser is not None:
            parsed = parser.parse(raw_text)
        else:
            # Use classification result as-is
            from parsers.base_parser import ParsedInvoice
            parsed = ParsedInvoice(
                invoice_type=classification.invoice_type,
                expense_category=classification.expense_category,
                confidence=classification.confidence,
                parser_name="ClassificationOnly",
            )

        # Step 4: Create Invoice record
        invoice = Invoice(
            trip_id=ocr_result.trip_id,
            document_id=ocr_result.document_id,
            ocr_result_id=ocr_result.id,
            invoice_type=parsed.invoice_type,
            expense_category=parsed.expense_category,
            invoice_code=parsed.invoice_code,
            invoice_number=parsed.invoice_number,
            invoice_date=parsed.invoice_date,
            seller_name=parsed.seller_name,
            buyer_name=parsed.buyer_name,
            total_amount=parsed.total_amount,
            tax_amount=parsed.tax_amount,
            business_date=parsed.business_date,
            person_name=parsed.person_name,
            from_city=parsed.from_city,
            to_city=parsed.to_city,
            from_place=parsed.from_place,
            to_place=parsed.to_place,
            transport_no=parsed.transport_no,
            seat_class=parsed.seat_class,
            depart_time_str=parsed.depart_time,
            hotel_name=parsed.hotel_name,
            checkin_date=parsed.checkin_date,
            checkout_date=parsed.checkout_date,
            nights=parsed.nights,
            confidence=parsed.confidence,
            parser_name=parsed.parser_name,
            review_status=ReviewStatus.NEEDS_REVIEW,
            reimbursement_status=ReimbursementStatus.THIS_TRIP,
        )
        db.add(invoice)
        db.commit()
        db.refresh(invoice)
        return invoice

    @staticmethod
    def _create_invoice_from_coord(
        db: Session, ocr_result: OCRResult, cr: TrainTicketResult
    ) -> Invoice:
        """Create an Invoice from coordinate-parsed train ticket result."""
        # Determine total_amount: fare takes priority, fallback to change fee
        total = cr.fare_amount or cr.change_fee_amount

        # Build business_date with time if available
        business_dt = cr.travel_date

        invoice = Invoice(
            trip_id=ocr_result.trip_id,
            document_id=ocr_result.document_id,
            ocr_result_id=ocr_result.id,
            invoice_type=cr.invoice_type,
            expense_category=cr.expense_category,
            invoice_date=cr.invoice_date,
            total_amount=total,
            business_date=business_dt,
            depart_time_str=cr.depart_time,
            person_name=cr.person_name,
            from_place=cr.departure_station,
            to_place=cr.arrival_station,
            transport_no=cr.train_no,
            seat_class=cr.seat_class,
            buyer_name=cr.buyer_name,
            confidence=cr.confidence,
            parser_name="TrainTicketCoordParser",
            review_status=ReviewStatus.NEEDS_REVIEW if cr.needs_review else ReviewStatus.AUTO_CONFIRMED,
            reimbursement_status=ReimbursementStatus.THIS_TRIP,
        )
        db.add(invoice)
        db.commit()
        db.refresh(invoice)
        return invoice

    @staticmethod
    def _is_platform_hotel_invoice(raw_text: str, classification) -> bool:
        """Check if this is a platform-booked hotel invoice."""
        from services.classification_service import PLATFORM_SELLER_KEYWORDS, PLATFORM_HOTEL_ITEM_KEYWORDS
        seller_hit = any(kw in raw_text for kw in PLATFORM_SELLER_KEYWORDS)
        item_hit = any(kw in raw_text for kw in PLATFORM_HOTEL_ITEM_KEYWORDS)
        return seller_hit and item_hit

    @staticmethod
    def _create_booking_proof(db: Session, ocr_result: OCRResult, raw_text: str, classification) -> Invoice:
        """Create an invoice record for a platform booking screenshot."""
        import re as _re
        from decimal import Decimal as _Decimal
        from datetime import date as _date

        amount = None
        am = _re.search(r"[¥￥已在线付]\s*(\d+\.?\d{0,2})", raw_text)
        if am:
            try: amount = _Decimal(am.group(1))
            except: pass

        checkin, checkout, nights = None, None, None
        date_matches = _re.findall(r"(\d{4})[年\-/\.](\d{1,2})[月\-/\.](\d{1,2})[日]?", raw_text)
        dates = []
        for dm in date_matches:
            try: dates.append(_date(int(dm[0]), int(dm[1]), int(dm[2])))
            except: pass
        if len(dates) >= 2:
            checkin = min(dates)
            checkout = max(dates)
            nights = (checkout - checkin).days

        hotel = None
        hm = _re.search(r"酒店[：:]\s*(\S+)", raw_text)
        if not hm:
            hm = _re.search(r"([\u4e00-\u9fff]{3,20}(?:酒店|宾馆|民宿|旅馆))", raw_text)
        if hm: hotel = hm.group(1)

        platform = None
        for p in ["携程", "飞猪", "美团", "同程", "去哪儿", "艺龙"]:
            if p in raw_text: platform = p; break

        order_no = None
        om = _re.search(r"订单号[：:]\s*(\d+)", raw_text)
        if om: order_no = om.group(1)

        invoice = Invoice(
            trip_id=ocr_result.trip_id, document_id=ocr_result.document_id,
            ocr_result_id=ocr_result.id,
            invoice_type="HOTEL_BOOKING_PROOF", expense_category=ExpenseCategory.LODGING,
            total_amount=amount, hotel_name=hotel, actual_hotel_name=hotel,
            checkin_date=checkin, checkout_date=checkout, nights=nights,
            platform_name=platform, booking_order_no=order_no,
            document_role="BOOKING_SCREENSHOT", include_in_summary=False,
            confidence=classification.confidence, parser_name="PlatformBookingDetector",
            review_status=ReviewStatus.AUTO_CONFIRMED,
            reimbursement_status=ReimbursementStatus.THIS_TRIP,
        )
        db.add(invoice)
        db.commit()
        db.refresh(invoice)
        return invoice

    @staticmethod
    def _create_flight_order_proof(db: Session, ocr_result: OCRResult, raw_text: str, classification) -> Invoice:
        """Create an invoice record for a flight order screenshot."""
        import re as _re
        from decimal import Decimal as _Decimal
        from datetime import date as _date

        # Order total – try multiple patterns
        order_total = None
        for pat in [
            r"总额[：:]?\s*[¥￥]\s*(\d+\.?\d{0,2})",
            r"总额[：:]?\s*[¥￥]?\s*(\d+\.?\d{0,2})",
            r"[¥￥]\s*(\d{4}\.?\d{0,2})",
        ]:
            am = _re.search(pat, raw_text)
            if am:
                try:
                    val = _Decimal(am.group(1))
                    if 10 < val < 100000:
                        order_total = val; break
                except: pass

        # Flight number
        flight_no = None
        fn = _re.search(r"([A-Z]{2}\d{3,4})", raw_text)
        if fn: flight_no = fn.group(1)

        # Dates and times – prefer those near flight info (after "单程" or near airport)
        flight_date = None
        depart_time = None
        arrive_time = None
        
        # Find the flight info section (after "单程" or "南京-太原")
        flight_section = raw_text
        section_markers = ["单程", "南京-太原", "太原-南京"]
        for marker in section_markers:
            idx = raw_text.find(marker)
            if idx > 0:
                flight_section = raw_text[idx:]
                break
        
        # Date: find "X月X日" in flight section
        dm = _re.search(r"(\d{1,2})月(\d{1,2})日", flight_section)
        if not dm:
            dm = _re.search(r"(\d{1,2})月(\d{1,2})日", raw_text)
        if dm:
            try:
                year = 2026
                flight_date = _date(year, int(dm.group(1)), int(dm.group(2)))
            except: pass
        
        # Times: find in flight section (near airport names)
        tm = _re.findall(r"(\d{1,2}:\d{2})", flight_section)
        if len(tm) >= 2:
            depart_time = tm[0]
            arrive_time = tm[1]
        elif len(tm) == 1:
            depart_time = tm[0]
        else:
            # Fallback to full text
            tm = _re.findall(r"(\d{1,2}:\d{2})", raw_text)
            if len(tm) >= 2:
                depart_time = tm[0]
                arrive_time = tm[1]

        # Airports
        depart_airport = None
        arrive_airport = None
        airports = _re.findall(r"([\u4e00-\u9fff]{2,6}(?:国际|国内)?机场\s*T?\d?)", raw_text)
        if len(airports) >= 2:
            depart_airport = airports[0].strip()
            arrive_airport = airports[1].strip()

        # Cities
        from_city = None
        to_city = None
        cities = _re.findall(r"([\u4e00-\u9fff]{2,4})[\-—→]([\u4e00-\u9fff]{2,4})", raw_text)
        if cities:
            from_city = cities[0][0]
            to_city = cities[0][1]

        # Airline
        airline = None
        al = _re.search(r"(深航|国航|东航|南航|海航|厦航|川航|春秋|吉祥|首都航)", raw_text)
        if al: airline = al.group(1)

        # Cabin
        cabin = None
        cb = _re.search(r"(经济舱|商务舱|头等舱|超级经济舱)", raw_text)
        if cb: cabin = cb.group(1)

        # Order number
        order_no = None
        om = _re.search(r"订单号[：:]\s*(\d+)", raw_text)
        if om: order_no = om.group(1)

        # Insurance
        insurance = None
        im = _re.search(r"保险[：:]?\s*[¥￥]?\s*(\d+\.?\d{0,2})", raw_text)
        if im:
            try: insurance = _Decimal(im.group(1))
            except: pass

        # Platform
        platform = None
        for p in ["飞猪", "携程", "同程", "去哪儿", "航旅纵横", "美团"]:
            if p in raw_text: platform = p; break

        invoice = Invoice(
            trip_id=ocr_result.trip_id, document_id=ocr_result.document_id,
            ocr_result_id=ocr_result.id,
            invoice_type="FLIGHT_ORDER_PROOF", expense_category=ExpenseCategory.INTERCITY_TRANSPORT,
            order_total_amount=order_total, insurance_amount=insurance,
            flight_date=flight_date, depart_time_str=depart_time,
            depart_airport=depart_airport, arrive_airport=arrive_airport,
            from_city=from_city, to_city=to_city,
            transport_no=flight_no, airline_name=airline, cabin_class=cabin,
            booking_order_no=order_no, platform_name=platform,
            document_role="ORDER_SCREENSHOT", include_in_summary=False,
            confidence=classification.confidence, parser_name="FlightOrderDetector",
            review_status=ReviewStatus.AUTO_CONFIRMED,
            reimbursement_status=ReimbursementStatus.THIS_TRIP,
        )
        db.add(invoice)
        db.commit()
        db.refresh(invoice)
        return invoice

    @staticmethod
    def _create_insurance_invoice(db: Session, ocr_result: OCRResult, raw_text: str, classification) -> Invoice:
        """Create an invoice record for a travel insurance invoice."""
        import re as _re
        from decimal import Decimal as _Decimal
        from datetime import date as _date

        # Amount – for insurance, the largest ¥ amount is usually the total (价税合计)
        amount = None
        amount_without_tax = None
        tax_amount = None
        
        # Find all ¥ amounts
        all_amounts = _re.findall(r"[¥￥]\s*(\d+\.\d{2})", raw_text)
        nums = []
        for a in all_amounts:
            try:
                n = _Decimal(a)
                if 1 < n < 100000:
                    nums.append(n)
            except: pass
        
        if len(nums) >= 3:
            # Insurance invoice: 金额, 税额, 价税合计 → largest is total
            amount = max(nums)
            nums.remove(amount)
            if len(nums) >= 2:
                amount_without_tax = max(nums)
                tax_amount = min(nums)
        elif len(nums) == 2:
            amount = max(nums)
            tax_amount = min(nums)
            amount_without_tax = amount - tax_amount
        elif len(nums) == 1:
            amount = nums[0]

        # Policy number
        policy_no = None
        pm = _re.search(r"保单号[：:]\s*(\S+)", raw_text)
        if pm: policy_no = pm.group(1)

        # Invoice number
        inv_no = None
        im = _re.search(r"发票号码[：:]\s*(\S+)", raw_text)
        if im: inv_no = im.group(1)

        # Dates
        inv_date = None
        dm = _re.search(r"(\d{4})[年\-/\.](\d{1,2})[月\-/\.](\d{1,2})[日]?", raw_text)
        if dm:
            try: inv_date = _date(int(dm.group(1)), int(dm.group(2)), int(dm.group(3)))
            except: pass

        # Seller / Buyer
        seller = None
        sm = _re.search(r"销售方[：:]\s*(\S+)", raw_text)
        if sm: seller = sm.group(1)
        buyer = None
        bm = _re.search(r"购买方[：:]\s*(\S+)", raw_text)
        if bm: buyer = bm.group(1)

        invoice = Invoice(
            trip_id=ocr_result.trip_id, document_id=ocr_result.document_id,
            ocr_result_id=ocr_result.id,
            invoice_type="TRAVEL_INSURANCE_INVOICE",
            expense_category="TRAVEL_INSURANCE",
            total_amount=amount, amount_without_tax=amount_without_tax,
            tax_amount=tax_amount, invoice_date=inv_date,
            invoice_number=inv_no, seller_name=seller, buyer_name=buyer,
            booking_order_no=policy_no,
            document_role="OFFICIAL_INVOICE", include_in_summary=True,
            confidence=classification.confidence, parser_name="InsuranceDetector",
            review_status=ReviewStatus.AUTO_CONFIRMED,
            reimbursement_status=ReimbursementStatus.THIS_TRIP,
        )
        db.add(invoice)
        db.commit()
        db.refresh(invoice)
        return invoice

    @staticmethod
    def _create_general_invoice(db: Session, ocr_result: OCRResult, raw_text: str, classification) -> Invoice:
        """Create a general (non-travel) invoice with proper amount calculation."""
        import re as _re
        from decimal import Decimal as _Decimal
        from datetime import date as _date

        # Find all ¥ amounts
        all_amounts = _re.findall(r"[¥￥]\s*(\d+\.\d{2})", raw_text)
        nums = []
        for a in all_amounts:
            try:
                n = _Decimal(a)
                if 1 < n < 100000:
                    nums.append(n)
            except: pass

        # Largest is usually 价税合计, smallest is 税额, middle is 金额
        amount = None
        amount_without_tax = None
        tax_amount = None
        if len(nums) >= 3:
            amount = max(nums)
            tax_amount = min(nums)
            nums.remove(amount)
            nums.remove(tax_amount)
            amount_without_tax = nums[0] if nums else None
        elif len(nums) == 2:
            amount = max(nums)
            tax_amount = min(nums)
            amount_without_tax = amount - tax_amount
        elif len(nums) == 1:
            amount = nums[0]

        # Also try explicit 价税合计
        total_m = _re.search(r"[（(]小写[）)]\s*[¥￥]\s*(\d+\.?\d{0,2})", raw_text)
        if total_m:
            try:
                val = _Decimal(total_m.group(1))
                if 1 < val < 100000:
                    amount = val
            except: pass

        # Invoice number
        inv_no = None
        im = _re.search(r"发票号码[：:]\s*(\S+)", raw_text)
        if im: inv_no = im.group(1)

        # Date
        inv_date = None
        dm = _re.search(r"(\d{4})[年\-/\.](\d{1,2})[月\-/\.](\d{1,2})[日]?", raw_text)
        if dm:
            try: inv_date = _date(int(dm.group(1)), int(dm.group(2)), int(dm.group(3)))
            except: pass

        # Seller / Buyer
        seller = None
        sm = _re.search(r"名称[：:]\s*(\S{2,30}(?:公司|有限公司|店|餐厅|酒店))", raw_text)
        if sm: seller = sm.group(1)
        buyer = None
        bm = _re.search(r"购买方[：:]\s*名称[：:]\s*(\S+)", raw_text)
        if bm: buyer = bm.group(1)

        # Item name
        item = None
        im2 = _re.search(r"项目名称[：:]\s*(\S+)", raw_text)
        if im2: item = im2.group(1)

        invoice = Invoice(
            trip_id=ocr_result.trip_id, document_id=ocr_result.document_id,
            ocr_result_id=ocr_result.id,
            invoice_type="GENERAL_INVOICE", expense_category=classification.expense_category,
            total_amount=amount, amount_without_tax=amount_without_tax,
            tax_amount=tax_amount, invoice_date=inv_date,
            invoice_number=inv_no, seller_name=seller, buyer_name=buyer,
            item_name=item,
            document_role="OFFICIAL_INVOICE", include_in_summary=True,
            confidence=classification.confidence, parser_name="GeneralInvoiceParser",
            review_status=ReviewStatus.AUTO_CONFIRMED,
            reimbursement_status=ReimbursementStatus.THIS_TRIP,
        )
        db.add(invoice)
        db.commit()
        db.refresh(invoice)
        return invoice

    @staticmethod
    def _create_refund_ticket(db: Session, ocr_result: OCRResult, raw_text: str, classification) -> Invoice:
        """Create a refund ticket – extract flight info from remarks for reference only."""
        import re as _re
        from decimal import Decimal as _Decimal
        from datetime import date as _date

        # Amount from 价税合计
        amount = None
        for pat in [r"价税合计[：:]?\s*[¥￥]?\s*(\d+\.?\d{0,2})", r"[¥￥]\s*(\d+\.\d{2})"]:
            m = _re.search(pat, raw_text)
            if m:
                try:
                    val = _Decimal(m.group(1))
                    if 1 < val < 100000:
                        amount = val; break
                except: pass

        # Extract flight info from remarks: "2026/05/12 太原-南京 MU2686 经济舱R"
        flight_date = None
        from_city = None
        to_city = None
        flight_no = None
        cabin = None

        remark_match = _re.search(r"备注[：:]?\s*(.+)", raw_text)
        remark_text = remark_match.group(1) if remark_match else raw_text

        # Date: 2026/05/12 or 2026-05-12
        dm = _re.search(r"(\d{4})[/\-](\d{1,2})[/\-](\d{1,2})", remark_text)
        if dm:
            try: flight_date = _date(int(dm.group(1)), int(dm.group(2)), int(dm.group(3)))
            except: pass

        # Route: 太原-南京
        rm = _re.search(r"([\u4e00-\u9fff]{2,4})[\-—→]([\u4e00-\u9fff]{2,4})", remark_text)
        if rm:
            from_city = rm.group(1)
            to_city = rm.group(2)

        # Flight number: MU2686
        fm = _re.search(r"([A-Z]{2}\d{3,4})", remark_text)
        if fm: flight_no = fm.group(1)

        # Cabin: 经济舱R
        cm = _re.search(r"(经济舱|商务舱|头等舱)\s*[A-Z]?", remark_text)
        if cm: cabin = cm.group(1)

        invoice = Invoice(
            trip_id=ocr_result.trip_id, document_id=ocr_result.document_id,
            ocr_result_id=ocr_result.id,
            invoice_type="OTHER", expense_category="REFUND_CHANGE_FEE",
            total_amount=amount,
            flight_date=flight_date, from_city=from_city, to_city=to_city,
            transport_no=flight_no, cabin_class=cabin,
            document_role="OFFICIAL_INVOICE", include_in_summary=True,
            confidence=classification.confidence, parser_name="RefundTicketDetector",
            review_status=ReviewStatus.AUTO_CONFIRMED,
            reimbursement_status=ReimbursementStatus.THIS_TRIP,
            note=f"退票/改签费（原航班: {flight_no} {from_city}-{to_city} {flight_date}）",
        )
        db.add(invoice)
        db.commit()
        db.refresh(invoice)
        return invoice

    @staticmethod
    def _match_flight_orders(db: Session, trip_id: int):
        """Match flight order screenshots with official invoices + insurance, merge data."""
        orders = db.query(Invoice).filter(
            Invoice.trip_id == trip_id,
            Invoice.document_role == "ORDER_SCREENSHOT",
            Invoice.invoice_type == "FLIGHT_ORDER_PROOF",
            Invoice.linked_invoice_id == None,
        ).all()

        flight_invoices = db.query(Invoice).filter(
            Invoice.trip_id == trip_id,
            Invoice.document_role == "OFFICIAL_INVOICE",
            Invoice.expense_category == ExpenseCategory.INTERCITY_TRANSPORT,
            Invoice.invoice_type.in_(["FLIGHT_TICKET", "PLATFORM_FLIGHT_INVOICE", "VAT_INVOICE"]),
        ).all()

        insurance_invoices = db.query(Invoice).filter(
            Invoice.trip_id == trip_id,
            Invoice.invoice_type == "TRAVEL_INSURANCE_INVOICE",
        ).all()

        for order in orders:
            best_flight = None
            for inv in flight_invoices:
                if inv.linked_invoice_id:
                    continue
                if order.transport_no and inv.transport_no and order.transport_no == inv.transport_no:
                    best_flight = inv; break
                if order.order_total_amount and inv.total_amount:
                    diff = abs(order.order_total_amount - inv.total_amount)
                    if diff <= 100:
                        best_flight = inv; break

            if not best_flight:
                continue

            order.linked_invoice_id = best_flight.id

            # Merge missing fields from order
            for field in ["flight_date", "depart_airport", "arrive_airport",
                          "from_city", "to_city", "transport_no", "airline_name", "cabin_class"]:
                if not getattr(best_flight, field) and getattr(order, field):
                    setattr(best_flight, field, getattr(order, field))
            if not best_flight.depart_time_str and order.depart_time_str:
                best_flight.depart_time_str = order.depart_time_str

            # Try to match insurance to explain order total
            if order.order_total_amount and best_flight.total_amount:
                remaining = order.order_total_amount - best_flight.total_amount
                if remaining > 0:
                    for ins in insurance_invoices:
                        if ins.linked_invoice_id:
                            continue
                        if ins.total_amount and abs(ins.total_amount - remaining) <= 1:
                            ins.linked_invoice_id = best_flight.id
                            best_flight.insurance_amount = ins.total_amount
                            best_flight.ancillary_amount = remaining
                            break
                    if not best_flight.insurance_amount:
                        best_flight.ancillary_amount = remaining

            db.commit()

    @staticmethod
    def extract_trip_invoices(db: Session, trip_id: int) -> list[Invoice]:
        """Run extraction on all OCR results for a trip."""
        ocr_results = (
            db.query(OCRResult)
            .filter(OCRResult.trip_id == trip_id, OCRResult.success == True)
            .all()
        )

        invoices: list[Invoice] = []
        for ocr in ocr_results:
            # Skip if already has an invoice
            existing = (
                db.query(Invoice)
                .filter(Invoice.ocr_result_id == ocr.id)
                .first()
            )
            if existing:
                invoices.append(existing)
                continue

            inv = ExtractionService.extract_from_ocr_result(db, ocr)
            if inv:
                invoices.append(inv)

        # ── Match flight orders with invoices ──
        ExtractionService._match_flight_orders(db, trip_id)

        # ── Deduplicate: same train/flight + date + amount → keep PDF over image ──
        invoices = ExtractionService._deduplicate_invoices(db, invoices)

        return invoices

    @staticmethod
    def _deduplicate_invoices(db: Session, invoices: list[Invoice]) -> list[Invoice]:
        """Remove duplicate invoices where PDF and screenshot produce same result."""
        from models.document import Document

        seen: dict[tuple, Invoice] = {}
        to_remove: list[Invoice] = []

        for inv in invoices:
            if not inv.transport_no or not inv.business_date:
                continue
            key = (inv.transport_no, str(inv.business_date), str(inv.total_amount))

            if key in seen:
                existing = seen[key]
                # Prefer PDF over image
                existing_doc = db.query(Document).filter(Document.id == existing.document_id).first()
                current_doc = db.query(Document).filter(Document.id == inv.document_id).first()

                existing_is_pdf = existing_doc and existing_doc.file_ext == ".pdf"
                current_is_pdf = current_doc and current_doc.file_ext == ".pdf"

                if current_is_pdf and not existing_is_pdf:
                    # Current is PDF, replace existing
                    to_remove.append(existing)
                    seen[key] = inv
                else:
                    # Keep existing (either PDF or first seen)
                    to_remove.append(inv)
            else:
                seen[key] = inv

        # Delete duplicate invoices
        for inv in to_remove:
            db.delete(inv)
        if to_remove:
            db.commit()

        return [inv for inv in invoices if inv not in to_remove]