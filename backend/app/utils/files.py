from __future__ import annotations

from pathlib import Path


def build_file_index(root: Path) -> dict[str, Path]:
    exact_matches: dict[str, Path] = {}
    basename_matches: dict[str, Path] = {}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative_key = path.relative_to(root).as_posix()
        exact_matches[relative_key] = path
        basename = path.name
        basename_matches.setdefault(basename, path)
    return {**basename_matches, **exact_matches}


def resolve_file_path(root: Path, file_index: dict[str, Path], name: str) -> Path | None:
    normalized = Path(name).as_posix()
    if normalized in file_index:
        return file_index[normalized]
    basename = Path(name).name
    if basename in file_index:
        return file_index[basename]
    exact = root / name
    if exact.exists():
        return exact
    for path in root.rglob(basename):
        if path.is_file():
            return path
    return None
