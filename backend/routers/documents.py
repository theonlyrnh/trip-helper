"""Document API endpoints."""

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from database import get_db
from services.trip_service import TripService
from services.document_service import DocumentService

router = APIRouter(prefix="/api/trips/{trip_id}/documents", tags=["documents"])


class DocumentResponse(BaseModel):
    id: int
    trip_id: int
    file_name: str
    file_path: str
    file_ext: str
    file_hash: str
    file_size: int
    page_count: int
    document_type: str
    scan_status: str
    ocr_status: str
    thumbnail_path: Optional[str] = None
    preview_image_path: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ScanResponse(BaseModel):
    trip_id: int
    total_scanned: int
    new_documents: int
    documents: list[DocumentResponse]


@router.post("/scan", response_model=ScanResponse)
def scan_trip_documents(trip_id: int, db: Session = Depends(get_db)):
    """Scan the trip's folder for invoice files and create Document records."""
    trip = TripService.get_trip(db, trip_id)
    if trip is None:
        raise HTTPException(status_code=404, detail="Trip not found")

    new_docs = DocumentService.scan_trip_folder(db, trip)

    # Get all documents for this trip
    from models.document import Document
    all_docs = (
        db.query(Document)
        .filter(Document.trip_id == trip_id)
        .order_by(Document.file_name)
        .all()
    )

    return ScanResponse(
        trip_id=trip_id,
        total_scanned=len(all_docs),
        new_documents=len(new_docs),
        documents=[DocumentResponse.model_validate(d) for d in all_docs],
    )


class PreprocessResponse(BaseModel):
    trip_id: int
    processed_count: int
    documents: list[DocumentResponse]


@router.post("/preprocess", response_model=PreprocessResponse)
def preprocess_documents(trip_id: int, db: Session = Depends(get_db)):
    """Preprocess all documents: extract PDF text, render previews, generate thumbnails."""
    trip = TripService.get_trip(db, trip_id)
    if trip is None:
        raise HTTPException(status_code=404, detail="Trip not found")

    results = DocumentService.preprocess_trip_documents(db, trip_id)

    return PreprocessResponse(
        trip_id=trip_id,
        processed_count=len(results),
        documents=[DocumentResponse.model_validate(d) for d in results],
    )


@router.get("", response_model=list[DocumentResponse])
def list_documents(trip_id: int, db: Session = Depends(get_db)):
    """List all documents for a trip."""
    from models.document import Document
    docs = (
        db.query(Document)
        .filter(Document.trip_id == trip_id)
        .order_by(Document.file_name)
        .all()
    )
    return [DocumentResponse.model_validate(d) for d in docs]