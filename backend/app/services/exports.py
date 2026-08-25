"""Asynchronous export generation into private A100 storage."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path
from re import compile as re_compile, sub

from openpyxl import Workbook
from openpyxl.styles import Font
from reportlab.lib.pagesizes import A4
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.reporting.summary import calculate_summary
from app.core.config import get_settings
from app.infrastructure.db.models import Document, Export, Invoice, ReviewIssue, Trip
from app.infrastructure.storage.local import LocalStorage


def create_export_bytes(db: Session, trip: Trip, export_format: str) -> tuple[bytes, str, str]:
    invoices = list(db.scalars(select(Invoice).where(Invoice.trip_id == trip.id).order_by(Invoice.created_at)))
    documents = {item.id: item for item in db.scalars(select(Document).where(Document.trip_id == trip.id))}
    summary = calculate_summary(trip, invoices)
    safe_title = sub(r"[^\w.-]+", "_", trip.title, flags=0)[:80] or "trip"
    if export_format == "XLSX":
        return _xlsx_bytes(trip, invoices, documents, summary), f"{safe_title}_reimbursement.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    if export_format == "PDF":
        issues = list(db.scalars(select(ReviewIssue).where(ReviewIssue.trip_id == trip.id).order_by(ReviewIssue.created_at)))
        return _pdf_bytes(trip, summary, invoices, documents, issues), f"{safe_title}_reimbursement.pdf", "application/pdf"
    raise ValueError("Unsupported export format")


def store_export(db: Session, storage: LocalStorage, trip: Trip, export: Export) -> None:
    content, filename, _mime = create_export_bytes(db, trip, export.format)
    key = storage.new_key("exports", ".xlsx" if export.format == "XLSX" else ".pdf")
    storage.put_bytes(content, key)
    export.storage_key = key
    export.original_filename = filename
    export.status = "SUCCEEDED"
    export.error_code = None
    export.error_message = None
    export.expires_at = datetime.now(UTC) + timedelta(hours=get_settings().export_retention_hours)


def cleanup_expired_exports(
    db: Session,
    storage: LocalStorage,
    *,
    now: datetime | None = None,
) -> int:
    """Delete expired objects after a grace period and clear their metadata."""
    now = now or datetime.now(UTC)
    grace = timedelta(seconds=get_settings().export_cleanup_grace_seconds)
    candidates = list(
        db.scalars(
            select(Export).where(
                Export.status == "SUCCEEDED",
                Export.expires_at.is_not(None),
                Export.expires_at < now - grace,
            )
        )
    )
    deleted = 0
    for export in candidates:
        # A download updates last_accessed_at. Keep a recently touched object
        # for one grace window to avoid deleting a stream that just started.
        if export.last_accessed_at and export.last_accessed_at > now - grace:
            continue
        storage.delete(export.storage_key)
        export.storage_key = None
        export.status = "EXPIRED"
        export.last_accessed_at = now
        deleted += 1
    if deleted:
        db.commit()
    return deleted


def _xlsx_bytes(trip: Trip, invoices: list[Invoice], documents: dict[str, Document], summary: dict) -> bytes:
    workbook = Workbook()
    overview = workbook.active
    overview.title = "项目摘要"
    rows = [
        ("项目名称", trip.title),
        ("出差人", trip.traveler_name or ""),
        ("开始日期", str(trip.confirmed_start_date or trip.inferred_start_date or "")),
        ("结束日期", str(trip.confirmed_end_date or trip.inferred_end_date or "")),
        ("天数", summary["trip_days"]),
        ("项目票据合计", float(summary["invoice_total_amount"])),
        ("出差补助", float(summary["allowance_amount"])),
        ("项目总支出", float(summary["grand_total_amount"])),
        ("本次待报销", float(summary["reimbursement_total_amount"])),
        ("已报销", float(summary["reimbursed_total_amount"])),
    ]
    for row_index, (label, value) in enumerate(rows, 1):
        overview.cell(row=row_index, column=1, value=label).font = Font(bold=True)
        overview.cell(row=row_index, column=2, value=_excel_value(value))
    overview.column_dimensions["A"].width = 24
    overview.column_dimensions["B"].width = 32

    detail = workbook.create_sheet("发票明细")
    headers = ["文件名", "凭证角色", "是否计入本次报销", "报销状态", "发票类型", "费用类别", "识别金额", "确认金额", "本次报销金额", "发票日期", "备注"]
    detail.append(headers)
    for cell in detail[1]:
        cell.font = Font(bold=True)
    for invoice in invoices:
        selected = invoice.reimbursement_status == "THIS_TRIP" and invoice.include_in_summary
        amount = invoice.confirmed_amount if invoice.confirmed_amount is not None else invoice.total_amount
        reimbursement = amount if selected and (invoice.confirmed_amount is not None or (amount or 0) <= 100000) else 0
        detail.append([
            _excel_value(documents.get(invoice.document_id).original_filename if invoice.document_id in documents else ""),
            _excel_value(invoice.document_role),
            _excel_value("是" if invoice.include_in_summary else "否"),
            _excel_value(invoice.reimbursement_status),
            _excel_value(invoice.invoice_type),
            _excel_value(invoice.expense_category),
            float(invoice.total_amount) if invoice.total_amount is not None else None,
            float(invoice.confirmed_amount) if invoice.confirmed_amount is not None else None,
            float(reimbursement) if reimbursement is not None else 0,
            _excel_value(str(invoice.invoice_date or "")),
            _excel_value(invoice.note or ""),
        ])
    for column in detail.columns:
        detail.column_dimensions[column[0].column_letter].width = 18
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


_FORMULA_PREFIX = re_compile(r"^\s*[=+\-@]")


def _excel_value(value: object) -> object:
    """Prevent spreadsheet formula execution while preserving numeric types."""
    if isinstance(value, str) and _FORMULA_PREFIX.match(value):
        return "'" + value
    return value


def _pdf_font_name() -> str:
    settings = get_settings()
    candidates = [
        settings.pdf_font_path,
        "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
        "/usr/share/fonts/truetype/arphic-gbsn00lp/gbsn00lp.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for candidate in candidates:
        if not candidate or not Path(candidate).is_file():
            continue
        name = "TripHelperCJK"
        try:
            if name not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont(name, candidate))
            return name
        except Exception:
            continue
    return "Helvetica"


def _pdf_bytes(
    trip: Trip,
    summary: dict,
    invoices: list[Invoice] | None = None,
    documents: dict[str, Document] | None = None,
    issues: list[ReviewIssue] | None = None,
) -> bytes:
    output = BytesIO()
    document = SimpleDocTemplate(output, pagesize=A4)
    styles = getSampleStyleSheet()
    font_name = _pdf_font_name()
    title_style = ParagraphStyle("TripHelperTitle", parent=styles["Title"], fontName=font_name)
    body_style = ParagraphStyle("TripHelperBody", parent=styles["BodyText"], fontName=font_name)
    content = [Paragraph("差旅报销汇总", title_style), Spacer(1, 16)]
    data = [
        ["项目", Paragraph(str(trip.title), body_style)],
        ["天数", str(summary["trip_days"])],
        ["票据合计", f"{summary['invoice_total_amount']:.2f}"],
        ["出差补助", f"{summary['allowance_amount']:.2f}"],
        ["项目总计", f"{summary['grand_total_amount']:.2f}"],
        ["本次待报销", f"{summary['reimbursement_total_amount']:.2f}"],
        ["已报销", f"{summary['reimbursed_total_amount']:.2f}"],
    ]
    content.append(Table(data, colWidths=[140, 300]))
    if invoices:
        content.append(Spacer(1, 16))
        content.append(Paragraph("票据明细", body_style))
        detail = [["文件", "类别", "金额", "状态"]]
        for invoice in invoices:
            filename = documents.get(invoice.document_id).original_filename if documents and invoice.document_id in documents else ""
            amount = invoice.confirmed_amount if invoice.confirmed_amount is not None else invoice.total_amount
            detail.append([Paragraph(str(filename), body_style), invoice.expense_category, f"{amount or 0:.2f}", invoice.reimbursement_status])
        content.append(Table(detail, colWidths=[180, 100, 80, 80]))
    if issues:
        content.append(Spacer(1, 16))
        content.append(Paragraph("待复核异常", body_style))
        content.extend(Paragraph(f"{issue.severity}: {issue.message}", body_style) for issue in issues if issue.resolution_status == "OPEN")
    document.build(content)
    return output.getvalue()
