from __future__ import annotations

from pathlib import Path

from lxml import etree
from PIL import Image

from backend.app.models import Annotation, AnnotationType, DatasetManifest, ImageInfo

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}


def _safe_int(value: str | None, default: int = 0) -> int:
    try:
        return int(float(value)) if value is not None else default
    except (TypeError, ValueError):
        return default


def _is_pascal_voc_xml(xml_path: Path) -> bool:
    try:
        root = etree.parse(str(xml_path)).getroot()
    except Exception:
        return False
    return root.tag == "annotation" and (root.find("filename") is not None or root.find("size") is not None or root.find("object") is not None)


def _find_image_root(root: Path) -> Path:
    for candidate in (root / "JPEGImages", root / "images", root / "Data", root / "data"):
        if candidate.exists() and candidate.is_dir():
            return candidate
    return root


def _build_image_indexes(image_root: Path) -> tuple[dict[str, Path], dict[str, Path], dict[str, Path]]:
    by_relative: dict[str, Path] = {}
    by_name: dict[str, Path] = {}
    by_stem: dict[str, Path] = {}
    for image_path in image_root.rglob("*"):
        if not image_path.is_file() or image_path.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        by_relative[image_path.relative_to(image_root).as_posix()] = image_path
        by_name.setdefault(image_path.name, image_path)
        by_stem.setdefault(image_path.stem, image_path)
    return by_relative, by_name, by_stem


def _resolve_image_path(
    filename: str,
    xml_path: Path,
    by_relative: dict[str, Path],
    by_name: dict[str, Path],
    by_stem: dict[str, Path],
) -> Path | None:
    normalized = Path(filename).as_posix()
    return by_relative.get(normalized) or by_name.get(Path(filename).name) or by_stem.get(xml_path.stem)


def _resolve_image_dimensions(image_path: Path | None, xml_width: int, xml_height: int) -> tuple[int, int]:
    if xml_width > 0 and xml_height > 0:
        return xml_width, xml_height
    if image_path is None:
        return xml_width, xml_height
    try:
        with Image.open(image_path) as image:
            return image.size
    except Exception:
        return xml_width, xml_height


def _resolve_image_filename(image_root: Path, filename: str, image_path: Path | None) -> str:
    if image_path is not None:
        return image_path.relative_to(image_root).as_posix()
    return Path(filename).name


def parse_pascal_voc(dataset_root: Path) -> DatasetManifest:
    xml_files = [path for path in sorted(dataset_root.rglob("*.xml")) if _is_pascal_voc_xml(path)]
    image_root = _find_image_root(dataset_root)
    images: list[ImageInfo] = []
    annotations: dict[str, list[Annotation]] = {}
    labels: set[str] = set()
    seen_images: set[str] = set()
    by_relative, by_name, by_stem = _build_image_indexes(image_root)

    for xml_path in xml_files:
        root = etree.parse(str(xml_path)).getroot()
        xml_filename = root.findtext("filename") or f"{xml_path.stem}.jpg"
        image_path = _resolve_image_path(xml_filename, xml_path, by_relative, by_name, by_stem)
        filename = _resolve_image_filename(image_root, xml_filename, image_path)
        size_node = root.find("size")
        xml_width = _safe_int(size_node.findtext("width") if size_node is not None else None)
        xml_height = _safe_int(size_node.findtext("height") if size_node is not None else None)
        width, height = _resolve_image_dimensions(image_path, xml_width, xml_height)
        if filename not in seen_images:
            images.append(ImageInfo(filename=filename, width=width, height=height))
            seen_images.add(filename)

        parsed_annotations: list[Annotation] = []
        for object_index, object_node in enumerate(root.findall("object")):
            label = object_node.findtext("name") or ""
            if label:
                labels.add(label)
            bndbox = object_node.find("bndbox")
            if bndbox is None:
                continue
            xmin = float(bndbox.findtext("xmin", default="0"))
            ymin = float(bndbox.findtext("ymin", default="0"))
            xmax = float(bndbox.findtext("xmax", default="0"))
            ymax = float(bndbox.findtext("ymax", default="0"))
            parsed_annotations.append(
                Annotation(
                    id=f"{xml_path.stem}-{object_index}",
                    type=AnnotationType.rectangle,
                    label=label,
                    attributes={
                        "pose": object_node.findtext("pose", default="Unspecified"),
                        "truncated": _safe_int(object_node.findtext("truncated")),
                        "difficult": _safe_int(object_node.findtext("difficult")),
                    },
                    geometry={"x1": xmin, "y1": ymin, "x2": xmax, "y2": ymax},
                )
            )
        annotations[filename] = parsed_annotations

    return DatasetManifest(format="pascal_voc", images=images, annotations=annotations, labels=sorted(labels))
