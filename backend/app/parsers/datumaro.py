from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from backend.app.models import Annotation, AnnotationType, DatasetManifest, ImageInfo
from backend.app.utils.files import resolve_file_path


def _resolve_image_root(dataset_root: Path) -> Path:
    for candidate in (dataset_root / "images", dataset_root / "Images", dataset_root / "data", dataset_root):
        if candidate.exists():
            return candidate
    return dataset_root


def _annotation_from_item(item: dict[str, object], annotation_id: str) -> Annotation | None:
    annotation_type = str(item.get("type", "")).lower()
    label = str(item.get("label", ""))
    if annotation_type == "bbox":
        bbox = item.get("bbox", [])
        if not isinstance(bbox, list) or len(bbox) < 4:
            return None
        x1, y1, width, height = [float(value) for value in bbox[:4]]
        return Annotation(
            id=annotation_id,
            type=AnnotationType.rectangle,
            label=label,
            attributes=dict(item.get("attributes", {})) if isinstance(item.get("attributes", {}), dict) else {},
            geometry={"x1": x1, "y1": y1, "x2": x1 + width, "y2": y1 + height},
        )
    if annotation_type == "polygon":
        points = item.get("points", [])
        parsed_points = [[float(point[0]), float(point[1])] for point in points] if isinstance(points, list) else []
        return Annotation(id=annotation_id, type=AnnotationType.polygon, label=label, attributes={}, geometry={"points": parsed_points})
    if annotation_type == "polyline":
        points = item.get("points", [])
        parsed_points = [[float(point[0]), float(point[1])] for point in points] if isinstance(points, list) else []
        return Annotation(id=annotation_id, type=AnnotationType.polyline, label=label, attributes={}, geometry={"points": parsed_points})
    if annotation_type == "points":
        points = item.get("points", [])
        parsed_points = [[float(point[0]), float(point[1])] for point in points] if isinstance(points, list) else []
        return Annotation(id=annotation_id, type=AnnotationType.points, label=label, attributes={}, geometry={"points": parsed_points})
    return None


def parse_datumaro(dataset_root: Path) -> DatasetManifest:
    dataset_json_path = dataset_root / "dataset.json"
    if not dataset_json_path.exists():
        dataset_json_path = next(dataset_root.rglob("dataset.json"), None)  # type: ignore[assignment]
    if dataset_json_path is None or not dataset_json_path.exists():
        return DatasetManifest(format="datumaro", images=[], annotations={})
    payload = json.loads(dataset_json_path.read_text(encoding="utf-8"))
    image_root = _resolve_image_root(dataset_root)
    images: list[ImageInfo] = []
    annotations: dict[str, list[Annotation]] = {}
    for item_index, item in enumerate(payload.get("items", [])):
        if not isinstance(item, dict):
            continue
        image_info = item.get("image", {})
        image_path_name = ""
        if isinstance(image_info, dict):
            image_path_name = str(image_info.get("path", "") or image_info.get("name", ""))
        image_id = str(item.get("id", f"item_{item_index}"))
        image_path = resolve_file_path(image_root, {path.relative_to(image_root).as_posix(): path for path in image_root.rglob("*") if path.is_file()}, image_path_name)
        width = int(image_info.get("size", [0, 0])[0]) if isinstance(image_info, dict) and isinstance(image_info.get("size"), list) and image_info.get("size") else 0
        height = int(image_info.get("size", [0, 0])[1]) if isinstance(image_info, dict) and isinstance(image_info.get("size"), list) and len(image_info.get("size")) >= 2 else 0
        if (width <= 0 or height <= 0) and image_path is not None:
            try:
                with Image.open(image_path) as image:
                    width, height = image.size
            except Exception:
                width, height = 0, 0
        filename = Path(image_path_name).name if image_path_name else f"{image_id}.jpg"
        images.append(ImageInfo(filename=filename, width=width, height=height))
        parsed_annotations: list[Annotation] = []
        for annotation_index, annotation_item in enumerate(item.get("annotations", [])):
            if isinstance(annotation_item, dict):
                annotation = _annotation_from_item(annotation_item, f"{image_id}-{annotation_index}")
                if annotation is not None:
                    parsed_annotations.append(annotation)
        annotations[filename] = parsed_annotations
    return DatasetManifest(format="datumaro", images=images, annotations=annotations)
