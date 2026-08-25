"""Owned projects and durable job creation."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_owned_trip, require_csrf
from app.infrastructure.db.models import Document, Export, Job, TravelSegment, Trip, User
from app.infrastructure.db.session import get_db
from app.schemas import ExportCreate, ExportRead, JobCreate, JobRead, RouteSegmentRead, SummaryRead, TripCreate, TripRead, TripUpdate
from app.services.audit import record_audit
from app.services.documents import remove_document_objects
from app.services.jobs import create_job, dispatch_job
from app.services.invoices import mark_trip_reimbursed
from app.services.trips import default_settings_for_user, get_summary, ordered_route_segments, rebuild_trip_projections, serialize_trip
from app.infrastructure.storage.local import LocalStorage


router = APIRouter(prefix="/trips", tags=["trips"])


def _owned_trip_or_404(trip_id: str, db: Session, user: User) -> Trip:
    return get_owned_trip(trip_id, db, user)


def _serialize_export(export: Export) -> ExportRead:
    return ExportRead(
        id=export.id,
        trip_id=export.trip_id,
        job_id=export.job_id,
        format=export.format,
        status=export.status,
        original_filename=export.original_filename,
        filename=export.original_filename,
        expires_at=export.expires_at,
        error_code=export.error_code,
        error_message=export.error_message,
        created_at=export.created_at,
    )


@router.get("", response_model=list[TripRead])
def list_trips(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[TripRead]:
    trips = db.scalars(select(Trip).where(Trip.owner_id == user.id).order_by(Trip.updated_at.desc())).all()
    return [serialize_trip(db, trip) for trip in trips]


@router.post("", response_model=TripRead, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_csrf)])
def create_trip(payload: TripCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> TripRead:
    user_settings = default_settings_for_user(db, user.id)
    trip = Trip(
        owner_id=user.id,
        title=payload.title,
        source_label=payload.source_label,
        traveler_name=payload.traveler_name or user_settings.default_traveler_name,
        company_name=payload.company_name or user_settings.default_company_name,
        company_tax_id=payload.company_tax_id or user_settings.default_company_tax_id,
        project_type=payload.project_type,
        input_start_date=payload.input_start_date,
        input_end_date=payload.input_end_date,
        daily_allowance=user_settings.daily_allowance,
        include_start_day=user_settings.include_start_day,
        include_end_day=user_settings.include_end_day,
        lodging_limit_per_day=user_settings.lodging_limit_per_day,
        require_return_ticket=user_settings.require_return_ticket,
        require_lodging_invoice=user_settings.require_lodging_invoice,
    )
    db.add(trip)
    db.flush()
    rebuild_trip_projections(db, trip)
    record_audit(db, actor_id=user.id, action="TRIP_CREATE", resource_type="trip", resource_id=trip.id)
    db.commit()
    db.refresh(trip)
    return serialize_trip(db, trip)


@router.get("/{trip_id}", response_model=TripRead)
def get_trip(trip_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> TripRead:
    return serialize_trip(db, _owned_trip_or_404(trip_id, db, user))


@router.patch("/{trip_id}", response_model=TripRead, dependencies=[Depends(require_csrf)])
def update_trip(trip_id: str, payload: TripUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> TripRead:
    trip = _owned_trip_or_404(trip_id, db, user)
    values = payload.model_dump(exclude_unset=True)
    if "start_date" in values:
        values["confirmed_start_date"] = values.pop("start_date")
    if "end_date" in values:
        values["confirmed_end_date"] = values.pop("end_date")
    prospective_start = values.get("confirmed_start_date", trip.confirmed_start_date)
    prospective_end = values.get("confirmed_end_date", trip.confirmed_end_date)
    if prospective_start and prospective_end and prospective_start > prospective_end:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Trip end date must be on or after start date")
    input_start = values.get("input_start_date", trip.input_start_date)
    input_end = values.get("input_end_date", trip.input_end_date)
    if input_start and input_end and input_start > input_end:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Input end date must be on or after start date")
    for field, value in values.items():
        setattr(trip, field, value)
    rebuild_trip_projections(
        db,
        trip,
        sync_settings=not bool(
            {
                "daily_allowance",
                "include_start_day",
                "include_end_day",
                "lodging_limit_per_day",
                "require_return_ticket",
                "require_lodging_invoice",
            }
            & set(values)
        ),
    )
    record_audit(db, actor_id=user.id, action="TRIP_UPDATE", resource_type="trip", resource_id=trip.id)
    db.commit()
    db.refresh(trip)
    return serialize_trip(db, trip)


@router.post("/{trip_id}/mark-reimbursed", response_model=TripRead, dependencies=[Depends(require_csrf)])
def mark_trip_as_reimbursed(trip_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> TripRead:
    trip = _owned_trip_or_404(trip_id, db, user)
    changed = mark_trip_reimbursed(db, trip)
    record_audit(
        db,
        actor_id=user.id,
        action="TRIP_MARK_REIMBURSED",
        resource_type="trip",
        resource_id=trip.id,
        metadata={"updated_invoice_count": changed},
    )
    db.commit()
    return serialize_trip(db, trip)


@router.get("/{trip_id}/jobs", response_model=list[JobRead])
def list_jobs(trip_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[JobRead]:
    trip = _owned_trip_or_404(trip_id, db, user)
    return [JobRead.model_validate(job) for job in db.scalars(select(Job).where(Job.trip_id == trip.id).order_by(Job.created_at.desc()))]


@router.delete("/{trip_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_csrf)])
def delete_trip(trip_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> None:
    trip = _owned_trip_or_404(trip_id, db, user)
    storage = LocalStorage()
    from app.infrastructure.db.models import DocumentPage

    for document in db.scalars(select(Document).where(Document.trip_id == trip.id)):
        pages = list(db.scalars(select(DocumentPage).where(DocumentPage.document_id == document.id)))
        remove_document_objects(storage, document, pages)
    for export in db.scalars(select(Export).where(Export.trip_id == trip.id)):
        storage.delete(export.storage_key)
    record_audit(db, actor_id=user.id, action="TRIP_DELETE", resource_type="trip", resource_id=trip.id)
    db.delete(trip)
    db.commit()


@router.get("/{trip_id}/summary", response_model=SummaryRead)
def summary(trip_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> SummaryRead:
    return get_summary(db, _owned_trip_or_404(trip_id, db, user))


@router.get("/{trip_id}/route-segments", response_model=list[RouteSegmentRead])
def list_route_segments(
    trip_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[RouteSegmentRead]:
    trip = _owned_trip_or_404(trip_id, db, user)
    segments = ordered_route_segments(
        db.scalars(select(TravelSegment).where(TravelSegment.trip_id == trip.id))
    )
    return [RouteSegmentRead.model_validate(segment) for segment in segments]


@router.post("/{trip_id}/jobs", response_model=JobRead, status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(require_csrf)])
def create_processing_job(
    trip_id: str,
    payload: JobCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> JobRead:
    trip = _owned_trip_or_404(trip_id, db, user)
    if payload.document_id:
        document = db.get(Document, payload.document_id)
        if not document or document.trip_id != trip.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    if payload.kind in {"EXPORT_XLSX", "EXPORT_PDF"}:
        export = Export(owner_id=user.id, trip_id=trip.id, format="XLSX" if payload.kind == "EXPORT_XLSX" else "PDF")
        db.add(export)
        db.flush()
        job = create_job(db, owner_id=user.id, kind=payload.kind, trip_id=trip.id, queue="cpu", result_ref=export.id)
        export.job_id = job.id
    else:
        job = create_job(
            db,
            owner_id=user.id,
            kind="PROCESS_DOCUMENT" if payload.kind == "REPROCESS_DOCUMENT" else payload.kind,
            trip_id=trip.id,
            document_id=payload.document_id,
            queue="cpu",
        )
    record_audit(db, actor_id=user.id, action="JOB_CREATE", resource_type="job", resource_id=job.id)
    return JobRead.model_validate(dispatch_job(db, job))


@router.post("/{trip_id}/exports", response_model=ExportRead, status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(require_csrf)])
def create_export(
    trip_id: str,
    payload: ExportCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ExportRead:
    trip = _owned_trip_or_404(trip_id, db, user)
    export = Export(owner_id=user.id, trip_id=trip.id, format=payload.format)
    db.add(export)
    db.flush()
    job = create_job(db, owner_id=user.id, trip_id=trip.id, kind=f"EXPORT_{payload.format}", queue="cpu", result_ref=export.id)
    export.job_id = job.id
    record_audit(db, actor_id=user.id, action="EXPORT_CREATE", resource_type="export", resource_id=export.id)
    dispatch_job(db, job)
    db.refresh(export)
    return _serialize_export(export)


@router.get("/{trip_id}/exports", response_model=list[ExportRead])
def list_exports(trip_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[ExportRead]:
    trip = _owned_trip_or_404(trip_id, db, user)
    return [_serialize_export(item) for item in db.scalars(select(Export).where(Export.trip_id == trip.id).order_by(Export.created_at.desc()))]
