from __future__ import annotations

from pathlib import Path

from PIL import Image

from backend.app.models import Annotation, AnnotationType, DatasetManifest, ImageInfo


def _class_names(dataset_root: Path) -> dict[str, str]:
    names_file = next((path for path in (dataset_root / "classes.txt", dataset_root / "obj.names") if path.exists()), None)
    if names_file is not None:
        return {str(index): line.strip() for index, line in enumerate(names_file.read_text(encoding="utf-8").splitlines()) if line.strip()}
    data_yaml = dataset_root / "data.yaml"
    if data_yaml.exists():
        text = data_yaml.read_text(encoding="utf-8")
        if "names:" in text:
            names_text = text.split("names:", 1)[1].strip()
            if names_text.startswith("["):
                names_text = names_text.split("]", 1)[0].lstrip("[").strip()
                names = [name.strip().strip("'\"") for name in names_text.split(",") if name.strip()]
                return {str(index): name for index, name in enumerate(names)}
    return {}


def _label_path_for_image(dataset_root: Path, image_path: Path) -> Path:
    if image_path.parent.name.lower() == "images":
        candidate = image_path.parent.parent / "labels" / f"{image_path.stem}.txt"
        if candidate.exists():
            return candidate
    candidate = image_path.with_suffix(".txt")
    if candidate.exists():
        return candidate
    return next(dataset_root.rglob(f"{image_path.stem}.txt"), candidate)


def _denormalize_point(x: float, y: float, width: int, height: int) -> list[float]:
    return [x * width if 0 <= x <= 1 else x, y * height if 0 <= y <= 1 else y]


def parse_yolo_dataset(dataset_root: Path) -> DatasetManifest:
    images: list[ImageInfo] = []
    annotations: dict[str, list[Annotation]] = {}
    classes = _class_names(dataset_root)
    for image_path in sorted(dataset_root.rglob("*")):
        if image_path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".bmp", ".webp"}:
            continue
        try:
            with Image.open(image_path) as image:
                width, height = image.size
        except Exception:
            width, height = 0, 0
        images.append(ImageInfo(filename=image_path.name, width=width, height=height))
        label_path = _label_path_for_image(dataset_root, image_path)
        parsed: list[Annotation] = []
        if label_path.exists():
            for line_index, line in enumerate(label_path.read_text(encoding="utf-8").splitlines()):
                parts = line.split()
                if len(parts) >= 5:
                    class_id = parts[0]
                    label = classes.get(class_id, class_id)
                    values = [float(value) for value in parts[1:]]
                    annotation_id = f"{image_path.stem}-{line_index}"
                    if len(values) == 8:
                        points = [_denormalize_point(values[index], values[index + 1], width, height) for index in range(0, 8, 2)]
                        parsed.append(
                            Annotation(
                                id=annotation_id,
                                type=AnnotationType.rotated_rectangle,
                                label=label,
                                attributes={"class_id": class_id},
                                geometry={"points": points, "angle": 0.0},
                            )
                        )
                    elif len(values) > 5 and (len(values) - 4) % 3 == 0:
                        cx, cy, box_width, box_height = values[:4]
                        box_center = _denormalize_point(cx, cy, width, height)
                        box_size = [box_width * width if 0 <= box_width <= 1 else box_width, box_height * height if 0 <= box_height <= 1 else box_height]
                        nodes = {}
                        for keypoint_index, value_index in enumerate(range(4, len(values) - 2, 3)):
                            x, y = _denormalize_point(values[value_index], values[value_index + 1], width, height)
                            visibility = values[value_index + 2]
                            nodes[f"point_{keypoint_index}"] = [x, y, visibility]
                        parsed.append(
                            Annotation(
                                id=annotation_id,
                                type=AnnotationType.skeleton,
                                label=label,
                                attributes={"class_id": class_id},
                                geometry={
                                    "nodes": nodes,
                                    "bbox": [
                                        box_center[0] - box_size[0] / 2,
                                        box_center[1] - box_size[1] / 2,
                                        box_size[0],
                                        box_size[1],
                                    ],
                                },
                            )
                        )
                    elif len(values) > 4 and len(values) % 2 == 0:
                        points = [_denormalize_point(values[index], values[index + 1], width, height) for index in range(0, len(values), 2)]
                        parsed.append(
                            Annotation(
                                id=annotation_id,
                                type=AnnotationType.polygon,
                                label=label,
                                attributes={"class_id": class_id},
                                geometry={"points": points},
                            )
                        )
                    else:
                        cx, cy, box_width, box_height = values[:4]
                        center = _denormalize_point(cx, cy, width, height)
                        absolute_width = box_width * width if 0 <= box_width <= 1 else box_width
                        absolute_height = box_height * height if 0 <= box_height <= 1 else box_height
                        parsed.append(
                            Annotation(
                                id=annotation_id,
                                type=AnnotationType.rectangle,
                                label=label,
                                attributes={"class_id": class_id},
                                geometry={
                                    "x1": center[0] - absolute_width / 2,
                                    "y1": center[1] - absolute_height / 2,
                                    "x2": center[0] + absolute_width / 2,
                                    "y2": center[1] + absolute_height / 2,
                                },
                            )
                        )
        annotations[image_path.name] = parsed
    return DatasetManifest(format="yolo", images=images, annotations=annotations)
