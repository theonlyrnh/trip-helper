"""Per-user business settings; internal OCR configuration never leaves this API."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_csrf
from app.infrastructure.db.models import Trip, User
from app.infrastructure.db.session import get_db
from app.schemas import UserSettingsRead, UserSettingsUpdate
from app.services.audit import record_audit
from app.services.trips import default_settings_for_user


router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=UserSettingsRead)
def get_settings(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> UserSettingsRead:
    user_settings = default_settings_for_user(db, user.id)
    db.commit()
    db.refresh(user_settings)
    return UserSettingsRead.model_validate(user_settings)


@router.patch("", response_model=UserSettingsRead, dependencies=[Depends(require_csrf)])
def patch_settings(payload: UserSettingsUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> UserSettingsRead:
    user_settings = default_settings_for_user(db, user.id)
    changed = payload.model_dump(exclude_unset=True)
    for field, value in changed.items():
        setattr(user_settings, field, value)
    if {
        "daily_allowance",
        "include_start_day",
        "include_end_day",
        "lodging_limit_per_day",
        "require_return_ticket",
        "require_lodging_invoice",
    }.intersection(changed):
        for trip in db.scalars(select(Trip).where(Trip.owner_id == user.id)):
            trip.daily_allowance = user_settings.daily_allowance
            trip.include_start_day = user_settings.include_start_day
            trip.include_end_day = user_settings.include_end_day
            trip.lodging_limit_per_day = user_settings.lodging_limit_per_day
            trip.require_return_ticket = user_settings.require_return_ticket
            trip.require_lodging_invoice = user_settings.require_lodging_invoice
    record_audit(db, actor_id=user.id, action="SETTINGS_UPDATE", resource_type="user_settings", resource_id=user_settings.id)
    db.commit()
    db.refresh(user_settings)
    return UserSettingsRead.model_validate(user_settings)


@router.put("", response_model=UserSettingsRead, dependencies=[Depends(require_csrf)])
def put_settings(payload: UserSettingsUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> UserSettingsRead:
    return patch_settings(payload, db, user)
