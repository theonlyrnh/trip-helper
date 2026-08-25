from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session, sessionmaker

from app.domain.reporting.summary import calculate_summary
from app.infrastructure.db.base import Base
from app.infrastructure.db.models import (
    Document,
    Export,
    Invoice,
    Job,
    ReviewIssue,
    Trip,
    TravelSegment,
    User,
)
from app.infrastructure.db.session import get_engine
from app.infrastructure.storage.local import LocalStorage
from app.schemas import TripCreate, TripUpdate
from app.services.exports import _excel_value, cleanup_expired_exports, create_export_bytes, store_export
from app.services.invoices import update_invoice
from app.services.recognition import ensure_manual_review_invoice
from app.services.trips import rebuild_trip_projections


@dataclass
class SummaryTrip:
    project_type: str = "TRAVEL"
    trip_days: int | None = None
    confirmed_start_date: date | None = date(2026, 8, 20)
    confirmed_end_date: date | None = date(2026, 8, 22)
    daily_allowance: Decimal | None = Decimal("100.00")
    include_start_day: bool = True
    include_end_day: bool = True


@dataclass
class SummaryInvoice:
    reimbursement_status: str = "THIS_TRIP"
    include_in_summary: bool = True
    confirmed_amount: Decimal | None = None
    total_amount: Decimal | None = Decimal("10.00")
    expense_category: str = "OTHER"
    document_role: str = "OFFICIAL_INVOICE"


def make_db() -> tuple[Session, sessionmaker[Session]]:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    return factory(), factory


def test_date_range_contract_rejects_reverse_ranges() -> None:
    with pytest.raises(ValidationError):
        TripCreate(title="invalid", input_start_date=date(2026, 8, 24), input_end_date=date(2026, 8, 23))
    with pytest.raises(ValidationError):
        TripUpdate(confirmed_start_date=date(2026, 8, 24), confirmed_end_date=date(2026, 8, 23))


def test_summary_never_emits_negative_days_or_amounts_and_preserves_zero_allowance() -> None:
    trip = SummaryTrip(trip_days=-8, daily_allowance=Decimal("0.00"))
    result = calculate_summary(
        trip,
        [SummaryInvoice(total_amount=Decimal("-12.345"), confirmed_amount=None)],
    )
    assert result["trip_days"] == 0
    assert result["daily_allowance"] == Decimal("0.00")
    assert result["allowance_amount"] == Decimal("0.00")
    assert result["invoice_total_amount"] == Decimal("0.00")
    assert result["grand_total_amount"] == Decimal("0.00")


def test_settings_drive_endpoint_count() -> None:
    # The same-day trip is counted once when either endpoint is enabled; a
    # cross-day trip counts intermediate days plus enabled endpoints.
    trip = SummaryTrip(
        confirmed_start_date=date(2026, 8, 20),
        confirmed_end_date=date(2026, 8, 22),
        trip_days=None,
        include_start_day=False,
        include_end_day=True,
    )
    result = calculate_summary(trip, [])
    assert result["trip_days"] == 2


def test_worker_registry_is_loaded_by_standalone_entrypoint() -> None:
    from app.workers.celery_app import celery_app

    # Importing the entrypoint must be enough for a fresh worker process to see
    # every task; operators should not need to import an implementation module.
    assert {
        "app.workers.tasks.execute_job",
        "app.workers.tasks.process_document",
        "app.workers.tasks.recognize_document",
    }.issubset(celery_app.tasks)
    assert celery_app.conf.task_routes["app.workers.tasks.recognize_document"]["queue"] == "gpu"


def test_sqlite_foreign_keys_are_enabled() -> None:
    engine = get_engine()
    if not engine.url.drivername.startswith("sqlite"):
        pytest.skip("SQLite-only contract")
    with engine.connect() as connection:
        assert connection.scalar(text("PRAGMA foreign_keys")) == 1


def test_projection_rebuild_is_idempotent() -> None:
    db, _ = make_db()
    try:
        user = User(email="idempotent@example.test", password_hash="x")
        db.add(user)
        db.flush()
        trip = Trip(owner_id=user.id, title="idempotent")
        db.add(trip)
        db.flush()
        invoice = Invoice(
            trip_id=trip.id,
            invoice_type="TRAIN_TICKET",
            expense_category="INTERCITY_TRANSPORT",
            business_date=date(2026, 8, 20),
            from_city="北京",
            to_city="上海",
            transport_no="G1",
            total_amount=Decimal("88.00"),
        )
        db.add(invoice)
        db.flush()
        rebuild_trip_projections(db, trip)
        db.commit()
        first = db.scalar(select(TravelSegment).where(TravelSegment.invoice_id == invoice.id))
        assert first is not None
        first_id = first.id
        rebuild_trip_projections(db, trip)
        db.commit()
        segments = list(db.scalars(select(TravelSegment).where(TravelSegment.invoice_id == invoice.id)))
        assert len(segments) == 1
        assert segments[0].id == first_id
    finally:
        db.close()


def test_empty_ocr_creates_manual_review_projection() -> None:
    db, _ = make_db()
    try:
        user = User(email="manual@example.test", password_hash="x")
        db.add(user)
        db.flush()
        trip = Trip(owner_id=user.id, title="manual")
        db.add(trip)
        db.flush()
        from app.infrastructure.db.models import Document

        document = Document(
            trip_id=trip.id,
            storage_key="originals/a/file.png",
            original_filename="file.png",
            sha256="a" * 64,
            size_bytes=1,
            mime_type="image/png",
            file_extension=".png",
            document_type="IMAGE",
        )
        db.add(document)
        db.flush()
        invoice = ensure_manual_review_invoice(db, document, reason="OCR returned no text")
        db.commit()
        assert invoice.review_status == "NEEDS_REVIEW"
        assert invoice.include_in_summary is False
        assert "OCR" in (invoice.note or "")
        assert ensure_manual_review_invoice(db, document).id == invoice.id
    finally:
        db.close()


def test_stale_invoice_writer_is_rejected() -> None:
    engine = create_engine(
        f"sqlite:///file:optimization_concurrency_{uuid4().hex}?mode=memory&cache=shared",
        connect_args={"uri": True, "check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    first, second = factory(), factory()
    try:
        user = User(email="concurrency@example.test", password_hash="x")
        first.add(user)
        first.flush()
        trip = Trip(owner_id=user.id, title="concurrency")
        first.add(trip)
        first.flush()
        invoice = Invoice(trip_id=trip.id, invoice_type="GENERAL_INVOICE", expense_category="OTHER", version=1)
        first.add(invoice)
        first.commit()
        invoice_id = invoice.id
        left = first.get(Invoice, invoice_id)
        right = second.get(Invoice, invoice_id)
        assert left is not None and right is not None
        from app.schemas import InvoiceUpdate

        update_invoice(first, left, InvoiceUpdate(version=1, note="first"))
        with pytest.raises(Exception) as error:
            update_invoice(second, right, InvoiceUpdate(version=1, note="stale"))
        assert getattr(error.value, "status_code", None) == 409
    finally:
        first.close()
        second.close()


def test_manual_dates_override_inference_and_conflicts_are_explained() -> None:
    db, _ = make_db()
    try:
        user = User(email="date-conflict@example.test", password_hash="x")
        db.add(user)
        db.flush()
        trip = Trip(
            owner_id=user.id,
            title="date conflict",
            require_lodging_invoice=False,
            require_return_ticket=False,
        )
        db.add(trip)
        db.flush()
        invoice = Invoice(
            trip_id=trip.id,
            invoice_type="TRAIN_TICKET",
            expense_category="INTERCITY_TRANSPORT",
            business_date=date(2026, 8, 20),
            total_amount=Decimal("10.00"),
            confidence=Decimal("0.95"),
        )
        db.add(invoice)
        db.flush()
        rebuild_trip_projections(db, trip)
        assert trip.inferred_start_date == date(2026, 8, 20)
        trip.confirmed_start_date = date(2026, 8, 22)
        trip.confirmed_end_date = date(2026, 8, 23)
        rebuild_trip_projections(db, trip)
        issue = db.scalar(select(ReviewIssue).where(ReviewIssue.trip_id == trip.id, ReviewIssue.issue_type == "DATE_CONFLICT"))
        assert issue is not None
        assert issue.resolution_status == "OPEN"
        assert "人工确认日期" in issue.message
        assert trip.trip_days == 2
    finally:
        db.close()


def test_export_formats_escape_formulas_and_include_chinese_details(tmp_path) -> None:
    assert _excel_value("=HYPERLINK(\"https://example.test\")") == "'=HYPERLINK(\"https://example.test\")"
    assert _excel_value(Decimal("12.30")) == Decimal("12.30")

    db, _ = make_db()
    storage = LocalStorage(root=tmp_path)
    try:
        user = User(email="export@example.test", password_hash="x")
        db.add(user)
        db.flush()
        trip = Trip(
            owner_id=user.id,
            title="北京差旅",
            confirmed_start_date=date(2026, 8, 20),
            confirmed_end_date=date(2026, 8, 20),
            daily_allowance=Decimal("100.00"),
        )
        db.add(trip)
        db.flush()
        document = Document(
            trip_id=trip.id,
            storage_key="originals/export.pdf",
            original_filename="北京酒店发票.pdf",
            sha256="c" * 64,
            size_bytes=1,
            mime_type="application/pdf",
            file_extension=".pdf",
            document_type="PDF",
        )
        db.add(document)
        db.flush()
        invoice = Invoice(
            trip_id=trip.id,
            document_id=document.id,
            invoice_type="GENERAL_INVOICE",
            expense_category="OTHER",
            total_amount=Decimal("12.30"),
            seller_name="示例酒店",
        )
        db.add(invoice)
        db.flush()
        pdf, filename, mime = create_export_bytes(db, trip, "PDF")
        assert filename.endswith(".pdf")
        assert mime == "application/pdf"
        assert len(pdf) > 1_000
        import fitz

        extracted = "".join(page.get_text() for page in fitz.open(stream=pdf, filetype="pdf"))
        assert "差旅报销汇总" in extracted
        assert "北京酒店发票" in extracted

        export = Export(owner_id=user.id, trip_id=trip.id, format="XLSX")
        db.add(export)
        db.flush()
        store_export(db, storage, trip, export)
        db.commit()
        assert export.status == "SUCCEEDED"
        assert export.expires_at is not None
        old_key = export.storage_key
        export.expires_at = datetime.now(UTC) - timedelta(hours=1)
        db.commit()
        assert cleanup_expired_exports(db, storage, now=datetime.now(UTC)) == 1
        assert export.status == "EXPIRED"
        assert export.storage_key is None
        assert old_key is not None and not storage.exists(old_key)
    finally:
        db.close()


def test_celery_gpu_handoff_persists_queued_state_before_dispatch(web_runtime, monkeypatch) -> None:
    from app.infrastructure.db.models import Document, Trip
    from app.services.jobs import create_job
    from app.workers import tasks

    db = web_runtime.session_factory()
    try:
        user = User(email="handoff@example.test", password_hash="x")
        db.add(user)
        db.flush()
        trip = Trip(owner_id=user.id, title="handoff")
        db.add(trip)
        db.flush()
        document = Document(
            trip_id=trip.id,
            storage_key="originals/handoff.pdf",
            original_filename="handoff.pdf",
            sha256="b" * 64,
            size_bytes=1,
            mime_type="application/pdf",
            file_extension=".pdf",
            document_type="PDF",
        )
        db.add(document)
        db.flush()
        job = create_job(db, owner_id=user.id, kind="PROCESS_DOCUMENT", trip_id=trip.id, document_id=document.id, queue="cpu")
        db.commit()
        monkeypatch.setattr(tasks, "generate_previews_and_text", lambda *args, **kwargs: None)
        observed: list[str] = []

        def dispatch(*args, **kwargs):
            db.expire_all()
            current = db.get(Job, job.id)
            assert current is not None
            observed.append(current.state)
            return type("Result", (), {"id": "handoff-task"})()

        monkeypatch.setattr(tasks.recognize_document, "apply_async", dispatch)
        tasks.execute_job.run(job.id)
        assert observed == ["QUEUED"]
        db.expire_all()
        assert db.get(Job, job.id).state == "QUEUED"
    finally:
        db.close()
