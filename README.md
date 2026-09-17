# CVAT Dataset Rotation Tool

A full-stack editor for correcting rotated images in annotated computer-vision datasets. Rotate images visually, transform annotations into the rotated coordinate system, inspect X/Y overlays and CVAT white-dot orientation, save resumable workspaces, and export a corrected dataset.

## Features

- Automatic dataset-format detection
- Image rotation by 90° left, 90° right, or 180°
- Annotation coordinate and orientation updates
- Rectangles, rotated rectangles, polygons, polylines, points, ellipses, masks, skeletons, and cuboids
- Zoom, pan, fit-to-screen, thumbnails, label filtering, and rotation inspection
- On-image X/Y overlays and crosshair coordinate inspection
- Annotation white-dot orientation controls with keyboard shortcuts
- MD5 duplicate-image detection with selectable duplicate removal
- Collapsible sidebar cleanup panels for duplicate and no-label images
- Full-dataset or selected-range export
- Saved resumable workspaces
- Configurable resume, temporary-data, and export folders
- Folder-size display and temporary-data cleanup
- Dark and light themes
- ZIP or extracted-folder upload
- Multi-ZIP job merge into one workspace
- Image classification labels with one-click apply-to-all
- Upload, processing, save, and export status messages

## Supported Formats

The application detects supported input formats from files inside the uploaded ZIP or selected folder.

| Format | Import | Export |
| --- | --- | --- |
| CVAT for Images 1.1 XML | Yes | Yes |
| CVAT task backup / App Bundle | Yes | Yes |
| COCO | Yes | Yes |
| YOLO | Yes | Yes |
| Pascal VOC | Yes | Yes |
| LabelMe | Yes | Yes |
| Datumaro | Yes | Yes |
| Segmentation masks | Yes | Yes |
| KITTI | Yes | Yes |
| Open Images | Yes | Yes |
| Image-only folder | Yes | Export as selected format |
| Image classification folders | Yes | Yes |
| Merged multi-ZIP jobs | Yes | Export as selected format |

Some formats store only axis-aligned bounding boxes. Those formats cannot preserve CVAT-specific rotated-box orientation metadata exactly.

## Requirements

- Python 3.11 or newer
- Node.js 20.19+ or 22.12+
- npm
- Chrome or another modern browser
- Docker Desktop, optional

## Quick Start — Windows

The launcher creates `.venv` when needed, installs missing dependencies, starts backend and frontend terminals, and opens Chrome.

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\start-dev.ps1
```

Open `http://localhost:5173` if the browser does not open automatically.

## Manual Installation

### Windows

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"

cd frontend
npm install
cd ..
```

Run the backend:

```powershell
.\.venv\Scripts\Activate.ps1
uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

Run the frontend in a second terminal:

```powershell
cd frontend
npm run dev -- --port 5173
```

### Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[dev]"

cd frontend
npm install
npm run dev -- --port 5173
```

In a second terminal:

```bash
source .venv/bin/activate
uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

### macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[dev]"

cd frontend
npm install
npm run dev -- --port 5173
```

In a second terminal:

```bash
source .venv/bin/activate
uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

## Docker

```bash
docker compose up --build
```

Open `http://localhost:8000`. Docker stores resumable workspaces, temporary files, and exports under the local `storage/` directory.

## How to Use

1. Click **Choose dataset ZIP** or **Choose dataset folder** and upload a supported dataset.
   - Use **Merge ZIP jobs** to select multiple exported job/task ZIP files and load them as one combined workspace.
2. Select an image from the thumbnail browser.
3. Rotate the image with the left toolbar or keyboard.
4. Inspect export geometry, on-image X/Y, crosshair coordinates, and annotation-dot direction.
5. Use **Dot left/right/180** or **Reset dot** when only the white-dot orientation should change.
6. For image classification, set the current image label or apply one label to every non-deleted image.
7. Click **Save** to persist a resumable workspace.
8. Select an export format and optional image range.
9. Click **Export Dataset** or **Export Range**.

Example: rotating an 800×600 image 90° right produces a 600×800 image. Annotation coordinates are transformed into that new coordinate system, and supported orientation metadata is updated.

## Coordinate and Export Semantics

- **Original coordinates** are the annotation values from the uploaded dataset before any webapp edits.
- **Export geometry** is the backend geometry that will be written after image rotation is applied.
- **On-image X/Y** is the visual coordinate overlay shown on the canvas; it uses the same rotated image coordinate system as the crosshair cursor.
- **Annotation direction dot** follows annotation orientation. For CVAT formats this is stored as the rectangle `rotation` value.
- **Dot left/right/180** changes annotation orientation metadata without moving the visible box.
- **Reset Dot** moves the direction dot back to the visual top edge and exports `rotation=0` for CVAT-compatible rotated-box formats without moving the visible box.
- **Apply Rotations** is available for image-only folders. It writes pending image rotations into the app workspace copy and resets image rotation to `0°`; browsers cannot overwrite the original local folder directly.
- **Duplicate and no-label cleanup** is available from the thumbnail sidebar. The panels are collapsed by default so large duplicate groups do not hide the main thumbnail list.
- **Formats without rotated-box metadata** export the best supported geometry for that format, usually an axis-aligned bounding box or polygon points.
- **Image Classification export** writes images into class-name folders and includes `labels.csv`.
- **Merged ZIP jobs** are internally prefixed by job number to avoid filename collisions, then exported as a single combined dataset.

## Keyboard Shortcuts

| Key | Action |
| --- | --- |
| `Q` | Rotate 90° left |
| `E` | Rotate 90° right |
| `R` | Rotate 180° |
| `Left Arrow` | Previous image |
| `Right Arrow` | Next image |
| `Ctrl+S` | Save workspace |
| `D` | Delete current image |
| `F` | Fit image to screen |
| `+` | Zoom in |
| `-` | Zoom out |
| `Shift+Q` | Rotate selected/all annotation dots left |
| `Shift+E` | Rotate selected/all annotation dots right |
| `Shift+R` | Rotate selected/all annotation dots 180° |
| `Shift+0` | Reset selected/all annotation dots |

## Storage

Storage locations are configurable from **Settings**:

- **Resume folder:** saved workspaces; defaults to `%USERPROFILE%\Documents` on Windows.
- **Temporary data folder:** uploaded ZIP/folder files and extracted unsaved workspaces; defaults to `%TEMP%\cvat-dataset-rotation-tool`.
- **Export folder:** automatic export destination when folder mode is enabled.

Settings shows the current size of each folder. Large folders may take a moment to calculate.

The **Clear temporary data** button removes only unsaved working data inside the configured application temp folder. It does not delete saved workspaces or exports.

## API

FastAPI documentation is available while the backend is running:

- Swagger UI: `http://127.0.0.1:8000/docs`
- OpenAPI JSON: `http://127.0.0.1:8000/openapi.json`

Main endpoints:

- `POST /api/upload`
- `POST /api/upload-multiple`
- `POST /api/upload-folder`
- `GET /api/datasets`
- `GET /api/dataset/{id}/image/{index}`
- `POST /api/dataset/{id}/rotate`
- `POST /api/dataset/{id}/save`
- `POST /api/dataset/{id}/classification-label`
- `GET /api/dataset/{id}/download`
- `GET /api/settings`
- `PUT /api/settings`
- `DELETE /api/settings/temp-data`

## Testing

Backend tests:

```powershell
.\.venv\Scripts\python.exe -m pytest -q --basetemp .tmp\pytest
```

Frontend type check and production build:

```powershell
cd frontend
npm exec tsc -- --noEmit
npm run build
```

## Project Structure

```text
backend/
  api/ geometry/ exporters/ models/ parsers/ services/ utils/
frontend/
  src/api/ components/ hooks/ pages/ store/ types/
tests/
examples/
Dockerfile
docker-compose.yml
start-dev.ps1
```

## Security

- ZIP paths are validated to prevent zip-slip extraction.
- Upload size limits are enforced.
- Every dataset receives an isolated working directory.
- Temporary cleanup is restricted to the configured application temp folder.
- Avoid exposing the development server directly to the public internet.

## Contributing

1. Create a feature branch.
2. Keep changes focused and typed.
3. Add or update tests.
4. Run backend tests and the frontend build.
5. Open a pull request describing behavior and format compatibility.

## License

This project is licensed under the MIT License. See `LICENSE`.
