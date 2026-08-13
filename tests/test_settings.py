from pathlib import Path

import pytest

from backend.app.api.routes import _folder_size_bytes, _safe_upload_target


def test_folder_size_bytes_counts_nested_files(tmp_path: Path) -> None:
    nested = tmp_path / "nested"
    nested.mkdir()
    (tmp_path / "first.bin").write_bytes(b"abc")
    (nested / "second.bin").write_bytes(b"defgh")

    assert _folder_size_bytes(tmp_path) == 8


def test_folder_size_bytes_returns_zero_for_missing_folder(tmp_path: Path) -> None:
    assert _folder_size_bytes(tmp_path / "missing") == 0


def test_safe_upload_target_preserves_relative_folder_paths(tmp_path: Path) -> None:
    assert _safe_upload_target(tmp_path, "dataset/images/frame.jpg") == tmp_path / "dataset" / "images" / "frame.jpg"


@pytest.mark.parametrize("filename", ["../escape.jpg", "dataset/../escape.jpg", "/absolute/file.jpg", "", "dataset//file.jpg"])
def test_safe_upload_target_rejects_unsafe_paths(tmp_path: Path, filename: str) -> None:
    with pytest.raises(ValueError):
        _safe_upload_target(tmp_path, filename)
