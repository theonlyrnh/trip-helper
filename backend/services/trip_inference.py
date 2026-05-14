"""Trip inference – date estimation and route generation."""

import re
from datetime import date, timedelta
from dataclasses import dataclass
from sqlalchemy.orm import Session

from models.trip import Trip
from models.travel_segment import TravelSegment
from models.lodging_stay import LodgingStay
from models.invoice import Invoice


@dataclass
class TripDateInference:
    start_date: date | None
    end_date: date | None
    days: int | None
    confidence: float
    evidence: list[str]


class TripInference:

    @staticmethod
    def infer_dates(db: Session, trip: Trip) -> TripDateInference:
        """
        Infer trip start/end dates from available evidence.

        Priority:
        1. Intercity transport dates
        2. Lodging check-in/check-out dates
        3. Folder name date range
        4. Invoice business dates
        5. Invoice dates
        """
        trip_id = trip.id

        # 1. Intercity transport dates
        travel_dates = TripInference._get_intercity_travel_dates(db, trip_id)
        if travel_dates:
            return TripDateInference(
                start_date=min(travel_dates),
                end_date=max(travel_dates),
                days=(max(travel_dates) - min(travel_dates)).days + 1,
                confidence=0.95,
                evidence=["使用城际交通票据的最早和最晚日期"],
            )

        # 2. Lodging dates
        lodging_ranges = TripInference._get_lodging_ranges(db, trip_id)
        if lodging_ranges:
            checkins = [r[0] for r in lodging_ranges if r[0]]
            checkouts = [r[1] for r in lodging_ranges if r[1]]
            if checkins and checkouts:
                return TripDateInference(
                    start_date=min(checkins),
                    end_date=max(checkouts),
                    days=(max(checkouts) - min(checkins)).days + 1,
                    confidence=0.85,
                    evidence=["使用住宿记录的入住和离店日期"],
                )

        # 3. Folder name date range
        folder_range = TripInference._parse_date_range_from_name(
            trip.folder_name
        )
        if folder_range:
            return TripDateInference(
                start_date=folder_range[0],
                end_date=folder_range[1],
                days=(folder_range[1] - folder_range[0]).days + 1,
                confidence=0.75,
                evidence=["使用文件夹名称中的日期"],
            )

        # 4. Invoice business dates
        business_dates = TripInference._get_invoice_business_dates(db, trip_id)
        if business_dates:
            return TripDateInference(
                start_date=min(business_dates),
                end_date=max(business_dates),
                days=(max(business_dates) - min(business_dates)).days + 1,
                confidence=0.60,
                evidence=["使用发票业务日期"],
            )

        # 5. Invoice dates (issue date)
        invoice_dates = TripInference._get_invoice_dates(db, trip_id)
        if invoice_dates:
            return TripDateInference(
                start_date=min(invoice_dates),
                end_date=max(invoice_dates),
                days=(max(invoice_dates) - min(invoice_dates)).days + 1,
                confidence=0.40,
                evidence=["使用开票日期，仅供参考"],
            )

        return TripDateInference(
            start_date=None,
            end_date=None,
            days=None,
            confidence=0.0,
            evidence=["无法自动推断出差日期"],
        )

    @staticmethod
    def generate_route(db: Session, trip_id: int) -> str | None:
        """Generate a route string from sorted travel segments."""
        segments = (
            db.query(TravelSegment)
            .filter(TravelSegment.trip_id == trip_id)
            .order_by(TravelSegment.depart_date)
            .all()
        )

        if not segments:
            return None

        cities: list[str] = []
        for seg in segments:
            if seg.from_city and (not cities or seg.from_city != cities[-1]):
                cities.append(seg.from_city)
            if seg.to_city and seg.to_city != cities[-1]:
                cities.append(seg.to_city)

        if not cities:
            return None

        return " → ".join(cities)

    # ── Private helpers ──────────────────────────────────────────

    @staticmethod
    def _get_intercity_travel_dates(db: Session, trip_id: int) -> list[date]:
        segments = (
            db.query(TravelSegment)
            .filter(
                TravelSegment.trip_id == trip_id,
                TravelSegment.transport_type.in_(["TRAIN", "FLIGHT"]),
                TravelSegment.depart_date.isnot(None),
            )
            .all()
        )
        return [s.depart_date for s in segments if s.depart_date]

    @staticmethod
    def _get_lodging_ranges(
        db: Session, trip_id: int
    ) -> list[tuple[date | None, date | None]]:
        stays = (
            db.query(LodgingStay)
            .filter(LodgingStay.trip_id == trip_id)
            .all()
        )
        return [(s.checkin_date, s.checkout_date) for s in stays]

    @staticmethod
    def _parse_date_range_from_name(
        name: str,
    ) -> tuple[date, date] | None:
        """Try to extract a date range from folder name like '20260407-20260418'."""
        pattern = re.compile(r"(\d{8})[^\d]+(\d{8})")
        m = pattern.search(name)
        if m:
            try:
                d1 = date(
                    int(m.group(1)[:4]),
                    int(m.group(1)[4:6]),
                    int(m.group(1)[6:8]),
                )
                d2 = date(
                    int(m.group(2)[:4]),
                    int(m.group(2)[4:6]),
                    int(m.group(2)[6:8]),
                )
                return (min(d1, d2), max(d1, d2))
            except ValueError:
                pass
        return None

    @staticmethod
    def _get_invoice_business_dates(db: Session, trip_id: int) -> list[date]:
        invoices = (
            db.query(Invoice)
            .filter(
                Invoice.trip_id == trip_id,
                Invoice.business_date.isnot(None),
            )
            .all()
        )
        return [i.business_date for i in invoices if i.business_date]

    @staticmethod
    def _get_invoice_dates(db: Session, trip_id: int) -> list[date]:
        invoices = (
            db.query(Invoice)
            .filter(
                Invoice.trip_id == trip_id,
                Invoice.invoice_date.isnot(None),
            )
            .all()
        )
        return [i.invoice_date for i in invoices if i.invoice_date]