from __future__ import annotations

import io
import zipfile
from pathlib import Path

from PIL import Image

from backend.app.models import AnnotationType
from backend.app.services.dataset_store import DatasetRecord
from backend.app.services.export_service import _rotate_geometry_for_export, visual_bbox_for_annotation


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


def _bbox(annotation) -> tuple[float, float, float, float] | None:
    geometry = annotation.geometry
    if annotation.type == AnnotationType.rectangle:
        bbox = visual_bbox_for_annotation(annotation)
        if bbox is None:
            return None
        return bbox[0], bbox[1], bbox[0] + bbox[2], bbox[1] + bbox[3]
    if annotation.type in {AnnotationType.polygon, AnnotationType.polyline, AnnotationType.points, AnnotationType.rotated_rectangle} and "points" in geometry:
        xs = [float(point[0]) for point in geometry["points"]]
        ys = [float(point[1]) for point in geometry["points"]]
        return min(xs), min(ys), max(xs), max(ys)
    return None


def build_kitti_zip_subset(record: DatasetRecord, output_path: Path, start_index: int | None, end_index: int | None) -> None:
    selected_indices = [
        index
        for index in range(len(record.images))
        if not record.is_deleted(index)
        and (start_index is None or index >= start_index)
        and (end_index is None or index <= end_index)
    ]
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for image_index in selected_indices:
            image = record.images[image_index]
            image_path = record.resolve_image_path(image_index)
            if image_path is None:
                continue
            image_bytes, _, _ = _rotate_image_file(image_path, record.image_rotation(image_index))
            filename = Path(image.filename).name
            archive.writestr(f"image_2/{filename}", image_bytes)
            lines = []
            for annotation in record.annotations.get(image.filename, []):
                rotated = _rotate_geometry_for_export(annotation, image.width, image.height, record.image_rotation(image_index))
                bbox = _bbox(rotated)
                if bbox is None:
                    continue
                truncated = float(annotation.attributes.get("truncated", 0) or 0)
                occluded = int(annotation.attributes.get("occluded", 0) or 0)
                alpha = float(annotation.attributes.get("alpha", 0) or 0)
                x1, y1, x2, y2 = bbox
                lines.append(f"{rotated.label} {truncated:.2f} {occluded} {alpha:.2f} {x1:.2f} {y1:.2f} {x2:.2f} {y2:.2f} 0 0 0 0 0 0 0")
            archive.writestr(f"label_2/{Path(filename).stem}.txt", "\n".join(lines))
