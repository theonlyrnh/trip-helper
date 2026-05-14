"""Service layer for application settings."""

from decimal import Decimal
from sqlalchemy.orm import Session

from models.app_setting import AppSetting


class SettingsService:

    @staticmethod
    def get_settings(db: Session) -> AppSetting:
        """Get the singleton settings row, creating defaults if none exists."""
        setting = db.query(AppSetting).first()
        if setting is None:
            setting = AppSetting(
                daily_allowance=Decimal("180.00"),
                include_start_day=True,
                include_end_day=True,
                require_return_ticket=True,
                require_lodging_invoice=True,
                ocr_provider_mode="local_first",
            )
            db.add(setting)
            db.commit()
            db.refresh(setting)
        return setting

    @staticmethod
    def update_settings(db: Session, data: dict) -> AppSetting:
        """Update the singleton settings row."""
        setting = SettingsService.get_settings(db)

        updatable_fields = [
            "default_invoice_root_dir",
            "default_company_name",
            "default_company_tax_id",
            "default_traveler_name",
            "daily_allowance",
            "include_start_day",
            "include_end_day",
            "lodging_limit_per_day",
            "require_return_ticket",
            "require_lodging_invoice",
            "ocr_provider_mode",
            "paddleocr_api_url",
            "remote_api_base_url",
            "remote_api_key",
            "remote_model_name",
        ]

        for field in updatable_fields:
            if field in data:
                setattr(setting, field, data[field])

        db.commit()
        db.refresh(setting)
        return setting