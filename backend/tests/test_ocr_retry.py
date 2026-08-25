from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import select


def _seed_ocr_job(
    web_runtime: Any,
    *,
    attempt: int = 1,
    max_attempts: int = 3,
    existing_invoice: bool = False,
) -> tuple[str, str, str | None]:
    from app.infrastructure.db.models import Document, Invoice, Job, Trip, User

    db = web_runtime.session_factory()
    try:
        user = User(email="ocr-owner@example.test", password_hash="unused")
        db.add(user)
        db.flush()
        trip = Trip(owner_id=user.id, title="OCR retry fixture")
        db.add(trip)
        db.flush()
        document = Document(
            trip_id=trip.id,
            storage_key="uploads/ocr-retry.png",
            original_filename="ocr-retry.png",
            sha256="0" * 64,
            size_bytes=1,
            mime_type="image/png",
            file_extension=".png",
            document_type="IMAGE",
            processing_status="PREPROCESSED",
            ocr_status="QUEUED",
        )
        db.add(document)
        db.flush()
        invoice_id: str | None = None
        if existing_invoice:
            invoice = Invoice(
                trip_id=trip.id,
                document_id=document.id,
                invoice_type="GENERAL_INVOICE",
                expense_category="OTHER",
                review_status="MANUALLY_CONFIRMED",
                reimbursement_status="PENDING",
                include_in_summary=False,
            )
            db.add(invoice)
            db.flush()
            invoice_id = invoice.id
        job = Job(
            owner_id=user.id,
            trip_id=trip.id,
            document_id=document.id,
            kind="PROCESS_DOCUMENT",
            state="RUNNING",
            attempt=attempt,
            max_attempts=max_attempts,
            queue="gpu",
        )
        db.add(job)
        db.commit()
        return job.id, document.id, invoice_id
    finally:
        db.close()


def _make_ocr_unavailable(monkeypatch: pytest.MonkeyPatch) -> list[object]:
    from app.infrastructure.ocr.paddle import OcrProviderError, PaddleOcrClient

    calls: list[object] = []

    def unavailable(*args: object, **kwargs: object) -> None:
        calls.append(args)
        raise OcrProviderError("fixture OCR unavailable")

    monkeypatch.setattr(PaddleOcrClient, "recognize_image", unavailable)
    return calls


def test_eager_ocr_failure_finishes_for_manual_review_without_recursive_dispatch(
    web_runtime: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.infrastructure.db.models import Document, Invoice, Job
    from app.workers.tasks import recognize_document

    job_id, document_id, _ = _seed_ocr_job(web_runtime)
    calls = _make_ocr_unavailable(monkeypatch)

    recognize_document.apply_async(args=[job_id], queue="gpu")
    # A duplicate delivery must not restart a terminal OCR job.
    recognize_document.apply_async(args=[job_id], queue="gpu")

    assert len(calls) == 1
    db = web_runtime.session_factory()
    try:
        job = db.get(Job, job_id)
        document = db.get(Document, document_id)
        assert job is not None
        assert document is not None
        invoice = db.scalar(select(Invoice).where(Invoice.document_id == document_id))
        assert job.state == "FAILED"
        assert job.attempt == 1
        assert job.error_code == "OCR_FAILED"
        assert document.processing_status == "FAILED"
        assert document.ocr_status == "FAILED"
        assert document.error_code == "OCR_FAILED"
        assert invoice is not None
        assert invoice.review_status == "NEEDS_REVIEW"
    finally:
        db.close()


def test_ocr_failure_uses_celery_retry_with_gpu_backoff_outside_eager(
    web_runtime: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.infrastructure.db.models import Job
    from app.workers.tasks import recognize_document

    class RetryScheduled(Exception):
        pass

    job_id, _, _ = _seed_ocr_job(web_runtime)
    _make_ocr_unavailable(monkeypatch)
    retry_arguments: dict[str, object] = {}

    def schedule_retry(**kwargs: object) -> None:
        retry_arguments.update(kwargs)
        raise RetryScheduled()

    monkeypatch.setattr(recognize_document, "retry", schedule_retry)
    with pytest.raises(RetryScheduled):
        recognize_document.run(job_id)

    assert retry_arguments["countdown"] == 1
    assert retry_arguments["max_retries"] == 2
    assert retry_arguments["queue"] == "gpu"
    db = web_runtime.session_factory()
    try:
        job = db.get(Job, job_id)
        assert job is not None
        assert job.state == "RETRYING"
        assert job.attempt == 1
    finally:
        db.close()


def test_final_ocr_failure_marks_document_failed_and_creates_manual_invoice(
    web_runtime: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.infrastructure.db.models import Document, Invoice, Job
    from app.workers.tasks import recognize_document

    job_id, document_id, _ = _seed_ocr_job(web_runtime, attempt=3)
    calls = _make_ocr_unavailable(monkeypatch)

    recognize_document.apply_async(args=[job_id], queue="gpu")

    assert len(calls) == 1
    db = web_runtime.session_factory()
    try:
        job = db.get(Job, job_id)
        document = db.get(Document, document_id)
        invoice = db.scalar(select(Invoice).where(Invoice.document_id == document_id))
        assert job is not None
        assert document is not None
        assert invoice is not None
        assert job.state == "FAILED"
        assert job.attempt == 3
        assert job.error_code == "OCR_FAILED"
        assert document.processing_status == "FAILED"
        assert document.ocr_status == "FAILED"
        assert document.error_code == "OCR_FAILED"
        assert document.error_message == "OCR 识别失败，可人工录入"
        assert invoice.invoice_type == "UNKNOWN"
        assert invoice.review_status == "NEEDS_REVIEW"
        assert invoice.reimbursement_status == "PENDING"
        assert invoice.include_in_summary is False
    finally:
        db.close()


def test_final_ocr_failure_preserves_an_existing_manual_invoice(
    web_runtime: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.infrastructure.db.models import Invoice
    from app.workers.tasks import recognize_document

    job_id, document_id, existing_invoice_id = _seed_ocr_job(web_runtime, attempt=3, existing_invoice=True)
    _make_ocr_unavailable(monkeypatch)

    recognize_document.apply_async(args=[job_id], queue="gpu")

    db = web_runtime.session_factory()
    try:
        invoices = list(db.scalars(select(Invoice).where(Invoice.document_id == document_id)))
        assert [invoice.id for invoice in invoices] == [existing_invoice_id]
        assert invoices[0].review_status == "MANUALLY_CONFIRMED"
    finally:
        db.close()
