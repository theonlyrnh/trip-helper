"""Export API endpoints."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from database import get_db
from services.trip_service import TripService
from exporters.excel_exporter import ExcelExporter
from exporters.pdf_report_exporter import PDFReportExporter

router = APIRouter(prefix="/api/trips/{trip_id}/export", tags=["exports"])


@router.post("/excel")
def export_excel(trip_id: int, db: Session = Depends(get_db)):
    """Export trip data as an Excel workbook and return it as a download."""
    trip = TripService.get_trip(db, trip_id)
    if trip is None:
        raise HTTPException(status_code=404, detail="Trip not found")

    filepath = ExcelExporter.export(db, trip)
    filename = Path(filepath).name
    return FileResponse(
        path=filepath,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=filename,
    )


@router.post("/pdf")
def export_pdf(trip_id: int, db: Session = Depends(get_db)):
    """Export trip data as a PDF report and return it as a download."""
    trip = TripService.get_trip(db, trip_id)
    if trip is None:
        raise HTTPException(status_code=404, detail="Trip not found")

    filepath = PDFReportExporter.export(db, trip)
    filename = Path(filepath).name
    return FileResponse(
        path=filepath,
        media_type="application/pdf",
        filename=filename,
    )
