from __future__ import annotations

from decimal import Decimal
from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from database import Base, get_db  # noqa: E402
from main import app  # noqa: E402
from models.trip import Trip  # noqa: E402
from models.document import Document  # noqa: E402
from models.invoice import Invoice  # noqa: E402
from enums import ReimbursementStatus, ExpenseCategory  # noqa: E402


@pytest.fixture()
def client(tmp_path, monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
        expire_on_commit=False,
    )
    monkeypatch.setattr("exporters.excel_exporter.settings.EXPORT_DIR", str(tmp_path))

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        # Do not use TestClient as a context manager here: the app startup hook
        # initializes the default local SQLite file. These route tests override
        # get_db and only need request handling against the in-memory engine.
        yield TestClient(app), SessionLocal
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def seed_invoice(db, *, amount="100.00"):
    trip = Trip(title="API 测试", folder_path="D:/tmp", folder_name="tmp", project_type="DAILY")
    db.add(trip)
    db.commit()
    db.refresh(trip)
    doc = Document(trip_id=trip.id, file_name="invoice.pdf", file_path="D:/tmp/invoice.pdf", file_ext=".pdf")
    db.add(doc)
    db.commit()
    db.refresh(doc)
    invoice = Invoice(
        trip_id=trip.id,
        document_id=doc.id,
        invoice_type="GENERAL_INVOICE",
        expense_category=ExpenseCategory.MEAL,
        total_amount=Decimal(amount),
        reimbursement_status=ReimbursementStatus.THIS_TRIP,
        include_in_summary=True,
        document_role="OFFICIAL_INVOICE",
        confidence=1.0,
    )
    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    return trip, invoice


def test_invoice_patch_and_bulk_update_routes_refresh_summary(client):
    test_client, SessionLocal = client
    db = SessionLocal()
    trip, invoice = seed_invoice(db)
    trip_id = trip.id
    invoice_id = invoice.id
    db.close()

    patch_response = test_client.patch(
        f"/api/invoices/{invoice_id}",
        json={"confirmed_amount": 66.66, "reimbursement_status": "THIS_TRIP"},
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["confirmed_amount"] == 66.66

    summary_response = test_client.get(f"/api/trips/{trip_id}/summary")
    assert summary_response.status_code == 200
    assert summary_response.json()["invoice_total_amount"] == 66.66

    bulk_response = test_client.post(
        f"/api/trips/{trip_id}/invoices/bulk-update",
        json={"invoice_ids": [invoice_id], "updates": {"reimbursement_status": "PENDING"}},
    )
    assert bulk_response.status_code == 200
    assert bulk_response.json()[0]["include_in_summary"] is False

    summary_response = test_client.get(f"/api/trips/{trip_id}/summary")
    assert summary_response.json()["invoice_total_amount"] == 0.0


def test_excel_export_route_returns_download_file(client):
    test_client, SessionLocal = client
    db = SessionLocal()
    trip, _invoice = seed_invoice(db)
    trip_id = trip.id
    db.close()

    response = test_client.post(f"/api/trips/{trip_id}/export/excel")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert "attachment" in response.headers.get("content-disposition", "")
    assert response.content[:2] == b"PK"
