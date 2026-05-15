"""Trip service – CRUD operations for Trip entities."""

import os
import re
from datetime import date
from sqlalchemy.orm import Session

from models.trip import Trip
from enums import TripStatus


class TripService:

    @staticmethod
    def create_trip(db: Session, title: str, folder_path: str,
                    traveler_name: str | None = None,
                    company_name: str | None = None,
                    project_type: str = "TRAVEL") -> Trip:
        """Create a new trip from a folder path."""
        folder_name = os.path.basename(folder_path.rstrip("/\\")) if folder_path else ""

        # Try to parse dates from folder name (e.g. "20260122-20260201")
        folder_start, folder_end = TripService._parse_folder_dates(folder_name)

        trip = Trip(
            title=title,
            folder_path=folder_path,
            folder_name=folder_name,
            traveler_name=traveler_name,
            company_name=company_name,
            folder_date_start=folder_start,
            folder_date_end=folder_end,
            confirmed_start_date=folder_start,
            confirmed_end_date=folder_end,
            trip_days=(folder_end - folder_start).days + 1 if folder_start and folder_end else None,
            project_type=project_type,
            status=TripStatus.CREATED,
        )
        db.add(trip)
        db.commit()
        db.refresh(trip)
        return trip

    @staticmethod
    def _parse_folder_dates(name: str) -> tuple[date | None, date | None]:
        """Extract date range from folder name.
        Supports: 20260122-20260201, 2026-01-22至2026-02-01, 26-01-22~26-02-01, 2026.01.22-2026.02.01
        """
        # Pattern 1: 20260122-20260201 (8-digit compact)
        m = re.search(r"(\d{8})[^\d]+(\d{8})", name)
        if m:
            try:
                d1 = date(int(m.group(1)[:4]), int(m.group(1)[4:6]), int(m.group(1)[6:8]))
                d2 = date(int(m.group(2)[:4]), int(m.group(2)[4:6]), int(m.group(2)[6:8]))
                return (d1, d2) if d1 <= d2 else (d2, d1)
            except ValueError:
                pass
        # Pattern 2: 2026-01-22 至 2026-02-01 or 2026.01.22-2026.02.01
        m = re.search(r"(\d{4})[.\-](\d{1,2})[.\-](\d{1,2})[^\d]+(\d{4})[.\-](\d{1,2})[.\-](\d{1,2})", name)
        if m:
            try:
                d1 = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
                d2 = date(int(m.group(4)), int(m.group(5)), int(m.group(6)))
                return (d1, d2) if d1 <= d2 else (d2, d1)
            except ValueError:
                pass
        return None, None

    @staticmethod
    def find_by_folder(db: Session, folder_path: str) -> Trip | None:
        """Find an existing trip by folder path."""
        normalized = folder_path.replace("\\", "/").rstrip("/")
        trips = db.query(Trip).all()
        for t in trips:
            if t.folder_path.replace("\\", "/").rstrip("/") == normalized:
                return t
        return None

    @staticmethod
    def get_trips(db: Session) -> list[Trip]:
        """Get all trips ordered by creation time descending."""
        return db.query(Trip).order_by(Trip.created_at.desc()).all()

    @staticmethod
    def get_trip(db: Session, trip_id: int) -> Trip | None:
        """Get a single trip by ID."""
        return db.query(Trip).filter(Trip.id == trip_id).first()

    @staticmethod
    def update_trip(db: Session, trip_id: int, data: dict) -> Trip | None:
        """Update trip fields."""
        trip = TripService.get_trip(db, trip_id)
        if trip is None:
            return None

        updatable = [
            "title", "folder_path", "traveler_name", "company_name", "company_tax_id",
            "confirmed_start_date", "confirmed_end_date",
            "daily_allowance", "status", "reimbursement_status", "project_type",
        ]
        for field in updatable:
            if field in data:
                setattr(trip, field, data[field])

        db.commit()
        db.refresh(trip)
        return trip

    @staticmethod
    def get_recent_trip(db: Session) -> Trip | None:
        """Get the most recently updated trip."""
        return db.query(Trip).order_by(Trip.updated_at.desc()).first()

    @staticmethod
    def delete_trip(db: Session, trip_id: int) -> bool:
        """Delete a trip and all related records (cascade)."""
        trip = TripService.get_trip(db, trip_id)
        if trip is None:
            return False
        db.delete(trip)
        db.commit()
        return True