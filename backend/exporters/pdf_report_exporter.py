"""PDF report exporter – generates a summary PDF report for a trip."""

import os
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
)
from reportlab.lib import colors
from sqlalchemy.orm import Session

from models.trip import Trip
from config import settings
from exporters.excel_exporter import ExcelExporter


class PDFReportExporter:

    @staticmethod
    def export(db: Session, trip: Trip) -> str:
        """Generate PDF report and return the file path."""
        os.makedirs(settings.EXPORT_DIR, exist_ok=True)

        filename = ExcelExporter.safe_filename(f"trip_{trip.id}_{trip.title}.pdf")
        filepath = os.path.join(settings.EXPORT_DIR, filename)

        doc = SimpleDocTemplate(filepath, pagesize=A4)
        styles = getSampleStyleSheet()
        story = []

        # Title
        title_style = ParagraphStyle(
            "CustomTitle", parent=styles["Title"], fontSize=18, spaceAfter=12
        )
        story.append(Paragraph("Travel Invoice Summary Report", title_style))
        story.append(Spacer(1, 6 * mm))

        # Trip info
        info_data = [
            ["Trip Title", trip.title],
            ["Traveler", trip.traveler_name or "-"],
            ["Company", trip.company_name or "-"],
            ["Dates", f"{trip.inferred_start_date or '?'} to {trip.inferred_end_date or '?'}"],
            ["Days", str(trip.trip_days or 0)],
            ["Route", trip.route_text or "-"],
        ]
        info_table = Table(info_data, colWidths=[80, 200])
        info_table.setStyle(
            TableStyle([
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ])
        )
        story.append(info_table)
        story.append(Spacer(1, 8 * mm))

        # Expense summary
        story.append(Paragraph("Expense Summary", styles["Heading2"]))
        expense_data = [
            ["Category", "Amount (¥)"],
            ["Intercity Transport", f"{float(trip.intercity_transport_amount):.2f}"],
            ["Local Transport", f"{float(trip.local_transport_amount):.2f}"],
            ["Lodging", f"{float(trip.lodging_amount):.2f}"],
            ["Meal", f"{float(trip.meal_amount):.2f}"],
            ["Other", f"{float(trip.other_amount):.2f}"],
            ["Invoice Subtotal", f"{float(trip.invoice_total_amount):.2f}"],
            ["Allowance", f"{float(trip.allowance_amount):.2f}"],
            ["Grand Total", f"{float(trip.grand_total_amount):.2f}"],
        ]
        expense_table = Table(expense_data, colWidths=[140, 100])
        expense_table.setStyle(
            TableStyle([
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ])
        )
        story.append(expense_table)

        doc.build(story)
        return filepath
