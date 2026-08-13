from __future__ import annotations

from pathlib import Path

from PIL import Image

from backend.app.models import DatasetManifest, ImageInfo

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}


def iter_image_files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS)


def parse_image_folder(root: Path) -> DatasetManifest:
    images: list[ImageInfo] = []
    annotations: dict[str, list] = {}
    image_labels: dict[str, str] = {}
    for image_path in iter_image_files(root):
        try:
            with Image.open(image_path) as image:
                width, height = image.size
        except Exception:
            continue
        filename = image_path.relative_to(root).as_posix()
        images.append(ImageInfo(filename=filename, width=width, height=height))
        annotations[filename] = []
        relative_parent = image_path.relative_to(root).parent
        if str(relative_parent) not in {"", "."}:
            image_labels[filename] = relative_parent.parts[0]
    return DatasetManifest(
        format="image_folder",
        images=images,
        annotations=annotations,
        labels=sorted(set(image_labels.values())),
        image_labels=image_labels,
    )
