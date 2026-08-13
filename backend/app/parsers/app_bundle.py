from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from backend.app.models import Annotation, AnnotationType, DatasetManifest, ImageInfo


def _find_image_root(dataset_root: Path) -> Path | None:
    for candidate in (dataset_root / "Data", dataset_root / "data"):
        if candidate.exists() and candidate.is_dir():
            return candidate
    if dataset_root.is_dir():
        return dataset_root
    return None


def _parse_points(points_text: str) -> list[list[float]]:
    points: list[list[float]] = []
    for item in points_text.split(";"):
        if not item:
            continue
        x_text, y_text = item.split(",", 1)
        points.append([float(x_text), float(y_text)])
    return points


def _annotation_from_shape(shape: dict[str, object], annotation_id: str) -> Annotation | None:
    shape_type = str(shape.get("type", "")).lower()
    label = str(shape.get("label", ""))
    attributes = shape.get("attributes", [])
    if isinstance(attributes, dict):
        parsed_attributes = attributes
    else:
        parsed_attributes = {"items": attributes}

    if shape_type == "rectangle":
        points = shape.get("points", [])
        if not isinstance(points, list) or len(points) < 4:
            return None
        rotation = float(shape.get("rotation", 0) or 0)
        return Annotation(
            id=annotation_id,
            type=AnnotationType.rectangle,
            label=label,
            attributes=parsed_attributes,
            geometry={
                "x1": float(points[0]),
                "y1": float(points[1]),
                "x2": float(points[2]),
                "y2": float(points[3]),
                "angle": rotation,
            },
        )
    if shape_type == "polygon":
        points = shape.get("points", [])
        if isinstance(points, str):
            parsed_points = _parse_points(points)
        else:
            parsed_points = [[float(point[0]), float(point[1])] for point in points] if isinstance(points, list) else []
        return Annotation(
            id=annotation_id,
            type=AnnotationType.polygon,
            label=label,
            attributes=parsed_attributes,
            geometry={"points": parsed_points},
        )
    if shape_type == "polyline":
        points = shape.get("points", [])
        if isinstance(points, str):
            parsed_points = _parse_points(points)
        else:
            parsed_points = [[float(point[0]), float(point[1])] for point in points] if isinstance(points, list) else []
        return Annotation(
            id=annotation_id,
            type=AnnotationType.polyline,
            label=label,
            attributes=parsed_attributes,
            geometry={"points": parsed_points},
        )
    if shape_type == "points":
        points = shape.get("points", [])
        if isinstance(points, str):
            parsed_points = _parse_points(points)
        else:
            parsed_points = [[float(point[0]), float(point[1])] for point in points] if isinstance(points, list) else []
        return Annotation(
            id=annotation_id,
            type=AnnotationType.points,
            label=label,
            attributes=parsed_attributes,
            geometry={"points": parsed_points},
        )
    if shape_type == "ellipse":
        points = shape.get("points", [])
        if not isinstance(points, list) or len(points) < 4:
            return None
        return Annotation(
            id=annotation_id,
            type=AnnotationType.ellipse,
            label=label,
            attributes=parsed_attributes,
            geometry={
                "cx": float(points[0]),
                "cy": float(points[1]),
                "rx": float(points[2]),
                "ry": float(points[3]),
                "angle": float(shape.get("rotation", 0) or 0),
            },
        )
    if shape_type == "box":
        points = shape.get("points", [])
        rotation = float(shape.get("rotation", 0) or 0)
        if not isinstance(points, list) or len(points) < 4:
            return None
        return Annotation(
            id=annotation_id,
            type=AnnotationType.rectangle,
            label=label,
            attributes=parsed_attributes,
            geometry={
                "x1": float(points[0]),
                "y1": float(points[1]),
                "x2": float(points[2]),
                "y2": float(points[3]),
                "angle": rotation,
            },
        )
    return None


def parse_app_bundle(dataset_root: Path) -> DatasetManifest:
    image_root = _find_image_root(dataset_root)
    if image_root is None:
        return DatasetManifest(format="app_bundle", images=[], annotations={})

    image_paths = sorted(
        path
        for path in image_root.rglob("*")
        if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
    )
    images: list[ImageInfo] = []
    for path in image_paths:
        try:
            with Image.open(path) as image:
                width, height = image.size
        except Exception:
            width, height = 0, 0
        images.append(ImageInfo(filename=path.relative_to(image_root).as_posix(), width=width, height=height))
    annotations: dict[str, list[Annotation]] = {image.filename: [] for image in images}

    task_path = dataset_root / "task.json"
    annotations_path = dataset_root / "annotations.json"
    task_labels: dict[str, str] = {}
    if task_path.exists():
        try:
            task_payload = json.loads(task_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            task_payload = {}
        for label in task_payload.get("labels", []):
            name = str(label.get("name", ""))
            if name:
                task_labels[name] = name

    if annotations_path.exists():
        try:
            payload = json.loads(annotations_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            payload = []
        shape_counter = 0
        frame_entries = payload if isinstance(payload, list) else [payload] if isinstance(payload, dict) else []
        for frame_entry in frame_entries:
            shapes = frame_entry.get("shapes", []) if isinstance(frame_entry, dict) else []
            for shape in shapes if isinstance(shapes, list) else []:
                if not isinstance(shape, dict):
                    continue
                frame_index = int(shape.get("frame", 0) or 0)
                if frame_index < 0 or frame_index >= len(images):
                    continue
                annotation = _annotation_from_shape(shape, str(shape.get("id", shape_counter)))
                shape_counter += 1
                if annotation is None:
                    continue
                if annotation.label in task_labels:
                    annotation.label = task_labels[annotation.label]
                annotations[images[frame_index].filename].append(annotation)

    inferred_labels = sorted({annotation.label for items in annotations.values() for annotation in items if annotation.label})
    return DatasetManifest(format="app_bundle", images=images, annotations=annotations, labels=sorted(task_labels) or inferred_labels)
