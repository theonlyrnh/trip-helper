"""Review issue API endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from services.invoice_service import InvoiceService

router = APIRouter(prefix="/api/issues", tags=["issues"])


class IssueUpdateRequest(BaseModel):
    resolved: Optional[bool] = None
    ignored: Optional[bool] = None
    resolution_status: Optional[str] = None
    resolution_note: Optional[str] = None


class IssueUpdateResponse(BaseModel):
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
    resolved_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


@router.patch("/{issue_id}", response_model=IssueUpdateResponse)
def update_issue(issue_id: int, data: IssueUpdateRequest, db: Session = Depends(get_db)):
    issue = InvoiceService.update_issue(db, issue_id, data.model_dump(exclude_unset=True))
    if issue is None:
        raise HTTPException(status_code=404, detail="Issue not found")
    return issue
