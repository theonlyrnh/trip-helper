"""Annual reporting endpoints scoped to the authenticated account."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.infrastructure.db.models import User
from app.infrastructure.db.session import get_db
from app.schemas import YearlyDashboardRead
from app.services.dashboard import yearly_dashboard


router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/yearly", response_model=YearlyDashboardRead)
def get_yearly_dashboard(
    year: int | None = Query(default=None, ge=2000, le=2100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> YearlyDashboardRead:
    return yearly_dashboard(db, user, year)
