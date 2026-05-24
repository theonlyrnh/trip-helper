"""Invoice-level API endpoints."""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models.document import Document
from models.invoice import Invoice
from services.invoice_service import InvoiceService
from services.trip_service import TripService

router = APIRouter(tags=["invoices"])


class InvoiceUpdateRequest(BaseModel):
    reimbursement_status: Optional[str] = None
    include_in_summary: Optional[bool] = None
    confirmed_amount: Optional[float] = None
    review_status: Optional[str] = None
    note: Optional[str] = None
    expense_category: Optional[str] = None
    invoice_type: Optional[str] = None
    invoice_code: Optional[str] = None
    invoice_number: Optional[str] = None
    invoice_date: Optional[str] = None
    business_date: Optional[str] = None
    seller_name: Optional[str] = None
    buyer_name: Optional[str] = None
    total_amount: Optional[float] = None
    from_city: Optional[str] = None
    to_city: Optional[str] = None
    from_place: Optional[str] = None
    to_place: Optional[str] = None
    transport_no: Optional[str] = None
    depart_time_str: Optional[str] = None
    seat_class: Optional[str] = None
    hotel_name: Optional[str] = None
    checkin_date: Optional[str] = None
    checkout_date: Optional[str] = None
    nights: Optional[int] = None
    document_role: Optional[str] = None


class BulkInvoiceUpdateRequest(BaseModel):
    invoice_ids: list[int]
    updates: InvoiceUpdateRequest


class InvoiceResponse(BaseModel):
    id: int
    trip_id: int
    document_id: Optional[int] = None
    ocr_result_id: Optional[int] = None
    file_name: Optional[str] = None
    file_path: Optional[str] = None

    invoice_type: str
    expense_category: str
    invoice_code: Optional[str] = None
    invoice_number: Optional[str] = None
    invoice_date: Optional[date] = None

    seller_name: Optional[str] = None
    seller_tax_id: Optional[str] = None
    buyer_name: Optional[str] = None
    buyer_tax_id: Optional[str] = None

    item_name: Optional[str] = None
    service_name: Optional[str] = None

    amount_without_tax: Optional[float] = None
    tax_amount: Optional[float] = None
    total_amount: Optional[float] = None
    confirmed_amount: Optional[float] = None

    business_date: Optional[date] = None
    business_start_date: Optional[date] = None
    business_end_date: Optional[date] = None
    person_name: Optional[str] = None

    from_city: Optional[str] = None
    to_city: Optional[str] = None
    from_place: Optional[str] = None
    to_place: Optional[str] = None
    transport_no: Optional[str] = None
    depart_time_str: Optional[str] = None
    seat_class: Optional[str] = None

    hotel_name: Optional[str] = None
    checkin_date: Optional[date] = None
    checkout_date: Optional[date] = None
    nights: Optional[int] = None

    confidence: float
    parser_name: Optional[str] = None
    review_status: str
    reimbursement_status: str
    document_role: str
    include_in_summary: bool
    platform_name: Optional[str] = None
    booking_order_no: Optional[str] = None
    actual_hotel_name: Optional[str] = None
    order_total_amount: Optional[float] = None
    insurance_amount: Optional[float] = None
    ancillary_amount: Optional[float] = None
    flight_date: Optional[date] = None
    depart_airport: Optional[str] = None
    arrive_airport: Optional[str] = None
    airline_name: Optional[str] = None
    cabin_class: Optional[str] = None
    linked_invoice_id: Optional[int] = None
    note: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


def _to_response(db: Session, invoice: Invoice) -> InvoiceResponse:
    data = InvoiceResponse.model_validate(invoice)
    if invoice.document_id:
        doc = db.query(Document).filter(Document.id == invoice.document_id).first()
        if doc:
            data.file_name = doc.file_name
            data.file_path = doc.file_path
    return data


@router.get("/api/trips/{trip_id}/invoices", response_model=list[InvoiceResponse])
def list_trip_invoices(trip_id: int, db: Session = Depends(get_db)):
    trip = TripService.get_trip(db, trip_id)
    if trip is None:
        raise HTTPException(status_code=404, detail="Trip not found")

    invoices = InvoiceService.list_trip_invoices(db, trip_id)
    return [_to_response(db, invoice) for invoice in invoices]


@router.patch("/api/invoices/{invoice_id}", response_model=InvoiceResponse)
def update_invoice(invoice_id: int, data: InvoiceUpdateRequest, db: Session = Depends(get_db)):
    try:
        invoice = InvoiceService.update_invoice(
            db,
            invoice_id,
            data.model_dump(exclude_unset=True),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if invoice is None:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return _to_response(db, invoice)


@router.post("/api/trips/{trip_id}/invoices/bulk-update", response_model=list[InvoiceResponse])
def bulk_update_invoices(trip_id: int, data: BulkInvoiceUpdateRequest, db: Session = Depends(get_db)):
    trip = TripService.get_trip(db, trip_id)
    if trip is None:
        raise HTTPException(status_code=404, detail="Trip not found")

    try:
        invoices = InvoiceService.bulk_update_invoices(
            db,
            trip_id,
            data.invoice_ids,
            data.updates.model_dump(exclude_unset=True),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return [_to_response(db, invoice) for invoice in invoices]
