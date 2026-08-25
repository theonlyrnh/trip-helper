from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select

from app.infrastructure.db.models import Invoice, TravelSegment, Trip
from app.services.recognition import _flight_order_fields
from app.services.trips import rebuild_trip_projections


FLIGHT_ORDER_TEXT = """
订单详情
单程 4月7日 周二 南京-太原
15:15
禄口国际机场T2
深航ZH8585 | 经济舱 | 中型机737MAX8 |
1h50m
17:05
武宿国际机场T1
太原-南京 还没订返程？
总额 ¥1140
订单号 9489494072695
"""


def test_flight_order_fields_prioritize_the_itinerary_line() -> None:
    fields = _flight_order_fields(FLIGHT_ORDER_TEXT, reference_date=date(2026, 5, 14))

    assert fields["flight_date"] == date(2026, 4, 7)
    assert fields["business_date"] == date(2026, 4, 7)
    assert fields["from_city"] == "南京"
    assert fields["to_city"] == "太原"
    assert fields["from_place"] == "禄口国际机场T2"
    assert fields["to_place"] == "武宿国际机场T1"
    assert fields["depart_airport"] == "禄口国际机场T2"
    assert fields["arrive_airport"] == "武宿国际机场T1"
    assert fields["depart_time_str"] == "15:15"
    assert fields["transport_no"] == "ZH8585"
    assert fields["seat_class"] == "经济舱"
    assert fields["airline_name"] == "深航"
    assert fields["booking_order_no"] == "9489494072695"
    assert fields["order_total_amount"] == Decimal("1140")


def test_flight_order_proof_supersedes_incomplete_duplicate_ticket(web_runtime) -> None:
    client = web_runtime.client
    bootstrap = client.post(
        "/api/v1/auth/bootstrap",
        json={"email": "owner@example.test", "password": "correct-horse-battery-staple"},
    )
    assert bootstrap.status_code == 201, bootstrap.text
    created = client.post(
        "/api/v1/trips",
        headers={"X-CSRF-Token": bootstrap.json()["csrf_token"]},
        json={"title": "航班订单截图"},
    )
    assert created.status_code == 201, created.text

    session = web_runtime.session_factory()
    try:
        trip = session.get(Trip, created.json()["id"])
        assert trip is not None
        official = Invoice(
            trip_id=trip.id,
            invoice_type="FLIGHT_TICKET",
            expense_category="INTERCITY_TRANSPORT",
            business_date=date(2026, 4, 20),
            transport_no="ZH8585",
            total_amount=Decimal("1090"),
            confidence=0.9,
        )
        proof = Invoice(
            trip_id=trip.id,
            invoice_type="FLIGHT_ORDER_PROOF",
            expense_category="INTERCITY_TRANSPORT",
            business_date=date(2026, 4, 7),
            flight_date=date(2026, 4, 7),
            from_city="南京",
            to_city="太原",
            from_place="禄口国际机场T2",
            to_place="武宿国际机场T1",
            transport_no="ZH8585",
            depart_time_str="15:15",
            document_role="ORDER_SCREENSHOT",
            include_in_summary=False,
            confidence=0.85,
        )
        session.add_all((official, proof))
        session.flush()
        rebuild_trip_projections(session, trip)
        session.commit()

        segments = list(session.scalars(select(TravelSegment).where(TravelSegment.trip_id == trip.id)))
        assert len(segments) == 1
        segment = segments[0]
        assert segment.invoice_id == proof.id
        assert segment.depart_date == date(2026, 4, 7)
        assert segment.from_city == "南京"
        assert segment.to_city == "太原"
        assert trip.inferred_start_date == date(2026, 4, 7)
        assert trip.inferred_end_date == date(2026, 4, 7)
        assert trip.route_text == "南京 -> 太原"
    finally:
        session.close()
