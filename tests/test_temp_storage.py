from pathlib import Path

import pytest

from backend.app.config import set_temp_data_folder, settings
from backend.app.models import DatasetManifest, ImageInfo
from backend.app.services.dataset_store import DatasetStore


def _create_dataset(store: DatasetStore, root: Path) -> str:
    asset_root = root / "assets"
    asset_root.mkdir(parents=True)
    image_path = asset_root / "image.jpg"
    image_path.write_bytes(b"image")
    record = store.create_dataset(
        root,
        asset_root,
        DatasetManifest(
            format="cvat_xml",
            images=[ImageInfo(filename="image.jpg", width=100, height=50)],
        ),
        {"image.jpg": image_path},
    )
    return record.dataset_id


def test_save_moves_temporary_dataset_to_resume_folder(tmp_path: Path, monkeypatch) -> None:
    temp_folder = tmp_path / "temporary"
    resume_folder = tmp_path / "resume"
    export_folder = tmp_path / "exports"
    temp_folder.mkdir()
    resume_folder.mkdir()
    export_folder.mkdir()
    monkeypatch.setattr(settings, "temp_data_dir", temp_folder)
    monkeypatch.setattr(settings, "data_dir", resume_folder)
    monkeypatch.setattr(settings, "export_dir", export_folder)

    store = DatasetStore()
    temporary_root = temp_folder / "upload"
    dataset_id = _create_dataset(store, temporary_root)

    assert store.list_saved_records() == []
    saved_record = store.save(dataset_id)

    assert saved_record.root == resume_folder / dataset_id
    assert saved_record.asset_root == resume_folder / dataset_id / "assets"
    assert not temporary_root.exists()
    assert [record.dataset_id for record in store.list_saved_records()] == [dataset_id]


def test_clear_temp_data_preserves_saved_sessions_and_exports(tmp_path: Path, monkeypatch) -> None:
    temp_folder = tmp_path / "temporary"
    resume_folder = tmp_path / "resume"
    export_folder = tmp_path / "exports"
    temp_folder.mkdir()
    resume_folder.mkdir()
    export_folder.mkdir()
    monkeypatch.setattr(settings, "temp_data_dir", temp_folder)
    monkeypatch.setattr(settings, "data_dir", resume_folder)
    monkeypatch.setattr(settings, "export_dir", export_folder)

    store = DatasetStore()
    temporary_dataset_id = _create_dataset(store, temp_folder / "upload")
    saved_dataset_id = _create_dataset(store, resume_folder / "saved")
    export_file = export_folder / "dataset.zip"
    export_file.write_bytes(b"export")

    removed_datasets, removed_items = store.clear_temp_data()

    assert removed_datasets == [temporary_dataset_id]
    assert removed_items == 1
    assert list(temp_folder.iterdir()) == []
    assert store.get(saved_dataset_id).root.exists()
    assert export_file.exists()


def test_temp_folder_cannot_overlap_saved_or_export_data(tmp_path: Path, monkeypatch) -> None:
    resume_folder = tmp_path / "resume"
    export_folder = tmp_path / "exports"
    resume_folder.mkdir()
    export_folder.mkdir()
    monkeypatch.setattr(settings, "data_dir", resume_folder)
    monkeypatch.setattr(settings, "export_dir", export_folder)
    monkeypatch.setattr("backend.app.config._write_preferences", lambda: None)

    with pytest.raises(ValueError, match="must differ"):
        set_temp_data_folder(resume_folder / "temporary")

    with pytest.raises(ValueError, match="must differ"):
        set_temp_data_folder(tmp_path)
