from __future__ import annotations

import csv
from pathlib import Path

from PIL import Image

from backend.app.models import Annotation, AnnotationType, DatasetManifest, ImageInfo


def _images(root: Path) -> list[Path]:
    image_root = root / "images" if (root / "images").exists() else root
    return sorted(path for path in image_root.rglob("*") if path.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp", ".webp"})


def _annotation_csv(root: Path) -> Path | None:
    for candidate in root.rglob("*.csv"):
        try:
            header = candidate.read_text(encoding="utf-8").splitlines()[0]
        except Exception:
            continue
        if {"ImageID", "LabelName", "XMin", "XMax", "YMin", "YMax"}.issubset(set(header.split(","))):
            return candidate
    return None


def parse_open_images(dataset_root: Path) -> DatasetManifest:
    csv_path = _annotation_csv(dataset_root)
    if csv_path is None:
        return DatasetManifest(format="open_images", images=[], annotations={})
    image_paths = _images(dataset_root)
    image_by_id = {path.stem: path for path in image_paths}
    images: list[ImageInfo] = []
    annotations: dict[str, list[Annotation]] = {}
    for image_path in image_paths:
        try:
            with Image.open(image_path) as image:
                width, height = image.size
        except Exception:
            width, height = 0, 0
        images.append(ImageInfo(filename=image_path.name, width=width, height=height))
        annotations[image_path.name] = []
    with csv_path.open("r", encoding="utf-8", newline="") as source:
        for row_index, row in enumerate(csv.DictReader(source)):
            image_id = row.get("ImageID", "")
            image_path = image_by_id.get(image_id)
            if image_path is None:
                continue
            image_info = next((image for image in images if image.filename == image_path.name), None)
            if image_info is None:
                continue
            width, height = image_info.width, image_info.height
            annotations[image_path.name].append(
                Annotation(
                    id=str(row_index),
                    type=AnnotationType.rectangle,
                    label=row.get("LabelName", ""),
                    attributes={key: value for key, value in row.items() if key not in {"ImageID", "LabelName", "XMin", "XMax", "YMin", "YMax"}},
                    geometry={
                        "x1": float(row.get("XMin", 0) or 0) * width,
                        "y1": float(row.get("YMin", 0) or 0) * height,
                        "x2": float(row.get("XMax", 0) or 0) * width,
                        "y2": float(row.get("YMax", 0) or 0) * height,
                    },
                )
            )
    return DatasetManifest(format="open_images", images=images, annotations=annotations)
