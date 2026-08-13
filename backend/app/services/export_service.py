from __future__ import annotations

import json
import io
import zipfile
from pathlib import Path

from PIL import Image

from backend.app.geometry.rotator import rotate_image_dimensions
from backend.app.models import Annotation
from backend.app.services.dataset_store import DatasetRecord


def _rotation_degrees(rotation: int) -> int:
    return rotation % 360


def _label_color(label: str) -> str:
    palette = ["#4704fb", "#5b98c6", "#2acdcf", "#ff7f50", "#9b59b6", "#22c55e", "#eab308"]
    return palette[sum(ord(character) for character in label) % len(palette)]


def _rotate_point_for_export(x: float, y: float, width: int, height: int, rotation: int) -> tuple[float, float]:
    rotation = _rotation_degrees(rotation)
    if rotation == 90:
        return height - y, x
    if rotation == 180:
        return width - x, height - y
    if rotation == 270:
        return y, width - x
    return x, y


def _rotate_points_for_export(
    points: list[list[float]],
    width: int,
    height: int,
    rotation: int,
) -> list[list[float]]:
    return [[*_rotate_point_for_export(x, y, width, height, rotation)] for x, y in points]


def _rectangle_points(geometry: dict[str, object]) -> list[list[float]]:
    x1 = float(geometry["x1"])
    y1 = float(geometry["y1"])
    x2 = float(geometry["x2"])
    y2 = float(geometry["y2"])
    angle = float(geometry.get("display_angle", geometry.get("angle", 0)) or 0) % 360
    center_x = (x1 + x2) / 2
    center_y = (y1 + y2) / 2
    half_width = (x2 - x1) / 2
    half_height = (y2 - y1) / 2
    corners = [
        (-half_width, -half_height),
        (half_width, -half_height),
        (half_width, half_height),
        (-half_width, half_height),
    ]
    if angle == 0:
        return [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]

    import math

    radians = math.radians(angle)
    cos_angle = math.cos(radians)
    sin_angle = math.sin(radians)
    return [
        [
            center_x + local_x * cos_angle - local_y * sin_angle,
            center_y + local_x * sin_angle + local_y * cos_angle,
        ]
        for local_x, local_y in corners
    ]


def visual_bbox_for_annotation(annotation: Annotation) -> list[float] | None:
    geometry = annotation.geometry
    annotation_type = annotation.type.value
    points: list[list[float]] | None = None
    if annotation_type == "rectangle":
        points = _rectangle_points(geometry)
    elif annotation_type in {"polygon", "polyline", "points", "rotated_rectangle"} and "points" in geometry:
        points = [[float(point[0]), float(point[1])] for point in geometry["points"]]
    elif annotation_type == "ellipse":
        return [
            float(geometry["cx"]) - float(geometry["rx"]),
            float(geometry["cy"]) - float(geometry["ry"]),
            float(geometry["rx"]) * 2,
            float(geometry["ry"]) * 2,
        ]
    elif annotation_type == "skeleton" and geometry.get("nodes"):
        points = [[float(node[0]), float(node[1])] for node in geometry["nodes"].values()]
    if not points:
        return None
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return [min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)]


def _rotate_geometry_for_export(annotation: Annotation, width: int, height: int, rotation: int) -> Annotation:
    geometry = annotation.geometry
    annotation_type = annotation.type.value
    if rotation % 360 == 0 and geometry.get("dot_reset") is not True:
        return annotation

    if annotation_type == "rectangle":
        if geometry.get("dot_reset") is True:
            visual_points = _rotate_points_for_export(_rectangle_points(geometry), width, height, rotation)
            xs = [point[0] for point in visual_points]
            ys = [point[1] for point in visual_points]
            rotated_geometry = {
                **geometry,
                "x1": min(xs),
                "y1": min(ys),
                "x2": max(xs),
                "y2": max(ys),
                "angle": 0,
                "display_angle": 0,
            }
        else:
            center_x = (float(geometry["x1"]) + float(geometry["x2"])) / 2
            center_y = (float(geometry["y1"]) + float(geometry["y2"])) / 2
            new_center_x, new_center_y = _rotate_point_for_export(center_x, center_y, width, height, rotation)
            box_width = float(geometry["x2"]) - float(geometry["x1"])
            box_height = float(geometry["y2"]) - float(geometry["y1"])
            rotated_geometry = {
                **geometry,
                "x1": new_center_x - box_width / 2,
                "y1": new_center_y - box_height / 2,
                "x2": new_center_x + box_width / 2,
                "y2": new_center_y + box_height / 2,
                "angle": (float(geometry.get("angle", 0) or 0) + rotation) % 360,
            }
    elif annotation_type in {"polygon", "polyline", "points"}:
        rotated_geometry = {**geometry, "points": _rotate_points_for_export(geometry["points"], width, height, rotation)}
    elif annotation_type == "rotated_rectangle":
        rotated_geometry = {
            **geometry,
            "points": _rotate_points_for_export(geometry["points"], width, height, rotation),
            "angle": 0 if geometry.get("dot_reset") is True else (geometry.get("angle", 0) + rotation) % 360,
        }
    elif annotation_type == "ellipse":
        new_cx, new_cy = _rotate_point_for_export(geometry["cx"], geometry["cy"], width, height, rotation)
        rotated_geometry = {
            **geometry,
            "cx": new_cx,
            "cy": new_cy,
            "angle": 0 if geometry.get("dot_reset") is True else (geometry.get("angle", 0) + rotation) % 360,
        }
    elif annotation_type == "cuboid":
        rotated_geometry = {
            **geometry,
            "faces": [_rotate_points_for_export(face, width, height, rotation) for face in geometry.get("faces", [])],
        }
    elif annotation_type == "skeleton":
        rotated_nodes = {
            key: list(_rotate_point_for_export(point[0], point[1], width, height, rotation))
            for key, point in geometry.get("nodes", {}).items()
        }
        rotated_geometry = {**geometry, "nodes": rotated_nodes}
    elif annotation_type == "mask":
        import cv2
        import numpy as np

        mask = np.asarray(geometry["mask"], dtype=np.uint8)
        if rotation == 90:
            rotated_mask = cv2.rotate(mask, cv2.ROTATE_90_CLOCKWISE)
        elif rotation == 180:
            rotated_mask = cv2.rotate(mask, cv2.ROTATE_180)
        elif rotation == 270:
            rotated_mask = cv2.rotate(mask, cv2.ROTATE_90_COUNTERCLOCKWISE)
        else:
            rotated_mask = mask
        rotated_geometry = {**geometry, "mask": rotated_mask.tolist()}
    else:
        rotated_geometry = geometry

    return annotation.model_copy(update={"geometry": rotated_geometry})


def _rotate_image_file(image_path: Path, rotation: int) -> bytes:
    with Image.open(image_path) as image:
        rotation = _rotation_degrees(rotation)
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
        return buffer.getvalue()


def _build_task_json(record: DatasetRecord, selected_indices: list[int]) -> dict[str, object]:
    labels = sorted({annotation.label for index in selected_indices for annotation in record.annotations.get(record.images[index].filename, [])})
    labels = sorted({*labels, *(label for label in record.labels if label)})
    return {
        "name": record.dataset_id,
        "bug_tracker": "",
        "status": "annotation",
        "labels": [
            {
                "name": label,
                "color": _label_color(label),
                "attributes": [],
                "type": "any",
                "sublabels": [],
            }
            for label in labels
        ],
        "subset": "",
        "version": "1.0",
        "data": {
            "chunk_size": max(1, min(72, len(selected_indices) or 1)),
            "image_quality": 70,
            "start_frame": 0,
            "stop_frame": max(0, len(selected_indices) - 1),
            "storage_method": "cache",
            "storage": "local",
            "sorting_method": "lexicographical",
            "chunk_type": "imageset",
            "deleted_frames": [],
        },
        "jobs": [
            {
                "start_frame": 0,
                "stop_frame": max(0, len(selected_indices) - 1),
                "status": "annotation",
            }
        ],
    }


def _build_annotations_json(record: DatasetRecord, selected_indices: list[int]) -> list[dict[str, object]]:
    shapes: list[dict[str, object]] = []
    for frame_index, image_index in enumerate(selected_indices):
        image = record.images[image_index]
        annotation_rotation = record.image_rotation(image_index)
        for annotation in record.annotations.get(image.filename, []):
            if not annotation.label:
                continue
            rotated_annotation = _rotate_geometry_for_export(annotation, image.width, image.height, annotation_rotation)
            geometry = rotated_annotation.geometry
            shape: dict[str, object] = {
                "label": rotated_annotation.label,
                "group": 0,
                "frame": frame_index,
                "source": "manual",
                "attributes": [],
                "elements": [],
                "z_order": 0,
                "rotation": float(geometry.get("angle", 0) or 0),
                "occluded": False,
                "outside": False,
            }
            if rotated_annotation.type.value in {"rectangle", "rotated_rectangle"}:
                if rotated_annotation.type.value == "rotated_rectangle" and "points" in geometry:
                    points = geometry["points"]
                    shape["type"] = "polygon"
                    shape["points"] = [coordinate for point in points for coordinate in point]
                else:
                    shape["type"] = "rectangle"
                    shape["points"] = [geometry["x1"], geometry["y1"], geometry["x2"], geometry["y2"]]
            elif rotated_annotation.type.value == "polygon":
                shape["type"] = "polygon"
                shape["points"] = [coordinate for point in geometry["points"] for coordinate in point]
            elif rotated_annotation.type.value == "polyline":
                shape["type"] = "polyline"
                shape["points"] = [coordinate for point in geometry["points"] for coordinate in point]
            elif rotated_annotation.type.value == "points":
                shape["type"] = "points"
                shape["points"] = [coordinate for point in geometry["points"] for coordinate in point]
            elif rotated_annotation.type.value == "ellipse":
                shape["type"] = "ellipse"
                shape["points"] = [geometry["cx"], geometry["cy"], geometry["rx"], geometry["ry"]]
            else:
                continue
            shapes.append(shape)

    return [
        {
            "version": 0,
            "tags": [],
            "shapes": shapes,
            "tracks": [],
        }
    ]


def _build_manifest_jsonl(record: DatasetRecord, selected_indices: list[int]) -> tuple[str, str]:
    lines = [
        json.dumps({"version": "1.1"}, separators=(",", ":")),
        json.dumps({"type": "images"}, separators=(",", ":")),
    ]
    for index in selected_indices:
        image = record.images[index]
        rotated_width, rotated_height = rotate_image_dimensions(image.width, image.height, record.image_rotation(index))
        lines.append(
            json.dumps(
                {
                    "name": Path(image.filename).stem,
                    "extension": Path(image.filename).suffix or ".jpg",
                    "width": rotated_width,
                    "height": rotated_height,
                    "meta": {"related_images": []},
                },
                separators=(",", ":"),
            )
        )
    text = "\n".join(lines)
    index_map: dict[str, int] = {}
    offset = 0
    for line_index, line in enumerate(lines):
        if line_index >= 2:
            index_map[str(line_index - 2)] = offset
        offset += len(line.encode("utf-8")) + 1
    return text, json.dumps(index_map, indent=4)


def build_export_zip(record: DatasetRecord, output_path: Path) -> None:
    build_export_zip_subset(record, output_path, None, None)


def build_export_zip_subset(
    record: DatasetRecord,
    output_path: Path,
    start_index: int | None,
    end_index: int | None,
) -> None:
    data_dir_name = "data"
    manifest_jsonl_path = output_path.parent / "manifest.jsonl"
    index_json_path = output_path.parent / "index.json"
    annotations_json_path = output_path.parent / "annotations.json"
    selected_indices = [
        index
        for index in range(len(record.images))
        if not record.is_deleted(index)
        and (start_index is None or index >= start_index)
        and (end_index is None or index <= end_index)
    ]
    manifest_text, index_json_text = _build_manifest_jsonl(record, selected_indices)
    manifest_jsonl_path.write_text(manifest_text, encoding="utf-8")
    index_json_path.write_text(index_json_text, encoding="utf-8")
    annotations_json_path.write_text(
        json.dumps(_build_annotations_json(record, selected_indices), indent=2),
        encoding="utf-8",
    )
    task_json_path = output_path.parent / "task.json"
    task_json_path.write_text(json.dumps(_build_task_json(record, selected_indices), indent=2), encoding="utf-8")
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(task_json_path, arcname="task.json")
        archive.write(annotations_json_path, arcname="annotations.json")
        archive.write(manifest_jsonl_path, arcname=f"{data_dir_name}/manifest.jsonl")
        archive.write(index_json_path, arcname=f"{data_dir_name}/index.json")
        for index in selected_indices:
            image = record.images[index]
            image_path = record.resolve_image_path(index)
            if image_path is None:
                continue
            archive.writestr(f"data/{image.filename}", _rotate_image_file(image_path, record.image_rotation(index)))
    annotations_json_path.unlink(missing_ok=True)
    manifest_jsonl_path.unlink(missing_ok=True)
    index_json_path.unlink(missing_ok=True)
    task_json_path.unlink(missing_ok=True)
