"""Folder scanner – discovers PDF and image files in a directory tree."""

import os
from dataclasses import dataclass

SUPPORTED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}


@dataclass
class ScannedFile:
    file_name: str
    file_path: str
    file_ext: str
    file_size: int


def scan_folder(folder_path: str) -> list[ScannedFile]:
    """
    Recursively scan a folder for supported invoice files.

    Returns a list of ScannedFile objects sorted by file name.
    """
    if not os.path.isdir(folder_path):
        raise ValueError(f"Not a valid directory: {folder_path}")

    results: list[ScannedFile] = []

    for root, _dirs, files in os.walk(folder_path):
        for fname in files:
            ext = os.path.splitext(fname)[1].lower()
            if ext not in SUPPORTED_EXTENSIONS:
                continue

            full_path = os.path.join(root, fname)
            try:
                file_size = os.path.getsize(full_path)
            except OSError:
                continue

            results.append(
                ScannedFile(
                    file_name=fname,
                    file_path=full_path,
                    file_ext=ext,
                    file_size=file_size,
                )
            )

    results.sort(key=lambda x: x.file_name)
    return results