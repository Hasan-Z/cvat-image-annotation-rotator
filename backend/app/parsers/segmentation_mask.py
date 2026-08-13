from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from backend.app.models import Annotation, AnnotationType, DatasetManifest, ImageInfo
from backend.app.utils.files import resolve_file_path


def _image_paths(root: Path) -> list[Path]:
    image_root = root / "images" if (root / "images").exists() else root
    return sorted(
        path
        for path in image_root.rglob("*")
        if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
    )


def parse_segmentation_mask(dataset_root: Path) -> DatasetManifest:
    mask_root = next((candidate for candidate in (dataset_root / "masks", dataset_root / "SegmentationClass") if candidate.exists()), None)
    if mask_root is None:
        return DatasetManifest(format="segmentation_mask", images=[], annotations={})
    images: list[ImageInfo] = []
    annotations: dict[str, list[Annotation]] = {}
    for image_path in _image_paths(dataset_root):
        if mask_root in image_path.parents:
            continue
        try:
            with Image.open(image_path) as image:
                width, height = image.size
        except Exception:
            width, height = 0, 0
        filename = image_path.name
        images.append(ImageInfo(filename=filename, width=width, height=height))
        parsed: list[Annotation] = []
        mask_path = resolve_file_path(mask_root, {path.stem: path for path in mask_root.rglob("*") if path.is_file()}, image_path.stem)
        if mask_path is not None:
            with Image.open(mask_path) as mask_image:
                mask_array = np.asarray(mask_image.convert("L"))
            for value in sorted(int(value) for value in np.unique(mask_array) if int(value) != 0):
                parsed.append(
                    Annotation(
                        id=f"{image_path.stem}-{value}",
                        type=AnnotationType.mask,
                        label=str(value),
                        attributes={"mask_value": value},
                        geometry={"mask": (mask_array == value).astype(np.uint8).tolist()},
                    )
                )
        annotations[filename] = parsed
    return DatasetManifest(format="segmentation_mask", images=images, annotations=annotations)
