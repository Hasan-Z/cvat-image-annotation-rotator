from pathlib import Path
import json
import tempfile

from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_resume_dir() -> Path:
    documents = Path.home() / "Documents"
    return documents if documents.exists() else Path.home()


def _default_temp_dir() -> Path:
    return Path(tempfile.gettempdir()) / "cvat-dataset-rotation-tool"


def _paths_overlap(first: Path, second: Path) -> bool:
    first = first.resolve()
    second = second.resolve()
    try:
        first.relative_to(second)
        return True
    except ValueError:
        pass
    try:
        second.relative_to(first)
        return True
    except ValueError:
        return False


PREFERENCES_PATH = Path.home() / ".cvat_dataset_rotation_tool.json"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CVAT_ROTATOR_", extra="ignore")

    app_name: str = "CVAT Dataset Rotation Tool"
    cors_origins: list[str] = ["http://localhost:5173"]
    data_dir: Path = _default_resume_dir()
    temp_data_dir: Path = _default_temp_dir()
    export_dir: Path = _default_resume_dir()
    export_mode: str = "ask"
    max_upload_mb: int = 20_000
    thumbnail_size: int = 256


settings = Settings()


def load_saved_preferences() -> None:
    if not PREFERENCES_PATH.exists():
        return
    try:
        payload = json.loads(PREFERENCES_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    data_dir = payload.get("data_dir")
    if isinstance(data_dir, str) and data_dir.strip():
        settings.data_dir = Path(data_dir).expanduser()
    temp_data_dir = payload.get("temp_data_dir")
    if isinstance(temp_data_dir, str) and temp_data_dir.strip():
        settings.temp_data_dir = Path(temp_data_dir).expanduser()
    export_dir = payload.get("export_dir")
    if isinstance(export_dir, str) and export_dir.strip():
        settings.export_dir = Path(export_dir).expanduser()
    export_mode = payload.get("export_mode")
    if export_mode in {"ask", "folder"}:
        settings.export_mode = export_mode
    if _paths_overlap(settings.temp_data_dir, settings.data_dir) or _paths_overlap(
        settings.temp_data_dir,
        settings.export_dir,
    ):
        settings.temp_data_dir = _default_temp_dir()


def _write_preferences() -> None:
    PREFERENCES_PATH.write_text(
        json.dumps(
            {
                "data_dir": str(settings.data_dir),
                "temp_data_dir": str(settings.temp_data_dir),
                "export_dir": str(settings.export_dir),
                "export_mode": settings.export_mode,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def set_resume_folder(path: str | Path) -> Path:
    resolved = Path(path).expanduser().resolve()
    resolved.mkdir(parents=True, exist_ok=True)
    settings.data_dir = resolved
    _write_preferences()
    return resolved


def set_temp_data_folder(path: str | Path) -> Path:
    resolved = Path(path).expanduser().resolve()
    drive_root = Path(resolved.anchor).resolve()
    if resolved in {drive_root, Path.home().resolve()}:
        raise ValueError("Choose a dedicated application subfolder, not a drive root or home folder")
    if _paths_overlap(resolved, settings.data_dir) or _paths_overlap(resolved, settings.export_dir):
        raise ValueError("Temporary data folder must differ from resume and export folders")
    resolved.mkdir(parents=True, exist_ok=True)
    settings.temp_data_dir = resolved
    _write_preferences()
    return resolved


def set_export_preferences(folder: str | Path | None = None, mode: str | None = None) -> tuple[Path, str]:
    if folder is not None:
        resolved = Path(folder).expanduser().resolve()
        resolved.mkdir(parents=True, exist_ok=True)
        settings.export_dir = resolved
    if mode is not None:
        if mode not in {"ask", "folder"}:
            raise ValueError("export mode must be 'ask' or 'folder'")
        settings.export_mode = mode
    _write_preferences()
    return settings.export_dir, settings.export_mode


load_saved_preferences()
settings.data_dir.mkdir(parents=True, exist_ok=True)
settings.temp_data_dir.mkdir(parents=True, exist_ok=True)
settings.export_dir.mkdir(parents=True, exist_ok=True)
