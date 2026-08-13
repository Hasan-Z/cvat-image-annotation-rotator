from __future__ import annotations

import shutil
import zipfile
from pathlib import Path


class UnsafeArchiveError(RuntimeError):
    pass


def _safe_target(base: Path, member: zipfile.ZipInfo) -> Path:
    target = (base / member.filename).resolve()
    if not str(target).startswith(str(base.resolve())):
        raise UnsafeArchiveError(member.filename)
    return target


def extract_zip_streaming(archive_path: Path, destination: Path, max_bytes: int) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    extracted = 0
    with zipfile.ZipFile(archive_path) as archive:
        for member in archive.infolist():
            if member.is_dir():
                continue
            target = _safe_target(destination, member)
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source, target.open("wb") as sink:
                copied = shutil.copyfileobj(source, sink)
            extracted += member.file_size
            if extracted > max_bytes:
                raise UnsafeArchiveError("archive too large")
