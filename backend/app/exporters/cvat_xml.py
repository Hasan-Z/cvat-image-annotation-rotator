from __future__ import annotations

import io
import re
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from lxml import etree
from PIL import Image

from backend.app.geometry.rotator import rotate_image_dimensions
from backend.app.models import Annotation, AnnotationType
from backend.app.services.dataset_store import DatasetRecord
from backend.app.services.export_service import _rotate_geometry_for_export


def _expand_empty_xml_tags(xml_bytes: bytes) -> bytes:
    xml_text = xml_bytes.decode("utf-8")
    previous = None
    while previous != xml_text:
        previous = xml_text
        xml_text = re.sub(r"<([A-Za-z_][\w:.-]*)([^<>]*)\s*/>", r"<\1\2></\1>", xml_text)
    return xml_text.encode("utf-8")


def _label_color(label: str) -> str:
    palette = ["#4704fb", "#5b98c6", "#2acdcf", "#ff7f50", "#9b59b6", "#22c55e", "#eab308"]
    return palette[sum(ord(character) for character in label) % len(palette)]


def _collect_labels(record: DatasetRecord, selected_indices: list[int]) -> list[str]:
    labels = {
        annotation.label
        for index in selected_indices
        for annotation in record.annotations.get(record.images[index].filename, [])
        if annotation.label
    }
    labels.update(label for label in record.labels if label)
    return sorted(labels)


def _selected_indices(record: DatasetRecord, start_index: int | None, end_index: int | None) -> list[int]:
    return [
        index
        for index in range(len(record.images))
        if not record.is_deleted(index)
        and (start_index is None or index >= start_index)
        and (end_index is None or index <= end_index)
    ]


def _rotate_image_file(image_path: Path, rotation: int) -> bytes:
    with Image.open(image_path) as image:
        rotation = rotation % 360
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
        return buffer.getvalue()


def _points_to_string(points: list[list[float]]) -> str:
    return ";".join(f"{x:.6f},{y:.6f}" for x, y in points)


def _build_meta(record: DatasetRecord, selected_indices: list[int]) -> etree._Element:
    dumped_at = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S.%f+00:00")
    meta = etree.Element("meta")
    task = etree.SubElement(meta, "task")
    etree.SubElement(task, "id").text = "0"
    etree.SubElement(task, "name").text = record.dataset_id
    etree.SubElement(task, "size").text = str(len(selected_indices))
    etree.SubElement(task, "mode").text = "annotation"
    etree.SubElement(task, "overlap").text = "0"
    etree.SubElement(task, "bugtracker").text = ""
    etree.SubElement(task, "flipped").text = "False"
    etree.SubElement(task, "created").text = dumped_at
    etree.SubElement(task, "updated").text = dumped_at
    etree.SubElement(task, "subset").text = "default"
    etree.SubElement(task, "start_frame").text = "0"
    etree.SubElement(task, "stop_frame").text = str(max(0, len(selected_indices) - 1))
    etree.SubElement(task, "frame_filter").text = ""
    segments = etree.SubElement(task, "segments")
    segment = etree.SubElement(segments, "segment")
    etree.SubElement(segment, "id").text = "0"
    etree.SubElement(segment, "start").text = "0"
    etree.SubElement(segment, "stop").text = str(max(0, len(selected_indices) - 1))
    etree.SubElement(segment, "url").text = ""
    owner = etree.SubElement(task, "owner")
    etree.SubElement(owner, "username").text = ""
    etree.SubElement(owner, "email").text = ""
    etree.SubElement(task, "assignee")
    etree.SubElement(task, "labels")
    labels_parent = task.find("labels")
    assert labels_parent is not None
    for label in _collect_labels(record, selected_indices):
        label_node = etree.SubElement(labels_parent, "label")
        etree.SubElement(label_node, "name").text = label
        etree.SubElement(label_node, "color").text = _label_color(label)
        etree.SubElement(label_node, "type").text = "any"
        etree.SubElement(label_node, "attributes")
    etree.SubElement(meta, "dumped").text = dumped_at
    return meta


def _shape_common_attrs(label: str) -> dict[str, str]:
    return {
        "label": label,
        "occluded": "0",
        "source": "manual",
        "z_order": "0",
    }


def _add_rotation_attr(attrs: dict[str, str], angle: object, force_zero: bool = False) -> dict[str, str]:
    try:
        rotation = float(angle or 0)
    except (TypeError, ValueError):
        rotation = 0
    if force_zero or rotation % 360 != 0:
        attrs["rotation"] = str(int(rotation)) if float(rotation).is_integer() else str(rotation)
    return attrs


def _annotation_to_xml(image_node: etree._Element, annotation: Annotation, width: int, height: int, rotation: int) -> None:
    rotated = _rotate_geometry_for_export(annotation, width, height, rotation)
    geometry = rotated.geometry
    common_attrs = _shape_common_attrs(rotated.label)
    if rotated.type == AnnotationType.rectangle:
        box = etree.SubElement(
            image_node,
            "box",
            **_add_rotation_attr(
                {
                    **common_attrs,
                    "xtl": f"{float(geometry['x1']):.2f}",
                    "ytl": f"{float(geometry['y1']):.2f}",
                    "xbr": f"{float(geometry['x2']):.2f}",
                    "ybr": f"{float(geometry['y2']):.2f}",
                },
                geometry.get("angle", 0),
                force_zero=geometry.get("dot_reset") is True,
            ),
        )
        box.text = "\n    "
    elif rotated.type == AnnotationType.rotated_rectangle:
        points = geometry.get("points")
        if points:
            xs = [point[0] for point in points]
            ys = [point[1] for point in points]
            box = etree.SubElement(
                image_node,
                "box",
                **_add_rotation_attr(
                    {
                        **common_attrs,
                        "xtl": f"{float(min(xs)):.2f}",
                        "ytl": f"{float(min(ys)):.2f}",
                        "xbr": f"{float(max(xs)):.2f}",
                        "ybr": f"{float(max(ys)):.2f}",
                    },
                    geometry.get("angle", 0),
                    force_zero=geometry.get("dot_reset") is True,
                ),
            )
            box.text = "\n    "
        else:
            box = etree.SubElement(
                image_node,
                "box",
                **_add_rotation_attr(
                    {
                        **common_attrs,
                        "xtl": f"{float(geometry['x1']):.2f}",
                        "ytl": f"{float(geometry['y1']):.2f}",
                        "xbr": f"{float(geometry['x2']):.2f}",
                        "ybr": f"{float(geometry['y2']):.2f}",
                    },
                    geometry.get("angle", 0),
                    force_zero=geometry.get("dot_reset") is True,
                ),
            )
            box.text = "\n    "
    elif rotated.type == AnnotationType.polygon:
        polygon = etree.SubElement(image_node, "polygon", points=_points_to_string(geometry["points"]), **common_attrs)
        polygon.text = "\n    "
    elif rotated.type == AnnotationType.polyline:
        polyline = etree.SubElement(image_node, "polyline", points=_points_to_string(geometry["points"]), **common_attrs)
        polyline.text = "\n    "
    elif rotated.type == AnnotationType.points:
        points_node = etree.SubElement(image_node, "points", points=_points_to_string(geometry["points"]), **common_attrs)
        points_node.text = "\n    "
    elif rotated.type == AnnotationType.ellipse:
        ellipse = etree.SubElement(
            image_node,
            "ellipse",
            **_add_rotation_attr(
                {
                    **common_attrs,
                    "cx": f"{float(geometry['cx']):.2f}",
                    "cy": f"{float(geometry['cy']):.2f}",
                    "rx": f"{float(geometry['rx']):.2f}",
                    "ry": f"{float(geometry['ry']):.2f}",
                },
                geometry.get("angle", 0),
                force_zero=geometry.get("dot_reset") is True,
            ),
        )
        ellipse.text = "\n    "


def _export_image_name(image_filename: str, include_images_prefix: bool) -> str:
    basename = Path(image_filename).name
    return f"images/{basename}" if include_images_prefix else basename


def build_cvat_for_images_zip_subset(
    record: DatasetRecord,
    output_path: Path,
    start_index: int | None,
    end_index: int | None,
    include_images_prefix: bool = True,
) -> None:
    selected_indices = _selected_indices(record, start_index, end_index)
    annotations = etree.Element("annotations")
    version = etree.SubElement(annotations, "version")
    version.text = "1.1"
    annotations.append(_build_meta(record, selected_indices))

    for frame_index, image_index in enumerate(selected_indices):
        image = record.images[image_index]
        rotation = record.image_rotation(image_index)
        width, height = rotate_image_dimensions(image.width, image.height, rotation)
        image_node = etree.SubElement(
            annotations,
            "image",
            id=str(frame_index),
            name=_export_image_name(image.filename, include_images_prefix),
            width=str(width),
            height=str(height),
        )
        for annotation in record.annotations.get(image.filename, []):
            _annotation_to_xml(image_node, annotation, image.width, image.height, rotation)

    xml_bytes = _expand_empty_xml_tags(etree.tostring(annotations, pretty_print=True, xml_declaration=True, encoding="UTF-8"))
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("annotations.xml", xml_bytes)
        archive.writestr(
            "CVAT_IMPORT_NOTES.txt",
            "CVAT for Images 1.1 export from CVAT Dataset Rotation Tool.\n"
            "If importing annotations into an existing CVAT task, create matching task labels first:\n"
            + "\n".join(f"- {label}" for label in _collect_labels(record, selected_indices))
            + "\n",
        )
        for image_index in selected_indices:
            image = record.images[image_index]
            image_path = record.resolve_image_path(image_index)
            if image_path is None:
                continue
            archive.writestr(f"images/{Path(image.filename).name}", _rotate_image_file(image_path, record.image_rotation(image_index)))


def build_cvat_for_images_image_paths_zip_subset(
    record: DatasetRecord,
    output_path: Path,
    start_index: int | None,
    end_index: int | None,
) -> None:
    build_cvat_for_images_zip_subset(
        record,
        output_path,
        start_index,
        end_index,
        include_images_prefix=True,
    )


def export_cvat_xml(record: DatasetRecord, output_path: Path) -> None:
    build_cvat_for_images_zip_subset(record, output_path, None, None)
