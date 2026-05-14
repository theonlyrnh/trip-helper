"""Export API endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel

from database import get_db
from services.trip_service import TripService
from exporters.excel_exporter import ExcelExporter
from exporters.pdf_report_exporter import PDFReportExporter

router = APIRouter(prefix="/api/trips/{trip_id}/export", tags=["exports"])


class ExportResponse(BaseModel):
    trip_id: int
    format: str
    file_path: str
    message: str


@router.post("/excel", response_model=ExportResponse)
def export_excel(trip_id: int, db: Session = Depends(get_db)):
    """Export trip data as an Excel workbook with 5 sheets."""
    trip = TripService.get_trip(db, trip_id)
    if trip is None:
        raise HTTPException(status_code=404, detail="Trip not found")

    filepath = ExcelExporter.export(db, trip)
    return ExportResponse(
        trip_id=trip_id,
        format="excel",
        file_path=filepath,
        message=f"Excel exported to {filepath}",
    )


@router.post("/pdf", response_model=ExportResponse)
def export_pdf(trip_id: int, db: Session = Depends(get_db)):
    """Export trip data as a PDF report."""
    trip = TripService.get_trip(db, trip_id)
    if trip is None:
        raise HTTPException(status_code=404, detail="Trip not found")

    filepath = PDFReportExporter.export(db, trip)
    return ExportResponse(
        trip_id=trip_id,
        format="pdf",
        file_path=filepath,
        message=f"PDF exported to {filepath}",
    )