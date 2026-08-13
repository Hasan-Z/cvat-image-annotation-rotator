from __future__ import annotations

import json
import os
import shutil
import uuid
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from hashlib import md5
from pathlib import Path
from typing import Any

from lxml import etree
from PIL import Image

from backend.app.config import set_resume_folder, set_temp_data_folder, settings
from backend.app.geometry.rotator import rotate_annotation, rotate_image_dimensions
from backend.app.models import Annotation, AnnotationOrientationDirection, AnnotationType, DatasetManifest, ImageInfo, RotationDirection
from backend.app.parsers.pascal_voc import _is_pascal_voc_xml
from backend.app.utils.files import resolve_file_path


@dataclass
class DatasetRecord:
    dataset_id: str
    root: Path
    asset_root: Path
    asset_index: dict[str, Path] = field(default_factory=dict)
    images: list[ImageInfo] = field(default_factory=list)
    annotations: dict[str, list[Annotation]] = field(default_factory=dict)
    labels: list[str] = field(default_factory=list)
    image_labels: dict[str, str] = field(default_factory=dict)
    format: str = "unknown"
    rotation_state: dict[int, int] = field(default_factory=dict)
    deleted_images: set[int] = field(default_factory=set)
    image_hashes: dict[int, str] = field(default_factory=dict)
    source_root: Path | None = None
    editable_source: bool = False

    def image_rotation(self, index: int) -> int:
        return self.rotation_state.get(index, 0)

    def is_deleted(self, index: int) -> bool:
        return index in self.deleted_images

    def resolve_image_path(self, index: int) -> Path | None:
        image = self.images[index]
        return resolve_file_path(self.asset_root, self.asset_index, image.filename)

    def image_md5(self, index: int) -> str | None:
        if index in self.image_hashes:
            return self.image_hashes[index]
        image_path = self.resolve_image_path(index)
        if image_path is None:
            return None
        digest = md5()
        with image_path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
        value = digest.hexdigest()
        self.image_hashes[index] = value
        return value

    def image_cache_token(self, index: int) -> str:
        image_path = self.resolve_image_path(index)
        if image_path is None:
            return "missing"
        try:
            stat = image_path.stat()
        except OSError:
            return "missing"
        return f"{stat.st_mtime_ns}-{stat.st_size}"

    @property
    def manifest_path(self) -> Path:
        return self.root / "manifest.json"

    @property
    def state_path(self) -> Path:
        return self.root / "state.json"

    def persist_manifest(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.manifest_path.write_text(
            DatasetManifest(
                format=self.format,
                images=self.images,
                annotations=self.annotations,
                labels=self.labels,
                image_labels=self.image_labels,
            ).model_dump_json(),
            encoding="utf-8",
        )

    def persist_state(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        state = {
            "rotation_state": {str(key): value for key, value in self.rotation_state.items()},
            "deleted_images": sorted(self.deleted_images),
            "image_hashes": {str(key): value for key, value in self.image_hashes.items()},
        }
        self.state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")

    def restore_state(self) -> None:
        if not self.state_path.exists():
            return
        payload = json.loads(self.state_path.read_text(encoding="utf-8"))
        self.rotation_state = {int(key): int(value) for key, value in payload.get("rotation_state", {}).items()}
        self.deleted_images = set(int(item) for item in payload.get("deleted_images", []))
        self.image_hashes = {int(key): str(value) for key, value in payload.get("image_hashes", {}).items()}


class DatasetStore:
    def __init__(self) -> None:
        self._datasets: dict[str, DatasetRecord] = {}
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        self._restore_saved_datasets()

    def _restore_saved_datasets(self) -> None:
        for dataset_root in settings.data_dir.iterdir():
            if not dataset_root.is_dir():
                continue
            manifest_path = dataset_root / "manifest.json"
            asset_root = dataset_root / "assets"
            if not manifest_path.exists() or not asset_root.exists():
                continue
            try:
                manifest = DatasetManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
            except Exception:
                continue
            record = DatasetRecord(
                dataset_id=dataset_root.name,
                root=dataset_root,
                asset_root=asset_root,
                asset_index={},
                images=manifest.images,
                annotations=manifest.annotations,
                labels=manifest.labels or self._labels_from_annotations(manifest.annotations),
                image_labels=manifest.image_labels,
                format=manifest.format,
            )
            record.asset_index = {path.relative_to(asset_root).as_posix(): path for path in asset_root.rglob("*") if path.is_file()}
            record.asset_index.update({path.name: path for path in asset_root.rglob("*") if path.is_file()})
            record.restore_state()
            self._datasets[record.dataset_id] = record

    @staticmethod
    def _is_within(path: Path, parent: Path) -> bool:
        try:
            path.resolve().relative_to(parent.resolve())
        except ValueError:
            return False
        return True

    @staticmethod
    def _labels_from_annotations(annotations: dict[str, list[Annotation]]) -> list[str]:
        return sorted({annotation.label for items in annotations.values() for annotation in items if annotation.label})

    def create_dataset(
        self,
        root: Path,
        asset_root: Path,
        manifest: DatasetManifest,
        asset_index: dict[str, Path] | None = None,
        source_root: Path | None = None,
        editable_source: bool = False,
    ) -> DatasetRecord:
        dataset_id = uuid.uuid4().hex
        record = DatasetRecord(
            dataset_id=dataset_id,
            root=root,
            asset_root=asset_root,
            asset_index=asset_index or {},
            images=manifest.images,
            annotations=manifest.annotations,
            labels=sorted({*(manifest.labels or self._labels_from_annotations(manifest.annotations)), *manifest.image_labels.values()}),
            image_labels=manifest.image_labels,
            format=manifest.format,
            source_root=source_root,
            editable_source=editable_source,
        )
        self._datasets[dataset_id] = record
        record.persist_manifest()
        return record

    def set_classification_label(
        self,
        dataset_id: str,
        label: str,
        image_index: int | None = None,
        apply_to_all: bool = False,
    ) -> DatasetRecord:
        record = self.get(dataset_id)
        normalized_label = label.strip()
        if not normalized_label:
            raise ValueError("Classification label cannot be empty")
        if apply_to_all:
            target_images = [image for index, image in enumerate(record.images) if not record.is_deleted(index)]
        else:
            if image_index is None or image_index < 0 or image_index >= len(record.images):
                raise ValueError("A valid image_index is required")
            target_images = [record.images[image_index]]
        for image in target_images:
            record.image_labels[image.filename] = normalized_label
        record.labels = sorted({*record.labels, normalized_label})
        record.persist_manifest()
        return record

    def get(self, dataset_id: str) -> DatasetRecord:
        if dataset_id not in self._datasets:
            raise KeyError(dataset_id)
        return self._datasets[dataset_id]

    def list_images(self, dataset_id: str) -> list[ImageInfo]:
        return self.get(dataset_id).images

    def list_records(self) -> list[DatasetRecord]:
        return list(self._datasets.values())

    def list_saved_records(self) -> list[DatasetRecord]:
        return [
            record
            for record in self._datasets.values()
            if self._is_within(record.root, settings.data_dir)
        ]

    def update_resume_folder(self, folder: str | Path) -> Path:
        resolved = set_resume_folder(folder)
        resolved.mkdir(parents=True, exist_ok=True)
        self._restore_saved_datasets()
        return resolved

    def update_temp_data_folder(self, folder: str | Path) -> Path:
        return set_temp_data_folder(folder)

    def rotate(self, dataset_id: str, image_index: int, direction: RotationDirection) -> DatasetRecord:
        record = self.get(dataset_id)
        current = record.rotation_state.get(image_index, 0)
        delta = {"left": 270, "right": 90, "180": 180}[direction.value]
        record.rotation_state[image_index] = (current + delta) % 360
        return record

    def reset_rotation(self, dataset_id: str, image_index: int) -> DatasetRecord:
        record = self.get(dataset_id)
        record.rotation_state[image_index] = 0
        return record

    def rotate_annotation_orientation(
        self,
        dataset_id: str,
        image_index: int,
        direction: AnnotationOrientationDirection,
        label: str | None,
    ) -> tuple[DatasetRecord, int]:
        record = self.get(dataset_id)
        image = record.images[image_index]
        updated_annotations: list[Annotation] = []
        updated_count = 0
        for annotation in record.annotations.get(image.filename, []):
            if label is not None and annotation.label != label:
                updated_annotations.append(annotation)
                continue
            if annotation.type not in {AnnotationType.rectangle, AnnotationType.rotated_rectangle, AnnotationType.ellipse}:
                updated_annotations.append(annotation)
                continue
            current_angle = float(annotation.geometry.get("angle", 0) or 0)
            next_angle = 0 if direction.value == "reset" else (current_angle + {"left": 270, "right": 90, "180": 180}[direction.value]) % 360
            geometry = {
                **annotation.geometry,
                "angle": next_angle,
            }
            if direction.value == "reset":
                geometry["dot_reset"] = True
                geometry["display_angle"] = current_angle
            else:
                geometry.pop("dot_reset", None)
                geometry.pop("display_angle", None)
            updated_annotations.append(annotation.model_copy(update={"geometry": geometry}))
            updated_count += 1
        record.annotations[image.filename] = updated_annotations
        return record, updated_count

    def delete_image(self, dataset_id: str, image_index: int) -> DatasetRecord:
        record = self.get(dataset_id)
        record.deleted_images.add(image_index)
        return record

    def delete_images(self, dataset_id: str, image_indexes: list[int]) -> DatasetRecord:
        record = self.get(dataset_id)
        for image_index in image_indexes:
            if 0 <= image_index < len(record.images):
                record.deleted_images.add(image_index)
        return record

    def duplicate_image_groups(self, dataset_id: str) -> list[dict[str, Any]]:
        record = self.get(dataset_id)
        groups: dict[str, list[dict[str, Any]]] = {}
        for index, image in enumerate(record.images):
            if record.is_deleted(index):
                continue
            image_hash = record.image_md5(index)
            if image_hash is None:
                continue
            groups.setdefault(image_hash, []).append(
                {
                    "index": index,
                    "filename": image.filename,
                    "width": image.width,
                    "height": image.height,
                    "image_url": f"/api/dataset/{dataset_id}/image/{index}/file?v={record.image_cache_token(index)}",
                }
            )
        return [{"md5": image_hash, "images": images} for image_hash, images in groups.items() if len(images) > 1]

    def apply_image_rotations_to_workspace(self, dataset_id: str) -> int:
        record = self.get(dataset_id)
        if any(record.annotations.get(image.filename) for image in record.images):
            raise ValueError("Applying rotations to image files is only available for unlabeled image-folder datasets")
        updated_count = 0
        for index, image in enumerate(record.images):
            rotation = record.image_rotation(index)
            if rotation == 0 or record.is_deleted(index):
                continue
            image_path = record.resolve_image_path(index)
            if image_path is None:
                continue
            with Image.open(image_path) as source:
                normalized_rotation = rotation % 360
                if normalized_rotation == 90:
                    rotated = source.rotate(-90, expand=True)
                elif normalized_rotation == 180:
                    rotated = source.rotate(180, expand=True)
                elif normalized_rotation == 270:
                    rotated = source.rotate(-270, expand=True)
                else:
                    rotated = source.copy()
                image_format = source.format or image_path.suffix.lstrip(".").upper() or "PNG"
                rotated.save(image_path, format=image_format)
                record.images[index] = image.model_copy(update={"width": rotated.width, "height": rotated.height})
            record.rotation_state[index] = 0
            record.image_hashes.pop(index, None)
            updated_count += 1
        record.persist_manifest()
        record.persist_state()
        return updated_count

    @staticmethod
    def _rotate_image_file_in_place(image_path: Path, rotation: int) -> tuple[int, int]:
        temporary_path = image_path.with_name(f".{image_path.stem}.cvat-rotator{image_path.suffix}")
        with Image.open(image_path) as source:
            source.load()
            normalized_rotation = rotation % 360
            if normalized_rotation == 90:
                rotated = source.rotate(-90, expand=True)
            elif normalized_rotation == 180:
                rotated = source.rotate(180, expand=True)
            elif normalized_rotation == 270:
                rotated = source.rotate(-270, expand=True)
            else:
                rotated = source.copy()
            image_format = source.format or image_path.suffix.lstrip(".").upper() or "PNG"
            new_width, new_height = rotated.width, rotated.height
            rotated.save(temporary_path, format=image_format)
        os.replace(temporary_path, image_path)
        return new_width, new_height

    @staticmethod
    def _pascal_xml_map(source_root: Path) -> dict[str, Path]:
        xml_map: dict[str, Path] = {}
        for xml_path in source_root.rglob("*.xml"):
            if not xml_path.is_file() or not _is_pascal_voc_xml(xml_path):
                continue
            try:
                root = etree.parse(str(xml_path)).getroot()
            except Exception:
                continue
            filename = root.findtext("filename")
            if filename:
                xml_map.setdefault(Path(filename).as_posix(), xml_path)
                xml_map.setdefault(Path(filename).name, xml_path)
                xml_map.setdefault(Path(filename).stem, xml_path)
            xml_map.setdefault(xml_path.stem, xml_path)
        return xml_map

    @staticmethod
    def _pascal_xml_for_image(xml_map: dict[str, Path], image: ImageInfo) -> Path | None:
        filename = Path(image.filename)
        return (
            xml_map.get(filename.as_posix())
            or xml_map.get(filename.name)
            or xml_map.get(filename.stem)
        )

    @staticmethod
    def _backup_source_files(source_root: Path, files: list[Path]) -> Path:
        backup_dir = source_root / ".cvat-rotator-backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_path = backup_dir / f"backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}.zip"
        with zipfile.ZipFile(backup_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for file_path in files:
                if file_path.exists() and file_path.is_file():
                    archive.write(file_path, file_path.relative_to(source_root).as_posix())
        return backup_path

    @staticmethod
    def _update_pascal_xml(
        xml_path: Path,
        image: ImageInfo,
        annotations: list[Annotation],
        rotation: int,
        new_width: int,
        new_height: int,
    ) -> list[Annotation]:
        tree = etree.parse(str(xml_path))
        root = tree.getroot()
        size_node = root.find("size")
        if size_node is None:
            size_node = etree.SubElement(root, "size")
        width_node = size_node.find("width")
        if width_node is None:
            width_node = etree.SubElement(size_node, "width")
        height_node = size_node.find("height")
        if height_node is None:
            height_node = etree.SubElement(size_node, "height")
        width_node.text = str(new_width)
        height_node.text = str(new_height)

        rotated_annotations = [rotate_annotation(annotation, image.width, image.height, rotation) for annotation in annotations]
        object_nodes = root.findall("object")
        rectangle_annotations = [
            annotation for annotation in rotated_annotations if annotation.type == AnnotationType.rectangle
        ]
        for object_node, annotation in zip(object_nodes, rectangle_annotations):
            bndbox = object_node.find("bndbox")
            if bndbox is None:
                bndbox = etree.SubElement(object_node, "bndbox")
            geometry = annotation.geometry
            values = {
                "xmin": int(round(float(geometry["x1"]))),
                "ymin": int(round(float(geometry["y1"]))),
                "xmax": int(round(float(geometry["x2"]))),
                "ymax": int(round(float(geometry["y2"]))),
            }
            for tag, value in values.items():
                node = bndbox.find(tag)
                if node is None:
                    node = etree.SubElement(bndbox, tag)
                node.text = str(value)
        tree.write(str(xml_path), encoding="utf-8", xml_declaration=False, pretty_print=True)
        return rotated_annotations

    def apply_changes_to_source(self, dataset_id: str) -> dict[str, Any]:
        record = self.get(dataset_id)
        if not record.editable_source or record.source_root is None:
            raise ValueError("This dataset was not opened as an editable local source folder")
        if record.format not in {"pascal_voc", "image_folder"}:
            raise ValueError("Applying changes to source is currently available for Pascal VOC and image-only folders")

        pending_indexes = [
            index
            for index, _ in enumerate(record.images)
            if record.image_rotation(index) != 0 and not record.is_deleted(index)
        ]
        if not pending_indexes:
            return {"updated": 0, "backup_path": None}

        xml_map = self._pascal_xml_map(record.source_root) if record.format == "pascal_voc" else {}
        files_to_backup: list[Path] = []
        work_items: list[tuple[int, ImageInfo, Path, Path | None]] = []
        for index in pending_indexes:
            image = record.images[index]
            image_path = record.resolve_image_path(index)
            if image_path is None:
                continue
            xml_path = self._pascal_xml_for_image(xml_map, image) if record.format == "pascal_voc" else None
            work_items.append((index, image, image_path, xml_path))
            files_to_backup.append(image_path)
            if xml_path is not None:
                files_to_backup.append(xml_path)

        if not work_items:
            return {"updated": 0, "backup_path": None}

        backup_path = self._backup_source_files(record.source_root, files_to_backup)
        updated_count = 0
        for index, image, image_path, xml_path in work_items:
            rotation = record.image_rotation(index)
            expected_width, expected_height = rotate_image_dimensions(image.width, image.height, rotation)
            new_width, new_height = self._rotate_image_file_in_place(image_path, rotation)
            annotations = record.annotations.get(image.filename, [])
            if xml_path is not None:
                record.annotations[image.filename] = self._update_pascal_xml(
                    xml_path,
                    image,
                    annotations,
                    rotation,
                    new_width,
                    new_height,
                )
            elif annotations:
                record.annotations[image.filename] = [
                    rotate_annotation(annotation, image.width, image.height, rotation)
                    for annotation in annotations
                ]
            record.images[index] = image.model_copy(
                update={
                    "width": new_width or expected_width,
                    "height": new_height or expected_height,
                }
            )
            record.rotation_state[index] = 0
            record.image_hashes.pop(index, None)
            updated_count += 1

        record.asset_index = {
            path.relative_to(record.asset_root).as_posix(): path
            for path in record.asset_root.rglob("*")
            if path.is_file()
        }
        record.asset_index.update({path.name: path for path in record.asset_root.rglob("*") if path.is_file()})
        record.persist_manifest()
        record.persist_state()
        return {"updated": updated_count, "backup_path": str(backup_path)}

    def save(self, dataset_id: str) -> DatasetRecord:
        record = self.get(dataset_id)
        record.persist_manifest()
        record.persist_state()
        if record.editable_source:
            return record
        if self._is_within(record.root, settings.temp_data_dir):
            temporary_root = record.root
            saved_root = settings.data_dir / record.dataset_id
            if saved_root.exists():
                shutil.rmtree(saved_root)
            shutil.copytree(temporary_root, saved_root)
            record.root = saved_root
            record.asset_root = saved_root / "assets"
            record.asset_index = {
                path.relative_to(record.asset_root).as_posix(): path
                for path in record.asset_root.rglob("*")
                if path.is_file()
            }
            record.asset_index.update(
                {path.name: path for path in record.asset_root.rglob("*") if path.is_file()}
            )
            shutil.rmtree(temporary_root)
        return record

    def cleanup(self, dataset_id: str) -> None:
        record = self._datasets.pop(dataset_id, None)
        if record and record.root.exists():
            shutil.rmtree(record.root, ignore_errors=True)

    def cleanup_all(self) -> None:
        for dataset_id in list(self._datasets):
            self.cleanup(dataset_id)

    def clear_temp_data(self) -> tuple[list[str], int]:
        temp_root = settings.temp_data_dir.resolve()
        drive_root = Path(temp_root.anchor).resolve()
        if temp_root in {drive_root, Path.home().resolve()}:
            raise ValueError("Refusing to clear a drive root or home folder")
        if self._is_within(settings.data_dir, temp_root) or self._is_within(temp_root, settings.data_dir):
            raise ValueError("Temporary data folder overlaps the resume folder")
        if self._is_within(settings.export_dir, temp_root) or self._is_within(temp_root, settings.export_dir):
            raise ValueError("Temporary data folder overlaps the export folder")
        removed_datasets = [
            dataset_id
            for dataset_id, record in self._datasets.items()
            if self._is_within(record.root, temp_root)
        ]
        for dataset_id in removed_datasets:
            self._datasets.pop(dataset_id, None)

        removed_items = 0
        temp_root.mkdir(parents=True, exist_ok=True)
        for item in list(temp_root.iterdir()):
            removed_items += 1
            if item.is_symlink() or item.is_file():
                item.unlink()
            elif item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()
        return removed_datasets, removed_items

    def export_manifest(self, dataset_id: str) -> dict[str, Any]:
        record = self.get(dataset_id)
        return {
            "dataset_id": record.dataset_id,
            "format": record.format,
            "labels": record.labels,
            "image_labels": record.image_labels,
            "rotation_state": record.rotation_state,
            "deleted_images": sorted(record.deleted_images),
            "images": [image.model_dump() for image in record.images],
            "annotations": {
                key: [annotation.model_dump() for annotation in value]
                for key, value in record.annotations.items()
            },
        }


dataset_store = DatasetStore()
