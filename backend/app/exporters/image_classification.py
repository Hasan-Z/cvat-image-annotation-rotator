from __future__ import annotations

import csv
import io
import zipfile
from pathlib import Path

from PIL import Image

from backend.app.services.dataset_store import DatasetRecord


def _safe_class_name(label: str) -> str:
    cleaned = "".join(character if character.isalnum() or character in {"-", "_", "."} else "_" for character in label.strip())
    return cleaned or "_unlabeled"


def _rotate_image_file(image_path: Path, rotation: int) -> bytes:
    with Image.open(image_path) as image:
        normalized_rotation = rotation % 360
        if normalized_rotation == 90:
            rotated = image.rotate(-90, expand=True)
        elif normalized_rotation == 180:
            rotated = image.rotate(180, expand=True)
        elif normalized_rotation == 270:
            rotated = image.rotate(-270, expand=True)
        else:
            rotated = image.copy()
        buffer = io.BytesIO()
        rotated.save(buffer, format=image.format or "PNG")
        return buffer.getvalue()


def build_image_classification_zip_subset(
    record: DatasetRecord,
    output_path: Path,
    start_index: int | None,
    end_index: int | None,
) -> None:
    selected_indices = [
        index
        for index in range(len(record.images))
        if not record.is_deleted(index)
        and (start_index is None or index >= start_index)
        and (end_index is None or index <= end_index)
    ]
    csv_buffer = io.StringIO()
    writer = csv.writer(csv_buffer)
    writer.writerow(["filename", "label"])
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for image_index in selected_indices:
            image = record.images[image_index]
            image_path = record.resolve_image_path(image_index)
            if image_path is None:
                continue
            label = record.image_labels.get(image.filename, "_unlabeled")
            class_name = _safe_class_name(label)
            image_name = Path(image.filename).name
            export_name = f"{class_name}/{image_name}"
            archive.writestr(export_name, _rotate_image_file(image_path, record.image_rotation(image_index)))
            writer.writerow([export_name, label])
        archive.writestr("labels.csv", csv_buffer.getvalue())
