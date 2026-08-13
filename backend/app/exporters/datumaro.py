from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

from PIL import Image

from backend.app.models import Annotation, AnnotationType
from backend.app.services.dataset_store import DatasetRecord
from backend.app.services.export_service import _rotate_geometry_for_export


def _rotate_image_file(image_path: Path, rotation: int) -> tuple[bytes, int, int]:
    with Image.open(image_path) as image:
        rotation = rotation % 360
        if rotation == 90:
            rotated = image.rotate(-90, expand=True)
        elif rotation == 180:
            rotated = image.rotate(180, expand=True)
        elif rotation == 270:
            rotated = image.rotate(-270, expand=True)
        else:
            rotated = image.copy()
        buffer = io.BytesIO()
        rotated.save(buffer, format=image.format or "PNG")
        return buffer.getvalue(), rotated.width, rotated.height


def _annotation_item(annotation: Annotation, width: int, height: int, rotation: int) -> dict[str, object] | None:
    rotated = _rotate_geometry_for_export(annotation, width, height, rotation)
    geometry = rotated.geometry
    if rotated.type == AnnotationType.rectangle:
        return {"id": rotated.id, "type": "bbox", "label": rotated.label, "bbox": [geometry["x1"], geometry["y1"], geometry["x2"] - geometry["x1"], geometry["y2"] - geometry["y1"]], "attributes": rotated.attributes}
    if rotated.type == AnnotationType.polygon:
        return {"id": rotated.id, "type": "polygon", "label": rotated.label, "points": geometry["points"], "attributes": rotated.attributes}
    if rotated.type == AnnotationType.polyline:
        return {"id": rotated.id, "type": "polyline", "label": rotated.label, "points": geometry["points"], "attributes": rotated.attributes}
    if rotated.type == AnnotationType.points:
        return {"id": rotated.id, "type": "points", "label": rotated.label, "points": geometry["points"], "attributes": rotated.attributes}
    if rotated.type == AnnotationType.ellipse:
        return {"id": rotated.id, "type": "bbox", "label": rotated.label, "bbox": [geometry["cx"] - geometry["rx"], geometry["cy"] - geometry["ry"], geometry["rx"] * 2, geometry["ry"] * 2], "attributes": rotated.attributes}
    if rotated.type == AnnotationType.rotated_rectangle and "points" in geometry:
        xs = [point[0] for point in geometry["points"]]
        ys = [point[1] for point in geometry["points"]]
        return {"id": rotated.id, "type": "bbox", "label": rotated.label, "bbox": [min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)], "attributes": rotated.attributes}
    return None


def build_datumaro_zip_subset(
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
    labels = sorted({annotation.label for index in selected_indices for annotation in record.annotations.get(record.images[index].filename, []) if annotation.label})
    payload: dict[str, object] = {
        "dm_format_version": "1.0",
        "media_type": "image",
        "categories": {"label": {"labels": [{"name": label} for label in labels]}},
        "items": [],
    }
    items: list[dict[str, object]] = []
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for image_index in selected_indices:
            image = record.images[image_index]
            image_path = record.resolve_image_path(image_index)
            if image_path is None:
                continue
            image_bytes, width, height = _rotate_image_file(image_path, record.image_rotation(image_index))
            archive.writestr(f"images/{Path(image.filename).name}", image_bytes)
            item_annotations = []
            for annotation in record.annotations.get(image.filename, []):
                item = _annotation_item(annotation, image.width, image.height, record.image_rotation(image_index))
                if item is not None:
                    item_annotations.append(item)
            items.append(
                {
                    "id": Path(image.filename).stem,
                    "subset": "default",
                    "image": {"path": f"images/{Path(image.filename).name}", "size": [width, height]},
                    "annotations": item_annotations,
                }
            )
        payload["items"] = items
        archive.writestr("dataset.json", json.dumps(payload, indent=2))
