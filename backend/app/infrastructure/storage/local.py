"""A100-local persistent storage behind opaque object keys."""

from __future__ import annotations

import hashlib
import os
import re
import shutil
from collections.abc import AsyncIterator, Iterator
from pathlib import Path, PurePosixPath
from typing import BinaryIO
from uuid import uuid4

from fastapi import UploadFile

from app.core.config import Settings, get_settings


class StorageError(RuntimeError):
    """A user-safe storage error; callers map it to an API error code."""


_SAFE_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")


class LocalStorage:
    """Stores bytes only on the A100 data volume, never under the web root."""

    def __init__(self, root: Path | None = None, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.root = (root or self.settings.storage_root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "tmp").mkdir(exist_ok=True)

    def new_key(self, category: str, suffix: str = "") -> str:
        category = re.sub(r"[^a-z0-9_-]", "", category.lower()) or "objects"
        suffix = re.sub(r"[^a-zA-Z0-9.]", "", suffix.lower())[:20]
        return f"{category}/{uuid4().hex[:2]}/{uuid4().hex}{suffix}"

    def _path_for(self, key: str) -> Path:
        if not _SAFE_KEY.fullmatch(key) or key.startswith("/") or ".." in PurePosixPath(key).parts:
            raise StorageError("Invalid storage key")
        path = (self.root / key).resolve()
        if self.root != path and self.root not in path.parents:
            raise StorageError("Invalid storage key")
        return path

    def path_for_internal_use(self, key: str) -> Path:
        """Return a path for trusted adapters only; API DTOs never receive it."""
        return self._path_for(key)

    async def put_upload(self, upload: UploadFile, key: str, max_bytes: int) -> tuple[int, str]:
        """Stream an upload to a temporary file while calculating its SHA-256."""
        target = self._path_for(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = self.root / "tmp" / f"{uuid4().hex}.upload"
        digest = hashlib.sha256()
        total = 0
        try:
            with temp.open("xb") as output:
                while chunk := await upload.read(self.settings.upload_chunk_bytes):
                    total += len(chunk)
                    if total > max_bytes:
                        raise StorageError("File exceeds the configured upload limit")
                    digest.update(chunk)
                    output.write(chunk)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temp, target)
            return total, digest.hexdigest()
        except Exception:
            temp.unlink(missing_ok=True)
            raise
        finally:
            await upload.close()

    def put_bytes(self, value: bytes, key: str) -> None:
        target = self._path_for(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = self.root / "tmp" / f"{uuid4().hex}.write"
        try:
            with temp.open("xb") as output:
                output.write(value)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temp, target)
        finally:
            temp.unlink(missing_ok=True)

    def open(self, key: str) -> BinaryIO:
        path = self._path_for(key)
        if not path.is_file():
            raise StorageError("Stored object is unavailable")
        return path.open("rb")

    def exists(self, key: str) -> bool:
        return self._path_for(key).is_file()

    def delete(self, key: str | None) -> None:
        if key:
            self._path_for(key).unlink(missing_ok=True)

    def delete_prefix(self, prefix: str) -> None:
        """Delete only application-generated object prefixes."""
        root = self._path_for(prefix)
        if root.exists() and root.is_dir():
            shutil.rmtree(root)

    def iter_bytes(self, key: str, chunk_size: int = 1_048_576) -> Iterator[bytes]:
        with self.open(key) as source:
            while chunk := source.read(chunk_size):
                yield chunk


def normalize_relative_path(value: str | None) -> str | None:
    """Accept browser directory paths without ever accepting a local absolute path."""
    if not value:
        return None
    normalized = value.replace("\\", "/").strip("/")
    if not normalized or len(normalized) > 1024:
        return None
    parts = PurePosixPath(normalized).parts
    if any(part in {"", ".", ".."} for part in parts):
        raise StorageError("Invalid relative path")
    if any(":" in part or "\x00" in part for part in parts):
        raise StorageError("Invalid relative path")
    return "/".join(parts)


def sanitize_filename(value: str | None) -> str:
    name = (value or "upload").replace("\\", "/").split("/")[-1]
    name = "".join(char for char in name if char >= " " and char != "\x7f").strip()
    return name[:512] or "upload"
