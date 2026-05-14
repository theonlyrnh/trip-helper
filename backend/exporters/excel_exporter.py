"""Excel exporter – generates a 5-sheet Excel workbook for a trip."""

import os
from datetime import date
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from sqlalchemy.orm import Session

from models.trip import Trip
from models.invoice import Invoice
from models.travel_segment import TravelSegment
from models.lodging_stay import LodgingStay
from models.review_issue import ReviewIssue
from config import settings


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

        # Sheet 1: Trip Summary
        ExcelExporter._write_summary(wb, trip)

        # Sheet 2: Invoice Details
        invoices = (
            db.query(Invoice).filter(Invoice.trip_id == trip.id).all()
        )
        ExcelExporter._write_invoices(wb, invoices)

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
        filename = f"trip_{trip.id}_{trip.title}.xlsx"
        filepath = os.path.join(settings.EXPORT_DIR, filename)
        wb.save(filepath)
        return filepath

    @staticmethod
    def _write_summary(wb: Workbook, trip: Trip):
        ws = wb.active
        ws.title = "Trip Summary"

        rows = [
            ("Trip Title", trip.title),
            ("Traveler", trip.traveler_name or ""),
            ("Company", trip.company_name or ""),
            ("Start Date", str(trip.inferred_start_date or trip.confirmed_start_date or "")),
            ("End Date", str(trip.inferred_end_date or trip.confirmed_end_date or "")),
            ("Trip Days", trip.trip_days or 0),
            ("Route", trip.route_text or ""),
            ("Daily Allowance", float(trip.daily_allowance)),
            ("Allowance Amount", float(trip.allowance_amount)),
            ("Intercity Transport", float(trip.intercity_transport_amount)),
            ("Local Transport", float(trip.local_transport_amount)),
            ("Lodging", float(trip.lodging_amount)),
            ("Meal", float(trip.meal_amount)),
            ("Other", float(trip.other_amount)),
            ("Invoice Total", float(trip.invoice_total_amount)),
            ("Grand Total", float(trip.grand_total_amount)),
        ]

        for i, (label, value) in enumerate(rows, 1):
            ws.cell(row=i, column=1, value=label).font = HEADER_FONT
            ws.cell(row=i, column=2, value=value)

        ws.column_dimensions["A"].width = 22
        ws.column_dimensions["B"].width = 30

    @staticmethod
    def _write_invoices(wb: Workbook, invoices: list[Invoice]):
        ws = wb.create_sheet("Invoice Details")
        headers = [
            "No.", "File Name", "Invoice Type", "Expense Category",
            "Invoice Date", "Business Date", "Seller", "Buyer",
            "Invoice Number", "Amount", "Confirmed Amount", "Status", "Note",
        ]
        ExcelExporter._write_header(ws, headers)

        for i, inv in enumerate(invoices, 2):
            ws.cell(row=i, column=1, value=i - 1)
            ws.cell(row=i, column=2, value="")
            ws.cell(row=i, column=3, value=inv.invoice_type)
            ws.cell(row=i, column=4, value=inv.expense_category)
            ws.cell(row=i, column=5, value=str(inv.invoice_date) if inv.invoice_date else "")
            ws.cell(row=i, column=6, value=str(inv.business_date) if inv.business_date else "")
            ws.cell(row=i, column=7, value=inv.seller_name or "")
            ws.cell(row=i, column=8, value=inv.buyer_name or "")
            ws.cell(row=i, column=9, value=inv.invoice_number or "")
            ws.cell(row=i, column=10, value=float(inv.total_amount) if inv.total_amount else 0)
            ws.cell(row=i, column=11, value=float(inv.confirmed_amount) if inv.confirmed_amount else "")
            ws.cell(row=i, column=12, value=inv.review_status)
            ws.cell(row=i, column=13, value=inv.note or "")

    @staticmethod
    def _write_travel(wb: Workbook, segments: list[TravelSegment]):
        ws = wb.create_sheet("Travel Segments")
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
        ws = wb.create_sheet("Lodging Details")
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
        ws = wb.create_sheet("Review Issues")
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