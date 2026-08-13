from __future__ import annotations

import asyncio
import shutil
import uuid
from pathlib import Path, PurePosixPath

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, Response
from starlette.datastructures import UploadFile as StarletteUploadFile

from PIL import Image

from backend.app.config import set_export_preferences, settings
from backend.app.models import AppSettingsResponse, AppSettingsUpdate, AnnotationOrientationRequest, BulkDeleteRequest, ClassificationLabelRequest, DatasetImageResponse, DatasetImageSummary, DuplicateImageGroup, ExportFormat, FolderExportResponse, RotateRequest, TempDataClearResponse, UploadResponse
from backend.app.parsers import parse_dataset_archive
from backend.app.exporters.coco import build_coco_zip_subset
from backend.app.exporters.datumaro import build_datumaro_zip_subset
from backend.app.exporters.cvat_xml import build_cvat_for_images_image_paths_zip_subset, build_cvat_for_images_zip_subset
from backend.app.exporters.image_classification import build_image_classification_zip_subset
from backend.app.exporters.kitti import build_kitti_zip_subset
from backend.app.exporters.labelme import build_labelme_zip_subset
from backend.app.exporters.modelarts_pascal_voc import build_modelarts_pascal_voc_zip_subset
from backend.app.exporters.open_images import build_open_images_zip_subset
from backend.app.exporters.pascal_voc import build_pascal_voc_zip_subset
from backend.app.exporters.segmentation_mask import build_segmentation_mask_zip_subset
from backend.app.exporters.yolo import build_yolo_zip_subset
from backend.app.services.dataset_store import dataset_store
from backend.app.services.export_service import build_export_zip_subset
from backend.app.services.safe_zip import extract_zip_streaming
from backend.app.utils.files import build_file_index
from backend.app.models import DatasetManifest, ImageInfo

router = APIRouter(prefix="/api")


def _folder_size_bytes(folder: Path) -> int:
    if not folder.exists():
        return 0
    total = 0
    try:
        for path in folder.rglob("*"):
            try:
                if path.is_file():
                    total += path.stat().st_size
            except OSError:
                continue
    except OSError:
        return total
    return total


def _choose_folder(initial_folder: Path, title: str) -> str | None:
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        selected = filedialog.askdirectory(
            title=title,
            initialdir=str(initial_folder),
            mustexist=True,
        )
        return selected or None
    finally:
        root.destroy()


def _safe_upload_target(destination: Path, filename: str | None) -> Path:
    raw_name = (filename or "").replace("\\", "/")
    if raw_name.startswith("/") or PurePosixPath(raw_name).is_absolute():
        raise ValueError(filename or "")
    normalized = raw_name.strip("/")
    relative_path = PurePosixPath(normalized)
    if not normalized or "//" in normalized or relative_path.is_absolute() or any(part in {"", ".", ".."} for part in relative_path.parts):
        raise ValueError(filename or "")
    target = (destination / Path(*relative_path.parts)).resolve()
    try:
        target.relative_to(destination.resolve())
    except ValueError as exc:
        raise ValueError(filename or "") from exc
    return target


async def _write_upload_file(upload_file: UploadFile, target: Path, max_bytes: int, written: int) -> int:
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("wb") as sink:
        while True:
            chunk = await upload_file.read(1024 * 1024)
            if not chunk:
                break
            written += len(chunk)
            if written > max_bytes:
                raise HTTPException(status_code=413, detail="Upload too large")
            sink.write(chunk)
    return written


@router.get("/settings", response_model=AppSettingsResponse)
async def get_app_settings() -> AppSettingsResponse:
    resume_size, temp_size, export_size = await asyncio.gather(
        asyncio.to_thread(_folder_size_bytes, settings.data_dir),
        asyncio.to_thread(_folder_size_bytes, settings.temp_data_dir),
        asyncio.to_thread(_folder_size_bytes, settings.export_dir),
    )
    return AppSettingsResponse(
        resume_folder=str(settings.data_dir),
        resume_folder_size_bytes=resume_size,
        temp_data_folder=str(settings.temp_data_dir),
        temp_data_folder_size_bytes=temp_size,
        export_folder=str(settings.export_dir),
        export_folder_size_bytes=export_size,
        export_mode=settings.export_mode,
    )


@router.put("/settings", response_model=AppSettingsResponse)
async def update_app_settings(payload: AppSettingsUpdate) -> AppSettingsResponse:
    try:
        if payload.resume_folder is not None:
            dataset_store.update_resume_folder(payload.resume_folder)
        if payload.temp_data_folder is not None:
            dataset_store.update_temp_data_folder(payload.temp_data_folder)
        set_export_preferences(payload.export_folder, payload.export_mode)
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=f"Unable to update application folders: {exc}") from exc
    return await get_app_settings()


@router.post("/settings/select-resume-folder", response_model=AppSettingsResponse)
async def select_resume_folder() -> AppSettingsResponse:
    try:
        selected = await asyncio.to_thread(_choose_folder, settings.data_dir, "Choose CVAT Rotator resume workspace folder")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Unable to open folder picker: {exc}") from exc
    if selected is None:
        return await get_app_settings()
    try:
        resume_folder = dataset_store.update_resume_folder(selected)
    except OSError as exc:
        raise HTTPException(status_code=400, detail=f"Unable to use resume workspace folder: {exc}") from exc
    return await get_app_settings()


@router.post("/settings/select-export-folder", response_model=AppSettingsResponse)
async def select_export_folder() -> AppSettingsResponse:
    try:
        selected = await asyncio.to_thread(_choose_folder, settings.export_dir, "Choose CVAT Rotator export folder")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Unable to open folder picker: {exc}") from exc
    if selected is None:
        return await get_app_settings()
    try:
        set_export_preferences(folder=selected)
    except OSError as exc:
        raise HTTPException(status_code=400, detail=f"Unable to use export folder: {exc}") from exc
    return await get_app_settings()


@router.post("/settings/select-temp-data-folder", response_model=AppSettingsResponse)
async def select_temp_data_folder() -> AppSettingsResponse:
    try:
        selected = await asyncio.to_thread(
            _choose_folder,
            settings.temp_data_dir,
            "Choose CVAT Rotator temporary data folder",
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Unable to open folder picker: {exc}") from exc
    if selected is None:
        return await get_app_settings()
    try:
        dataset_store.update_temp_data_folder(selected)
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=f"Unable to use temporary data folder: {exc}") from exc
    return await get_app_settings()


@router.delete("/settings/temp-data", response_model=TempDataClearResponse)
async def clear_temp_data() -> TempDataClearResponse:
    try:
        removed_datasets, removed_items = dataset_store.clear_temp_data()
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=500, detail=f"Unable to clear temporary data: {exc}") from exc
    return TempDataClearResponse(
        removed_datasets=removed_datasets,
        removed_items=removed_items,
    )


@router.post("/upload", response_model=UploadResponse)
async def upload_dataset(file: UploadFile = File(...)) -> UploadResponse:
    suffix = Path(file.filename or "dataset.zip").suffix or ".zip"
    dataset_id = uuid.uuid4().hex
    dataset_root = settings.temp_data_dir / dataset_id
    dataset_root.mkdir(parents=True, exist_ok=False)
    archive_path = dataset_root / f"upload{suffix}"
    max_bytes = settings.max_upload_mb * 1024 * 1024
    written = 0
    with archive_path.open("wb") as sink:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            written += len(chunk)
            if written > max_bytes:
                raise HTTPException(status_code=413, detail="Upload too large")
            sink.write(chunk)
    extracted_root = dataset_root / "assets"
    extract_zip_streaming(archive_path, extracted_root, max_bytes)
    archive_path.unlink(missing_ok=True)
    manifest = parse_dataset_archive(extracted_root)
    record = dataset_store.create_dataset(dataset_root, extracted_root, manifest, build_file_index(extracted_root))
    return UploadResponse(dataset_id=record.dataset_id, num_images=len(record.images), format=record.format)


def _prefix_manifest(manifest, prefix: str) -> DatasetManifest:
    images = [
        image.model_copy(update={"filename": f"{prefix}/{image.filename}"})
        for image in manifest.images
    ]
    annotations = {
        f"{prefix}/{filename}": values
        for filename, values in manifest.annotations.items()
    }
    image_labels = {
        f"{prefix}/{filename}": label
        for filename, label in manifest.image_labels.items()
    }
    return DatasetManifest(
        format=manifest.format,
        images=images,
        annotations=annotations,
        labels=manifest.labels,
        image_labels=image_labels,
    )


@router.post("/upload-multiple", response_model=UploadResponse)
async def upload_multiple_datasets(request: Request) -> UploadResponse:
    form = await request.form(max_files=500, max_fields=500)
    files = [item for item in form.getlist("files") if isinstance(item, StarletteUploadFile)]
    if len(files) < 2:
        raise HTTPException(status_code=400, detail="Upload at least two ZIP files to merge")
    dataset_id = uuid.uuid4().hex
    dataset_root = settings.temp_data_dir / dataset_id
    dataset_root.mkdir(parents=True, exist_ok=False)
    extracted_root = dataset_root / "assets"
    extracted_root.mkdir(parents=True, exist_ok=True)
    max_bytes = settings.max_upload_mb * 1024 * 1024
    combined_images: list[ImageInfo] = []
    combined_annotations = {}
    combined_labels: set[str] = set()
    combined_image_labels = {}
    try:
        for file_index, upload_file in enumerate(files):
            suffix = Path(upload_file.filename or f"dataset-{file_index}.zip").suffix or ".zip"
            job_prefix = f"job_{file_index + 1:03d}"
            archive_path = dataset_root / f"{job_prefix}{suffix}"
            written = await _write_upload_file(upload_file, archive_path, max_bytes, 0)
            job_root = extracted_root / job_prefix
            extract_zip_streaming(archive_path, job_root, max_bytes)
            archive_path.unlink(missing_ok=True)
            manifest = _prefix_manifest(parse_dataset_archive(job_root), job_prefix)
            combined_images.extend(manifest.images)
            combined_annotations.update(manifest.annotations)
            combined_labels.update(manifest.labels)
            combined_image_labels.update(manifest.image_labels)
        combined_manifest = DatasetManifest(
            format="merged",
            images=combined_images,
            annotations=combined_annotations,
            labels=sorted(combined_labels),
            image_labels=combined_image_labels,
        )
        record = dataset_store.create_dataset(dataset_root, extracted_root, combined_manifest, build_file_index(extracted_root))
    except Exception:
        shutil.rmtree(dataset_root, ignore_errors=True)
        raise
    return UploadResponse(dataset_id=record.dataset_id, num_images=len(record.images), format=record.format)


@router.post("/upload-folder", response_model=UploadResponse)
async def upload_dataset_folder(request: Request) -> UploadResponse:
    form = await request.form(max_files=200_000, max_fields=200_000)
    files = [item for item in form.getlist("files") if isinstance(item, StarletteUploadFile)]
    if not files:
        raise HTTPException(status_code=400, detail="No files were uploaded")
    dataset_id = uuid.uuid4().hex
    dataset_root = settings.temp_data_dir / dataset_id
    dataset_root.mkdir(parents=True, exist_ok=False)
    extracted_root = dataset_root / "assets"
    extracted_root.mkdir(parents=True, exist_ok=True)
    max_bytes = settings.max_upload_mb * 1024 * 1024
    written = 0
    try:
        for upload_file in files:
            try:
                target = _safe_upload_target(extracted_root, upload_file.filename)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=f"Unsafe folder upload path: {upload_file.filename}") from exc
            written = await _write_upload_file(upload_file, target, max_bytes, written)
        manifest = parse_dataset_archive(extracted_root)
        record = dataset_store.create_dataset(dataset_root, extracted_root, manifest, build_file_index(extracted_root))
    except Exception:
        shutil.rmtree(dataset_root, ignore_errors=True)
        raise
    return UploadResponse(dataset_id=record.dataset_id, num_images=len(record.images), format=record.format)


@router.post("/open-local-folder", response_model=UploadResponse)
async def open_local_folder() -> UploadResponse:
    try:
        selected = await asyncio.to_thread(
            _choose_folder,
            settings.data_dir,
            "Choose local dataset folder",
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Unable to open folder picker: {exc}") from exc
    if selected is None:
        raise HTTPException(status_code=400, detail="No local folder was selected")

    source_root = Path(selected).resolve()
    try:
        manifest = await asyncio.to_thread(parse_dataset_archive, source_root)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Unable to parse selected local folder: {exc}") from exc
    editable_source = manifest.format in {"pascal_voc", "image_folder"}

    dataset_id = uuid.uuid4().hex
    dataset_root = settings.temp_data_dir / dataset_id
    dataset_root.mkdir(parents=True, exist_ok=False)
    record = dataset_store.create_dataset(
        dataset_root,
        source_root,
        manifest,
        build_file_index(source_root),
        source_root=source_root,
        editable_source=editable_source,
    )
    return UploadResponse(
        dataset_id=record.dataset_id,
        num_images=len(record.images),
        format=record.format,
        editable_source=editable_source,
        source_folder=str(source_root),
    )


@router.get("/datasets", response_model=list[UploadResponse])
async def list_saved_datasets() -> list[UploadResponse]:
    return [
        UploadResponse(
            dataset_id=record.dataset_id,
            num_images=len(record.images),
            format=record.format,
            editable_source=record.editable_source,
            source_folder=str(record.source_root) if record.source_root else None,
        )
        for record in dataset_store.list_saved_records()
    ]


@router.get("/dataset/{dataset_id}/image/{index}", response_model=DatasetImageResponse)
async def get_image(dataset_id: str, index: int) -> DatasetImageResponse:
    try:
        record = dataset_store.get(dataset_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Dataset not found") from exc
    if index < 0 or index >= len(record.images):
        raise HTTPException(status_code=404, detail="Image not found")
    if record.is_deleted(index):
        raise HTTPException(status_code=404, detail="Image deleted")
    image = record.images[index]
    rotation = record.image_rotation(index)
    annotations = record.annotations.get(image.filename, [])
    return DatasetImageResponse(
        image_url=f"/api/dataset/{dataset_id}/image/{index}/file?v={record.image_cache_token(index)}",
        width=image.width,
        height=image.height,
        rotation=rotation,
        annotations=annotations,
        filename=image.filename,
        index=index,
        format=record.format,
        editable_source=record.editable_source,
        source_folder=str(record.source_root) if record.source_root else None,
        classification_label=record.image_labels.get(image.filename),
        labels=record.labels,
    )


@router.get("/dataset/{dataset_id}/images", response_model=list[DatasetImageSummary])
async def list_images(dataset_id: str) -> list[DatasetImageSummary]:
    try:
        record = dataset_store.get(dataset_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Dataset not found") from exc
    summaries: list[DatasetImageSummary] = []
    for index, image in enumerate(record.images):
        if record.is_deleted(index):
            continue
        rotation = record.image_rotation(index)
        summaries.append(
            DatasetImageSummary(
                image_url=f"/api/dataset/{dataset_id}/image/{index}/file?v={record.image_cache_token(index)}",
                width=image.width,
                height=image.height,
                rotation=rotation,
                filename=image.filename,
                index=index,
                format=record.format,
                annotation_count=len(record.annotations.get(image.filename, [])),
                editable_source=record.editable_source,
                source_folder=str(record.source_root) if record.source_root else None,
                classification_label=record.image_labels.get(image.filename),
            )
        )
    return summaries


@router.get("/dataset/{dataset_id}/image/{index}/file")
async def get_image_file(dataset_id: str, index: int) -> Response:
    try:
        record = dataset_store.get(dataset_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Dataset not found") from exc
    image = record.images[index]
    resolved_path = record.resolve_image_path(index)
    if resolved_path is None:
        raise HTTPException(status_code=404, detail="Image file not found")
    with Image.open(resolved_path) as source:
        from io import BytesIO

        buffer = BytesIO()
        source.save(buffer, format=source.format or "PNG")
        return Response(
            content=buffer.getvalue(),
            media_type=f"image/{(source.format or 'png').lower()}",
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                "Pragma": "no-cache",
            },
        )


@router.post("/dataset/{dataset_id}/rotate")
async def rotate_image(dataset_id: str, request: RotateRequest) -> dict[str, int]:
    try:
        record = dataset_store.rotate(dataset_id, request.image_index, request.direction)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Dataset not found") from exc
    return {"rotation": record.image_rotation(request.image_index)}


@router.post("/dataset/{dataset_id}/reset-rotation")
async def reset_rotation(dataset_id: str, request: RotateRequest) -> dict[str, int]:
    try:
        record = dataset_store.reset_rotation(dataset_id, request.image_index)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Dataset not found") from exc
    return {"rotation": record.image_rotation(request.image_index)}


@router.post("/dataset/{dataset_id}/annotation-orientation")
async def rotate_annotation_orientation(dataset_id: str, request: AnnotationOrientationRequest) -> dict[str, int]:
    try:
        _, updated_count = dataset_store.rotate_annotation_orientation(
            dataset_id,
            request.image_index,
            request.direction,
            request.label,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Dataset not found") from exc
    return {"updated": updated_count}


@router.post("/dataset/{dataset_id}/classification-label")
async def set_classification_label(dataset_id: str, request: ClassificationLabelRequest) -> dict[str, int | str]:
    try:
        record = dataset_store.set_classification_label(
            dataset_id,
            request.label,
            image_index=request.image_index,
            apply_to_all=request.apply_to_all,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Dataset not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    updated = len([image for index, image in enumerate(record.images) if not record.is_deleted(index)]) if request.apply_to_all else 1
    return {"label": request.label.strip(), "updated": updated}


@router.post("/dataset/{dataset_id}/delete")
async def delete_image(dataset_id: str, request: RotateRequest) -> dict[str, str]:
    try:
        dataset_store.delete_image(dataset_id, request.image_index)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Dataset not found") from exc
    return {"status": "deleted"}


@router.get("/dataset/{dataset_id}/duplicates", response_model=list[DuplicateImageGroup])
async def list_duplicate_images(dataset_id: str) -> list[DuplicateImageGroup]:
    try:
        groups = await asyncio.to_thread(dataset_store.duplicate_image_groups, dataset_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Dataset not found") from exc
    return [DuplicateImageGroup.model_validate(group) for group in groups]


@router.post("/dataset/{dataset_id}/delete-images")
async def delete_images(dataset_id: str, request: BulkDeleteRequest) -> dict[str, int]:
    try:
        record = dataset_store.delete_images(dataset_id, request.image_indexes)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Dataset not found") from exc
    return {"deleted": len([index for index in request.image_indexes if index in record.deleted_images])}


@router.post("/dataset/{dataset_id}/apply-image-rotations")
async def apply_image_rotations(dataset_id: str) -> dict[str, int]:
    try:
        updated = await asyncio.to_thread(dataset_store.apply_image_rotations_to_workspace, dataset_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Dataset not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"updated": updated}


@router.post("/dataset/{dataset_id}/apply-to-source")
async def apply_changes_to_source(dataset_id: str) -> dict[str, int | str | None]:
    try:
        result = await asyncio.to_thread(dataset_store.apply_changes_to_source, dataset_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Dataset not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"updated": int(result["updated"]), "backup_path": result["backup_path"]}


@router.post("/dataset/{dataset_id}/save")
async def save_dataset(dataset_id: str) -> dict[str, str]:
    try:
        dataset_store.save(dataset_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Dataset not found") from exc
    return {"status": "saved"}


@router.delete("/dataset/{dataset_id}")
async def cleanup_dataset(dataset_id: str) -> dict[str, str]:
    try:
        dataset_store.get(dataset_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Dataset not found") from exc
    dataset_store.cleanup(dataset_id)
    return {"status": "deleted"}


def _build_dataset_export(
    record,
    export_path: Path,
    start_index: int | None,
    end_index: int | None,
    export_format: ExportFormat,
) -> None:
    if export_format == ExportFormat.cvat_for_images_1_1:
        build_cvat_for_images_zip_subset(record, export_path, start_index=start_index, end_index=end_index)
    elif export_format == ExportFormat.cvat_for_images_1_1_image_paths:
        build_cvat_for_images_image_paths_zip_subset(record, export_path, start_index=start_index, end_index=end_index)
    elif export_format == ExportFormat.coco:
        build_coco_zip_subset(record, export_path, start_index=start_index, end_index=end_index)
    elif export_format == ExportFormat.yolo:
        build_yolo_zip_subset(record, export_path, start_index=start_index, end_index=end_index)
    elif export_format == ExportFormat.pascal_voc:
        build_pascal_voc_zip_subset(record, export_path, start_index=start_index, end_index=end_index)
    elif export_format == ExportFormat.modelarts_pascal_voc:
        build_modelarts_pascal_voc_zip_subset(record, export_path, start_index=start_index, end_index=end_index)
    elif export_format == ExportFormat.labelme:
        build_labelme_zip_subset(record, export_path, start_index=start_index, end_index=end_index)
    elif export_format == ExportFormat.datumaro:
        build_datumaro_zip_subset(record, export_path, start_index=start_index, end_index=end_index)
    elif export_format == ExportFormat.segmentation_mask:
        build_segmentation_mask_zip_subset(record, export_path, start_index=start_index, end_index=end_index)
    elif export_format == ExportFormat.kitti:
        build_kitti_zip_subset(record, export_path, start_index=start_index, end_index=end_index)
    elif export_format == ExportFormat.open_images:
        build_open_images_zip_subset(record, export_path, start_index=start_index, end_index=end_index)
    elif export_format == ExportFormat.image_classification:
        build_image_classification_zip_subset(record, export_path, start_index=start_index, end_index=end_index)
    else:
        build_export_zip_subset(record, export_path, start_index=start_index, end_index=end_index)


@router.post("/dataset/{dataset_id}/export-to-folder", response_model=FolderExportResponse)
async def export_dataset_to_folder(
    dataset_id: str,
    start_index: int | None = None,
    end_index: int | None = None,
    export_format: ExportFormat = Query(default=ExportFormat.app_bundle),
) -> FolderExportResponse:
    try:
        record = dataset_store.get(dataset_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Dataset not found") from exc
    if start_index is not None and start_index < 0:
        raise HTTPException(status_code=400, detail="start_index must be >= 0")
    if end_index is not None and end_index < 0:
        raise HTTPException(status_code=400, detail="end_index must be >= 0")
    if start_index is not None and end_index is not None and end_index < start_index:
        raise HTTPException(status_code=400, detail="end_index must be >= start_index")
    filename = f"{dataset_id}-{export_format.value}.zip"
    temporary_path = record.root / filename
    _build_dataset_export(record, temporary_path, start_index, end_index, export_format)
    destination = settings.export_dir / filename
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(temporary_path, destination)
    temporary_path.unlink(missing_ok=True)
    return FolderExportResponse(filename=filename, path=str(destination))


@router.get("/dataset/{dataset_id}/download")
async def download_dataset(
    dataset_id: str,
    background_tasks: BackgroundTasks,
    start_index: int | None = None,
    end_index: int | None = None,
    export_format: ExportFormat = Query(default=ExportFormat.app_bundle),
) -> FileResponse:
    try:
        record = dataset_store.get(dataset_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Dataset not found") from exc
    if start_index is not None and start_index < 0:
        raise HTTPException(status_code=400, detail="start_index must be >= 0")
    if end_index is not None and end_index < 0:
        raise HTTPException(status_code=400, detail="end_index must be >= 0")
    if start_index is not None and end_index is not None and end_index < start_index:
        raise HTTPException(status_code=400, detail="end_index must be >= start_index")
    suffix = export_format.value
    export_path = record.root / f"{dataset_id}-{suffix}.zip"
    _build_dataset_export(record, export_path, start_index, end_index, export_format)
    background_tasks.add_task(export_path.unlink, missing_ok=True)
    return FileResponse(export_path, filename=export_path.name)
