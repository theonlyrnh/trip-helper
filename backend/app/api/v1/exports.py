"""Authorized export downloads from private A100 object storage."""

from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, status
from datetime import UTC, datetime

from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_owned_export
from app.infrastructure.db.models import Export, User
from app.infrastructure.db.session import get_db
from app.infrastructure.storage.local import LocalStorage, StorageError


router = APIRouter(prefix="/exports", tags=["exports"])


@router.get("/{export_id}/download")
def download_export(export_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> StreamingResponse:
    export = get_owned_export(export_id, db, user)
    if export.status != "SUCCEEDED" or not export.storage_key or not export.original_filename:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Export is not ready")
    mime_type = "application/pdf" if export.format == "PDF" else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    try:
        export.last_accessed_at = datetime.now(UTC)
        db.commit()
        response = StreamingResponse(LocalStorage().iter_bytes(export.storage_key), media_type=mime_type)
    except StorageError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Export content is unavailable") from exc
    response.headers["Content-Disposition"] = f"attachment; filename*=UTF-8''{quote(export.original_filename)}"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "no-store"
    return response
