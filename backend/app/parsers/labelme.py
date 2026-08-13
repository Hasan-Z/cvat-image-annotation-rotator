from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from backend.app.models import Annotation, AnnotationType, DatasetManifest, ImageInfo
from backend.app.utils.files import resolve_file_path


def _looks_like_labelme(payload: object) -> bool:
    return isinstance(payload, dict) and "shapes" in payload and "imagePath" in payload


def _resolve_image_root(dataset_root: Path) -> Path:
    for candidate in (dataset_root, dataset_root / "images", dataset_root / "Images", dataset_root / "JPEGImages"):
        if candidate.exists():
            return candidate
    return dataset_root


def _shape_to_annotation(shape: dict[str, object], annotation_id: str) -> Annotation | None:
    label = str(shape.get("label", ""))
    shape_type = str(shape.get("shape_type", "polygon")).lower()
    points = shape.get("points", [])
    if not isinstance(points, list) or not points:
        return None
    parsed_points = [[float(point[0]), float(point[1])] for point in points if isinstance(point, list) and len(point) >= 2]
    if not parsed_points:
        return None
    if shape_type == "rectangle":
        first, second = parsed_points[0], parsed_points[1] if len(parsed_points) > 1 else parsed_points[0]
        return Annotation(
            id=annotation_id,
            type=AnnotationType.rectangle,
            label=label,
            attributes={},
            geometry={
                "x1": first[0],
                "y1": first[1],
                "x2": second[0],
                "y2": second[1],
                "angle": float(shape.get("rotation", 0) or 0),
            },
        )
    if shape_type == "point":
        point = parsed_points[0]
        return Annotation(id=annotation_id, type=AnnotationType.points, label=label, attributes={}, geometry={"points": [point]})
    if shape_type in {"line", "linestrip", "polyline"}:
        return Annotation(id=annotation_id, type=AnnotationType.polyline, label=label, attributes={}, geometry={"points": parsed_points})
    if shape_type == "circle" and len(parsed_points) >= 2:
        center, edge = parsed_points[0], parsed_points[1]
        rx = abs(edge[0] - center[0])
        ry = abs(edge[1] - center[1])
        return Annotation(
            id=annotation_id,
            type=AnnotationType.ellipse,
            label=label,
            attributes={},
            geometry={"cx": center[0], "cy": center[1], "rx": rx, "ry": ry, "angle": 0.0},
        )
    return Annotation(id=annotation_id, type=AnnotationType.polygon, label=label, attributes={}, geometry={"points": parsed_points})


def parse_labelme(dataset_root: Path) -> DatasetManifest:
    json_files = []
    for candidate in sorted(dataset_root.rglob("*.json")):
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if _looks_like_labelme(payload):
            json_files.append((candidate, payload))

    image_root = _resolve_image_root(dataset_root)
    images: list[ImageInfo] = []
    annotations: dict[str, list[Annotation]] = {}
    seen_images: set[str] = set()
    for json_path, payload in json_files:
        image_name = Path(str(payload.get("imagePath", json_path.with_suffix(".jpg").name))).name
        image_index_key = image_name
        image_path = resolve_file_path(image_root, {path.relative_to(image_root).as_posix(): path for path in image_root.rglob("*") if path.is_file()}, image_name)
        if image_path is None:
            image_path = resolve_file_path(dataset_root, {path.relative_to(dataset_root).as_posix(): path for path in dataset_root.rglob("*") if path.is_file()}, image_name)
        width = int(payload.get("imageWidth", 0) or 0)
        height = int(payload.get("imageHeight", 0) or 0)
        if (width <= 0 or height <= 0) and image_path is not None:
            try:
                with Image.open(image_path) as image:
                    width, height = image.size
            except Exception:
                width, height = 0, 0
        if image_index_key not in seen_images:
            images.append(ImageInfo(filename=image_name, width=width, height=height))
            seen_images.add(image_index_key)
        parsed_annotations: list[Annotation] = []
        for shape_index, shape in enumerate(payload.get("shapes", [])):
            if not isinstance(shape, dict):
                continue
            annotation = _shape_to_annotation(shape, f"{json_path.stem}-{shape_index}")
            if annotation is not None:
                parsed_annotations.append(annotation)
        annotations[image_name] = parsed_annotations
    return DatasetManifest(format="labelme", images=images, annotations=annotations)
