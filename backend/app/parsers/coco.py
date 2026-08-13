from __future__ import annotations

import json
from pathlib import Path

from backend.app.models import Annotation, AnnotationType, DatasetManifest, ImageInfo


def _category_name_lookup(payload: dict[str, object]) -> dict[int, str]:
    lookup: dict[int, str] = {}
    for category in payload.get("categories", []):
        if isinstance(category, dict) and "id" in category:
            lookup[int(category["id"])] = str(category.get("name", category["id"]))
    return lookup


def _flat_polygon_to_points(segmentation: list[object]) -> list[list[float]]:
    return [
        [float(segmentation[index]), float(segmentation[index + 1])]
        for index in range(0, len(segmentation) - 1, 2)
    ]


def _keypoints_to_nodes(keypoints: list[object], category: dict[str, object] | None) -> dict[str, list[float]]:
    names = category.get("keypoints", []) if category else []
    nodes: dict[str, list[float]] = {}
    for keypoint_index in range(0, len(keypoints) - 2, 3):
        x = float(keypoints[keypoint_index])
        y = float(keypoints[keypoint_index + 1])
        visible = float(keypoints[keypoint_index + 2])
        if visible <= 0:
            continue
        name_index = keypoint_index // 3
        name = str(names[name_index]) if isinstance(names, list) and name_index < len(names) else f"point_{name_index}"
        nodes[name] = [x, y, visible]
    return nodes


def parse_coco_json(json_path: Path, image_root: Path) -> DatasetManifest:
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    images: list[ImageInfo] = []
    annotations: dict[str, list[Annotation]] = {}
    image_lookup = {image["id"]: image for image in payload.get("images", [])}
    category_lookup = _category_name_lookup(payload)
    category_payload_lookup = {
        int(category["id"]): category
        for category in payload.get("categories", [])
        if isinstance(category, dict) and "id" in category
    }
    for image in payload.get("images", []):
        images.append(
            ImageInfo(
                filename=image["file_name"],
                width=int(image["width"]),
                height=int(image["height"]),
            )
        )
        annotations[image["file_name"]] = []
    for item in payload.get("annotations", []):
        if not isinstance(item, dict) or item.get("image_id") not in image_lookup:
            continue
        image = image_lookup[item["image_id"]]
        category_id = int(item.get("category_id", 0) or 0)
        label = category_lookup.get(category_id, str(category_id))
        bbox = item.get("bbox", [0, 0, 0, 0])
        base_attributes = {
            "category_id": category_id,
            "iscrowd": item.get("iscrowd", 0),
            "area": item.get("area"),
        }
        keypoints = item.get("keypoints")
        if isinstance(keypoints, list) and keypoints:
            nodes = _keypoints_to_nodes(keypoints, category_payload_lookup.get(category_id))
            if nodes:
                annotations[image["file_name"]].append(
                    Annotation(
                        id=str(item.get("id", "")),
                        type=AnnotationType.skeleton,
                        label=label,
                        attributes=base_attributes,
                        geometry={"nodes": nodes, "bbox": bbox},
                    )
                )
                continue

        segmentation = item.get("segmentation")
        if isinstance(segmentation, list) and segmentation:
            first_polygon = segmentation[0] if isinstance(segmentation[0], list) else segmentation
            if isinstance(first_polygon, list) and len(first_polygon) >= 6:
                annotations[image["file_name"]].append(
                    Annotation(
                        id=str(item.get("id", "")),
                        type=AnnotationType.polygon,
                        label=label,
                        attributes=base_attributes,
                        geometry={"points": _flat_polygon_to_points(first_polygon)},
                    )
                )
                continue

        if isinstance(bbox, list) and len(bbox) >= 4:
            annotations[image["file_name"]].append(
                Annotation(
                    id=str(item.get("id", "")),
                    type=AnnotationType.rectangle,
                    label=label,
                    attributes=base_attributes,
                    geometry={
                        "x1": float(bbox[0]),
                        "y1": float(bbox[1]),
                        "x2": float(bbox[0]) + float(bbox[2]),
                        "y2": float(bbox[1]) + float(bbox[3]),
                    },
                )
            )
    return DatasetManifest(format="coco", images=images, annotations=annotations)
