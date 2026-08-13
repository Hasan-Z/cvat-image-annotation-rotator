from __future__ import annotations

import io
import zipfile
from pathlib import Path

from PIL import Image

from backend.app.models import Annotation, AnnotationType
from backend.app.services.dataset_store import DatasetRecord
from backend.app.services.export_service import _rectangle_points, _rotate_geometry_for_export


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


def _normalize(value: float, size: int) -> float:
    return value / size if size else 0.0


def _bbox_line(class_id: int, geometry: dict[str, object], width: int, height: int) -> str:
    x1 = float(geometry["x1"])
    y1 = float(geometry["y1"])
    x2 = float(geometry["x2"])
    y2 = float(geometry["y2"])
    cx = _normalize((x1 + x2) / 2, width)
    cy = _normalize((y1 + y2) / 2, height)
    box_width = _normalize(x2 - x1, width)
    box_height = _normalize(y2 - y1, height)
    return f"{class_id} {cx:.6f} {cy:.6f} {box_width:.6f} {box_height:.6f}"


def _points_line(class_id: int, points: list[list[float]], width: int, height: int) -> str:
    values = [f"{class_id}"]
    for x, y in points:
        values.extend([f"{_normalize(float(x), width):.6f}", f"{_normalize(float(y), height):.6f}"])
    return " ".join(values)


def _annotation_line(annotation: Annotation, class_id: int, width: int, height: int) -> str | None:
    geometry = annotation.geometry
    if annotation.type == AnnotationType.rectangle:
        if float(geometry.get("angle", 0) or 0) % 360 != 0:
            return _points_line(class_id, _rectangle_points(geometry), width, height)
        return _bbox_line(class_id, geometry, width, height)
    if annotation.type == AnnotationType.polygon:
        return _points_line(class_id, geometry["points"], width, height)
    if annotation.type == AnnotationType.rotated_rectangle and "points" in geometry:
        return _points_line(class_id, geometry["points"], width, height)
    if annotation.type == AnnotationType.skeleton:
        bbox = geometry.get("bbox")
        if isinstance(bbox, list) and len(bbox) >= 4:
            cx = _normalize(float(bbox[0]) + float(bbox[2]) / 2, width)
            cy = _normalize(float(bbox[1]) + float(bbox[3]) / 2, height)
            box_width = _normalize(float(bbox[2]), width)
            box_height = _normalize(float(bbox[3]), height)
        else:
            nodes = list(geometry.get("nodes", {}).values())
            if not nodes:
                return None
            xs = [float(node[0]) for node in nodes]
            ys = [float(node[1]) for node in nodes]
            cx = _normalize((min(xs) + max(xs)) / 2, width)
            cy = _normalize((min(ys) + max(ys)) / 2, height)
            box_width = _normalize(max(xs) - min(xs), width)
            box_height = _normalize(max(ys) - min(ys), height)
        values = [f"{class_id}", f"{cx:.6f}", f"{cy:.6f}", f"{box_width:.6f}", f"{box_height:.6f}"]
        for node in geometry.get("nodes", {}).values():
            values.extend(
                [
                    f"{_normalize(float(node[0]), width):.6f}",
                    f"{_normalize(float(node[1]), height):.6f}",
                    f"{float(node[2]) if len(node) > 2 else 2.0:.0f}",
                ]
            )
        return " ".join(values)
    return None


def build_yolo_zip_subset(
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
    class_ids = {label: index for index, label in enumerate(labels)}
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("classes.txt", "\n".join(labels))
        for image_index in selected_indices:
            image = record.images[image_index]
            image_path = record.resolve_image_path(image_index)
            if image_path is None:
                continue
            image_bytes, width, height = _rotate_image_file(image_path, record.image_rotation(image_index))
            filename = Path(image.filename).name
            archive.writestr(f"images/{filename}", image_bytes)
            lines = []
            for annotation in record.annotations.get(image.filename, []):
                if not annotation.label:
                    continue
                rotated = _rotate_geometry_for_export(annotation, image.width, image.height, record.image_rotation(image_index))
                line = _annotation_line(rotated, class_ids[rotated.label], width, height)
                if line is not None:
                    lines.append(line)
            archive.writestr(f"labels/{Path(filename).stem}.txt", "\n".join(lines))
