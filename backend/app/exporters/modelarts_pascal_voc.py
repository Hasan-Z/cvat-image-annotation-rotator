from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path

from lxml import etree
from PIL import Image

from backend.app.models import Annotation
from backend.app.services.dataset_store import DatasetRecord
from backend.app.services.export_service import _rotate_geometry_for_export, visual_bbox_for_annotation


def _expand_empty_xml_tags(xml_bytes: bytes) -> bytes:
    xml_text = xml_bytes.decode("utf-8")
    previous = None
    while previous != xml_text:
        previous = xml_text
        xml_text = re.sub(r"<([A-Za-z_][\w:.-]*)([^<>]*)\s*/>", r"<\1\2></\1>", xml_text)
    return xml_text.encode("utf-8")


def _format_number(value: float | int | str) -> str:
    numeric = float(value)
    if numeric.is_integer():
        return str(int(numeric))
    return f"{numeric:.12f}".rstrip("0").rstrip(".")


def _rotate_image_file(image_path: Path, rotation: int) -> tuple[bytes, int, int]:
    with Image.open(image_path) as image:
        normalized_rotation = rotation % 360
        if normalized_rotation == 90:
            rotated = image.rotate(-90, expand=True)
        elif normalized_rotation == 180:
            rotated = image.rotate(180, expand=True)
        elif normalized_rotation == 270:
            rotated = image.rotate(-270, expand=True)
        else:
            rotated = image.copy()
        buffer = io.BytesIO()
        rotated.save(buffer, format=image.format or "PNG")
        return buffer.getvalue(), rotated.width, rotated.height


def _annotation_bbox(annotation: Annotation, width: int, height: int, rotation: int) -> tuple[float, float, float, float] | None:
    rotated = _rotate_geometry_for_export(annotation, width, height, rotation)
    bbox = visual_bbox_for_annotation(rotated)
    if bbox is None:
        return None
    return (
        float(bbox[0]),
        float(bbox[1]),
        float(bbox[0] + bbox[2]),
        float(bbox[1] + bbox[3]),
    )


def _build_annotation_xml(
    record: DatasetRecord,
    image_index: int,
    image_filename: str,
    width: int,
    height: int,
) -> bytes:
    root = etree.Element("annotation")
    etree.SubElement(root, "folder").text = "data"
    etree.SubElement(root, "filename").text = image_filename
    source = etree.SubElement(root, "source")
    etree.SubElement(source, "database").text = "unknown"
    size = etree.SubElement(root, "size")
    etree.SubElement(size, "width").text = str(width)
    etree.SubElement(size, "height").text = str(height)
    etree.SubElement(size, "depth").text = "3"
    etree.SubElement(root, "segmented").text = "0"

    rotation = record.image_rotation(image_index)
    image = record.images[image_index]
    for annotation in record.annotations.get(image.filename, []):
        bbox = _annotation_bbox(annotation, image.width, image.height, rotation)
        if bbox is None:
            continue
        xmin, ymin, xmax, ymax = bbox
        object_node = etree.SubElement(root, "object")
        etree.SubElement(object_node, "name").text = annotation.label
        etree.SubElement(object_node, "pose").text = str(annotation.attributes.get("pose", "Unspecified"))
        etree.SubElement(object_node, "truncated").text = str(int(annotation.attributes.get("truncated", 0) or 0))
        etree.SubElement(object_node, "difficult").text = str(int(annotation.attributes.get("difficult", 0) or 0))
        bndbox = etree.SubElement(object_node, "bndbox")
        etree.SubElement(bndbox, "xmin").text = _format_number(xmin)
        etree.SubElement(bndbox, "ymin").text = _format_number(ymin)
        etree.SubElement(bndbox, "xmax").text = _format_number(xmax)
        etree.SubElement(bndbox, "ymax").text = _format_number(ymax)

    return _expand_empty_xml_tags(etree.tostring(root, pretty_print=True, encoding="UTF-8"))


def build_modelarts_pascal_voc_zip_subset(
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
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for image_index in selected_indices:
            image = record.images[image_index]
            image_path = record.resolve_image_path(image_index)
            if image_path is None:
                continue
            image_name = Path(image.filename).name
            image_bytes, width, height = _rotate_image_file(image_path, record.image_rotation(image_index))
            archive.writestr(f"data/{image_name}", image_bytes)
            archive.writestr(
                f"data/{Path(image_name).stem}.xml",
                _build_annotation_xml(record, image_index, image_name, width, height),
            )
