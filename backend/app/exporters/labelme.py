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


def _shape_from_annotation(annotation: Annotation, width: int, height: int, rotation: int) -> dict[str, object] | None:
    rotated = _rotate_geometry_for_export(annotation, width, height, rotation)
    geometry = rotated.geometry
    if rotated.type == AnnotationType.rectangle:
        return {
            "label": rotated.label,
            "points": [[geometry["x1"], geometry["y1"]], [geometry["x2"], geometry["y2"]]],
            "group_id": None,
            "shape_type": "rectangle",
            "flags": {},
            "description": "",
            "rotation": float(geometry.get("angle", 0) or 0),
            "attributes": rotated.attributes,
        }
    if rotated.type in {AnnotationType.polygon, AnnotationType.polyline, AnnotationType.points}:
        return {
            "label": rotated.label,
            "points": geometry["points"],
            "group_id": None,
            "shape_type": rotated.type.value if rotated.type != AnnotationType.points else "point",
            "flags": {},
            "description": "",
            "rotation": 0.0,
            "attributes": rotated.attributes,
        }
    if rotated.type == AnnotationType.ellipse:
        return {
            "label": rotated.label,
            "points": [[geometry["cx"], geometry["cy"]], [geometry["cx"] + geometry["rx"], geometry["cy"] + geometry["ry"]]],
            "group_id": None,
            "shape_type": "circle",
            "flags": {},
            "description": "",
            "rotation": 0.0,
            "attributes": rotated.attributes,
        }
    if rotated.type in {AnnotationType.rotated_rectangle, AnnotationType.cuboid, AnnotationType.skeleton, AnnotationType.mask}:
        xs: list[float] = []
        ys: list[float] = []
        if rotated.type == AnnotationType.rotated_rectangle and "points" in geometry:
            for point in geometry["points"]:
                xs.append(float(point[0]))
                ys.append(float(point[1]))
        elif rotated.type == AnnotationType.cuboid:
            for face in geometry.get("faces", []):
                for point in face:
                    xs.append(float(point[0]))
                    ys.append(float(point[1]))
        elif rotated.type == AnnotationType.skeleton:
            for point in geometry.get("nodes", {}).values():
                xs.append(float(point[0]))
                ys.append(float(point[1]))
        elif rotated.type == AnnotationType.mask:
            mask = geometry.get("mask", [])
            for y, row in enumerate(mask):
                for x, value in enumerate(row):
                    if value:
                        xs.append(float(x))
                        ys.append(float(y))
        if xs and ys:
            return {
                "label": rotated.label,
                "points": [[min(xs), min(ys)], [max(xs), max(ys)]],
                "group_id": None,
                "shape_type": "rectangle",
                "flags": {},
                "description": "",
                "rotation": 0.0,
                "attributes": rotated.attributes,
            }
    return None


def build_labelme_zip_subset(
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
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for image_index in selected_indices:
            image = record.images[image_index]
            image_path = record.resolve_image_path(image_index)
            if image_path is None:
                continue
            image_bytes, width, height = _rotate_image_file(image_path, record.image_rotation(image_index))
            shapes = []
            for annotation in record.annotations.get(image.filename, []):
                shape = _shape_from_annotation(annotation, image.width, image.height, record.image_rotation(image_index))
                if shape is not None:
                    shapes.append(shape)
            payload = {
                "version": "5.0.1",
                "flags": {},
                "shapes": shapes,
                "imagePath": Path(image.filename).name,
                "imageData": None,
                "imageHeight": height,
                "imageWidth": width,
            }
            archive.writestr(f"images/{Path(image.filename).name}", image_bytes)
            archive.writestr(f"annotations/{Path(image.filename).stem}.json", json.dumps(payload, indent=2))
