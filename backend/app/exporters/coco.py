from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

from PIL import Image

from backend.app.models import Annotation, AnnotationType
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


def _bbox_from_points(points: list[list[float]]) -> list[float]:
    xs = [float(point[0]) for point in points]
    ys = [float(point[1]) for point in points]
    return [min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)]


def _bbox_from_annotation(annotation: Annotation) -> list[float] | None:
    geometry = annotation.geometry
    if annotation.type == AnnotationType.rectangle:
        return visual_bbox_for_annotation(annotation)
    if annotation.type in {AnnotationType.polygon, AnnotationType.polyline, AnnotationType.points, AnnotationType.rotated_rectangle} and "points" in geometry:
        return _bbox_from_points(geometry["points"])
    if annotation.type == AnnotationType.ellipse:
        return [
            float(geometry["cx"]) - float(geometry["rx"]),
            float(geometry["cy"]) - float(geometry["ry"]),
            float(geometry["rx"]) * 2,
            float(geometry["ry"]) * 2,
        ]
    if annotation.type == AnnotationType.skeleton and geometry.get("nodes"):
        points = [[float(node[0]), float(node[1])] for node in geometry["nodes"].values()]
        return _bbox_from_points(points)
    return None


def _coco_annotation(
    annotation: Annotation,
    image_id: int,
    annotation_id: int,
    category_id: int,
) -> dict[str, object] | None:
    bbox = _bbox_from_annotation(annotation)
    if bbox is None:
        return None
    item: dict[str, object] = {
        "id": annotation_id,
        "image_id": image_id,
        "category_id": category_id,
        "bbox": bbox,
        "area": max(0.0, bbox[2]) * max(0.0, bbox[3]),
        "iscrowd": int(annotation.attributes.get("iscrowd", 0) or 0),
    }
    if annotation.type == AnnotationType.polygon:
        item["segmentation"] = [[coordinate for point in annotation.geometry["points"] for coordinate in point]]
    elif annotation.type == AnnotationType.skeleton:
        nodes = annotation.geometry.get("nodes", {})
        keypoint_names = list(nodes.keys())
        keypoints: list[float] = []
        for name in keypoint_names:
            node = nodes[name]
            keypoints.extend([float(node[0]), float(node[1]), float(node[2]) if len(node) > 2 else 2.0])
        item["keypoints"] = keypoints
        item["num_keypoints"] = len(keypoint_names)
    else:
        item["segmentation"] = []
    return item


def build_coco_zip_subset(
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
    category_ids = {label: label_index + 1 for label_index, label in enumerate(labels)}
    payload: dict[str, object] = {
        "info": {"description": "CVAT Dataset Rotation Tool export"},
        "licenses": [],
        "categories": [{"id": category_id, "name": label, "supercategory": ""} for label, category_id in category_ids.items()],
        "images": [],
        "annotations": [],
    }
    image_entries: list[dict[str, object]] = []
    annotation_entries: list[dict[str, object]] = []
    annotation_id = 1
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for frame_id, image_index in enumerate(selected_indices, start=1):
            image = record.images[image_index]
            image_path = record.resolve_image_path(image_index)
            if image_path is None:
                continue
            image_bytes, width, height = _rotate_image_file(image_path, record.image_rotation(image_index))
            filename = Path(image.filename).name
            archive.writestr(f"images/{filename}", image_bytes)
            image_entries.append({"id": frame_id, "file_name": filename, "width": width, "height": height})
            for annotation in record.annotations.get(image.filename, []):
                if not annotation.label:
                    continue
                rotated = _rotate_geometry_for_export(annotation, image.width, image.height, record.image_rotation(image_index))
                item = _coco_annotation(rotated, frame_id, annotation_id, category_ids[rotated.label])
                if item is None:
                    continue
                annotation_entries.append(item)
                annotation_id += 1
        payload["images"] = image_entries
        payload["annotations"] = annotation_entries
        archive.writestr("annotations/instances_default.json", json.dumps(payload, indent=2))
