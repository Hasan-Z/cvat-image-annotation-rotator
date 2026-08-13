from __future__ import annotations

from pathlib import Path

from PIL import Image

from backend.app.models import Annotation, AnnotationType, DatasetManifest, ImageInfo


def _image_root(dataset_root: Path) -> Path:
    for candidate in (dataset_root / "image_2", dataset_root / "images", dataset_root):
        if candidate.exists():
            return candidate
    return dataset_root


def _label_root(dataset_root: Path) -> Path:
    for candidate in (dataset_root / "label_2", dataset_root / "labels"):
        if candidate.exists():
            return candidate
    return dataset_root


def parse_kitti(dataset_root: Path) -> DatasetManifest:
    images: list[ImageInfo] = []
    annotations: dict[str, list[Annotation]] = {}
    image_root = _image_root(dataset_root)
    label_root = _label_root(dataset_root)
    for image_path in sorted(path for path in image_root.rglob("*") if path.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp"}):
        try:
            with Image.open(image_path) as image:
                width, height = image.size
        except Exception:
            width, height = 0, 0
        images.append(ImageInfo(filename=image_path.name, width=width, height=height))
        parsed: list[Annotation] = []
        label_path = label_root / f"{image_path.stem}.txt"
        if label_path.exists():
            for line_index, line in enumerate(label_path.read_text(encoding="utf-8").splitlines()):
                parts = line.split()
                if len(parts) < 8:
                    continue
                parsed.append(
                    Annotation(
                        id=f"{image_path.stem}-{line_index}",
                        type=AnnotationType.rectangle,
                        label=parts[0],
                        attributes={
                            "truncated": float(parts[1]),
                            "occluded": int(float(parts[2])),
                            "alpha": float(parts[3]),
                        },
                        geometry={"x1": float(parts[4]), "y1": float(parts[5]), "x2": float(parts[6]), "y2": float(parts[7])},
                    )
                )
        annotations[image_path.name] = parsed
    return DatasetManifest(format="kitti", images=images, annotations=annotations)
