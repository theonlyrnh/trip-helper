"""Browser uploads and authorized private document streams."""

from __future__ import annotations

from urllib.parse import quote
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_owned_document, get_owned_trip, require_csrf
from app.core.config import get_settings
from app.infrastructure.db.models import Document, DocumentPage, Invoice, OcrRun, ReviewIssue, Trip, User
from app.infrastructure.db.session import get_db
from app.infrastructure.storage.local import LocalStorage, StorageError, normalize_relative_path, sanitize_filename
from app.schemas import DocumentRead, JobRead, UploadResponse
from app.services.audit import record_audit
from app.services.documents import FileValidationError, get_preview_key, inspect_stored_object, remove_document_objects, serialize_document, serialize_documents
from app.services.jobs import create_job, dispatch_job
from app.services.trips import rebuild_trip_projections


router = APIRouter(tags=["documents"])


@router.post("/trips/{trip_id}/uploads", response_model=UploadResponse, status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(require_csrf)])
async def upload_document(
    trip_id: str,
    file: UploadFile = File(...),
    relative_path: str | None = Form(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> UploadResponse:
    trip = get_owned_trip(trip_id, db, user)
    settings = get_settings()
    count = db.scalar(select(func.count()).select_from(Document).where(Document.trip_id == trip.id)) or 0
    if count >= settings.max_documents_per_trip:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Project document limit reached")
    storage = LocalStorage()
    filename = sanitize_filename(file.filename)
    try:
        normalized_path = normalize_relative_path(relative_path)
        suffix = filename[filename.rfind(".") :] if "." in filename else ""
        storage_key = storage.new_key("originals", suffix)
        size_bytes, sha256 = await storage.put_upload(file, storage_key, settings.max_upload_bytes)
        mime_type, document_type, page_count = inspect_stored_object(storage, storage_key, filename)
    except StorageError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except FileValidationError as exc:
        storage.delete(storage_key if "storage_key" in locals() else None)
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=str(exc)) from exc
    except Exception:
        storage.delete(storage_key if "storage_key" in locals() else None)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unable to receive upload")

    existing = db.scalar(select(Document).where(Document.trip_id == trip.id, Document.sha256 == sha256))
    if existing:
        storage.delete(storage_key)
        job = create_job(
            db,
            owner_id=user.id,
            kind="PROCESS_DOCUMENT",
            trip_id=trip.id,
            document_id=existing.id,
            queue="cpu",
            idempotency_key=f"{existing.id}:{existing.processing_version}",
        )
        record_audit(db, actor_id=user.id, action="DOCUMENT_DUPLICATE", resource_type="document", resource_id=existing.id)
        queued_job = dispatch_job(db, job)
        return UploadResponse(document=serialize_document(db, existing), job_id=queued_job.id, job=JobRead.model_validate(queued_job), duplicate=True)

    document = Document(
        trip_id=trip.id,
        storage_key=storage_key,
        original_filename=filename,
        relative_path=normalized_path,
        sha256=sha256,
        size_bytes=size_bytes,
        mime_type=mime_type,
        file_extension=suffix.lower(),
        page_count=page_count,
        document_type=document_type,
    )
    db.add(document)
    db.flush()
    # Directory names are the browser-safe replacement for the old local
    # folder scanner and may already contain a useful trip date range.
    rebuild_trip_projections(db, trip)
    job = create_job(
        db,
        owner_id=user.id,
        kind="PROCESS_DOCUMENT",
        trip_id=trip.id,
        document_id=document.id,
        queue="cpu",
        idempotency_key=f"{document.id}:{document.processing_version}",
    )
    record_audit(db, actor_id=user.id, action="DOCUMENT_UPLOAD", resource_type="document", resource_id=document.id, metadata={"size_bytes": size_bytes})
    queued_job = dispatch_job(db, job)
    db.refresh(document)
    return UploadResponse(document=serialize_document(db, document), job_id=queued_job.id, job=JobRead.model_validate(queued_job))


@router.get("/trips/{trip_id}/documents", response_model=list[DocumentRead])
def list_documents(
    trip_id: str,
    response: Response,
    page: int = Query(default=1, ge=1, le=100_000),
    page_size: int = Query(default=100, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[DocumentRead]:
    trip = get_owned_trip(trip_id, db, user)
    base = select(Document).where(Document.trip_id == trip.id)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    documents = db.scalars(
        base.order_by(Document.created_at.desc(), Document.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    response.headers["X-Total-Count"] = str(total)
    response.headers["X-Page"] = str(page)
    response.headers["X-Page-Size"] = str(page_size)
    response.headers["Cache-Control"] = "no-store"
    return serialize_documents(db, list(documents))


@router.get("/documents/{document_id}/content")
def stream_content(document_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> StreamingResponse:
    document = get_owned_document(document_id, db, user)
    storage = LocalStorage()
    if not storage.exists(document.storage_key):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document content is unavailable")
    response = StreamingResponse(storage.iter_bytes(document.storage_key), media_type=document.mime_type)
    filename = quote(document.original_filename)
    response.headers["Content-Disposition"] = f"inline; filename*=UTF-8''{filename}"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "no-store"
    return response


@router.get("/documents/{document_id}/preview")
def stream_preview(
    document_id: str,
    page: int = 0,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StreamingResponse:
    document = get_owned_document(document_id, db, user)
    storage = LocalStorage()
    key, mime_type = get_preview_key(db, document, page)
    if not storage.exists(key):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Preview is unavailable")
    return StreamingResponse(
        storage.iter_bytes(key),
        media_type=mime_type,
        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "no-store"},
    )


@router.get("/documents/{document_id}/ocr")
def get_ocr_text(document_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    document = get_owned_document(document_id, db, user)
    runs = db.scalars(select(OcrRun).where(OcrRun.document_id == document.id).order_by(OcrRun.created_at.desc())).all()
    response = {
        "document_id": document.id,
        "runs": [
            {
                "id": run.id,
                "provider": run.provider,
                "model": run.model,
                "status": run.status,
                "raw_text": run.raw_text,
                "duration_ms": run.duration_ms,
                "created_at": run.created_at,
            }
            for run in runs
        ],
    }
    # JSON OCR is private source material; prevent browser/proxy persistence.
    from fastapi.responses import JSONResponse

    return JSONResponse(jsonable_encoder(response), headers={"Cache-Control": "no-store"})


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_csrf)])
def delete_document(document_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> None:
    document = get_owned_document(document_id, db, user)
    trip = db.get(Trip, document.trip_id)
    pages = list(db.scalars(select(DocumentPage).where(DocumentPage.document_id == document.id)))
    remove_document_objects(LocalStorage(), document, pages)
    db.execute(delete(Invoice).where(Invoice.document_id == document.id))
    db.delete(document)
    db.flush()
    if trip:
        rebuild_trip_projections(db, trip)
    record_audit(db, actor_id=user.id, action="DOCUMENT_DELETE", resource_type="document", resource_id=document.id)
    db.commit()


@router.post("/documents/{document_id}/retry", response_model=JobRead, status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(require_csrf)])
def retry_document(document_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> JobRead:
    document = get_owned_document(document_id, db, user)
    document.processing_version = uuid4().hex
    document.error_code = None
    document.error_message = None
    document.processing_status = "PENDING"
    document.ocr_status = "PENDING"
    job = create_job(
        db,
        owner_id=user.id,
        kind="REPROCESS_DOCUMENT",
        trip_id=document.trip_id,
        document_id=document.id,
        queue="cpu",
        idempotency_key=f"{document.id}:{document.processing_version}:retry",
    )
    record_audit(db, actor_id=user.id, action="DOCUMENT_RETRY", resource_type="document", resource_id=document.id)
    return JobRead.model_validate(dispatch_job(db, job))
