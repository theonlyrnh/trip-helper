"""Settings API endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from database import get_db
from services.settings_service import SettingsService

router = APIRouter(prefix="/api/settings", tags=["settings"])


class SettingsResponse(BaseModel):
    id: int
    default_invoice_root_dir: Optional[str] = None
    default_company_name: Optional[str] = None
    default_company_tax_id: Optional[str] = None
    default_traveler_name: Optional[str] = None
    daily_allowance: float
    include_start_day: bool
    include_end_day: bool
    lodging_limit_per_day: Optional[float] = None
    require_return_ticket: bool
    require_lodging_invoice: bool
    ocr_provider_mode: str
    paddleocr_api_url: Optional[str] = None
    remote_api_base_url: Optional[str] = None
    remote_api_key: Optional[str] = None
    remote_model_name: Optional[str] = None

    model_config = {"from_attributes": True}


class SettingsUpdate(BaseModel):
    default_invoice_root_dir: Optional[str] = None
    default_company_name: Optional[str] = None
    default_company_tax_id: Optional[str] = None
    default_traveler_name: Optional[str] = None
    daily_allowance: Optional[float] = None
    include_start_day: Optional[bool] = None
    include_end_day: Optional[bool] = None
    lodging_limit_per_day: Optional[float] = None
    require_return_ticket: Optional[bool] = None
    require_lodging_invoice: Optional[bool] = None
    ocr_provider_mode: Optional[str] = None
    paddleocr_api_url: Optional[str] = None
    remote_api_base_url: Optional[str] = None
    remote_api_key: Optional[str] = None
    remote_model_name: Optional[str] = None


@router.get("", response_model=SettingsResponse)
def get_settings(db: Session = Depends(get_db)):
    setting = SettingsService.get_settings(db)
    return setting


@router.put("", response_model=SettingsResponse)
def update_settings(data: SettingsUpdate, db: Session = Depends(get_db)):
    update_dict = data.model_dump(exclude_unset=True)
    setting = SettingsService.update_settings(db, update_dict)
    return setting