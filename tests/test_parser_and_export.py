import json
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile

import pytest
from PIL import Image

from backend.app.models import Annotation, AnnotationOrientationDirection, AnnotationType, DatasetManifest, ImageInfo, RotationDirection
from backend.app.exporters.coco import build_coco_zip_subset
from backend.app.exporters.cvat_xml import build_cvat_for_images_image_paths_zip_subset, build_cvat_for_images_zip_subset
from backend.app.exporters.datumaro import build_datumaro_zip_subset
from backend.app.exporters.image_classification import build_image_classification_zip_subset
from backend.app.exporters.kitti import build_kitti_zip_subset
from backend.app.exporters.labelme import build_labelme_zip_subset
from backend.app.exporters.modelarts_pascal_voc import build_modelarts_pascal_voc_zip_subset
from backend.app.exporters.open_images import build_open_images_zip_subset
from backend.app.exporters.pascal_voc import build_pascal_voc_zip_subset
from backend.app.exporters.segmentation_mask import build_segmentation_mask_zip_subset
from backend.app.exporters.yolo import build_yolo_zip_subset
from backend.app.parsers.coco import parse_coco_json
from backend.app.parsers.cvat_xml import parse_cvat_xml
from backend.app.parsers.datumaro import parse_datumaro
from backend.app.parsers.kitti import parse_kitti
from backend.app.parsers.labelme import parse_labelme
from backend.app.parsers.open_images import parse_open_images
from backend.app.parsers.registry import parse_dataset_archive
from backend.app.parsers.segmentation_mask import parse_segmentation_mask
from backend.app.parsers.yolo import parse_yolo_dataset
from backend.app.services.dataset_store import DatasetRecord, DatasetStore
from backend.app.services.export_service import _rotate_geometry_for_export, build_export_zip, visual_bbox_for_annotation
from backend.app.utils.files import build_file_index, resolve_file_path


def test_parse_cvat_xml_rectangle(tmp_path: Path) -> None:
    xml_path = tmp_path / "annotations.xml"
    xml_path.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<annotations>
  <meta>
    <task>
      <labels>
        <label>
          <name>car</name>
        </label>
        <label>
          <name>unused</name>
        </label>
      </labels>
    </task>
  </meta>
  <image id="0" name="image.jpg" width="100" height="80">
    <box id="1" label="car" xtl="10" ytl="20" xbr="30" ybr="40" rotation="15"/>
  </image>
</annotations>
""",
        encoding="utf-8",
    )
    manifest = parse_cvat_xml(xml_path, tmp_path)
    assert manifest.format == "cvat_xml"
    assert manifest.images[0].filename == "image.jpg"
    assert manifest.annotations["image.jpg"][0].geometry["x1"] == 10.0
    assert manifest.annotations["image.jpg"][0].geometry["angle"] == 15.0
    assert manifest.labels == ["car", "unused"]


def test_rotate_annotation_orientation_changes_angle_only(tmp_path: Path) -> None:
    store = DatasetStore()
    record = DatasetRecord(
        dataset_id="dataset",
        root=tmp_path,
        asset_root=tmp_path,
        images=[ImageInfo(filename="image.jpg", width=100, height=80)],
        annotations={
            "image.jpg": [
                Annotation(
                    id="1",
                    type=AnnotationType.rectangle,
                    label="car",
                    attributes={},
                    geometry={"x1": 10, "y1": 20, "x2": 30, "y2": 40, "angle": 0},
                ),
                Annotation(
                    id="2",
                    type=AnnotationType.rectangle,
                    label="logo",
                    attributes={},
                    geometry={"x1": 50, "y1": 20, "x2": 70, "y2": 40, "angle": 0},
                ),
            ]
        },
    )
    store._datasets["dataset"] = record

    _, updated = store.rotate_annotation_orientation("dataset", 0, RotationDirection.right, "car")

    assert updated == 1
    assert record.annotations["image.jpg"][0].geometry == {"x1": 10, "y1": 20, "x2": 30, "y2": 40, "angle": 90.0}
    assert record.annotations["image.jpg"][1].geometry["angle"] == 0


def test_reset_annotation_orientation_sets_angle_zero_and_dot_flag(tmp_path: Path) -> None:
    store = DatasetStore()
    record = DatasetRecord(
        dataset_id="dataset",
        root=tmp_path,
        asset_root=tmp_path,
        images=[ImageInfo(filename="image.jpg", width=100, height=80)],
        annotations={
            "image.jpg": [
                Annotation(
                    id="1",
                    type=AnnotationType.rectangle,
                    label="car",
                    attributes={},
                    geometry={"x1": 10, "y1": 20, "x2": 30, "y2": 40, "angle": 35},
                )
            ]
        },
    )
    store._datasets["dataset"] = record

    _, updated = store.rotate_annotation_orientation("dataset", 0, AnnotationOrientationDirection.reset, "car")

    assert updated == 1
    assert record.annotations["image.jpg"][0].geometry == {
        "x1": 10,
        "y1": 20,
        "x2": 30,
        "y2": 40,
        "angle": 0,
        "dot_reset": True,
        "display_angle": 35.0,
    }


@pytest.mark.parametrize(
    ("direction", "expected_angle"),
    [
        (AnnotationOrientationDirection.left, 280.0),
        (AnnotationOrientationDirection.right, 100.0),
        (AnnotationOrientationDirection.rotate_180, 190.0),
    ],
)
def test_annotation_orientation_buttons_rotate_angle_and_clear_reset_flag(
    tmp_path: Path,
    direction: AnnotationOrientationDirection,
    expected_angle: float,
) -> None:
    store = DatasetStore()
    record = DatasetRecord(
        dataset_id="dataset",
        root=tmp_path,
        asset_root=tmp_path,
        images=[ImageInfo(filename="image.jpg", width=100, height=80)],
        annotations={
            "image.jpg": [
                Annotation(
                    id="1",
                    type=AnnotationType.rectangle,
                    label="car",
                    attributes={},
                    geometry={"x1": 10, "y1": 20, "x2": 30, "y2": 40, "angle": 10, "dot_reset": True, "display_angle": 45},
                )
            ]
        },
    )
    store._datasets["dataset"] = record

    _, updated = store.rotate_annotation_orientation("dataset", 0, direction, "car")

    assert updated == 1
    geometry = record.annotations["image.jpg"][0].geometry
    assert geometry["angle"] == expected_angle
    assert "dot_reset" not in geometry
    assert "display_angle" not in geometry


def test_build_export_zip(tmp_path: Path) -> None:
    nested_dir = tmp_path / "nested" / "folder"
    nested_dir.mkdir(parents=True)
    image_path = nested_dir / "image.jpg"
    Image.new("RGB", (32, 24), color=(255, 255, 255)).save(image_path)
    file_index = build_file_index(tmp_path)
    assert resolve_file_path(tmp_path, file_index, "nested/folder/image.jpg") == image_path
    assert resolve_file_path(tmp_path, file_index, "image.jpg") == image_path
    record = DatasetRecord(
        dataset_id="dataset",
        root=tmp_path,
        asset_root=tmp_path,
        asset_index=file_index,
        images=[ImageInfo(filename="image.jpg", width=100, height=80)],
        annotations={
            "image.jpg": [
                Annotation(
                    id="1",
                    type=AnnotationType.rectangle,
                    label="car",
                    attributes={},
                    geometry={"x1": 10, "y1": 20, "x2": 30, "y2": 40},
                )
            ]
        },
    )
    output_path = tmp_path / "export.zip"
    build_export_zip(record, output_path)
    assert output_path.exists()
    with ZipFile(output_path) as archive:
        assert "task.json" in archive.namelist()
        assert "annotations.json" in archive.namelist()
        assert "data/image.jpg" in archive.namelist()


def test_build_export_zip_rotates_images_and_annotations(tmp_path: Path) -> None:
    image_path = tmp_path / "image.jpg"
    Image.new("RGB", (100, 50), color=(255, 255, 255)).save(image_path)
    file_index = build_file_index(tmp_path)
    record = DatasetRecord(
        dataset_id="dataset",
        root=tmp_path,
        asset_root=tmp_path,
        asset_index=file_index,
        images=[ImageInfo(filename="image.jpg", width=100, height=50)],
        annotations={
            "image.jpg": [
                Annotation(
                    id="1",
                    type=AnnotationType.rectangle,
                    label="car",
                    attributes={},
                    geometry={"x1": 10, "y1": 20, "x2": 30, "y2": 40},
                )
            ]
        },
        rotation_state={0: 90},
        labels=["car", "unused"],
    )
    output_path = tmp_path / "rotated-export.zip"
    build_export_zip(record, output_path)

    with ZipFile(output_path) as archive:
        with Image.open(archive.open("data/image.jpg")) as exported_image:
            assert exported_image.size == (50, 100)
        annotations = json.loads(archive.read("annotations.json"))
        task = json.loads(archive.read("task.json"))
        assert [label["name"] for label in task["labels"]] == ["car", "unused"]
        shape = annotations[0]["shapes"][0]
        assert shape["type"] == "rectangle"
        assert shape["points"] == [10.0, 10.0, 30.0, 30.0]
        assert shape["rotation"] == 90.0


def test_rotated_rectangle_export_geometry_keeps_center_size_and_angle() -> None:
    annotation = Annotation(
        id="1",
        type=AnnotationType.rectangle,
        label="car",
        attributes={},
        geometry={"x1": 10, "y1": 15, "x2": 50, "y2": 35, "angle": 0},
    )

    rotated = _rotate_geometry_for_export(annotation, width=100, height=60, rotation=90)

    assert rotated.geometry["x1"] == 15.0
    assert rotated.geometry["y1"] == 20.0
    assert rotated.geometry["x2"] == 55.0
    assert rotated.geometry["y2"] == 40.0
    assert rotated.geometry["angle"] == 90.0
    assert visual_bbox_for_annotation(rotated) == [25.0, 10.0, 20.0, 40.0]


def test_build_coco_zip_subset_rotates_rectangle_bbox_once(tmp_path: Path) -> None:
    image_path = tmp_path / "image.jpg"
    Image.new("RGB", (100, 60), color=(255, 255, 255)).save(image_path)
    record = DatasetRecord(
        dataset_id="dataset",
        root=tmp_path,
        asset_root=tmp_path,
        asset_index=build_file_index(tmp_path),
        images=[ImageInfo(filename="image.jpg", width=100, height=60)],
        annotations={
            "image.jpg": [
                Annotation(
                    id="1",
                    type=AnnotationType.rectangle,
                    label="car",
                    attributes={},
                    geometry={"x1": 10, "y1": 15, "x2": 50, "y2": 35, "angle": 0},
                )
            ]
        },
        rotation_state={0: 90},
    )
    output_path = tmp_path / "coco.zip"

    build_coco_zip_subset(record, output_path, None, None)

    with ZipFile(output_path) as archive:
        payload = json.loads(archive.read("annotations/instances_default.json"))
        assert payload["images"][0]["width"] == 60
        assert payload["images"][0]["height"] == 100
        assert payload["annotations"][0]["bbox"] == [25.0, 10.0, 20.0, 40.0]


def test_build_cvat_for_images_zip_subset(tmp_path: Path) -> None:
    image_path = tmp_path / "image.jpg"
    Image.new("RGB", (100, 50), color=(255, 255, 255)).save(image_path)
    file_index = build_file_index(tmp_path)
    record = DatasetRecord(
        dataset_id="dataset",
        root=tmp_path,
        asset_root=tmp_path,
        asset_index=file_index,
        images=[ImageInfo(filename="image.jpg", width=100, height=50)],
        annotations={
            "image.jpg": [
                Annotation(
                    id="1",
                    type=AnnotationType.rectangle,
                    label="car",
                    attributes={},
                    geometry={"x1": 10, "y1": 20, "x2": 30, "y2": 40},
                )
            ]
        },
        rotation_state={0: 90},
        labels=["car", "unused"],
    )
    output_path = tmp_path / "cvat-export.zip"
    build_cvat_for_images_zip_subset(record, output_path, None, None)

    with ZipFile(output_path) as archive:
        assert "annotations.xml" in archive.namelist()
        assert "images/image.jpg" in archive.namelist()
        with Image.open(archive.open("images/image.jpg")) as exported_image:
            assert exported_image.size == (50, 100)
        xml_text = archive.read("annotations.xml").decode("utf-8")
        assert 'label="car"' in xml_text
        assert "<name>car</name>" in xml_text
        assert "<name>unused</name>" in xml_text
        assert '<image id="0" name="images/image.jpg" width="50" height="100">' in xml_text
        assert 'rotation="90"' in xml_text
        assert "/>" not in xml_text
        assert "<attributes></attributes>" in xml_text
        assert "</box>" in xml_text


def test_build_cvat_for_images_zip_subset_uses_images_prefix_for_cvat_frame_matching(tmp_path: Path) -> None:
    nested_dir = tmp_path / "nested"
    nested_dir.mkdir()
    image_path = nested_dir / "image.jpg"
    Image.new("RGB", (100, 50), color=(255, 255, 255)).save(image_path)
    record = DatasetRecord(
        dataset_id="dataset",
        root=tmp_path,
        asset_root=tmp_path,
        asset_index=build_file_index(tmp_path),
        images=[ImageInfo(filename="nested/image.jpg", width=100, height=50)],
        annotations={
            "nested/image.jpg": [
                Annotation(
                    id="1",
                    type=AnnotationType.rectangle,
                    label="car",
                    attributes={},
                    geometry={"x1": 10, "y1": 20, "x2": 30, "y2": 40},
                )
            ]
        },
        labels=["car"],
    )
    output_path = tmp_path / "cvat-export.zip"

    build_cvat_for_images_zip_subset(record, output_path, None, None)

    with ZipFile(output_path) as archive:
        assert "images/image.jpg" in archive.namelist()
        assert "images/nested/image.jpg" not in archive.namelist()
        xml_text = archive.read("annotations.xml").decode("utf-8")
        assert '<image id="0" name="images/image.jpg" width="100" height="50">' in xml_text
        assert 'name="nested/image.jpg"' not in xml_text
        assert 'label="car"' in xml_text


def test_build_cvat_for_images_image_paths_zip_subset_uses_images_prefix(tmp_path: Path) -> None:
    image_path = tmp_path / "image.jpg"
    Image.new("RGB", (100, 50), color=(255, 255, 255)).save(image_path)
    record = DatasetRecord(
        dataset_id="dataset",
        root=tmp_path,
        asset_root=tmp_path,
        asset_index=build_file_index(tmp_path),
        images=[ImageInfo(filename="image.jpg", width=100, height=50)],
        annotations={
            "image.jpg": [
                Annotation(
                    id="1",
                    type=AnnotationType.rectangle,
                    label="car",
                    attributes={},
                    geometry={"x1": 10, "y1": 20, "x2": 30, "y2": 40},
                )
            ]
        },
        labels=["car"],
    )
    output_path = tmp_path / "cvat-export-paths.zip"

    build_cvat_for_images_image_paths_zip_subset(record, output_path, None, None)

    with ZipFile(output_path) as archive:
        assert "images/image.jpg" in archive.namelist()
        xml_text = archive.read("annotations.xml").decode("utf-8")
        assert '<image id="0" name="images/image.jpg" width="100" height="50">' in xml_text
        assert 'label="car"' in xml_text
        assert "/>" not in xml_text


def test_build_cvat_for_images_zip_subset_exports_reset_dot_rotation_zero(tmp_path: Path) -> None:
    image_path = tmp_path / "image.jpg"
    Image.new("RGB", (100, 50), color=(255, 255, 255)).save(image_path)
    file_index = build_file_index(tmp_path)
    record = DatasetRecord(
        dataset_id="dataset",
        root=tmp_path,
        asset_root=tmp_path,
        asset_index=file_index,
        images=[ImageInfo(filename="image.jpg", width=100, height=50)],
        annotations={
            "image.jpg": [
                Annotation(
                    id="1",
                    type=AnnotationType.rectangle,
                    label="car",
                    attributes={},
                    geometry={"x1": 10, "y1": 20, "x2": 30, "y2": 40, "angle": 0, "dot_reset": True, "display_angle": 35},
                )
            ]
        },
        rotation_state={0: 90},
    )
    output_path = tmp_path / "cvat-export.zip"
    build_cvat_for_images_zip_subset(record, output_path, None, None)

    with ZipFile(output_path) as archive:
        xml_text = archive.read("annotations.xml").decode("utf-8")
        assert 'rotation="0"' in xml_text
        assert 'rotation="90.0"' not in xml_text
        box = ET.fromstring(xml_text).find(".//box")
        assert box is not None
        assert float(box.attrib["xtl"]) != 10.0
        assert float(box.attrib["xbr"]) != 30.0


def test_build_cvat_for_images_zip_subset_uses_reset_dot_display_angle_without_image_rotation(tmp_path: Path) -> None:
    image_path = tmp_path / "image.jpg"
    Image.new("RGB", (100, 80), color=(255, 255, 255)).save(image_path)
    record = DatasetRecord(
        dataset_id="dataset",
        root=tmp_path,
        asset_root=tmp_path,
        asset_index=build_file_index(tmp_path),
        images=[ImageInfo(filename="image.jpg", width=100, height=80)],
        annotations={
            "image.jpg": [
                Annotation(
                    id="1",
                    type=AnnotationType.rectangle,
                    label="car",
                    attributes={},
                    geometry={"x1": 10, "y1": 20, "x2": 50, "y2": 40, "angle": 0, "dot_reset": True, "display_angle": 90},
                )
            ]
        },
        rotation_state={0: 0},
    )
    output_path = tmp_path / "cvat-export.zip"
    build_cvat_for_images_zip_subset(record, output_path, None, None)

    with ZipFile(output_path) as archive:
        box = ET.fromstring(archive.read("annotations.xml").decode("utf-8")).find(".//box")
        assert box is not None
        assert box.attrib["rotation"] == "0"
        assert float(box.attrib["xtl"]) == 20.0
        assert float(box.attrib["ytl"]) == 10.0
        assert float(box.attrib["xbr"]) == 40.0
        assert float(box.attrib["ybr"]) == 50.0


def test_build_cvat_for_images_zip_subset_uses_reset_dot_visual_bbox_after_image_rotation(tmp_path: Path) -> None:
    image_path = tmp_path / "image.jpg"
    Image.new("RGB", (100, 80), color=(255, 255, 255)).save(image_path)
    record = DatasetRecord(
        dataset_id="dataset",
        root=tmp_path,
        asset_root=tmp_path,
        asset_index=build_file_index(tmp_path),
        images=[ImageInfo(filename="image.jpg", width=100, height=80)],
        annotations={
            "image.jpg": [
                Annotation(
                    id="1",
                    type=AnnotationType.rectangle,
                    label="car",
                    attributes={},
                    geometry={"x1": 10, "y1": 20, "x2": 50, "y2": 40, "angle": 0, "dot_reset": True, "display_angle": 90},
                )
            ]
        },
        rotation_state={0: 90},
    )
    output_path = tmp_path / "cvat-export.zip"
    build_cvat_for_images_zip_subset(record, output_path, None, None)

    with ZipFile(output_path) as archive:
        with Image.open(archive.open("images/image.jpg")) as exported_image:
            assert exported_image.size == (80, 100)
        box = ET.fromstring(archive.read("annotations.xml").decode("utf-8")).find(".//box")
        assert box is not None
        assert box.attrib["rotation"] == "0"
        assert float(box.attrib["xtl"]) == 30.0
        assert float(box.attrib["ytl"]) == 20.0
        assert float(box.attrib["xbr"]) == 70.0
        assert float(box.attrib["ybr"]) == 40.0


def test_parse_app_bundle_archive(tmp_path: Path) -> None:
    data_dir = tmp_path / "Data"
    data_dir.mkdir()
    image_path = data_dir / "frame_0001.jpg"
    Image.new("RGB", (120, 80), color=(255, 255, 255)).save(image_path)
    (tmp_path / "task.json").write_text(
        json.dumps(
            {
                "name": "bundle-task",
                "labels": [
                    {"name": "car", "color": "#ff0000", "attributes": [], "type": "any", "sublabels": []},
                    {"name": "unused", "color": "#00ff00", "attributes": [], "type": "any", "sublabels": []},
                ],
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "annotations.json").write_text(
        json.dumps(
            [
                {
                    "version": 0,
                    "tags": [],
                    "shapes": [
                        {
                            "type": "rectangle",
                            "occluded": False,
                            "outside": False,
                            "z_order": 0,
                            "rotation": 0.0,
                            "points": [10, 12, 40, 50],
                            "frame": 0,
                            "group": 0,
                            "source": "manual",
                            "attributes": [],
                            "elements": [],
                            "label": "car",
                        }
                    ],
                    "tracks": [],
                }
            ]
        ),
        encoding="utf-8",
    )

    manifest = parse_dataset_archive(tmp_path)
    assert manifest.format == "app_bundle"
    assert manifest.images[0].filename == "frame_0001.jpg"
    assert manifest.images[0].width == 120
    assert manifest.images[0].height == 80
    assert manifest.annotations["frame_0001.jpg"][0].label == "car"
    assert manifest.annotations["frame_0001.jpg"][0].geometry["x1"] == 10.0
    assert manifest.labels == ["car", "unused"]


def test_parse_image_only_folder(tmp_path: Path) -> None:
    images_dir = tmp_path / "photos"
    images_dir.mkdir()
    Image.new("RGB", (32, 24), color=(255, 0, 0)).save(images_dir / "one.jpg")
    Image.new("RGB", (16, 12), color=(0, 255, 0)).save(images_dir / "two.png")

    manifest = parse_dataset_archive(tmp_path)

    assert manifest.format == "image_folder"
    assert [image.filename for image in manifest.images] == ["photos/one.jpg", "photos/two.png"]
    assert manifest.annotations == {"photos/one.jpg": [], "photos/two.png": []}


def test_dataset_store_detects_and_deletes_duplicate_images(tmp_path: Path) -> None:
    first_path = tmp_path / "first.jpg"
    second_path = tmp_path / "second.jpg"
    third_path = tmp_path / "third.jpg"
    Image.new("RGB", (20, 10), color=(123, 0, 0)).save(first_path)
    first_path.write_bytes(b"same-image-bytes")
    second_path.write_bytes(b"same-image-bytes")
    third_path.write_bytes(b"different-image-bytes")
    store = DatasetStore()
    record = DatasetRecord(
        dataset_id="dataset",
        root=tmp_path,
        asset_root=tmp_path,
        asset_index=build_file_index(tmp_path),
        images=[
            ImageInfo(filename="first.jpg", width=20, height=10),
            ImageInfo(filename="second.jpg", width=20, height=10),
            ImageInfo(filename="third.jpg", width=20, height=10),
        ],
        annotations={},
    )
    store._datasets["dataset"] = record

    groups = store.duplicate_image_groups("dataset")

    assert len(groups) == 1
    assert [image["index"] for image in groups[0]["images"]] == [0, 1]
    store.delete_images("dataset", [1])
    assert store.duplicate_image_groups("dataset") == []


def test_dataset_store_applies_image_folder_rotations_to_workspace_files(tmp_path: Path) -> None:
    image_path = tmp_path / "image.jpg"
    Image.new("RGB", (20, 10), color=(255, 255, 255)).save(image_path)
    store = DatasetStore()
    record = DatasetRecord(
        dataset_id="dataset",
        root=tmp_path,
        asset_root=tmp_path,
        asset_index=build_file_index(tmp_path),
        images=[ImageInfo(filename="image.jpg", width=20, height=10)],
        annotations={"image.jpg": []},
        format="image_folder",
        rotation_state={0: 90},
    )
    store._datasets["dataset"] = record

    updated = store.apply_image_rotations_to_workspace("dataset")

    assert updated == 1
    assert record.image_rotation(0) == 0
    assert record.images[0].width == 10
    assert record.images[0].height == 20
    with Image.open(image_path) as image:
        assert image.size == (10, 20)


def test_image_cache_token_tracks_file_changes_not_visual_rotation(tmp_path: Path) -> None:
    image_path = tmp_path / "image.jpg"
    Image.new("RGB", (20, 10), color=(255, 255, 255)).save(image_path)
    record = DatasetRecord(
        dataset_id="dataset",
        root=tmp_path,
        asset_root=tmp_path,
        asset_index=build_file_index(tmp_path),
        images=[ImageInfo(filename="image.jpg", width=20, height=10)],
    )
    original_token = record.image_cache_token(0)
    record.rotation_state[0] = 90

    assert record.image_cache_token(0) == original_token

    DatasetStore._rotate_image_file_in_place(image_path, 90)

    assert record.image_cache_token(0) != original_token


def test_dataset_store_applies_pascal_voc_rotations_to_source_folder(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    source_root.mkdir()
    image_path = source_root / "frame_0001.jpg"
    xml_path = source_root / "frame_0001.xml"
    Image.new("RGB", (100, 50), color=(255, 255, 255)).save(image_path)
    xml_path.write_text(
        """<annotation>
  <filename>frame_0001.jpg</filename>
  <size>
    <width>100</width>
    <height>50</height>
  </size>
  <object>
    <name>car</name>
    <bndbox>
      <xmin>10</xmin>
      <ymin>20</ymin>
      <xmax>30</xmax>
      <ymax>40</ymax>
    </bndbox>
  </object>
</annotation>
""",
        encoding="utf-8",
    )
    store = DatasetStore()
    record = DatasetRecord(
        dataset_id="dataset",
        root=tmp_path / "workspace",
        asset_root=source_root,
        asset_index=build_file_index(source_root),
        images=[ImageInfo(filename="frame_0001.jpg", width=100, height=50)],
        annotations={
            "frame_0001.jpg": [
                Annotation(
                    id="frame_0001-0",
                    type=AnnotationType.rectangle,
                    label="car",
                    attributes={},
                    geometry={"x1": 10, "y1": 20, "x2": 30, "y2": 40},
                )
            ]
        },
        format="pascal_voc",
        rotation_state={0: 90},
        source_root=source_root,
        editable_source=True,
    )
    store._datasets["dataset"] = record
    original_token = record.image_cache_token(0)

    result = store.apply_changes_to_source("dataset")

    assert result["updated"] == 1
    assert result["backup_path"] is not None
    assert Path(result["backup_path"]).exists()
    with ZipFile(Path(result["backup_path"])) as backup:
        with Image.open(backup.open("frame_0001.jpg")) as backed_up_image:
            assert backed_up_image.size == (100, 50)
    assert record.image_rotation(0) == 0
    assert record.images[0].width == 50
    assert record.images[0].height == 100
    assert record.annotations["frame_0001.jpg"][0].geometry == {"x1": 10, "y1": 10, "x2": 30, "y2": 30}
    with Image.open(image_path) as image:
        assert image.size == (50, 100)
    root = ET.parse(xml_path).getroot()
    assert root.findtext("size/width") == "50"
    assert root.findtext("size/height") == "100"
    assert root.findtext("object/bndbox/xmin") == "10"
    assert root.findtext("object/bndbox/ymin") == "10"
    assert root.findtext("object/bndbox/xmax") == "30"
    assert root.findtext("object/bndbox/ymax") == "30"


def test_dataset_store_applies_image_folder_rotations_to_source_folder(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    source_root.mkdir()
    image_path = source_root / "image.jpg"
    Image.new("RGB", (30, 10), color=(255, 255, 255)).save(image_path)
    store = DatasetStore()
    record = DatasetRecord(
        dataset_id="dataset",
        root=tmp_path / "workspace",
        asset_root=source_root,
        asset_index=build_file_index(source_root),
        images=[ImageInfo(filename="image.jpg", width=30, height=10)],
        annotations={"image.jpg": []},
        format="image_folder",
        rotation_state={0: 90},
        source_root=source_root,
        editable_source=True,
    )
    store._datasets["dataset"] = record
    original_token = record.image_cache_token(0)

    result = store.apply_changes_to_source("dataset")

    assert result["updated"] == 1
    assert result["backup_path"] is not None
    assert Path(result["backup_path"]).exists()
    with ZipFile(Path(result["backup_path"])) as backup:
        with Image.open(backup.open("image.jpg")) as backed_up_image:
            assert backed_up_image.size == (30, 10)
    assert not (source_root / ".image.cvat-rotator.jpg").exists()
    assert record.image_rotation(0) == 0
    assert record.images[0].width == 10
    assert record.images[0].height == 30
    assert record.image_cache_token(0) != original_token
    with Image.open(image_path) as image:
        assert image.size == (10, 30)


def test_parse_labelme_archive(tmp_path: Path) -> None:
    image_path = tmp_path / "frame_0001.jpg"
    Image.new("RGB", (120, 80), color=(255, 255, 255)).save(image_path)
    (tmp_path / "frame_0001.json").write_text(
        json.dumps(
            {
                "version": "5.0.1",
                "flags": {},
                "shapes": [
                    {"label": "car", "points": [[10, 12], [40, 50]], "group_id": None, "shape_type": "rectangle", "flags": {}, "description": "", "rotation": 0.0, "attributes": {}}
                ],
                "imagePath": "frame_0001.jpg",
                "imageData": None,
                "imageHeight": 80,
                "imageWidth": 120,
            }
        ),
        encoding="utf-8",
    )
    manifest = parse_labelme(tmp_path)
    assert manifest.format == "labelme"
    assert manifest.images[0].filename == "frame_0001.jpg"
    assert manifest.annotations["frame_0001.jpg"][0].label == "car"


def test_parse_datumaro_archive(tmp_path: Path) -> None:
    images_dir = tmp_path / "images"
    images_dir.mkdir()
    image_path = images_dir / "frame_0001.jpg"
    Image.new("RGB", (160, 90), color=(255, 255, 255)).save(image_path)
    (tmp_path / "dataset.json").write_text(
        json.dumps(
            {
                "dm_format_version": "1.0",
                "media_type": "image",
                "categories": {"label": {"labels": [{"name": "car"}]}},
                "items": [
                    {
                        "id": "frame_0001",
                        "subset": "default",
                        "image": {"path": "images/frame_0001.jpg", "size": [160, 90]},
                        "annotations": [{"id": "1", "type": "bbox", "label": "car", "bbox": [10, 12, 30, 40], "attributes": {}}],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    manifest = parse_datumaro(tmp_path)
    assert manifest.format == "datumaro"
    assert manifest.images[0].filename == "frame_0001.jpg"
    assert manifest.annotations["frame_0001.jpg"][0].geometry["x2"] == 40.0


def test_parse_pascal_voc_archive(tmp_path: Path) -> None:
    images_dir = tmp_path / "JPEGImages"
    annotations_dir = tmp_path / "Annotations"
    images_dir.mkdir()
    annotations_dir.mkdir()
    image_path = images_dir / "frame_0001.jpg"
    Image.new("RGB", (160, 90), color=(255, 255, 255)).save(image_path)
    (annotations_dir / "frame_0001.xml").write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<annotation>
  <folder>JPEGImages</folder>
  <filename>frame_0001.jpg</filename>
  <size>
    <width>160</width>
    <height>90</height>
    <depth>3</depth>
  </size>
  <object>
    <name>car</name>
    <pose>Unspecified</pose>
    <truncated>0</truncated>
    <difficult>0</difficult>
    <bndbox>
      <xmin>12</xmin>
      <ymin>15</ymin>
      <xmax>45</xmax>
      <ymax>60</ymax>
    </bndbox>
  </object>
</annotation>
""",
        encoding="utf-8",
    )

    manifest = parse_dataset_archive(tmp_path)
    assert manifest.format == "pascal_voc"
    assert manifest.images[0].filename == "frame_0001.jpg"
    assert manifest.annotations["frame_0001.jpg"][0].label == "car"
    assert manifest.annotations["frame_0001.jpg"][0].geometry["x2"] == 45.0
    assert manifest.labels == ["car"]


def test_parse_flat_pascal_voc_folder_does_not_count_xml_as_images(tmp_path: Path) -> None:
    Image.new("RGB", (160, 90), color=(255, 255, 255)).save(tmp_path / "frame_0001.jpg")
    Image.new("RGB", (120, 80), color=(255, 255, 255)).save(tmp_path / "frame_0002.jpg")
    for stem, width, height in (("frame_0001", 160, 90), ("frame_0002", 120, 80)):
        (tmp_path / f"{stem}.xml").write_text(
            f"""<?xml version="1.0" encoding="UTF-8"?>
<annotation>
  <filename>{stem}.jpg</filename>
  <size>
    <width>{width}</width>
    <height>{height}</height>
  </size>
  <object>
    <name>car</name>
    <bndbox>
      <xmin>1</xmin>
      <ymin>2</ymin>
      <xmax>10</xmax>
      <ymax>20</ymax>
    </bndbox>
  </object>
</annotation>
""",
            encoding="utf-8",
        )

    manifest = parse_dataset_archive(tmp_path)

    assert manifest.format == "pascal_voc"
    assert [image.filename for image in manifest.images] == ["frame_0001.jpg", "frame_0002.jpg"]
    assert len(manifest.images) == 2
    assert set(manifest.annotations) == {"frame_0001.jpg", "frame_0002.jpg"}


def test_build_pascal_voc_zip_subset(tmp_path: Path) -> None:
    image_path = tmp_path / "frame_0001.jpg"
    Image.new("RGB", (100, 50), color=(255, 255, 255)).save(image_path)
    file_index = build_file_index(tmp_path)
    record = DatasetRecord(
        dataset_id="dataset",
        root=tmp_path,
        asset_root=tmp_path,
        asset_index=file_index,
        images=[ImageInfo(filename="frame_0001.jpg", width=100, height=50)],
        annotations={
            "frame_0001.jpg": [
                Annotation(
                    id="1",
                    type=AnnotationType.rectangle,
                    label="car",
                    attributes={},
                    geometry={"x1": 10, "y1": 20, "x2": 30, "y2": 40},
                ),
                Annotation(
                    id="2",
                    type=AnnotationType.polygon,
                    label="road",
                    attributes={},
                    geometry={"points": [[5, 5], [10, 5], [10, 10]]},
                ),
            ]
        },
        rotation_state={0: 90},
    )
    output_path = tmp_path / "voc-export.zip"
    build_pascal_voc_zip_subset(record, output_path, None, None)

    with ZipFile(output_path) as archive:
        assert "JPEGImages/frame_0001.jpg" in archive.namelist()
        assert "Annotations/frame_0001.xml" in archive.namelist()
        assert "ImageSets/Main/default.txt" in archive.namelist()
        assert archive.read("ImageSets/Main/default.txt").decode("utf-8").strip() == "frame_0001"
        assert "CVAT_IMPORT_NOTES.txt" in archive.namelist()
        with Image.open(archive.open("JPEGImages/frame_0001.jpg")) as exported_image:
            assert exported_image.size == (50, 100)
        xml_text = archive.read("Annotations/frame_0001.xml").decode("utf-8")
        assert "<folder></folder>" in xml_text
        assert "<filename>frame_0001.jpg</filename>" in xml_text
        assert "<annotation>Unknown</annotation>" in xml_text
        assert "<image>Unknown</image>" in xml_text
        assert "<depth></depth>" in xml_text
        assert "<name>car</name>" in xml_text
        assert "<occluded>0</occluded>" in xml_text
        assert "<xmin>10</xmin>" in xml_text
        assert "<attributes>" in xml_text
        assert "<name>rotation</name>" in xml_text
        assert "<value>90</value>" in xml_text
        assert "<path>" not in xml_text
        assert "<pose>" not in xml_text
        assert "/>" not in xml_text


def test_build_modelarts_pascal_voc_zip_subset(tmp_path: Path) -> None:
    image_path = tmp_path / "test_jpg.jpg"
    Image.new("RGB", (640, 480), color=(255, 255, 255)).save(image_path)
    record = DatasetRecord(
        dataset_id="dataset",
        root=tmp_path,
        asset_root=tmp_path,
        asset_index=build_file_index(tmp_path),
        images=[ImageInfo(filename="test_jpg.jpg", width=640, height=480)],
        annotations={
            "test_jpg.jpg": [
                Annotation(
                    id="1",
                    type=AnnotationType.rectangle,
                    label="zebra",
                    attributes={},
                    geometry={"x1": 85, "y1": 68, "x2": 401, "y2": 480},
                ),
                Annotation(
                    id="2",
                    type=AnnotationType.rectangle,
                    label="zebra",
                    attributes={},
                    geometry={"x1": 571, "y1": 33, "x2": 640, "y2": 231},
                ),
            ]
        },
    )
    output_path = tmp_path / "modelarts-voc.zip"

    build_modelarts_pascal_voc_zip_subset(record, output_path, None, None)

    with ZipFile(output_path) as archive:
        assert sorted(archive.namelist()) == ["data/test_jpg.jpg", "data/test_jpg.xml"]
        xml_text = archive.read("data/test_jpg.xml").decode("utf-8")
        assert "<folder>data</folder>" in xml_text
        assert "<filename>test_jpg.jpg</filename>" in xml_text
        assert "<database>unknown</database>" in xml_text
        assert "<width>640</width>" in xml_text
        assert "<height>480</height>" in xml_text
        assert "<depth>3</depth>" in xml_text
        assert xml_text.count("<object>") == 2
        assert "<name>zebra</name>" in xml_text
        assert "<pose>Unspecified</pose>" in xml_text
        assert "<truncated>0</truncated>" in xml_text
        assert "<difficult>0</difficult>" in xml_text
        assert "<xmin>85</xmin>" in xml_text
        assert "<ymax>480</ymax>" in xml_text
        assert "<attributes>" not in xml_text
        assert "/>" not in xml_text


def test_build_labelme_zip_subset(tmp_path: Path) -> None:
    image_path = tmp_path / "frame_0001.jpg"
    Image.new("RGB", (100, 50), color=(255, 255, 255)).save(image_path)
    file_index = build_file_index(tmp_path)
    record = DatasetRecord(
        dataset_id="dataset",
        root=tmp_path,
        asset_root=tmp_path,
        asset_index=file_index,
        images=[ImageInfo(filename="frame_0001.jpg", width=100, height=50)],
        annotations={
            "frame_0001.jpg": [
                Annotation(
                    id="1",
                    type=AnnotationType.rectangle,
                    label="car",
                    attributes={},
                    geometry={"x1": 10, "y1": 20, "x2": 30, "y2": 40},
                )
            ]
        },
        rotation_state={0: 90},
    )
    output_path = tmp_path / "labelme-export.zip"
    build_labelme_zip_subset(record, output_path, None, None)
    with ZipFile(output_path) as archive:
        assert "annotations/frame_0001.json" in archive.namelist()
        payload = json.loads(archive.read("annotations/frame_0001.json"))
        assert payload["imagePath"] == "frame_0001.jpg"
        assert payload["shapes"][0]["label"] == "car"


def test_build_datumaro_zip_subset(tmp_path: Path) -> None:
    image_path = tmp_path / "frame_0001.jpg"
    Image.new("RGB", (100, 50), color=(255, 255, 255)).save(image_path)
    file_index = build_file_index(tmp_path)
    record = DatasetRecord(
        dataset_id="dataset",
        root=tmp_path,
        asset_root=tmp_path,
        asset_index=file_index,
        images=[ImageInfo(filename="frame_0001.jpg", width=100, height=50)],
        annotations={
            "frame_0001.jpg": [
                Annotation(
                    id="1",
                    type=AnnotationType.rectangle,
                    label="car",
                    attributes={},
                    geometry={"x1": 10, "y1": 20, "x2": 30, "y2": 40},
                )
            ]
        },
        rotation_state={0: 90},
    )
    output_path = tmp_path / "datumaro-export.zip"
    build_datumaro_zip_subset(record, output_path, None, None)
    with ZipFile(output_path) as archive:
        assert "dataset.json" in archive.namelist()
        payload = json.loads(archive.read("dataset.json"))
        assert payload["items"][0]["image"]["path"] == "images/frame_0001.jpg"
        assert payload["items"][0]["annotations"][0]["label"] == "car"


def test_parse_coco_polygons_and_keypoints(tmp_path: Path) -> None:
    coco_path = tmp_path / "instances.json"
    coco_path.write_text(
        json.dumps(
            {
                "images": [{"id": 1, "file_name": "frame.jpg", "width": 100, "height": 80}],
                "categories": [{"id": 7, "name": "person", "keypoints": ["head", "hand"]}],
                "annotations": [
                    {"id": 1, "image_id": 1, "category_id": 7, "segmentation": [[10, 10, 20, 10, 20, 20]], "bbox": [10, 10, 10, 10]},
                    {"id": 2, "image_id": 1, "category_id": 7, "keypoints": [15, 16, 2, 20, 22, 2], "bbox": [10, 10, 20, 20]},
                ],
            }
        ),
        encoding="utf-8",
    )
    manifest = parse_coco_json(coco_path, tmp_path)
    assert manifest.annotations["frame.jpg"][0].type == AnnotationType.polygon
    assert manifest.annotations["frame.jpg"][1].type == AnnotationType.skeleton


def test_parse_yolo_detection_and_segmentation(tmp_path: Path) -> None:
    images_dir = tmp_path / "images"
    labels_dir = tmp_path / "labels"
    images_dir.mkdir()
    labels_dir.mkdir()
    Image.new("RGB", (100, 50), color=(255, 255, 255)).save(images_dir / "frame.jpg")
    (tmp_path / "classes.txt").write_text("car\nroad", encoding="utf-8")
    (labels_dir / "frame.txt").write_text("0 0.5 0.5 0.2 0.4\n1 0.1 0.1 0.2 0.1 0.2 0.2\n", encoding="utf-8")
    manifest = parse_yolo_dataset(tmp_path)
    assert manifest.annotations["frame.jpg"][0].geometry == {"x1": 40.0, "y1": 15.0, "x2": 60.0, "y2": 35.0}
    assert manifest.annotations["frame.jpg"][1].type == AnnotationType.polygon


def test_parse_segmentation_mask_archive(tmp_path: Path) -> None:
    images_dir = tmp_path / "images"
    masks_dir = tmp_path / "masks"
    images_dir.mkdir()
    masks_dir.mkdir()
    Image.new("RGB", (4, 3), color=(255, 255, 255)).save(images_dir / "frame.png")
    mask = Image.new("L", (4, 3), 0)
    mask.putpixel((1, 1), 2)
    mask.save(masks_dir / "frame.png")
    manifest = parse_segmentation_mask(tmp_path)
    assert manifest.format == "segmentation_mask"
    assert manifest.annotations["frame.png"][0].label == "2"


def test_parse_kitti_archive(tmp_path: Path) -> None:
    image_dir = tmp_path / "image_2"
    label_dir = tmp_path / "label_2"
    image_dir.mkdir()
    label_dir.mkdir()
    Image.new("RGB", (100, 50), color=(255, 255, 255)).save(image_dir / "000001.png")
    (label_dir / "000001.txt").write_text("Car 0.00 0 0.00 10.00 12.00 40.00 30.00 0 0 0 0 0 0 0\n", encoding="utf-8")
    manifest = parse_kitti(tmp_path)
    assert manifest.format == "kitti"
    assert manifest.annotations["000001.png"][0].label == "Car"


def test_parse_open_images_archive(tmp_path: Path) -> None:
    images_dir = tmp_path / "images"
    images_dir.mkdir()
    Image.new("RGB", (100, 50), color=(255, 255, 255)).save(images_dir / "abc.jpg")
    (tmp_path / "annotations.csv").write_text(
        "ImageID,Source,LabelName,Confidence,XMin,XMax,YMin,YMax,IsOccluded,IsTruncated,IsGroupOf,IsDepiction,IsInside\n"
        "abc,xclick,/m/car,1,0.1,0.4,0.2,0.6,0,0,0,0,0\n",
        encoding="utf-8",
    )
    manifest = parse_open_images(tmp_path)
    assert manifest.format == "open_images"
    assert manifest.annotations["abc.jpg"][0].geometry["x2"] == 40.0


def test_build_new_format_exports(tmp_path: Path) -> None:
    image_path = tmp_path / "frame.jpg"
    Image.new("RGB", (100, 50), color=(255, 255, 255)).save(image_path)
    file_index = build_file_index(tmp_path)
    record = DatasetRecord(
        dataset_id="dataset",
        root=tmp_path,
        asset_root=tmp_path,
        asset_index=file_index,
        images=[ImageInfo(filename="frame.jpg", width=100, height=50)],
        annotations={
            "frame.jpg": [
                Annotation(id="1", type=AnnotationType.rectangle, label="car", attributes={}, geometry={"x1": 10, "y1": 10, "x2": 30, "y2": 30}),
                Annotation(id="2", type=AnnotationType.polygon, label="road", attributes={}, geometry={"points": [[5, 5], [20, 5], [20, 20]]}),
            ]
        },
        rotation_state={0: 90},
    )
    exporters = [
        ("coco.zip", build_coco_zip_subset, "annotations/instances_default.json"),
        ("yolo.zip", build_yolo_zip_subset, "labels/frame.txt"),
        ("mask.zip", build_segmentation_mask_zip_subset, "masks/frame.png"),
        ("kitti.zip", build_kitti_zip_subset, "label_2/frame.txt"),
        ("open-images.zip", build_open_images_zip_subset, "annotations.csv"),
    ]
    for filename, builder, expected_member in exporters:
        output_path = tmp_path / filename
        builder(record, output_path, None, None)
        with ZipFile(output_path) as archive:
            assert expected_member in archive.namelist()


def test_parse_image_folder_classification_labels(tmp_path: Path) -> None:
    cat_dir = tmp_path / "cat"
    dog_dir = tmp_path / "dog"
    cat_dir.mkdir()
    dog_dir.mkdir()
    Image.new("RGB", (16, 12), color=(255, 0, 0)).save(cat_dir / "one.jpg")
    Image.new("RGB", (20, 10), color=(0, 255, 0)).save(dog_dir / "two.jpg")

    manifest = parse_dataset_archive(tmp_path)

    assert manifest.format == "image_folder"
    assert manifest.labels == ["cat", "dog"]
    assert manifest.image_labels == {"cat/one.jpg": "cat", "dog/two.jpg": "dog"}


def test_set_classification_label_current_and_all(tmp_path: Path) -> None:
    store = DatasetStore()
    record = DatasetRecord(
        dataset_id="dataset",
        root=tmp_path,
        asset_root=tmp_path,
        images=[
            ImageInfo(filename="one.jpg", width=16, height=12),
            ImageInfo(filename="two.jpg", width=20, height=10),
        ],
        labels=[],
    )
    store._datasets["dataset"] = record

    store.set_classification_label("dataset", "cat", image_index=0)
    assert record.image_labels == {"one.jpg": "cat"}
    assert record.labels == ["cat"]

    store.set_classification_label("dataset", "review", apply_to_all=True)
    assert record.image_labels == {"one.jpg": "review", "two.jpg": "review"}
    assert record.labels == ["cat", "review"]
    assert record.manifest_path.exists()


def test_build_image_classification_export(tmp_path: Path) -> None:
    Image.new("RGB", (100, 50), color=(255, 255, 255)).save(tmp_path / "frame.jpg")
    record = DatasetRecord(
        dataset_id="dataset",
        root=tmp_path,
        asset_root=tmp_path,
        asset_index=build_file_index(tmp_path),
        images=[ImageInfo(filename="frame.jpg", width=100, height=50)],
        image_labels={"frame.jpg": "uniform"},
        rotation_state={0: 90},
    )
    output_path = tmp_path / "classification.zip"

    build_image_classification_zip_subset(record, output_path, None, None)

    with ZipFile(output_path) as archive:
        assert "uniform/frame.jpg" in archive.namelist()
        labels_csv = archive.read("labels.csv").decode("utf-8")
        assert "filename,label" in labels_csv
        assert "frame.jpg,uniform" in labels_csv
        with Image.open(archive.open("uniform/frame.jpg")) as exported_image:
            assert exported_image.size == (50, 100)
