from backend.app.geometry.rotator import rotate_annotation, rotate_image_dimensions
from backend.app.models import Annotation, AnnotationType


def test_rotate_rectangle_90() -> None:
    annotation = Annotation(
        id="1",
        type=AnnotationType.rectangle,
        label="car",
        attributes={},
        geometry={"x1": 10, "y1": 20, "x2": 30, "y2": 50},
    )
    rotated = rotate_annotation(annotation, 100, 200, 90)
    assert rotated.geometry["x1"] == 150
    assert rotated.geometry["y1"] == 10
    assert rotated.geometry["x2"] == 180
    assert rotated.geometry["y2"] == 30


def test_rotate_dimensions() -> None:
    assert rotate_image_dimensions(1920, 1080, 90) == (1080, 1920)
