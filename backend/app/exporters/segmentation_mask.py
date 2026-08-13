from __future__ import annotations

import io
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from backend.app.models import AnnotationType
from backend.app.services.dataset_store import DatasetRecord
from backend.app.services.export_service import _rectangle_points, _rotate_geometry_for_export


def _rotate_image_file(image_path: Path, rotation: int) -> tuple[bytes, int, int]:
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
        return buffer.getvalue(), rotated.width, rotated.height


def _draw_annotation(mask: Image.Image, annotation, value: int) -> None:
    draw = ImageDraw.Draw(mask)
    geometry = annotation.geometry
    if annotation.type == AnnotationType.rectangle:
        if float(geometry.get("angle", 0) or 0) % 360:
            draw.polygon([tuple(point) for point in _rectangle_points(geometry)], fill=value)
        else:
            draw.rectangle([geometry["x1"], geometry["y1"], geometry["x2"], geometry["y2"]], fill=value)
    elif annotation.type in {AnnotationType.polygon, AnnotationType.rotated_rectangle} and "points" in geometry:
        draw.polygon([tuple(point) for point in geometry["points"]], fill=value)
    elif annotation.type == AnnotationType.ellipse:
        draw.ellipse(
            [
                geometry["cx"] - geometry["rx"],
                geometry["cy"] - geometry["ry"],
                geometry["cx"] + geometry["rx"],
                geometry["cy"] + geometry["ry"],
            ],
            fill=value,
        )
    elif annotation.type == AnnotationType.mask:
        mask_array = np.array(mask)
        source = np.asarray(geometry["mask"], dtype=np.uint8)
        if source.shape == mask_array.shape:
            mask_array[source > 0] = value
            mask.paste(Image.fromarray(mask_array))


def build_segmentation_mask_zip_subset(
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
    labels = sorted({annotation.label for index in selected_indices for annotation in record.annotations.get(record.images[index].filename, []) if annotation.label})
    values = {label: index + 1 for index, label in enumerate(labels)}
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("labelmap.txt", "\n".join(f"{value} {label}" for label, value in values.items()))
        for image_index in selected_indices:
            image = record.images[image_index]
            image_path = record.resolve_image_path(image_index)
            if image_path is None:
                continue
            image_bytes, width, height = _rotate_image_file(image_path, record.image_rotation(image_index))
            filename = Path(image.filename).name
            archive.writestr(f"images/{filename}", image_bytes)
            mask = Image.new("L", (width, height), 0)
            for annotation in record.annotations.get(image.filename, []):
                if not annotation.label:
                    continue
                rotated = _rotate_geometry_for_export(annotation, image.width, image.height, record.image_rotation(image_index))
                _draw_annotation(mask, rotated, values[rotated.label])
            buffer = io.BytesIO()
            mask.save(buffer, format="PNG")
            archive.writestr(f"masks/{Path(filename).stem}.png", buffer.getvalue())
