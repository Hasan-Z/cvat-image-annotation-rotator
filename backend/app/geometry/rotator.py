from __future__ import annotations

from typing import Any

from backend.app.models import Annotation, AnnotationType, RotationDirection


def _normalize_angle(angle: int) -> int:
    return angle % 360


def _to_degrees(angle: int | RotationDirection) -> int:
    if isinstance(angle, RotationDirection):
        mapping = {
            RotationDirection.left: 270,
            RotationDirection.right: 90,
            RotationDirection.rotate_180: 180,
        }
        return mapping[angle]
    return _normalize_angle(angle)


def _center(width: int, height: int) -> tuple[float, float]:
    return (width - 1) / 2.0, (height - 1) / 2.0


def rotate_point(x: float, y: float, width: int, height: int, angle: int) -> tuple[float, float]:
    angle = _normalize_angle(angle)
    if angle == 90:
        return height - y, x
    if angle == 180:
        return width - x, height - y
    if angle == 270:
        return y, width - x
    return x, y


def _rotate_rectangle(geometry: dict[str, Any], width: int, height: int, angle: int) -> dict[str, Any]:
    x1, y1 = geometry["x1"], geometry["y1"]
    x2, y2 = geometry["x2"], geometry["y2"]
    points = [
        rotate_point(x1, y1, width, height, angle),
        rotate_point(x2, y1, width, height, angle),
        rotate_point(x2, y2, width, height, angle),
        rotate_point(x1, y2, width, height, angle),
    ]
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return {"x1": min(xs), "y1": min(ys), "x2": max(xs), "y2": max(ys)}


def _rotate_points(points: list[list[float]], width: int, height: int, angle: int) -> list[list[float]]:
    return [[*rotate_point(x, y, width, height, angle)] for x, y in points]


def _rotate_polygon(geometry: dict[str, Any], width: int, height: int, angle: int) -> dict[str, Any]:
    return {**geometry, "points": _rotate_points(geometry["points"], width, height, angle)}


def _rotate_polyline(geometry: dict[str, Any], width: int, height: int, angle: int) -> dict[str, Any]:
    return {**geometry, "points": _rotate_points(geometry["points"], width, height, angle)}


def _rotate_points_geometry(geometry: dict[str, Any], width: int, height: int, angle: int) -> dict[str, Any]:
    return {**geometry, "points": _rotate_points(geometry["points"], width, height, angle)}


def _rotate_ellipse(geometry: dict[str, Any], width: int, height: int, angle: int) -> dict[str, Any]:
    center_x, center_y = geometry["cx"], geometry["cy"]
    new_cx, new_cy = rotate_point(center_x, center_y, width, height, angle)
    new_angle = _normalize_angle(geometry.get("angle", 0) + angle)
    return {**geometry, "cx": new_cx, "cy": new_cy, "angle": new_angle}


def _rotate_rotated_rectangle(geometry: dict[str, Any], width: int, height: int, angle: int) -> dict[str, Any]:
    points = geometry["points"]
    rotated = _rotate_points(points, width, height, angle)
    return {**geometry, "points": rotated, "angle": _normalize_angle(geometry.get("angle", 0) + angle)}


def _rotate_cuboid(geometry: dict[str, Any], width: int, height: int, angle: int) -> dict[str, Any]:
    faces = geometry.get("faces", [])
    rotated_faces = []
    for face in faces:
        rotated_faces.append(_rotate_points(face, width, height, angle))
    return {**geometry, "faces": rotated_faces}


def _rotate_skeleton(geometry: dict[str, Any], width: int, height: int, angle: int) -> dict[str, Any]:
    nodes = geometry.get("nodes", {})
    rotated_nodes = {}
    for key, point in nodes.items():
        rotated_nodes[key] = list(rotate_point(point[0], point[1], width, height, angle))
    edges = geometry.get("edges", [])
    return {**geometry, "nodes": rotated_nodes, "edges": edges}


def _rotate_mask(geometry: dict[str, Any], width: int, height: int, angle: int) -> dict[str, Any]:
    import cv2
    import numpy as np

    mask = np.asarray(geometry["mask"], dtype=np.uint8)
    if angle == 90:
        rotated = cv2.rotate(mask, cv2.ROTATE_90_CLOCKWISE)
    elif angle == 180:
        rotated = cv2.rotate(mask, cv2.ROTATE_180)
    elif angle == 270:
        rotated = cv2.rotate(mask, cv2.ROTATE_90_COUNTERCLOCKWISE)
    else:
        rotated = mask
    return {**geometry, "mask": rotated.tolist()}


def rotate_annotation(
    annotation: Annotation,
    image_width: int,
    image_height: int,
    angle: int | RotationDirection,
) -> Annotation:
    rotation = _to_degrees(angle)
    geometry = annotation.geometry
    annotation_type = annotation.type

    if rotation == 0:
        return annotation

    if annotation_type == AnnotationType.rectangle:
        rotated_geometry = _rotate_rectangle(geometry, image_width, image_height, rotation)
    elif annotation_type == AnnotationType.polygon:
        rotated_geometry = _rotate_polygon(geometry, image_width, image_height, rotation)
    elif annotation_type == AnnotationType.polyline:
        rotated_geometry = _rotate_polyline(geometry, image_width, image_height, rotation)
    elif annotation_type == AnnotationType.points:
        rotated_geometry = _rotate_points_geometry(geometry, image_width, image_height, rotation)
    elif annotation_type == AnnotationType.ellipse:
        rotated_geometry = _rotate_ellipse(geometry, image_width, image_height, rotation)
    elif annotation_type == AnnotationType.rotated_rectangle:
        rotated_geometry = _rotate_rotated_rectangle(geometry, image_width, image_height, rotation)
    elif annotation_type == AnnotationType.cuboid:
        rotated_geometry = _rotate_cuboid(geometry, image_width, image_height, rotation)
    elif annotation_type == AnnotationType.skeleton:
        rotated_geometry = _rotate_skeleton(geometry, image_width, image_height, rotation)
    elif annotation_type == AnnotationType.mask:
        rotated_geometry = _rotate_mask(geometry, image_width, image_height, rotation)
    else:
        rotated_geometry = geometry

    return annotation.model_copy(update={"geometry": rotated_geometry})


def rotate_image_dimensions(width: int, height: int, angle: int | RotationDirection) -> tuple[int, int]:
    rotation = _to_degrees(angle)
    if rotation in (90, 270):
        return height, width
    return width, height
