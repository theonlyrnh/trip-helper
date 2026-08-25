"""Private object storage ports and implementations."""

from .local import LocalStorage, StorageError

__all__ = ["LocalStorage", "StorageError"]

