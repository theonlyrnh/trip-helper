"""Excel exporter – generates a reimbursement workbook for a trip."""

import os
import re
from decimal import Decimal
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from sqlalchemy.orm import Session

from models.trip import Trip
from models.document import Document
from models.invoice import Invoice
from models.travel_segment import TravelSegment
from models.lodging_stay import LodgingStay
from models.review_issue import ReviewIssue
from config import settings
from enums import ReimbursementStatus


HEADER_FONT = Font(bold=True, size=11)
HEADER_FILL = PatternFill(start_color="D9E1F2", end_color="D9E1F2", fill_type="solid")
THIN_BORDER = Border(
    left=Side(style="thin"),
    right=Side(style="thin"),
    top=Side(style="thin"),
    bottom=Side(style="thin"),
)


class ExcelExporter:

    @staticmethod
    def export(db: Session, trip: Trip) -> str:
        """Generate Excel file and return the file path."""
        os.makedirs(settings.EXPORT_DIR, exist_ok=True)

        wb = Workbook()

        # Sheet 1: Project Summary
        ExcelExporter._write_summary(wb, trip)

        # Sheet 2: Invoice Details
        invoices = (
            db.query(Invoice).filter(Invoice.trip_id == trip.id).order_by(Invoice.id.asc()).all()
        )
        documents = {
            d.id: d
            for d in db.query(Document).filter(Document.trip_id == trip.id).all()
        }
        ExcelExporter._write_invoices(wb, invoices, documents)

        # Sheet 3: Travel Segments
        segments = (
            db.query(TravelSegment)
            .filter(TravelSegment.trip_id == trip.id)
            .all()
        )
        ExcelExporter._write_travel(wb, segments)

        # Sheet 4: Lodging Details
        stays = (
            db.query(LodgingStay)
            .filter(LodgingStay.trip_id == trip.id)
            .all()
        )
        ExcelExporter._write_lodging(wb, stays)

        # Sheet 5: Review Issues
        issues = (
            db.query(ReviewIssue)
            .filter(ReviewIssue.trip_id == trip.id)
            .all()
        )
        ExcelExporter._write_issues(wb, issues)

        # Remove default sheet if exists
        if "Sheet" in wb.sheetnames:
            del wb["Sheet"]

        # Save
        filename = ExcelExporter.safe_filename(f"trip_{trip.id}_{trip.title}.xlsx")
        filepath = os.path.join(settings.EXPORT_DIR, filename)
        wb.save(filepath)
        return filepath

    @staticmethod
    def safe_filename(filename: str) -> str:
        """Return a Windows-safe filename while keeping useful Chinese text."""
        cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", filename).strip(" .")
        cleaned = re.sub(r"_+", "_", cleaned)
        return cleaned or "trip_export.xlsx"

    @staticmethod
    def _write_summary(wb: Workbook, trip: Trip):
        ws = wb.active
        ws.title = "项目摘要"

        rows = [
            ("项目名称", trip.title),
            ("出差人", trip.traveler_name or ""),
            ("公司", trip.company_name or ""),
            ("开始日期", str(trip.inferred_start_date or trip.confirmed_start_date or "")),
            ("结束日期", str(trip.inferred_end_date or trip.confirmed_end_date or "")),
            ("天数", trip.trip_days or 0),
            ("路线", trip.route_text or ""),
            ("日补助", float(trip.daily_allowance)),
            ("补助合计", float(trip.allowance_amount)),
            ("城际交通", float(trip.intercity_transport_amount)),
            ("市内交通", float(trip.local_transport_amount)),
            ("住宿费", float(trip.lodging_amount)),
            ("餐饮费", float(trip.meal_amount)),
            ("其他", float(trip.other_amount)),
            ("本次报销票据合计", float(trip.invoice_total_amount)),
            ("含补助总计", float(trip.grand_total_amount)),
        ]

        for i, (label, value) in enumerate(rows, 1):
            ws.cell(row=i, column=1, value=label).font = HEADER_FONT
            ws.cell(row=i, column=2, value=value)

        ws.column_dimensions["A"].width = 22
        ws.column_dimensions["B"].width = 30

    @staticmethod
    def _write_invoices(
        wb: Workbook,
        invoices: list[Invoice],
        documents: dict[int, Document],
    ):
        ws = wb.create_sheet("发票明细")
        headers = [
            "序号",
            "文件名",
            "凭证角色",
            "是否计入本次报销",
            "报销状态",
            "发票类型",
            "费用类别",
            "发票日期",
            "业务日期",
            "销售方",
            "购买方",
            "发票号码",
            "识别金额",
            "确认金额",
            "本次报销金额",
            "复核状态",
            "车次/航班号",
            "出发地",
            "到达地",
            "出发时间",
            "酒店名称",
            "入住日期",
            "离店日期",
            "住宿晚数",
            "异常状态",
            "备注",
        ]
        ExcelExporter._write_header(ws, headers)

        for i, inv in enumerate(invoices, 2):
            doc = documents.get(inv.document_id) if inv.document_id else None
            reimbursement_amount = ExcelExporter._reimbursement_amount(inv)
            ws.cell(row=i, column=1, value=i - 1)
            ws.cell(row=i, column=2, value=doc.file_name if doc else "")
            ws.cell(row=i, column=3, value=inv.document_role)
            ws.cell(row=i, column=4, value="是" if inv.include_in_summary else "否")
            ws.cell(row=i, column=5, value=inv.reimbursement_status)
            ws.cell(row=i, column=6, value=inv.invoice_type)
            ws.cell(row=i, column=7, value=inv.expense_category)
            ws.cell(row=i, column=8, value=str(inv.invoice_date) if inv.invoice_date else "")
            ws.cell(row=i, column=9, value=str(inv.business_date) if inv.business_date else "")
            ws.cell(row=i, column=10, value=inv.seller_name or "")
            ws.cell(row=i, column=11, value=inv.buyer_name or "")
            ws.cell(row=i, column=12, value=inv.invoice_number or "")
            ws.cell(row=i, column=13, value=float(inv.total_amount) if inv.total_amount is not None else 0)
            ws.cell(row=i, column=14, value=float(inv.confirmed_amount) if inv.confirmed_amount is not None else "")
            ws.cell(row=i, column=15, value=float(reimbursement_amount) if reimbursement_amount is not None else 0)
            ws.cell(row=i, column=16, value=inv.review_status)
            ws.cell(row=i, column=17, value=inv.transport_no or "")
            ws.cell(row=i, column=18, value=inv.from_place or inv.from_city or inv.depart_airport or "")
            ws.cell(row=i, column=19, value=inv.to_place or inv.to_city or inv.arrive_airport or "")
            ws.cell(row=i, column=20, value=inv.depart_time_str or "")
            ws.cell(row=i, column=21, value=inv.hotel_name or inv.actual_hotel_name or "")
            ws.cell(row=i, column=22, value=str(inv.checkin_date) if inv.checkin_date else "")
            ws.cell(row=i, column=23, value=str(inv.checkout_date) if inv.checkout_date else "")
            ws.cell(row=i, column=24, value=inv.nights or 0)
            ws.cell(row=i, column=25, value="")
            ws.cell(row=i, column=26, value=inv.note or "")

    @staticmethod
    def _reimbursement_amount(inv: Invoice) -> Decimal | None:
        if not inv.include_in_summary:
            return None
        if inv.reimbursement_status != ReimbursementStatus.THIS_TRIP:
            return None
        return inv.confirmed_amount if inv.confirmed_amount is not None else inv.total_amount

    @staticmethod
    def _write_travel(wb: Workbook, segments: list[TravelSegment]):
        ws = wb.create_sheet("路线明细")
        headers = [
            "Date", "Transport Type", "From", "To",
            "Transport No.", "Seat Class", "Amount", "Source File",
        ]
        ExcelExporter._write_header(ws, headers)

        for i, seg in enumerate(segments, 2):
            ws.cell(row=i, column=1, value=str(seg.depart_date) if seg.depart_date else "")
            ws.cell(row=i, column=2, value=seg.transport_type)
            ws.cell(row=i, column=3, value=seg.from_place or seg.from_city or "")
            ws.cell(row=i, column=4, value=seg.to_place or seg.to_city or "")
            ws.cell(row=i, column=5, value=seg.transport_no or "")
            ws.cell(row=i, column=6, value=seg.seat_class or "")
            ws.cell(row=i, column=7, value=float(seg.amount) if seg.amount else 0)
            ws.cell(row=i, column=8, value="")

    @staticmethod
    def _write_lodging(wb: Workbook, stays: list[LodgingStay]):
        ws = wb.create_sheet("住宿明细")
        headers = [
            "Hotel", "City", "Check-in", "Check-out",
            "Nights", "Amount", "Source File",
        ]
        ExcelExporter._write_header(ws, headers)

        for i, stay in enumerate(stays, 2):
            ws.cell(row=i, column=1, value=stay.hotel_name or "")
            ws.cell(row=i, column=2, value=stay.city or "")
            ws.cell(row=i, column=3, value=str(stay.checkin_date) if stay.checkin_date else "")
            ws.cell(row=i, column=4, value=str(stay.checkout_date) if stay.checkout_date else "")
            ws.cell(row=i, column=5, value=stay.nights or 0)
            ws.cell(row=i, column=6, value=float(stay.amount) if stay.amount else 0)
            ws.cell(row=i, column=7, value="")

    @staticmethod
    def _write_issues(wb: Workbook, issues: list[ReviewIssue]):
        ws = wb.create_sheet("异常明细")
        headers = [
            "Severity", "Issue Type", "Message", "Suggestion", "Resolved", "Source File",
        ]
        ExcelExporter._write_header(ws, headers)

        for i, issue in enumerate(issues, 2):
            ws.cell(row=i, column=1, value=issue.severity)
            ws.cell(row=i, column=2, value=issue.issue_type)
            ws.cell(row=i, column=3, value=issue.message)
            ws.cell(row=i, column=4, value=issue.suggestion or "")
            ws.cell(row=i, column=5, value="Yes" if issue.resolved else "No")
            ws.cell(row=i, column=6, value="")

    @staticmethod
    def _write_header(ws, headers: list[str]):
        for col, h in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=h)
            cell.font = HEADER_FONT
            cell.fill = HEADER_FILL
            cell.border = THIN_BORDER
            cell.alignment = Alignment(horizontal="center")
        # Auto-width
        for col in range(1, len(headers) + 1):
            ws.column_dimensions[ws.cell(row=1, column=col).column_letter].width = 16
