"""Analysis API endpoints – trip analysis, date inference, route generation."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from database import get_db
from services.trip_service import TripService
from services.extraction_service import ExtractionService
from services.travel_builder import TravelBuilder
from services.lodging_builder import LodgingBuilder
from services.trip_inference import TripInference

router = APIRouter(prefix="/api/trips/{trip_id}", tags=["analysis"])


class AnalysisResponse(BaseModel):
    trip_id: int
    status: str
    inferred_start_date: Optional[str] = None
    inferred_end_date: Optional[str] = None
    trip_days: Optional[int] = None
    date_confidence: float
    date_evidence: list[str]
    route_text: Optional[str] = None
    travel_segments_count: int
    lodging_stays_count: int
    invoices_count: int


@router.post("/analyze", response_model=AnalysisResponse)
def analyze_trip(trip_id: int, db: Session = Depends(get_db)):
    """
    Run full analysis on a trip:
    1. Extract invoices from OCR results
    2. Build travel segments and lodging stays
    3. Infer trip dates and generate route
    """
    trip = TripService.get_trip(db, trip_id)
    if trip is None:
        raise HTTPException(status_code=404, detail="Trip not found")

    # Step 1: Extract invoices
    invoices = ExtractionService.extract_trip_invoices(db, trip_id)

    # Step 2: Build travel segments
    segments = TravelBuilder.build_for_trip(db, trip_id)

    # Step 3: Build lodging stays
    stays = LodgingBuilder.build_for_trip(db, trip_id)

    # Step 4: Infer dates
    inference = TripInference.infer_dates(db, trip)
    if inference.start_date and inference.end_date:
        trip.inferred_start_date = inference.start_date
        trip.inferred_end_date = inference.end_date
        trip.trip_days = inference.days

    # Step 5: Generate route
    route = TripInference.generate_route(db, trip_id)
    if route:
        trip.route_text = route

    # Update trip status
    from enums import TripStatus
    trip.status = TripStatus.ANALYZED
    db.commit()
    db.refresh(trip)

    return AnalysisResponse(
        trip_id=trip_id,
        status=trip.status,
        inferred_start_date=str(trip.inferred_start_date) if trip.inferred_start_date else None,
        inferred_end_date=str(trip.inferred_end_date) if trip.inferred_end_date else None,
        trip_days=trip.trip_days,
        date_confidence=inference.confidence,
        date_evidence=inference.evidence,
        route_text=trip.route_text,
        travel_segments_count=len(segments),
        lodging_stays_count=len(stays),
        invoices_count=len(invoices),
    )