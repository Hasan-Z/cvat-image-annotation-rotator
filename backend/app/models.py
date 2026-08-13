from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class RotationDirection(str, Enum):
    left = "left"
    right = "right"
    rotate_180 = "180"


class AnnotationOrientationDirection(str, Enum):
    left = "left"
    right = "right"
    rotate_180 = "180"
    reset = "reset"


class AnnotationType(str, Enum):
    rectangle = "rectangle"
    polygon = "polygon"
    polyline = "polyline"
    points = "points"
    ellipse = "ellipse"
    cuboid = "cuboid"
    skeleton = "skeleton"
    mask = "mask"
    rotated_rectangle = "rotated_rectangle"


class Annotation(BaseModel):
    id: str
    type: AnnotationType
    label: str
    attributes: dict[str, Any] = Field(default_factory=dict)
    geometry: dict[str, Any]


class ImageInfo(BaseModel):
    filename: str
    width: int
    height: int
    thumbnail_url: str | None = None


class DatasetSummary(BaseModel):
    dataset_id: str
    num_images: int


class DatasetImageResponse(BaseModel):
    image_url: str
    width: int
    height: int
    rotation: int
    annotations: list[Annotation]
    filename: str
    index: int
    format: str
    editable_source: bool = False
    source_folder: str | None = None
    classification_label: str | None = None
    labels: list[str] = Field(default_factory=list)


class DatasetImageSummary(BaseModel):
    image_url: str
    width: int
    height: int
    rotation: int
    filename: str
    index: int
    format: str
    annotation_count: int = 0
    editable_source: bool = False
    source_folder: str | None = None
    classification_label: str | None = None


class RotateRequest(BaseModel):
    image_index: int
    direction: RotationDirection


class AnnotationOrientationRequest(BaseModel):
    image_index: int
    direction: AnnotationOrientationDirection
    label: str | None = None


class RangeExportRequest(BaseModel):
    start_index: int | None = None
    end_index: int | None = None


class DuplicateImageItem(BaseModel):
    index: int
    filename: str
    width: int
    height: int
    image_url: str


class DuplicateImageGroup(BaseModel):
    md5: str
    images: list[DuplicateImageItem]


class BulkDeleteRequest(BaseModel):
    image_indexes: list[int]


class ClassificationLabelRequest(BaseModel):
    image_index: int | None = None
    label: str
    apply_to_all: bool = False


class UploadResponse(BaseModel):
    dataset_id: str
    num_images: int
    format: str
    editable_source: bool = False
    source_folder: str | None = None


class AppSettingsResponse(BaseModel):
    resume_folder: str
    resume_folder_size_bytes: int
    temp_data_folder: str
    temp_data_folder_size_bytes: int
    export_folder: str
    export_folder_size_bytes: int
    export_mode: Literal["ask", "folder"]


class AppSettingsUpdate(BaseModel):
    resume_folder: str | None = None
    temp_data_folder: str | None = None
    export_folder: str | None = None
    export_mode: Literal["ask", "folder"] | None = None


class TempDataClearResponse(BaseModel):
    removed_datasets: list[str]
    removed_items: int


class FolderExportResponse(BaseModel):
    filename: str
    path: str


class ExportFormat(str, Enum):
    app_bundle = "app_bundle"
    cvat_for_images_1_1 = "cvat_for_images_1_1"
    cvat_for_images_1_1_image_paths = "cvat_for_images_1_1_image_paths"
    coco = "coco"
    yolo = "yolo"
    pascal_voc = "pascal_voc"
    modelarts_pascal_voc = "modelarts_pascal_voc"
    labelme = "labelme"
    datumaro = "datumaro"
    segmentation_mask = "segmentation_mask"
    kitti = "kitti"
    open_images = "open_images"
    image_classification = "image_classification"


class DatasetManifest(BaseModel):
    format: Literal[
        "cvat_xml",
        "coco",
        "yolo",
        "app_bundle",
        "pascal_voc",
        "labelme",
        "datumaro",
        "segmentation_mask",
        "kitti",
        "open_images",
        "image_folder",
        "merged",
        "unknown",
    ] = "unknown"
    images: list[ImageInfo] = Field(default_factory=list)
    annotations: dict[str, list[Annotation]] = Field(default_factory=dict)
    labels: list[str] = Field(default_factory=list)
    image_labels: dict[str, str] = Field(default_factory=dict)
