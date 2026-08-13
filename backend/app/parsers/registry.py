from __future__ import annotations

import json
from pathlib import Path
from zipfile import ZipFile

from backend.app.models import DatasetManifest
from backend.app.parsers.datumaro import parse_datumaro
from backend.app.parsers.app_bundle import parse_app_bundle
from backend.app.parsers.coco import parse_coco_json
from backend.app.parsers.cvat_xml import parse_cvat_xml
from backend.app.parsers.image_folder import iter_image_files, parse_image_folder
from backend.app.parsers.kitti import parse_kitti
from backend.app.parsers.labelme import parse_labelme
from backend.app.parsers.open_images import parse_open_images
from backend.app.parsers.pascal_voc import _is_pascal_voc_xml, parse_pascal_voc
from backend.app.parsers.segmentation_mask import parse_segmentation_mask
from backend.app.parsers.yolo import parse_yolo_dataset


def detect_dataset_format(root: Path) -> str:
    if (root / "task.json").exists() and (root / "annotations.json").exists():
        return "app_bundle"
    if (root / "masks").exists() or (root / "SegmentationClass").exists():
        return "segmentation_mask"
    if (root / "label_2").exists() or (root / "image_2").exists():
        return "kitti"
    dataset_json = root / "dataset.json"
    if dataset_json.exists():
        try:
            payload = json.loads(dataset_json.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            payload = {}
        if isinstance(payload, dict) and ("items" in payload or "dm_format_version" in payload):
            return "datumaro"
    if any(path.is_file() for path in root.rglob("*.json")):
        for json_file in root.rglob("*.json"):
            try:
                payload = json.loads(json_file.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict) and "shapes" in payload and "imagePath" in payload:
                return "labelme"
    for csv_file in root.rglob("*.csv"):
        try:
            header = csv_file.read_text(encoding="utf-8").splitlines()[0]
        except Exception:
            continue
        if {"ImageID", "LabelName", "XMin", "XMax", "YMin", "YMax"}.issubset(set(header.split(","))):
            return "open_images"
    if list(root.rglob("Annotations/*.xml")) or any(_is_pascal_voc_xml(path) for path in root.rglob("*.xml") if path.is_file()):
        return "pascal_voc"
    xml_files = list(root.rglob("*.xml"))
    if xml_files:
        return "cvat_xml"
    json_files = list(root.rglob("*.json"))
    for json_file in json_files:
        try:
            payload = json.loads(json_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if "images" in payload and "annotations" in payload:
            return "coco"
    if list(root.rglob("*.txt")):
        return "yolo"
    if iter_image_files(root):
        return "image_folder"
    return "unknown"


def parse_dataset_archive(extracted_root: Path) -> DatasetManifest:
    dataset_format = detect_dataset_format(extracted_root)
    if dataset_format == "app_bundle":
        return parse_app_bundle(extracted_root)
    if dataset_format == "datumaro":
        return parse_datumaro(extracted_root)
    if dataset_format == "labelme":
        return parse_labelme(extracted_root)
    if dataset_format == "segmentation_mask":
        return parse_segmentation_mask(extracted_root)
    if dataset_format == "kitti":
        return parse_kitti(extracted_root)
    if dataset_format == "open_images":
        return parse_open_images(extracted_root)
    if dataset_format == "pascal_voc":
        return parse_pascal_voc(extracted_root)
    if dataset_format == "cvat_xml":
        xml_path = next(extracted_root.rglob("*.xml"))
        return parse_cvat_xml(xml_path, extracted_root)
    if dataset_format == "coco":
        json_path = next(extracted_root.rglob("*.json"))
        return parse_coco_json(json_path, extracted_root)
    if dataset_format == "yolo":
        return parse_yolo_dataset(extracted_root)
    if dataset_format == "image_folder":
        return parse_image_folder(extracted_root)
    return DatasetManifest(format="unknown", images=[], annotations={})
