from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import fitz


API = "/api/v1"
TEST_LOGIN_VALUE = "correct-horse-battery-staple"


def _pdf_bytes() -> bytes:
    document = fitz.open()
    page = document.new_page()
    page.insert_text(
        (72, 72),
        "Travel invoice fixture with embedded text for the asynchronous processing workflow.",
    )
    try:
        return document.tobytes()
    finally:
        document.close()


def _bootstrap(client, email: str = "owner@example.test") -> str:
    response = client.post(
        f"{API}/auth/bootstrap",
        json={"email": email, "password": TEST_LOGIN_VALUE},
    )
    assert response.status_code == 201, response.text
    return response.json()["csrf_token"]


def _headers(csrf_token: str) -> dict[str, str]:
    return {"X-CSRF-Token": csrf_token}


def _create_trip(client, csrf_token: str, title: str = "API test trip") -> dict[str, Any]:
    response = client.post(
        f"{API}/trips",
        headers=_headers(csrf_token),
        json={"title": title, "source_label": "browser upload"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _upload_pdf(client, trip_id: str, csrf_token: str) -> dict[str, Any]:
    response = client.post(
        f"{API}/trips/{trip_id}/uploads",
        headers=_headers(csrf_token),
        data={"relative_path": "receipts/invoice.pdf"},
        files={
            "file": (
                r"C:\\Users\\alice\\Documents\\invoice.pdf",
                _pdf_bytes(),
                "application/pdf",
            )
        },
    )
    assert response.status_code == 202, response.text
    return response.json()


def _seed_user(web_runtime: Any, email: str, password: str = TEST_LOGIN_VALUE) -> None:
    from app.core.security import hash_password
    from app.infrastructure.db.models import User

    session = web_runtime.session_factory()
    try:
        session.add(User(email=email, password_hash=hash_password(password)))
        session.commit()
    finally:
        session.close()


def test_bootstrap_login_and_csrf_protect_writes(web_runtime: Any) -> None:
    client = web_runtime.client
    csrf_token = _bootstrap(client)

    assert client.get(f"{API}/auth/me").status_code == 200
    assert client.post(f"{API}/trips", json={"title": "blocked"}).status_code == 403
    assert _create_trip(client, csrf_token)["title"] == "API test trip"

    logout = client.post(f"{API}/auth/logout", headers=_headers(csrf_token))
    assert logout.status_code == 204
    assert client.get(f"{API}/auth/me").status_code == 401

    login = client.post(
        f"{API}/auth/login",
        json={"email": "owner@example.test", "password": TEST_LOGIN_VALUE},
    )
    assert login.status_code == 200, login.text
    assert login.json()["user"]["email"] == "owner@example.test"
    assert login.json()["csrf_token"] != csrf_token


def test_regular_username_with_six_character_password_can_log_in(web_runtime: Any) -> None:
    client = web_runtime.client
    owner_csrf = _bootstrap(client)
    _seed_user(web_runtime, "lyk", "990202")

    assert client.post(f"{API}/auth/logout", headers=_headers(owner_csrf)).status_code == 204
    login = client.post(
        f"{API}/auth/login",
        json={"email": "lyk", "password": "990202"},
    )

    assert login.status_code == 200, login.text
    assert login.json()["user"]["email"] == "lyk"
    assert login.json()["user"]["is_admin"] is False


def test_owner_isolation_hides_trips_documents_and_jobs(web_runtime: Any) -> None:
    from sqlalchemy import select

    from app.infrastructure.db.models import Export, Invoice, ReviewIssue, User

    client = web_runtime.client
    owner_csrf = _bootstrap(client)
    trip = _create_trip(client, owner_csrf)
    upload = _upload_pdf(client, trip["id"], owner_csrf)
    document_id = upload["document"]["id"]
    job_id = upload["job_id"]

    update_trip = client.patch(
        f"{API}/trips/{trip['id']}",
        headers=_headers(owner_csrf),
        json={"input_start_date": "2026-08-22", "input_end_date": "2026-08-22"},
    )
    assert update_trip.status_code == 200, update_trip.text
    update_settings = client.patch(
        f"{API}/settings",
        headers=_headers(owner_csrf),
        json={"default_company_name": "Owner-only company"},
    )
    assert update_settings.status_code == 200, update_settings.text

    session = web_runtime.session_factory()
    try:
        owner = session.scalar(select(User).where(User.email == "owner@example.test"))
        assert owner is not None
        invoice = Invoice(
            trip_id=trip["id"],
            invoice_type="GENERAL_INVOICE",
            expense_category="OTHER",
        )
        issue = ReviewIssue(
            trip_id=trip["id"],
            issue_type="OWNER_ONLY_FIXTURE",
            rule_fingerprint="owner-only-isolation-fixture",
            message="owner-only issue",
        )
        export = Export(
            owner_id=owner.id,
            trip_id=trip["id"],
            format="XLSX",
            status="SUCCEEDED",
            storage_key="exports/owner-only.xlsx",
            original_filename="owner-only.xlsx",
        )
        session.add_all((invoice, issue, export))
        session.commit()
        invoice_id = invoice.id
        issue_id = issue.id
        export_id = export.id
    finally:
        session.close()

    owner_dashboard = client.get(f"{API}/dashboard/yearly?year=2026")
    assert owner_dashboard.status_code == 200
    assert owner_dashboard.json()["total_project_count"] == 1

    _seed_user(web_runtime, "other@example.test")
    assert client.post(f"{API}/auth/logout", headers=_headers(owner_csrf)).status_code == 204
    login = client.post(
        f"{API}/auth/login",
        json={"email": "other@example.test", "password": TEST_LOGIN_VALUE},
    )
    assert login.status_code == 200, login.text
    other_csrf = login.json()["csrf_token"]

    assert client.get(f"{API}/trips").json() == []
    assert client.get(f"{API}/trips/{trip['id']}").status_code == 404
    assert client.patch(
        f"{API}/trips/{trip['id']}",
        headers=_headers(other_csrf),
        json={"title": "cross-account write"},
    ).status_code == 404
    assert client.delete(
        f"{API}/trips/{trip['id']}",
        headers=_headers(other_csrf),
    ).status_code == 404
    assert client.get(f"{API}/trips/{trip['id']}/documents").status_code == 404
    assert client.get(f"{API}/documents/{document_id}/content").status_code == 404
    assert client.get(f"{API}/documents/{document_id}/preview").status_code == 404
    assert client.get(f"{API}/jobs/{job_id}").status_code == 404
    assert client.get(f"{API}/trips/{trip['id']}/invoices").status_code == 404
    assert client.patch(
        f"{API}/invoices/{invoice_id}",
        headers=_headers(other_csrf),
        json={"note": "cross-account write"},
    ).status_code == 404
    assert client.get(f"{API}/trips/{trip['id']}/issues").status_code == 404
    assert client.patch(
        f"{API}/issues/{issue_id}",
        headers=_headers(other_csrf),
        json={"resolution_status": "RESOLVED"},
    ).status_code == 404
    assert client.get(f"{API}/trips/{trip['id']}/exports").status_code == 404
    assert client.post(
        f"{API}/trips/{trip['id']}/exports",
        headers=_headers(other_csrf),
        json={"format": "XLSX"},
    ).status_code == 404
    assert client.get(f"{API}/exports/{export_id}/download").status_code == 404

    other_settings = client.get(f"{API}/settings")
    assert other_settings.status_code == 200
    assert other_settings.json()["default_company_name"] is None
    other_dashboard = client.get(f"{API}/dashboard/yearly?year=2026")
    assert other_dashboard.status_code == 200
    assert other_dashboard.json()["total_project_count"] == 0
    assert other_dashboard.json()["recent_projects"] == []


def test_pdf_upload_uses_authorized_streams_without_path_leaks(web_runtime: Any) -> None:
    client = web_runtime.client
    csrf_token = _bootstrap(client)
    trip = _create_trip(client, csrf_token)
    upload = _upload_pdf(client, trip["id"], csrf_token)
    document = upload["document"]

    assert document["original_filename"] == "invoice.pdf"
    assert document["relative_path"] == "receipts/invoice.pdf"
    assert {"file_path", "storage_key", "preview_image_path", "thumbnail_path"}.isdisjoint(document)
    serialized = str(upload)
    assert str(web_runtime.storage_root) not in serialized
    assert "C:\\Users\\alice" not in serialized

    content = client.get(f"{API}/documents/{document['id']}/content")
    assert content.status_code == 200
    assert content.headers["content-type"].startswith("application/pdf")
    assert content.content.startswith(b"%PDF-")

    preview = client.get(f"{API}/documents/{document['id']}/preview")
    assert preview.status_code == 200
    assert preview.headers["content-type"].startswith("image/png")
    assert preview.content.startswith(b"\x89PNG")


def test_delete_trip_removes_owned_records_and_persistent_objects(web_runtime: Any) -> None:
    from sqlalchemy import select

    from app.infrastructure.db.models import AuditEvent, Document, DocumentPage, Export, Trip
    from app.infrastructure.storage.local import LocalStorage

    client = web_runtime.client
    csrf_token = _bootstrap(client)
    trip = _create_trip(client, csrf_token, "待删除项目")
    _upload_pdf(client, trip["id"], csrf_token)

    storage = LocalStorage(root=web_runtime.storage_root)
    export_key = storage.new_key("exports", ".xlsx")
    storage.put_bytes(b"export fixture", export_key)
    session = web_runtime.session_factory()
    try:
        owned_trip = session.get(Trip, trip["id"])
        assert owned_trip is not None
        session.add(
            Export(
                owner_id=owned_trip.owner_id,
                trip_id=owned_trip.id,
                format="XLSX",
                status="SUCCEEDED",
                storage_key=export_key,
                original_filename="trip.xlsx",
            )
        )
        session.commit()
        document = session.scalar(select(Document).where(Document.trip_id == trip["id"]))
        assert document is not None
        pages = list(session.scalars(select(DocumentPage).where(DocumentPage.document_id == document.id)))
        object_keys = [document.storage_key, export_key]
        object_keys.extend(key for page in pages for key in (page.preview_key, page.thumbnail_key) if key)
    finally:
        session.close()

    assert all(storage.exists(key) for key in set(object_keys))
    assert client.delete(f"{API}/trips/{trip['id']}").status_code == 403

    response = client.delete(f"{API}/trips/{trip['id']}", headers=_headers(csrf_token))
    assert response.status_code == 204, response.text
    assert client.get(f"{API}/trips/{trip['id']}").status_code == 404
    assert all(not storage.exists(key) for key in set(object_keys))

    session = web_runtime.session_factory()
    try:
        assert session.get(Trip, trip["id"]) is None
        audit = session.scalar(
            select(AuditEvent).where(
                AuditEvent.action == "TRIP_DELETE",
                AuditEvent.resource_id == trip["id"],
            )
        )
        assert audit is not None
    finally:
        session.close()


def test_manual_amount_refreshes_summary_and_exposes_durable_job_state(web_runtime: Any) -> None:
    client = web_runtime.client
    csrf_token = _bootstrap(client)
    trip = _create_trip(client, csrf_token)
    upload = _upload_pdf(client, trip["id"], csrf_token)
    job_id = upload["job_id"]

    job = client.get(f"{API}/jobs/{job_id}")
    assert job.status_code == 200
    assert job.json()["kind"] == "PROCESS_DOCUMENT"
    assert job.json()["state"] == "SUCCEEDED"

    jobs = client.get(f"{API}/trips/{trip['id']}/jobs")
    assert jobs.status_code == 200
    assert any(item["id"] == job_id for item in jobs.json())

    invoices = client.get(f"{API}/trips/{trip['id']}/invoices")
    assert invoices.status_code == 200
    assert len(invoices.json()) == 1
    invoice = invoices.json()[0]

    update = client.patch(
        f"{API}/invoices/{invoice['id']}",
        headers=_headers(csrf_token),
        json={
            "confirmed_amount": "88.50",
            "reimbursement_status": "THIS_TRIP",
            "include_in_summary": True,
            "version": invoice["version"],
        },
    )
    assert update.status_code == 200, update.text
    assert update.json()["review_status"] == "MANUALLY_CONFIRMED"

    summary = client.get(f"{API}/trips/{trip['id']}/summary")
    assert summary.status_code == 200
    assert float(summary.json()["invoice_total_amount"]) == 88.5
    assert float(summary.json()["grand_total_amount"]) == 88.5


def test_marking_a_project_reimbursed_updates_all_reimbursable_invoices_once(web_runtime: Any) -> None:
    from sqlalchemy import select

    from app.infrastructure.db.models import AuditEvent, Invoice, Trip
    from app.services.trips import rebuild_trip_projections

    client = web_runtime.client
    csrf_token = _bootstrap(client)
    created = _create_trip(client, csrf_token, "项目级报销状态")

    session = web_runtime.session_factory()
    try:
        trip = session.get(Trip, created["id"])
        assert trip is not None
        reimbursable = Invoice(
            trip_id=trip.id,
            invoice_type="TRAIN_TICKET",
            expense_category="INTERCITY_TRANSPORT",
            total_amount=Decimal("288.00"),
            confirmed_amount=Decimal("288.00"),
            reimbursement_status="THIS_TRIP",
            include_in_summary=True,
        )
        supporting = Invoice(
            trip_id=trip.id,
            invoice_type="FLIGHT_ORDER_PROOF",
            expense_category="INTERCITY_TRANSPORT",
            document_role="ORDER_SCREENSHOT",
            reimbursement_status="THIS_TRIP",
            include_in_summary=False,
        )
        session.add_all((reimbursable, supporting))
        session.flush()
        rebuild_trip_projections(session, trip)
        session.commit()
        reimbursable_id = reimbursable.id
        supporting_id = supporting.id
    finally:
        session.close()

    before = client.get(f"{API}/trips/{created['id']}")
    assert before.status_code == 200, before.text
    assert before.json()["reimbursement_status"] == "THIS_TRIP"

    response = client.post(f"{API}/trips/{created['id']}/mark-reimbursed", headers=_headers(csrf_token))
    assert response.status_code == 200, response.text
    assert response.json()["reimbursement_status"] == "ALREADY_REIMBURSED"
    assert float(response.json()["invoice_total_amount"]) == 288
    assert float(response.json()["summary"]["grand_total_amount"]) == 288
    assert float(response.json()["summary"]["reimbursement_total_amount"]) == 0
    assert float(response.json()["summary"]["reimbursed_total_amount"]) == 288

    session = web_runtime.session_factory()
    try:
        reimbursable = session.get(Invoice, reimbursable_id)
        supporting = session.get(Invoice, supporting_id)
        assert reimbursable is not None
        assert supporting is not None
        assert reimbursable.reimbursement_status == "ALREADY_REIMBURSED"
        assert reimbursable.include_in_summary is False
        assert supporting.reimbursement_status == "THIS_TRIP"
        audit = session.scalar(
            select(AuditEvent).where(
                AuditEvent.action == "TRIP_MARK_REIMBURSED",
                AuditEvent.resource_id == created["id"],
            )
        )
        assert audit is not None
        assert audit.metadata_json == {"updated_invoice_count": 1}
    finally:
        session.close()


def test_document_detail_keeps_transport_and_lodging_review_fields(web_runtime: Any) -> None:
    client = web_runtime.client
    csrf_token = _bootstrap(client)
    trip = _create_trip(client, csrf_token)
    upload = _upload_pdf(client, trip["id"], csrf_token)
    invoice = client.get(f"{API}/trips/{trip['id']}/invoices").json()[0]

    update = client.patch(
        f"{API}/invoices/{invoice['id']}",
        headers=_headers(csrf_token),
        json={
            "from_city": "北京",
            "to_city": "上海",
            "from_place": "北京南站",
            "to_place": "上海虹桥站",
            "transport_no": "G123",
            "depart_time_str": "08:30",
            "seat_class": "二等座",
            "hotel_name": "示例酒店",
            "checkin_date": "2026-07-01",
            "checkout_date": "2026-07-03",
            "nights": 2,
        },
    )
    assert update.status_code == 200, update.text

    document = client.get(f"{API}/trips/{trip['id']}/documents").json()[0]
    nested = document["invoice"]
    assert nested["from_city"] == "北京"
    assert nested["to_city"] == "上海"
    assert nested["from_place"] == "北京南站"
    assert nested["to_place"] == "上海虹桥站"
    assert nested["transport_no"] == "G123"
    assert nested["depart_time_str"] == "08:30"
    assert nested["seat_class"] == "二等座"
    assert nested["hotel_name"] == "示例酒店"
    assert nested["checkin_date"] == "2026-07-01"
    assert nested["checkout_date"] == "2026-07-03"
    assert nested["nights"] == 2


def test_project_metadata_and_uploaded_directory_restore_legacy_date_inference(web_runtime: Any) -> None:
    client = web_runtime.client
    csrf_token = _bootstrap(client)
    created = client.post(
        f"{API}/trips",
        headers=_headers(csrf_token),
        json={"title": "上海客户拜访", "source_label": "2026.04.07 至 2026.04.18"},
    )
    assert created.status_code == 201, created.text
    metadata_trip = created.json()
    assert metadata_trip["inferred_start_date"] == "2026-04-07"
    assert metadata_trip["inferred_end_date"] == "2026-04-18"
    assert metadata_trip["trip_days"] == 12
    assert metadata_trip["date_evidence"] == ["使用项目来源标签中的日期"]

    trip = _create_trip(client, csrf_token, "目录日期示例")
    upload = client.post(
        f"{API}/trips/{trip['id']}/uploads",
        headers=_headers(csrf_token),
        data={"relative_path": "20260407-20260418/receipts/invoice.pdf"},
        files={"file": ("invoice.pdf", _pdf_bytes(), "application/pdf")},
    )
    assert upload.status_code == 202, upload.text
    inferred = client.get(f"{API}/trips/{trip['id']}")
    assert inferred.status_code == 200, inferred.text
    assert inferred.json()["inferred_start_date"] == "2026-04-07"
    assert inferred.json()["inferred_end_date"] == "2026-04-18"
    assert inferred.json()["date_evidence"] == ["使用上传目录中的日期"]


def test_manual_trip_dates_rebuild_allowance_and_clear_missing_date_issue(web_runtime: Any) -> None:
    client = web_runtime.client
    csrf_token = _bootstrap(client)
    trip = _create_trip(client, csrf_token, "手动日期示例")

    updated = client.patch(
        f"{API}/trips/{trip['id']}",
        headers=_headers(csrf_token),
        json={
            "confirmed_start_date": "2026-07-01",
            "confirmed_end_date": "2026-07-03",
            "daily_allowance": "100.00",
        },
    )
    assert updated.status_code == 200, updated.text
    body = updated.json()
    assert body["confirmed_start_date"] == "2026-07-01"
    assert body["confirmed_end_date"] == "2026-07-03"
    assert body["start_date"] == "2026-07-01"
    assert body["end_date"] == "2026-07-03"
    assert body["trip_days"] == 3
    assert float(body["allowance_amount"]) == 300
    issues = client.get(f"{API}/trips/{trip['id']}/issues").json()
    assert len(issues) == 1
    assert issues[0]["issue_type"] == "CANNOT_INFER_DATES"
    assert issues[0]["resolution_status"] == "AUTO_CLEARED"
    assert issues[0]["resolved"] is True


def test_route_segments_expose_rebuilt_transport_details_to_the_owned_project(web_runtime: Any) -> None:
    client = web_runtime.client
    csrf_token = _bootstrap(client)
    trip = _create_trip(client, csrf_token, "路线示例")
    _upload_pdf(client, trip["id"], csrf_token)
    invoice = client.get(f"{API}/trips/{trip['id']}/invoices").json()[0]

    update = client.patch(
        f"{API}/invoices/{invoice['id']}",
        headers=_headers(csrf_token),
        json={
            "invoice_type": "TRAIN_TICKET",
            "expense_category": "INTERCITY_TRANSPORT",
            "business_date": "2026-07-02",
            "from_city": "北京",
            "to_city": "上海",
            "from_place": "北京南站",
            "to_place": "上海虹桥站",
            "transport_no": "G123",
            "depart_time_str": "08:30",
            "seat_class": "二等座",
            "confirmed_amount": "553.00",
            "reimbursement_status": "THIS_TRIP",
            "include_in_summary": True,
        },
    )
    assert update.status_code == 200, update.text

    response = client.get(f"{API}/trips/{trip['id']}/route-segments")
    assert response.status_code == 200, response.text
    segments = response.json()
    assert len(segments) == 1
    segment = segments[0]
    assert segment["trip_id"] == trip["id"]
    assert segment["invoice_id"] == invoice["id"]
    assert segment["transport_type"] == "TRAIN"
    assert segment["depart_date"] == "2026-07-02"
    assert segment["depart_time"] == "08:30"
    assert segment["from_city"] == "北京"
    assert segment["to_city"] == "上海"
    assert segment["from_place"] == "北京南站"
    assert segment["to_place"] == "上海虹桥站"
    assert segment["transport_no"] == "G123"
    assert segment["seat_class"] == "二等座"
    assert float(segment["amount"]) == 553


def test_route_summary_and_timeline_order_same_day_connecting_tickets_by_departure_time(web_runtime: Any) -> None:
    """OCR completion order must not change the apparent departure city."""
    from app.infrastructure.db.models import Invoice, Trip
    from app.services.trips import rebuild_trip_projections

    client = web_runtime.client
    csrf_token = _bootstrap(client)
    created = _create_trip(client, csrf_token, "北京开会")
    session = web_runtime.session_factory()
    try:
        trip = session.get(Trip, created["id"])
        assert trip is not None
        # Deliberately add these in the inverse of their travel chronology, as
        # asynchronous OCR workers may complete them in this order.
        for from_city, to_city, depart_time in (
            ("济南西", "北京南", "21:36"),
            ("蚌埠南", "济南西", "19:15"),
            ("南京南", "蚌埠南", "18:31"),
            ("北京南", "南京南", "18:00"),
        ):
            session.add(
                Invoice(
                    trip_id=trip.id,
                    invoice_type="TRAIN_TICKET",
                    expense_category="INTERCITY_TRANSPORT",
                    business_date=date(2026, 7, 11 if from_city != "北京南" else 15),
                    depart_time_str=depart_time,
                    from_city=from_city,
                    to_city=to_city,
                )
            )
        session.flush()
        rebuild_trip_projections(session, trip)
        session.commit()
    finally:
        session.close()

    trip_response = client.get(f"{API}/trips/{created['id']}")
    assert trip_response.status_code == 200, trip_response.text
    assert trip_response.json()["route_text"] == "南京南 -> 蚌埠南 -> 济南西 -> 北京南 -> 南京南"

    segments_response = client.get(f"{API}/trips/{created['id']}/route-segments")
    assert segments_response.status_code == 200, segments_response.text
    assert [segment["from_city"] for segment in segments_response.json()] == [
        "南京南",
        "蚌埠南",
        "济南西",
        "北京南",
    ]


def test_yearly_dashboard_counts_each_connected_route_stop_once(web_runtime: Any) -> None:
    """A transfer station is one visit, not an arrival plus a second departure."""
    from app.infrastructure.db.models import Invoice, Trip
    from app.services.trips import rebuild_trip_projections

    client = web_runtime.client
    csrf_token = _bootstrap(client)
    created = _create_trip(client, csrf_token, "华东客户拜访")
    session = web_runtime.session_factory()
    try:
        trip = session.get(Trip, created["id"])
        assert trip is not None
        # Reverse insertion order mirrors asynchronous OCR completion.  The
        # dashboard must still use the chronological route-stop sequence.
        for from_city, to_city, depart_time in (
            ("北京南", "南京南", "21:00"),
            ("徐州东", "北京南", "20:00"),
            ("蚌埠南", "徐州东", "19:00"),
            ("南京南", "蚌埠南", "18:00"),
        ):
            session.add(
                Invoice(
                    trip_id=trip.id,
                    invoice_type="TRAIN_TICKET",
                    expense_category="INTERCITY_TRANSPORT",
                    business_date=date(2026, 7, 11),
                    depart_time_str=depart_time,
                    from_city=from_city,
                    to_city=to_city,
                )
            )
        session.flush()
        rebuild_trip_projections(session, trip)
        session.commit()
    finally:
        session.close()

    response = client.get(f"{API}/dashboard/yearly?year=2026")
    assert response.status_code == 200, response.text
    city_counts = {item["city"]: item["count"] for item in response.json()["city_summary"]}
    assert city_counts == {
        "南京南": 2,
        "蚌埠南": 1,
        "徐州东": 1,
        "北京南": 1,
    }


def test_yearly_dashboard_restores_owned_annual_trip_details(web_runtime: Any) -> None:
    """Annual reporting uses current Web records and never crosses account boundaries."""
    from sqlalchemy import select

    from app.infrastructure.db.models import Invoice, Trip, User
    from app.services.trips import rebuild_trip_projections

    client = web_runtime.client
    _bootstrap(client)
    session = web_runtime.session_factory()
    try:
        owner = session.scalar(select(User).where(User.email == "owner@example.test"))
        assert owner is not None
        other = User(email="annual-other@example.test", password_hash="not-used-by-this-test")
        session.add(other)
        session.flush()

        travel = Trip(
            owner_id=owner.id,
            title="北京客户拜访",
            project_type="TRAVEL",
            confirmed_start_date=date(2026, 7, 11),
            confirmed_end_date=date(2026, 7, 15),
            daily_allowance=Decimal("100.00"),
        )
        daily = Trip(
            owner_id=owner.id,
            title="七月日常采购",
            project_type="DAILY",
            confirmed_start_date=date(2026, 7, 20),
            confirmed_end_date=date(2026, 7, 20),
            daily_allowance=Decimal("100.00"),
        )
        hidden = Trip(
            owner_id=other.id,
            title="其他账号项目",
            project_type="TRAVEL",
            confirmed_start_date=date(2026, 7, 1),
            confirmed_end_date=date(2026, 7, 2),
            daily_allowance=Decimal("100.00"),
        )
        session.add_all((travel, daily, hidden))
        session.flush()
        session.add_all(
            (
                Invoice(
                    trip_id=travel.id,
                    invoice_type="TRAIN_TICKET",
                    expense_category="INTERCITY_TRANSPORT",
                    business_date=date(2026, 7, 11),
                    depart_time_str="08:30",
                    from_city="南京",
                    to_city="北京",
                    total_amount=Decimal("120.00"),
                    confirmed_amount=Decimal("120.00"),
                    reimbursement_status="THIS_TRIP",
                    include_in_summary=True,
                ),
                Invoice(
                    trip_id=travel.id,
                    invoice_type="HOTEL_INVOICE",
                    expense_category="LODGING",
                    total_amount=Decimal("80.00"),
                    confirmed_amount=Decimal("80.00"),
                    reimbursement_status="THIS_TRIP",
                    include_in_summary=True,
                ),
                Invoice(
                    trip_id=travel.id,
                    invoice_type="GENERAL_INVOICE",
                    expense_category="OTHER",
                    total_amount=Decimal("50.00"),
                    confirmed_amount=Decimal("50.00"),
                    reimbursement_status="ALREADY_REIMBURSED",
                    include_in_summary=False,
                ),
                Invoice(
                    trip_id=daily.id,
                    invoice_type="MEAL_INVOICE",
                    expense_category="MEAL",
                    total_amount=Decimal("20.00"),
                    confirmed_amount=Decimal("20.00"),
                    reimbursement_status="THIS_TRIP",
                    include_in_summary=True,
                ),
                Invoice(
                    trip_id=hidden.id,
                    invoice_type="GENERAL_INVOICE",
                    expense_category="OTHER",
                    total_amount=Decimal("999.00"),
                    confirmed_amount=Decimal("999.00"),
                    reimbursement_status="THIS_TRIP",
                    include_in_summary=True,
                ),
            )
        )
        session.flush()
        for trip in (travel, daily, hidden):
            rebuild_trip_projections(session, trip)
        session.commit()
    finally:
        session.close()

    response = client.get(f"{API}/dashboard/yearly?year=2026")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["year"] == 2026
    assert body["available_years"] == [2026]
    assert body["total_project_count"] == 2
    assert body["travel_project_count"] == 1
    assert body["daily_project_count"] == 1
    assert body["total_trip_days"] == 6
    assert float(body["total_invoice_amount"]) == 270
    assert float(body["total_income_amount"]) == 500
    assert "total_with_allowance" not in body
    assert float(body["reimbursed_amount"]) == 50
    assert float(body["unreimbursed_amount"]) == 720
    assert body["monthly_trends"][6] == {
        "month": 7,
        "project_count": 2,
        "invoice_amount": "270.00",
        "allowance_amount": "500.00",
    }
    assert float(body["category_summary"]["intercity_transport_amount"]) == 120
    assert float(body["category_summary"]["lodging_amount"]) == 80
    assert float(body["category_summary"]["meal_amount"]) == 20
    assert float(body["category_summary"]["other_amount"]) == 50
    assert body["city_summary"] == [{"city": "北京", "count": 1}, {"city": "南京", "count": 1}]
    assert body["reimbursement_summary"] == {
        "THIS_TRIP": 1,
        "ALREADY_REIMBURSED": 0,
        "PARTIAL_REIMBURSED": 1,
        "NOT_REIMBURSED": 0,
        "PENDING": 0,
    }
    assert {project["title"] for project in body["recent_projects"]} == {"北京客户拜访", "七月日常采购"}
    assert next(project for project in body["recent_projects"] if project["title"] == "北京客户拜访")["route_text"] == "南京 -> 北京"
