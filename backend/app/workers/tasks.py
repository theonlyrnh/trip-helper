"""Durable Celery task pipeline for preprocessing, OCR, analysis, and exports."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from celery import Task
from sqlalchemy import select, update

from app.infrastructure.db.models import Document, DocumentPage, Export, Job, OcrRun, Trip
from app.infrastructure.db.session import get_session_factory
from app.infrastructure.ocr.paddle import PaddleOcrClient
from app.infrastructure.queue.celery import celery_app
from app.infrastructure.storage.local import LocalStorage
from app.services.documents import generate_previews_and_text
from app.services.exports import cleanup_expired_exports as cleanup_expired_export_files, store_export
from app.services.jobs import conditional_terminal_update, create_job
from app.services.recognition import ensure_manual_review_invoice, extract_invoice_from_ocr
from app.services.trips import default_settings_for_user, rebuild_trip_projections


logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(UTC)


def _load_job(job_id: str) -> tuple[object, Job]:
    db = get_session_factory()()
    job = db.get(Job, job_id)
    if not job:
        db.close()
        raise RuntimeError("Job no longer exists")
    return db, job


def _start(job: Job) -> None:
    job.state = "RUNNING"
    job.attempt += 1
    job.started_at = _now()
    job.progress = max(job.progress, 1)
    job.message = "正在处理"


def _claim_job(db: object, job: Job, *, allow_existing_running: bool = False) -> int | None:
    """Atomically claim one delivery and return its attempt token."""
    if allow_existing_running and job.state == "RUNNING" and not job.celery_task_id:
        return job.attempt
    result = db.execute(
        update(Job)
        .where(Job.id == job.id, Job.state.in_({"PENDING", "QUEUED", "RETRYING"}))
        .values(state="RUNNING", attempt=Job.attempt + 1, started_at=_now(), progress=1, message="正在处理")
    )
    if result.rowcount != 1:
        return None
    db.refresh(job)
    return job.attempt


def _succeed(job: Job, message: str = "任务已完成") -> None:
    job.state = "SUCCEEDED"
    job.progress = 100
    job.message = message
    job.finished_at = _now()
    job.error_code = None
    job.error_message = None


def _fail(job: Job, code: str, message: str) -> None:
    job.state = "FAILED"
    job.error_code = code
    job.error_message = message[:2000]
    job.message = "任务失败"
    job.finished_at = _now()


@celery_app.task(bind=True, name="app.workers.tasks.execute_job")
def execute_job(self: Task, job_id: str) -> None:
    """CPU entry point. GPU work is explicitly handed to the gpu queue."""
    db, job = _load_job(job_id)
    try:
        attempt = _claim_job(db, job)
        if attempt is None:
            return
        db.commit()
        if job.kind in {"PROCESS_DOCUMENT", "REPROCESS_DOCUMENT"}:
            terminal = _preprocess_document(db, job)
            if terminal:
                conditional_terminal_update(db, job, state="SUCCEEDED", attempt=attempt, message="文档已处理")
        elif job.kind == "FULL_ANALYSIS":
            _enqueue_trip_documents(db, job)
            conditional_terminal_update(db, job, state="SUCCEEDED", attempt=attempt, message="已为项目文档创建处理任务")
        elif job.kind in {"EXPORT_XLSX", "EXPORT_PDF"}:
            _create_export(db, job)
            conditional_terminal_update(db, job, state="SUCCEEDED", attempt=attempt, message="导出文件已生成")
        else:
            raise RuntimeError("Unknown job kind")
        db.commit()
    except Exception:
        db.rollback()
        job = db.get(Job, job_id)
        if job and job.state == "RUNNING":
            conditional_terminal_update(
                db,
                job,
                state="FAILED",
                attempt=job.attempt,
                message="任务失败",
                error_code="PROCESSING_FAILED",
                error_message="处理失败，可重试",
            )
            if job.document_id:
                document = db.get(Document, job.document_id)
                if document:
                    document.processing_status = "FAILED"
                    document.error_code = "PROCESSING_FAILED"
                    document.error_message = "处理失败，可重试"
            if job.result_ref:
                export = db.get(Export, job.result_ref)
                if export and export.status not in {"SUCCEEDED", "EXPIRED"}:
                    export.status = "FAILED"
                    export.error_code = "EXPORT_FAILED"
                    export.error_message = "导出失败，可重试"
            db.commit()
        logger.exception("Job execution failed", extra={"job_id": job_id, "event": "job_failed"})
    finally:
        db.close()


@celery_app.task(bind=True, name="app.workers.tasks.process_document")
def process_document(self: Task, job_id: str) -> None:
    """Alias retained for queue observability and direct worker invocation."""
    execute_job(job_id)


@celery_app.task(bind=True, name="app.workers.tasks.recognize_document", autoretry_for=(), retry_backoff=True)
def recognize_document(self: Task, job_id: str) -> None:
    """GPU queue entry point. Systemd config fixes this worker at concurrency one."""
    db, job = _load_job(job_id)
    try:
        if job.state in {"CANCELLED", "SUCCEEDED", "FAILED"} or not job.document_id:
            return
        attempt = _claim_job(db, job, allow_existing_running=True)
        if attempt is None:
            return
        job.queue = "gpu"
        job.progress = max(job.progress, 45)
        job.message = "GPU OCR 识别中"
        job.started_at = job.started_at or _now()
        # Make an OCR attempt durable before making a potentially long GPU call.
        db.commit()
        document = db.get(Document, job.document_id)
        if not document:
            raise RuntimeError("Document no longer exists")
        storage = LocalStorage()
        pages = list(
            db.scalars(
                select(DocumentPage)
                .where(DocumentPage.document_id == document.id)
                .order_by(DocumentPage.page_index)
            )
        )
        if not pages:
            pages = [None]
        user_settings = default_settings_for_user(db, job.owner_id)
        client = PaddleOcrClient()
        page_runs: list[OcrRun] = []
        for position, page in enumerate(pages, 1):
            image_key = page.preview_key if page and page.preview_key else document.storage_key
            mime_type = "image/png" if page and page.preview_key else document.mime_type
            result = client.recognize_image(
                storage.path_for_internal_use(image_key),
                mime_type,
                allow_remote=user_settings.remote_provider_enabled,
            )
            if not result.raw_text or not result.raw_text.strip():
                raise RuntimeError("OCR returned no text")
            ocr_run = OcrRun(
                document_id=document.id,
                page_index=page.page_index if page else 0,
                provider=result.provider,
                model=result.model,
                raw_text=result.raw_text,
                raw_json=result.raw_json,
                duration_ms=result.duration_ms,
                status="SUCCEEDED",
                attempt=job.attempt,
            )
            db.add(ocr_run)
            page_runs.append(ocr_run)
            job.progress = 45 + int(30 * position / len(pages))
        db.flush()
        providers = {item.provider for item in page_runs}
        models = {item.model for item in page_runs}
        combined_run = OcrRun(
            document_id=document.id,
            page_index=None,
            provider=f"{page_runs[0].provider}_aggregate" if len(providers) == 1 else "mixed_ocr_aggregate",
            model=page_runs[0].model if len(models) == 1 else "mixed",
            raw_text="\n\n".join(item.raw_text for item in page_runs),
            raw_json={"page_run_ids": [item.id for item in page_runs]},
            duration_ms=sum(item.duration_ms for item in page_runs),
            status="SUCCEEDED",
            attempt=job.attempt,
        )
        db.add(combined_run)
        db.flush()
        document.ocr_status = "SUCCEEDED"
        document.processing_status = "RECOGNIZED"
        document.error_code = None
        document.error_message = None
        job.progress = 80
        invoice = extract_invoice_from_ocr(db, document, combined_run)
        if invoice is None:
            raise RuntimeError("OCR returned no text")
        trip = db.get(Trip, document.trip_id)
        if trip:
            rebuild_trip_projections(db, trip)
        conditional_terminal_update(db, job, state="SUCCEEDED", attempt=attempt, message="OCR 和解析已完成")
        db.commit()
    except Exception as exc:
        db.rollback()
        job = db.get(Job, job_id)
        retry_delay: int | None = None
        if job and job.state == "RUNNING":
            # The disposable SQLite acceptance runtime has no GPU worker. Do
            # not leave a browser upload permanently RETRYING there; expose a
            # manual-reviewable failure immediately. Real workers receive the
            # remaining attempts through Celery's retry scheduler.
            should_retry = job.attempt < job.max_attempts and not self.request.is_eager
            if should_retry:
                job.state = "RETRYING"
                job.error_code = "OCR_UNAVAILABLE"
                job.error_message = "OCR 服务暂不可用，任务将重试"
                job.message = "OCR 暂不可用，正在安排重试"
                retry_delay = 2 ** max(0, job.attempt - 1)
            else:
                conditional_terminal_update(
                    db,
                    job,
                    state="FAILED",
                    attempt=job.attempt,
                    message="任务失败",
                    error_code="OCR_FAILED",
                    error_message="OCR 识别失败，可人工录入",
                )
            document = db.get(Document, job.document_id) if job.document_id else None
            if document:
                document.ocr_status = "RETRYING" if job.state == "RETRYING" else "FAILED"
                document.error_code = job.error_code
                document.error_message = job.error_message
                if job.state == "FAILED":
                    document.processing_status = "FAILED"
                    ensure_manual_review_invoice(db, document, reason="OCR 识别失败，请人工录入票据信息。")
                    trip = db.get(Trip, document.trip_id)
                    if trip:
                        rebuild_trip_projections(db, trip)
            db.commit()
        logger.exception("GPU OCR failed", extra={"job_id": job_id, "event": "ocr_failed"})
        if retry_delay is not None:
            # Celery owns the next delivery in production. Re-enqueueing with
            # apply_async here would recursively execute in eager mode.
            raise self.retry(
                exc=exc,
                countdown=retry_delay,
                max_retries=max(0, job.max_attempts - 1),
                queue="gpu",
            ) from exc
    finally:
        db.close()


def _preprocess_document(db, job: Job) -> bool:
    if not job.document_id:
        raise RuntimeError("Document job requires a document")
    document = db.get(Document, job.document_id)
    if not document:
        raise RuntimeError("Document no longer exists")
    document.processing_status = "PREPROCESSING"
    job.progress = 15
    db.commit()
    native_text = generate_previews_and_text(db, LocalStorage(), document)
    job.progress = 45
    if native_text:
        coordinate_words, page_width = _first_page_words(LocalStorage(), document)
        ocr_run = OcrRun(
            document_id=document.id,
            page_index=None,
            provider="pymupdf",
            model="native-text",
            raw_text=native_text,
            raw_json=None,
            duration_ms=0,
            status="SUCCEEDED",
            attempt=job.attempt,
        )
        db.add(ocr_run)
        db.flush()
        document.ocr_status = "SUCCEEDED"
        document.processing_status = "RECOGNIZED"
        job.progress = 80
        extract_invoice_from_ocr(db, document, ocr_run, coordinate_words=coordinate_words, page_width=page_width)
        trip = db.get(Trip, document.trip_id)
        if trip:
            rebuild_trip_projections(db, trip)
        return True
    document.ocr_status = "QUEUED"
    job.queue = "gpu"
    # Hand the durable row to the GPU delivery. The GPU task claims QUEUED,
    # which works identically for eager fixtures and an independent worker.
    job.state = "QUEUED"
    job.progress = 45
    job.message = "等待 GPU OCR"
    db.commit()
    result = recognize_document.apply_async(args=[job.id], queue="gpu")
    # Eager execution may already have reached a terminal state. Never move it
    # backwards or attach an obsolete delivery id after completion.
    job = db.get(Job, job.id)
    if job and job.state not in {"SUCCEEDED", "FAILED", "CANCELLED"}:
        job.celery_task_id = result.id
        db.commit()
    return False


def _first_page_words(storage: LocalStorage, document: Document) -> tuple[list | None, float | None]:
    """Retain coordinate parsing for high-speed rail PDFs without exposing paths."""
    if document.document_type != "PDF":
        return None, None
    try:
        import fitz

        pdf = fitz.open(storage.path_for_internal_use(document.storage_key))
        try:
            page = pdf[0]
            return page.get_text("words"), float(page.rect.width)
        finally:
            pdf.close()
    except Exception:
        return None, None


def _enqueue_trip_documents(db, job: Job) -> None:
    if not job.trip_id:
        raise RuntimeError("Analysis job requires a trip")
    documents = list(db.scalars(select(Document).where(Document.trip_id == job.trip_id)))
    child_ids: list[str] = []
    for document in documents:
        idempotency_key = f"{document.id}:{document.processing_version}"
        existing = db.scalar(
            select(Job).where(Job.owner_id == job.owner_id, Job.idempotency_key == idempotency_key)
        )
        if existing:
            continue
        child = create_job(
            db,
            owner_id=job.owner_id,
            kind="PROCESS_DOCUMENT",
            trip_id=job.trip_id,
            document_id=document.id,
            queue="cpu",
            idempotency_key=idempotency_key,
        )
        child_ids.append(child.id)
    db.commit()
    for child_id in child_ids:
        child = db.get(Job, child_id)
        if not child:
            continue
        child.state = "QUEUED"
        result = execute_job.apply_async(args=[child.id], queue="cpu")
        child.celery_task_id = result.id
    db.commit()


def _create_export(db, job: Job) -> None:
    if not job.trip_id or not job.result_ref:
        raise RuntimeError("Export job is missing its export record")
    trip = db.get(Trip, job.trip_id)
    export = db.get(Export, job.result_ref)
    if not trip or not export:
        raise RuntimeError("Export target no longer exists")
    export.status = "RUNNING"
    db.commit()
    store_export(db, LocalStorage(), trip, export)
    job.progress = 95


@celery_app.task(bind=True, name="app.workers.tasks.cleanup_expired_exports")
def cleanup_expired_exports_task(self: Task) -> int:
    db = get_session_factory()()
    try:
        deleted = cleanup_expired_export_files(db, LocalStorage())
        return deleted
    finally:
        db.close()
