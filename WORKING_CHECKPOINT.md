# Working Checkpoint — 2026-06-22

This checkpoint marks the state where dataset upload, image rotation, annotation rotation, reset-dot behavior, and CVAT XML export were verified working.

Key verified behaviors:

- Frontend proxy uses `127.0.0.1:8000` and uploads work through Vite.
- `Reset dot` keeps the displayed box geometry stable, moves the white dot to the upper edge, and exports CVAT XML with rotation value `0`.
- CVAT XML export uses preserved visual geometry for reset-dot boxes so exported boxes do not rotate unexpectedly.
- Dot left/right/180 controls rotate annotation direction and clear reset-dot state.
- Unsaved uploads use `%TEMP%\cvat-dataset-rotation-tool` by default.
- Save moves working datasets into the configured resume folder.
- Clear temp data preserves saved sessions and completed exports.
- All supported parser and exporter regression tests pass.

Verification commands:

```powershell
.\.venv\Scripts\python.exe -m pytest -q --basetemp .tmp\pytest-full
cd frontend
npm exec tsc -- --noEmit
npm run build
```
