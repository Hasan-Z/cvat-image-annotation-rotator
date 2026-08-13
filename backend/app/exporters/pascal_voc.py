from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path

from lxml import etree
from PIL import Image

from backend.app.models import Annotation, AnnotationType
from backend.app.services.dataset_store import DatasetRecord
from backend.app.services.export_service import _rotate_geometry_for_export, visual_bbox_for_annotation


def _expand_empty_xml_tags(xml_bytes: bytes) -> bytes:
    xml_text = xml_bytes.decode("utf-8")
    previous = None
    while previous != xml_text:
        previous = xml_text
        xml_text = re.sub(r"<([A-Za-z_][\w:.-]*)([^<>]*)\s*/>", r"<\1\2></\1>", xml_text)
    return xml_text.encode("utf-8")


def _rotation_degrees(rotation: int) -> int:
    return rotation % 360


def _rotate_image_file(image_path: Path, rotation: int) -> tuple[bytes, int, int]:
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
        return buffer.getvalue(), rotated.width, rotated.height


def _format_number(value: float | int | str) -> str:
    numeric = float(value)
    if numeric.is_integer():
        return str(int(numeric))
    return f"{numeric:.12f}".rstrip("0").rstrip(".")


def _annotation_bbox(annotation: Annotation, width: int, height: int, rotation: int) -> tuple[float, float, float, float] | None:
    rotated = _rotate_geometry_for_export(annotation, width, height, rotation)
    geometry = rotated.geometry
    annotation_type = rotated.type.value
    if annotation_type == "rectangle":
        bbox = visual_bbox_for_annotation(rotated)
        if bbox is None:
            return None
        return (
            float(bbox[0]),
            float(bbox[1]),
            float(bbox[0] + bbox[2]),
            float(bbox[1] + bbox[3]),
        )
    if annotation_type == "rotated_rectangle" and "points" in geometry:
        xs = [float(point[0]) for point in geometry["points"]]
        ys = [float(point[1]) for point in geometry["points"]]
        return (min(xs), min(ys), max(xs), max(ys))
    if annotation_type in {"polygon", "polyline", "points"}:
        xs = [float(point[0]) for point in geometry["points"]]
        ys = [float(point[1]) for point in geometry["points"]]
        return (min(xs), min(ys), max(xs), max(ys))
    if annotation_type == "ellipse":
        cx = float(geometry["cx"])
        cy = float(geometry["cy"])
        rx = float(geometry["rx"])
        ry = float(geometry["ry"])
        return (
            cx - rx,
            cy - ry,
            cx + rx,
            cy + ry,
        )
    if annotation_type == "cuboid":
        faces = geometry.get("faces", [])
        points = [point for face in faces for point in face]
        if not points:
            return None
        xs = [float(point[0]) for point in points]
        ys = [float(point[1]) for point in points]
        return (min(xs), min(ys), max(xs), max(ys))
    if annotation_type == "skeleton":
        nodes = geometry.get("nodes", {})
        points = list(nodes.values())
        if not points:
            return None
        xs = [float(point[0]) for point in points]
        ys = [float(point[1]) for point in points]
        return (min(xs), min(ys), max(xs), max(ys))
    if annotation_type == "mask":
        mask = geometry.get("mask", [])
        rows = [index for index, row in enumerate(mask) if any(bool(value) for value in row)]
        if not rows:
            return None
        cols = [index for index in range(len(mask[0])) if any(bool(mask[row][index]) for row in rows)]
        if not cols:
            return None
        return (float(min(cols)), float(min(rows)), float(max(cols)), float(max(rows)))
    return None


def _annotation_rotation(annotation: Annotation, width: int, height: int, rotation: int) -> float:
    rotated = _rotate_geometry_for_export(annotation, width, height, rotation)
    return float(rotated.geometry.get("angle", 0) or 0)


def _build_annotation_xml(
    record: DatasetRecord,
    image_index: int,
    image_filename: str,
    width: int,
    height: int,
) -> bytes:
    root = etree.Element("annotation")
    etree.SubElement(root, "folder").text = ""
    etree.SubElement(root, "filename").text = image_filename
    source = etree.SubElement(root, "source")
    etree.SubElement(source, "database").text = "Unknown"
    etree.SubElement(source, "annotation").text = "Unknown"
    etree.SubElement(source, "image").text = "Unknown"
    size = etree.SubElement(root, "size")
    etree.SubElement(size, "width").text = str(width)
    etree.SubElement(size, "height").text = str(height)
    etree.SubElement(size, "depth").text = ""
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
        etree.SubElement(object_node, "truncated").text = str(int(annotation.attributes.get("truncated", 0) or 0))
        etree.SubElement(object_node, "occluded").text = str(int(annotation.attributes.get("occluded", 0) or 0))
        etree.SubElement(object_node, "difficult").text = str(int(annotation.attributes.get("difficult", 0) or 0))
        bndbox = etree.SubElement(object_node, "bndbox")
        etree.SubElement(bndbox, "xmin").text = _format_number(xmin)
        etree.SubElement(bndbox, "ymin").text = _format_number(ymin)
        etree.SubElement(bndbox, "xmax").text = _format_number(xmax)
        etree.SubElement(bndbox, "ymax").text = _format_number(ymax)
        attributes = etree.SubElement(object_node, "attributes")
        rotation_attribute = etree.SubElement(attributes, "attribute")
        etree.SubElement(rotation_attribute, "name").text = "rotation"
        etree.SubElement(rotation_attribute, "value").text = _format_number(
            _annotation_rotation(annotation, image.width, image.height, rotation)
        )

    return _expand_empty_xml_tags(etree.tostring(root, pretty_print=True, xml_declaration=True, encoding="UTF-8"))


def build_pascal_voc_zip_subset(
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
        image_ids: list[str] = []
        for image_index in selected_indices:
            image = record.images[image_index]
            image_path = record.resolve_image_path(image_index)
            if image_path is None:
                continue
            image_bytes, width, height = _rotate_image_file(image_path, record.image_rotation(image_index))
            image_name = Path(image.filename).name
            image_id = Path(image_name).stem
            image_ids.append(image_id)
            archive.writestr(f"JPEGImages/{image_name}", image_bytes)
            archive.writestr(
                f"Annotations/{image_id}.xml",
                _build_annotation_xml(record, image_index, image_name, width, height),
            )
        archive.writestr("ImageSets/Main/default.txt", "\n".join(image_ids) + ("\n" if image_ids else ""))
        archive.writestr(
            "CVAT_IMPORT_NOTES.txt",
            "Pascal VOC export from CVAT Dataset Rotation Tool.\n"
            "If importing annotations into an existing CVAT task, create matching task labels first:\n"
            + "\n".join(f"- {label}" for label in sorted(record.labels))
            + "\n",
        )
