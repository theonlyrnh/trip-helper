"""Trip API endpoints."""

from datetime import datetime, date, time as dt_time
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from database import get_db
from services.trip_service import TripService
from services.ocr_service import OCRService
from services.expense_summary import ExpenseSummary
from services.issue_detector import IssueDetector

router = APIRouter(prefix="/api/trips", tags=["trips"])


class TripCreateRequest(BaseModel):
    title: str
    folder_path: str
    traveler_name: Optional[str] = None
    company_name: Optional[str] = None
    project_type: Optional[str] = "TRAVEL"


class TripResponse(BaseModel):
    id: int
    title: str
    folder_path: str
    folder_name: str
    traveler_name: Optional[str] = None
    company_name: Optional[str] = None
    folder_date_start: Optional[date] = None
    folder_date_end: Optional[date] = None
    inferred_start_date: Optional[date] = None
    inferred_end_date: Optional[date] = None
    confirmed_start_date: Optional[date] = None
    confirmed_end_date: Optional[date] = None
    trip_days: Optional[int] = None
    route_text: Optional[str] = None
    document_count: int
    recognized_count: int
    review_count: int
    issue_count: int
    invoice_total_amount: float
    allowance_amount: float
    grand_total_amount: float
    status: str
    reimbursement_status: str = "NOT_REIMBURSED"
    project_type: str = "TRAVEL"
    last_opened_at: Optional[datetime] = None
    last_analyzed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TripUpdateRequest(BaseModel):
    title: Optional[str] = None
    folder_path: Optional[str] = None
    traveler_name: Optional[str] = None
    company_name: Optional[str] = None
    company_tax_id: Optional[str] = None
    confirmed_start_date: Optional[str] = None
    confirmed_end_date: Optional[str] = None
    daily_allowance: Optional[float] = None
    status: Optional[str] = None
    reimbursement_status: Optional[str] = None
    project_type: Optional[str] = None


@router.post("", response_model=TripResponse, status_code=201)
def create_trip(data: TripCreateRequest, db: Session = Depends(get_db)):
    trip = TripService.create_trip(
        db,
        title=data.title,
        folder_path=data.folder_path,
        traveler_name=data.traveler_name,
        company_name=data.company_name,
    )
    return trip


@router.get("", response_model=list[TripResponse])
def list_trips(db: Session = Depends(get_db)):
    return TripService.get_trips(db)


@router.get("/recent", response_model=TripResponse)
def get_recent_trip(db: Session = Depends(get_db)):
    """Get the most recently updated trip."""
    trip = TripService.get_recent_trip(db)
    if trip is None:
        raise HTTPException(status_code=404, detail="No trips found")
    return trip


class FindByFolderRequest(BaseModel):
    folder_path: str


@router.post("/find-by-folder", response_model=TripResponse)
def find_trip_by_folder(data: FindByFolderRequest, db: Session = Depends(get_db)):
    """Find an existing trip by folder path, or 404 if not found."""
    trip = TripService.find_by_folder(db, data.folder_path)
    if trip is None:
        raise HTTPException(status_code=404, detail="No trip found for this folder")
    return trip


@router.get("/{trip_id}", response_model=TripResponse)
def get_trip(trip_id: int, db: Session = Depends(get_db)):
    trip = TripService.get_trip(db, trip_id)
    if trip is None:
        raise HTTPException(status_code=404, detail="Trip not found")
    return trip


@router.put("/{trip_id}", response_model=TripResponse)
def update_trip(trip_id: int, data: TripUpdateRequest, db: Session = Depends(get_db)):
    update_dict = data.model_dump(exclude_unset=True)
    trip = TripService.update_trip(db, trip_id, update_dict)
    if trip is None:
        raise HTTPException(status_code=404, detail="Trip not found")
    return trip


@router.delete("/{trip_id}", status_code=204)
def delete_trip(trip_id: int, db: Session = Depends(get_db)):
    success = TripService.delete_trip(db, trip_id)
    if not success:
        raise HTTPException(status_code=404, detail="Trip not found")


class RecognizeResponse(BaseModel):
    trip_id: int
    recognized_count: int
    message: str


@router.post("/{trip_id}/recognize", response_model=RecognizeResponse)
def recognize_trip(trip_id: int, db: Session = Depends(get_db)):
    """Run OCR recognition on all pending documents in a trip."""
    trip = TripService.get_trip(db, trip_id)
    if trip is None:
        raise HTTPException(status_code=404, detail="Trip not found")

    ocr_service = OCRService()
    results = ocr_service.recognize_trip_documents(db, trip_id)

    return RecognizeResponse(
        trip_id=trip_id,
        recognized_count=len(results),
        message=f"Recognized {len(results)} documents",
    )


class SummaryResponse(BaseModel):
    trip_id: int
    trip_title: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    trip_days: int
    route_text: Optional[str] = None
    daily_allowance: float
    allowance_amount: float
    intercity_transport_amount: float
    local_transport_amount: float
    lodging_amount: float
    meal_amount: float
    refund_change_fee: float
    travel_insurance_amount: float
    other_amount: float
    invoice_total_amount: float
    grand_total_amount: float


class IssueResponse(BaseModel):
    id: int
    trip_id: int
    document_id: Optional[int] = None
    invoice_id: Optional[int] = None
    issue_type: str
    severity: str
    message: str
    suggestion: Optional[str] = None
    auto_generated: bool
    resolved: bool
    # Joined fields from Document
    file_name: Optional[str] = None
    file_path: Optional[str] = None
    # Joined fields from Invoice
    invoice_type: Optional[str] = None
    expense_category: Optional[str] = None
    invoice_total_amount: Optional[float] = None

    model_config = {"from_attributes": True}


@router.get("/{trip_id}/summary", response_model=SummaryResponse)
def get_trip_summary(trip_id: int, db: Session = Depends(get_db)):
    """Get expense summary for a trip."""
    trip = TripService.get_trip(db, trip_id)
    if trip is None:
        raise HTTPException(status_code=404, detail="Trip not found")

    # Compute and update summary
    ExpenseSummary.update_trip(db, trip)
    summary = ExpenseSummary.compute(db, trip)

    return SummaryResponse(
        trip_id=trip_id,
        trip_title=trip.title,
        start_date=str(trip.inferred_start_date) if trip.inferred_start_date else None,
        end_date=str(trip.inferred_end_date) if trip.inferred_end_date else None,
        trip_days=summary["trip_days"],
        route_text=trip.route_text,
        daily_allowance=summary["daily_allowance"],
        allowance_amount=summary["allowance_amount"],
        intercity_transport_amount=summary["intercity_transport_amount"],
        local_transport_amount=summary["local_transport_amount"],
        lodging_amount=summary["lodging_amount"],
        meal_amount=summary["meal_amount"],
        refund_change_fee=summary.get("refund_change_fee", 0),
        travel_insurance_amount=summary.get("travel_insurance_amount", 0),
        other_amount=summary["other_amount"],
        invoice_total_amount=summary["invoice_total_amount"],
        grand_total_amount=summary["grand_total_amount"],
    )


class WorkspaceResponse(BaseModel):
    trip: TripResponse
    stats: dict
    summary: dict
    documents: list[dict]
    issues: list[IssueResponse]
    route_segments: list[dict]


@router.get("/{trip_id}/workspace", response_model=WorkspaceResponse)
def get_workspace(trip_id: int, db: Session = Depends(get_db)):
    """Aggregate endpoint: returns everything needed for the workspace UI."""
    trip = TripService.get_trip(db, trip_id)
    if trip is None:
        raise HTTPException(status_code=404, detail="Trip not found")

    # Stats
    from models.document import Document
    from models.ocr_result import OCRResult
    from models.review_issue import ReviewIssue

    doc_count = db.query(Document).filter(Document.trip_id == trip_id).count()
    rec_count = db.query(OCRResult).filter(
        OCRResult.trip_id == trip_id, OCRResult.success == True
    ).count()
    stats = {
        "total_files": doc_count,
        "recognized": rec_count,
        "review_count": trip.review_count or 0,
        "issues": trip.issue_count or 0,
    }

    # Summary
    ExpenseSummary.update_trip(db, trip)
    summary = ExpenseSummary.compute(db, trip)

    # Documents with invoice join
    from models.invoice import Invoice
    docs = db.query(Document).filter(Document.trip_id == trip_id).order_by(Document.file_name).all()
    doc_list = []
    for d in docs:
        inv = db.query(Invoice).filter(Invoice.document_id == d.id).first()
        doc_issues = db.query(ReviewIssue).filter(
            ReviewIssue.document_id == d.id, ReviewIssue.resolved == False
        ).count()
        doc_list.append({
            "id": d.id,
            "file_name": d.file_name,
            "file_path": d.file_path,
            "file_ext": d.file_ext,
            "file_size": d.file_size,
            "document_type": d.document_type,
            "scan_status": d.scan_status,
            "ocr_status": d.ocr_status,
            "invoice_id": inv.id if inv else None,
            "invoice_type": inv.invoice_type if inv else None,
            "expense_category": inv.expense_category if inv else None,
            "total_amount": float(inv.total_amount) if inv and inv.total_amount else None,
            "order_total_amount": float(inv.order_total_amount) if inv and inv.order_total_amount else None,
            "nights": inv.nights if inv else None,
            "issue_count": doc_issues,
        })

    # Issues with joins
    issues = get_trip_issues(trip_id, db)

    # Route segments – sorted by date then time
    from models.travel_segment import TravelSegment
    segs = db.query(TravelSegment).filter(
        TravelSegment.trip_id == trip_id
    ).order_by(
        TravelSegment.depart_date.asc().nullslast(),
        TravelSegment.depart_time.asc().nullslast()
    ).all()
    route_segments = [{
        "id": s.id,
        "depart_date": str(s.depart_date) if s.depart_date else None,
        "depart_time": str(s.depart_time)[:5] if s.depart_time else None,
        "transport_type": s.transport_type,
        "from_place": s.from_place,
        "to_place": s.to_place,
        "transport_no": s.transport_no,
        "seat_class": s.seat_class,
        "amount": float(s.amount) if s.amount else None,
        "source_document_id": s.source_document_id,
    } for s in segs]

    # Update last_opened_at
    trip.last_opened_at = datetime.now()
    db.commit()

    return WorkspaceResponse(
        trip=TripResponse.model_validate(trip),
        stats=stats,
        summary=summary,
        documents=doc_list,
        issues=issues,
        route_segments=route_segments,
    )


@router.get("/{trip_id}/issues", response_model=list[IssueResponse])
def get_trip_issues(trip_id: int, db: Session = Depends(get_db)):
    """Get all issues for a trip with joined document/invoice data."""
    trip = TripService.get_trip(db, trip_id)
    if trip is None:
        raise HTTPException(status_code=404, detail="Trip not found")

    # Run detection
    IssueDetector.detect_all(db, trip)

    from models.review_issue import ReviewIssue
    from models.document import Document
    from models.invoice import Invoice

    issues = (
        db.query(ReviewIssue)
        .filter(ReviewIssue.trip_id == trip_id)
        .order_by(ReviewIssue.severity.desc(), ReviewIssue.created_at.desc())
        .all()
    )

    result = []
    for issue in issues:
        data = IssueResponse.model_validate(issue)
        # Join document info
        if issue.document_id:
            doc = db.query(Document).filter(Document.id == issue.document_id).first()
            if doc:
                data.file_name = doc.file_name
                data.file_path = doc.file_path
        # Join invoice info
        if issue.invoice_id:
            inv = db.query(Invoice).filter(Invoice.id == issue.invoice_id).first()
            if inv:
                data.invoice_type = inv.invoice_type
                data.expense_category = inv.expense_category
                data.invoice_total_amount = float(inv.total_amount) if inv.total_amount else None
        result.append(data)

    return result