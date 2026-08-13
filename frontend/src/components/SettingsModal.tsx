import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useDatasetStore } from "../store/useDatasetStore";

type SettingsModalProps = {
  open: boolean;
  onClose: () => void;
};

type AppSettings = {
  resume_folder: string;
  resume_folder_size_bytes: number;
  temp_data_folder: string;
  temp_data_folder_size_bytes: number;
  export_folder: string;
  export_folder_size_bytes: number;
  export_mode: "ask" | "folder";
};

function formatFolderSize(bytes: number | null): string {
  if (bytes === null) return "Calculating...";
  if (bytes <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let value = bytes;
  let unitIndex = 0;
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }
  return `${value >= 10 || unitIndex === 0 ? value.toFixed(0) : value.toFixed(1)} ${units[unitIndex]}`;
}

export function SettingsModal({ open, onClose }: SettingsModalProps) {
  const showInspector = useDatasetStore((state) => state.showInspector);
  const showCoordinateLabels = useDatasetStore((state) => state.showCoordinateLabels);
  const coordinateLabelFontSize = useDatasetStore((state) => state.coordinateLabelFontSize);
  const showCrosshairCursor = useDatasetStore((state) => state.showCrosshairCursor);
  const autoFitOnImageChange = useDatasetStore((state) => state.autoFitOnImageChange);
  const theme = useDatasetStore((state) => state.theme);
  const setShowInspector = useDatasetStore((state) => state.setShowInspector);
  const setShowCoordinateLabels = useDatasetStore((state) => state.setShowCoordinateLabels);
  const setCoordinateLabelFontSize = useDatasetStore((state) => state.setCoordinateLabelFontSize);
  const setShowCrosshairCursor = useDatasetStore((state) => state.setShowCrosshairCursor);
  const setAutoFitOnImageChange = useDatasetStore((state) => state.setAutoFitOnImageChange);
  const loadSavedDatasets = useDatasetStore((state) => state.loadSavedDatasets);
  const pushNotification = useDatasetStore((state) => state.pushNotification);
  const datasetId = useDatasetStore((state) => state.datasetId);
  const [resumeFolder, setResumeFolder] = useState("");
  const [tempDataFolder, setTempDataFolder] = useState("");
  const [exportFolder, setExportFolder] = useState("");
  const [exportMode, setExportMode] = useState<"ask" | "folder">("ask");
  const [resumeFolderSizeBytes, setResumeFolderSizeBytes] = useState<number | null>(null);
  const [tempDataFolderSizeBytes, setTempDataFolderSizeBytes] = useState<number | null>(null);
  const [exportFolderSizeBytes, setExportFolderSizeBytes] = useState<number | null>(null);
  const [savingFolder, setSavingFolder] = useState(false);
  const [browsingFolder, setBrowsingFolder] = useState(false);
  const [browsingTempFolder, setBrowsingTempFolder] = useState(false);
  const [browsingExportFolder, setBrowsingExportFolder] = useState(false);
  const [clearingTempData, setClearingTempData] = useState(false);

  const applySettings = (settings: AppSettings) => {
    setResumeFolder(settings.resume_folder);
    setResumeFolderSizeBytes(settings.resume_folder_size_bytes);
    setTempDataFolder(settings.temp_data_folder);
    setTempDataFolderSizeBytes(settings.temp_data_folder_size_bytes);
    setExportFolder(settings.export_folder);
    setExportFolderSizeBytes(settings.export_folder_size_bytes);
    setExportMode(settings.export_mode);
  };

  useEffect(() => {
    if (!open) return;
    setResumeFolderSizeBytes(null);
    setTempDataFolderSizeBytes(null);
    setExportFolderSizeBytes(null);
    api
      .get<AppSettings>("/api/settings")
      .then((response) => applySettings(response.data))
      .catch((error) => pushNotification("error", "Settings failed", error instanceof Error ? error.message : "Unable to load application settings."));
  }, [open, pushNotification]);

  const saveResumeFolder = async () => {
    if (!resumeFolder.trim() || !tempDataFolder.trim() || !exportFolder.trim()) return;
    setSavingFolder(true);
    try {
      const response = await api.put<AppSettings>("/api/settings", {
        resume_folder: resumeFolder.trim(),
        temp_data_folder: tempDataFolder.trim(),
        export_folder: exportFolder.trim(),
        export_mode: exportMode,
      });
      applySettings(response.data);
      await loadSavedDatasets();
      pushNotification("success", "Storage settings updated", "Resume, temporary-data, and export folder preferences were saved.");
    } catch (error) {
      pushNotification("error", "Folder update failed", error instanceof Error ? error.message : "Unable to update storage folders.");
    } finally {
      setSavingFolder(false);
    }
  };

  const browseResumeFolder = async () => {
    setBrowsingFolder(true);
    try {
      const response = await api.post<AppSettings>("/api/settings/select-resume-folder");
      applySettings(response.data);
      await loadSavedDatasets();
      pushNotification("success", "Resume folder selected", `Saved workspaces will be listed from: ${response.data.resume_folder}`);
    } catch (error) {
      pushNotification("error", "Folder picker failed", error instanceof Error ? error.message : "Unable to open folder picker.");
    } finally {
      setBrowsingFolder(false);
    }
  };

  const browseTempDataFolder = async () => {
    setBrowsingTempFolder(true);
    try {
      const response = await api.post<AppSettings>("/api/settings/select-temp-data-folder");
      applySettings(response.data);
      pushNotification("success", "Temporary folder selected", `Unsaved uploads will use: ${response.data.temp_data_folder}`);
    } catch (error) {
      pushNotification("error", "Folder picker failed", error instanceof Error ? error.message : "Unable to open folder picker.");
    } finally {
      setBrowsingTempFolder(false);
    }
  };

  const clearTempData = async () => {
    if (!window.confirm("Clear all unsaved temporary workspaces? Saved workspaces and completed exports will not be deleted.")) return;
    setClearingTempData(true);
    try {
      const response = await api.delete<{ removed_datasets: string[]; removed_items: number }>("/api/settings/temp-data");
      await loadSavedDatasets();
      const currentDatasetRemoved = Boolean(datasetId && response.data.removed_datasets.includes(datasetId));
      pushNotification(
        "success",
        "Temporary data cleared",
        `${response.data.removed_items} temporary item${response.data.removed_items === 1 ? "" : "s"} removed. Folder sizes were refreshed.`,
      );
      if (currentDatasetRemoved) {
        window.setTimeout(() => window.location.reload(), 500);
      } else {
        const settingsResponse = await api.get<AppSettings>("/api/settings");
        applySettings(settingsResponse.data);
      }
    } catch (error) {
      pushNotification("error", "Cleanup failed", error instanceof Error ? error.message : "Unable to clear temporary data.");
    } finally {
      setClearingTempData(false);
    }
  };

  const browseExportFolder = async () => {
    setBrowsingExportFolder(true);
    try {
      const response = await api.post<AppSettings>("/api/settings/select-export-folder");
      applySettings(response.data);
      pushNotification("success", "Export folder selected", `Folder-mode exports will be saved to: ${response.data.export_folder}`);
    } catch (error) {
      pushNotification("error", "Folder picker failed", error instanceof Error ? error.message : "Unable to open folder picker.");
    } finally {
      setBrowsingExportFolder(false);
    }
  };

  if (!open) {
    return null;
  }

  const calculatingFolderSizes = resumeFolderSizeBytes === null || tempDataFolderSizeBytes === null || exportFolderSizeBytes === null;
  const folderSizeClass = `rounded-full border px-2.5 py-1 text-xs font-semibold ${
    theme === "light" ? "border-slate-200 bg-slate-100 text-slate-700" : "border-slate-700 bg-slate-950 text-slate-300"
  }`;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/75 px-4 py-6 backdrop-blur-sm">
      <div className={`flex h-[90vh] max-h-[900px] w-full max-w-3xl flex-col overflow-hidden rounded-2xl shadow-2xl ${theme === "light" ? "border border-slate-200 bg-white" : "border border-slate-700 bg-slate-900"}`}>
        <div className={`flex shrink-0 items-center justify-between border-b px-6 py-4 ${theme === "light" ? "border-slate-200" : "border-slate-800"}`}>
          <div>
            <div className="text-xs uppercase tracking-[0.24em] text-slate-500">Settings</div>
            <h2 className={`mt-1 text-xl font-semibold ${theme === "light" ? "text-slate-900" : "text-slate-50"}`}>Editor, storage, and export preferences</h2>
          </div>
          <button className={`rounded-md px-3 py-2 text-sm ${theme === "light" ? "text-slate-600 hover:bg-slate-100 hover:text-slate-900" : "text-slate-300 hover:bg-slate-800 hover:text-white"}`} onClick={onClose}>
            ✖️ Close
          </button>
        </div>

        <div className="min-h-0 flex-1 overflow-y-scroll overscroll-contain p-6 [scrollbar-gutter:stable]">
          <section className={`space-y-4 rounded-xl border p-4 ${theme === "light" ? "border-slate-200 bg-slate-50" : "border-slate-800 bg-slate-950/70"}`}>
            {calculatingFolderSizes ? (
              <div className={`flex items-center gap-3 rounded-xl border px-4 py-3 text-sm ${theme === "light" ? "border-indigo-200 bg-indigo-50 text-indigo-800" : "border-indigo-900/70 bg-indigo-950/40 text-indigo-100"}`}>
                <span className="h-2.5 w-2.5 animate-pulse rounded-full bg-indigo-500" />
                <span>Calculating folder sizes… large folders can take a moment.</span>
              </div>
            ) : null}
            <div>
              <h3 className={`text-base font-semibold ${theme === "light" ? "text-slate-900" : "text-slate-100"}`}>View</h3>
              <p className="mt-1 text-sm text-slate-400">Tune canvas overlays, fit behavior, storage locations, and export destinations.</p>
            </div>
            <button className={`rounded-lg border px-3 py-2 text-left text-sm ${theme === "light" ? "border-slate-200 bg-white text-slate-800" : "border-slate-800 bg-slate-900/80 text-slate-100"}`}>
              🎨 Theme is controlled from the top toolbar.
            </button>
            <label className={`flex cursor-pointer items-start gap-3 rounded-lg border p-3 ${theme === "light" ? "border-slate-200 bg-white" : "border-slate-800 bg-slate-900/80"}`}>
              <input
                type="checkbox"
                className="mt-1 h-4 w-4 rounded border-slate-600 bg-slate-800 text-indigo-500"
                checked={showInspector}
                onChange={(event) => setShowInspector(event.target.checked)}
              />
              <span>
                <span className={`block font-medium ${theme === "light" ? "text-slate-900" : "text-slate-100"}`}>Show rotation inspector</span>
                <span className="mt-1 block text-sm text-slate-400">Shows original geometry, export geometry, on-image X/Y, dot rule, and label color beside the canvas.</span>
              </span>
            </label>
            <div className={`rounded-lg border p-3 ${theme === "light" ? "border-slate-200 bg-white" : "border-slate-800 bg-slate-900/80"}`}>
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className={`font-medium ${theme === "light" ? "text-slate-900" : "text-slate-100"}`}>Label X/Y font size</div>
                  <div className="mt-1 text-sm text-slate-400">Controls the X1/Y1 and X2/Y2 coordinate overlay size on the image.</div>
                </div>
                <input
                  className={`w-20 rounded-lg border px-3 py-2 text-sm ${
                    theme === "light" ? "border-slate-300 bg-white text-slate-900" : "border-slate-700 bg-slate-950 text-slate-100"
                  }`}
                  type="number"
                  min={3}
                  max={24}
                  step={0.5}
                  value={coordinateLabelFontSize}
                  onChange={(event) => setCoordinateLabelFontSize(Number(event.target.value))}
                  title="Label X/Y font size"
                />
              </div>
              <input
                className="mt-3 w-full accent-indigo-500"
                type="range"
                min={3}
                max={24}
                step={0.5}
                value={coordinateLabelFontSize}
                onChange={(event) => setCoordinateLabelFontSize(Number(event.target.value))}
              />
            </div>
            <label className={`flex cursor-pointer items-start gap-3 rounded-lg border p-3 ${theme === "light" ? "border-slate-200 bg-white" : "border-slate-800 bg-slate-900/80"}`}>
              <input
                type="checkbox"
                className="mt-1 h-4 w-4 rounded border-slate-600 bg-slate-800 text-indigo-500"
                checked={showCoordinateLabels}
                onChange={(event) => setShowCoordinateLabels(event.target.checked)}
              />
              <span>
                <span className={`block font-medium ${theme === "light" ? "text-slate-900" : "text-slate-100"}`}>Show label X/Y positions</span>
                <span className="mt-1 block text-sm text-slate-400">Draws each label name plus X1/Y1 and X2/Y2 at their current rotated-image corners.</span>
              </span>
            </label>
            <label className={`flex cursor-pointer items-start gap-3 rounded-lg border p-3 ${theme === "light" ? "border-slate-200 bg-white" : "border-slate-800 bg-slate-900/80"}`}>
              <input
                type="checkbox"
                className="mt-1 h-4 w-4 rounded border-slate-600 bg-slate-800 text-indigo-500"
                checked={showCrosshairCursor}
                onChange={(event) => setShowCrosshairCursor(event.target.checked)}
              />
              <span>
                <span className={`block font-medium ${theme === "light" ? "text-slate-900" : "text-slate-100"}`}>Show crosshair cursor</span>
                <span className="mt-1 block text-sm text-slate-400">Displays vertical and horizontal guide lines with live rotated-image X/Y coordinates under the mouse.</span>
              </span>
            </label>
            <label className={`flex cursor-pointer items-start gap-3 rounded-lg border p-3 ${theme === "light" ? "border-slate-200 bg-white" : "border-slate-800 bg-slate-900/80"}`}>
              <input
                type="checkbox"
                className="mt-1 h-4 w-4 rounded border-slate-600 bg-slate-800 text-indigo-500"
                checked={autoFitOnImageChange}
                onChange={(event) => setAutoFitOnImageChange(event.target.checked)}
              />
              <span>
                <span className={`block font-medium ${theme === "light" ? "text-slate-900" : "text-slate-100"}`}>Auto-fit on image change</span>
                <span className="mt-1 block text-sm text-slate-400">Fits the current image after navigation and image rotation.</span>
              </span>
            </label>
            <div className={`rounded-xl border p-4 ${theme === "light" ? "border-slate-200 bg-white" : "border-slate-800 bg-slate-900/80"}`}>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className={`font-medium ${theme === "light" ? "text-slate-900" : "text-slate-100"}`}>Resume workspace folder</div>
                <span className={folderSizeClass}>Size: {formatFolderSize(resumeFolderSizeBytes)}</span>
              </div>
              <p className="mt-1 text-sm text-slate-400">
                Saved workspaces are stored on disk here. The Windows default is <code>%USERPROFILE%\Documents</code>.
              </p>
              <div className="mt-3 flex flex-col gap-2 sm:flex-row">
                <input
                  className={`min-w-0 flex-1 rounded-lg border px-3 py-2 text-sm ${
                    theme === "light" ? "border-slate-300 bg-white text-slate-900" : "border-slate-700 bg-slate-950 text-slate-100"
                  }`}
                  value={resumeFolder}
                  onChange={(event) => setResumeFolder(event.target.value)}
                  placeholder="C:\\Users\\YourName\\Documents"
                  title="Resume workspace folder"
                />
                <button
                  className={`rounded-lg border px-4 py-2 text-sm font-semibold transition disabled:opacity-60 ${
                    theme === "light" ? "border-slate-300 bg-white text-slate-700 hover:bg-slate-100" : "border-slate-700 bg-slate-950 text-slate-200 hover:bg-slate-800"
                  }`}
                  disabled={browsingFolder || savingFolder}
                  onClick={browseResumeFolder}
                  title="Open Windows folder picker"
                >
                  📂 {browsingFolder ? "Opening..." : "Browse..."}
                </button>
                <button
                  className={`rounded-lg border px-4 py-2 text-sm font-semibold transition disabled:opacity-60 ${
                    theme === "light" ? "border-indigo-300 bg-indigo-50 text-indigo-800 hover:bg-indigo-100" : "border-indigo-700 bg-indigo-950 text-indigo-100 hover:bg-indigo-900"
                  }`}
                  disabled={savingFolder || browsingFolder || !resumeFolder.trim()}
                  onClick={saveResumeFolder}
                >
                  💾 {savingFolder ? "Applying..." : "Apply resume folder"}
                </button>
              </div>
              <p className="mt-2 text-xs text-slate-500">Changing this folder reloads the saved-workspace list from the selected location.</p>
            </div>
            <div className={`rounded-xl border p-4 ${theme === "light" ? "border-slate-200 bg-white" : "border-slate-800 bg-slate-900/80"}`}>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className={`font-medium ${theme === "light" ? "text-slate-900" : "text-slate-100"}`}>Export destination</div>
                <span className={folderSizeClass}>Size: {formatFolderSize(exportFolderSizeBytes)}</span>
              </div>
              <p className="mt-1 text-sm text-slate-400">Choose whether exports download through the browser or save automatically to a default folder.</p>
              <div className="mt-3 grid gap-2 sm:grid-cols-2">
                <label className={`flex cursor-pointer items-center gap-3 rounded-lg border p-3 ${theme === "light" ? "border-slate-200 bg-slate-50" : "border-slate-800 bg-slate-950"}`}>
                  <input type="radio" name="export-mode" checked={exportMode === "ask"} onChange={() => setExportMode("ask")} />
                  <span className="text-sm">Ask where to save</span>
                </label>
                <label className={`flex cursor-pointer items-center gap-3 rounded-lg border p-3 ${theme === "light" ? "border-slate-200 bg-slate-50" : "border-slate-800 bg-slate-950"}`}>
                  <input type="radio" name="export-mode" checked={exportMode === "folder"} onChange={() => setExportMode("folder")} />
                  <span className="text-sm">Save to default export folder</span>
                </label>
              </div>
              <div className="mt-3 flex flex-col gap-2 sm:flex-row">
                <input
                  className={`min-w-0 flex-1 rounded-lg border px-3 py-2 text-sm ${
                    theme === "light" ? "border-slate-300 bg-white text-slate-900" : "border-slate-700 bg-slate-950 text-slate-100"
                  }`}
                  value={exportFolder}
                  onChange={(event) => setExportFolder(event.target.value)}
                  placeholder="C:\\Users\\YourName\\Documents"
                  title="Default export folder"
                />
                <button
                  className={`rounded-lg border px-4 py-2 text-sm font-semibold transition disabled:opacity-60 ${
                    theme === "light" ? "border-slate-300 bg-white text-slate-700 hover:bg-slate-100" : "border-slate-700 bg-slate-950 text-slate-200 hover:bg-slate-800"
                  }`}
                  disabled={browsingExportFolder || savingFolder}
                  onClick={browseExportFolder}
                  title="Open Windows folder picker"
                >
                  📂 {browsingExportFolder ? "Opening..." : "Browse..."}
                </button>
              </div>
              <button
                className={`mt-3 rounded-lg border px-4 py-2 text-sm font-semibold transition disabled:opacity-60 ${
                  theme === "light" ? "border-indigo-300 bg-indigo-50 text-indigo-800 hover:bg-indigo-100" : "border-indigo-700 bg-indigo-950 text-indigo-100 hover:bg-indigo-900"
                }`}
                disabled={savingFolder || !resumeFolder.trim() || !tempDataFolder.trim() || !exportFolder.trim()}
                onClick={saveResumeFolder}
              >
                💾 {savingFolder ? "Applying..." : "Apply export destination"}
              </button>
            </div>
            <div className={`rounded-xl border p-4 ${theme === "light" ? "border-amber-200 bg-amber-50/60" : "border-amber-900/70 bg-amber-950/20"}`}>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className={`font-medium ${theme === "light" ? "text-slate-900" : "text-slate-100"}`}>Temporary data folder</div>
                <span className={folderSizeClass}>Size: {formatFolderSize(tempDataFolderSizeBytes)}</span>
              </div>
              <p className="mt-1 text-sm text-slate-400">
                Uploaded archives and extracted unsaved workspaces are kept here until you save, export, discard, or clear them. The default is <code>%TEMP%\cvat-dataset-rotation-tool</code>.
              </p>
              <div className="mt-3 flex flex-col gap-2 sm:flex-row">
                <input
                  className={`min-w-0 flex-1 rounded-lg border px-3 py-2 text-sm ${
                    theme === "light" ? "border-slate-300 bg-white text-slate-900" : "border-slate-700 bg-slate-950 text-slate-100"
                  }`}
                  value={tempDataFolder}
                  onChange={(event) => setTempDataFolder(event.target.value)}
                  placeholder="%TEMP%\\cvat-dataset-rotation-tool"
                  title="Temporary data folder"
                />
                <button
                  className={`rounded-lg border px-4 py-2 text-sm font-semibold transition disabled:opacity-60 ${
                    theme === "light" ? "border-slate-300 bg-white text-slate-700 hover:bg-slate-100" : "border-slate-700 bg-slate-950 text-slate-200 hover:bg-slate-800"
                  }`}
                  disabled={browsingTempFolder || savingFolder}
                  onClick={browseTempDataFolder}
                  title="Open Windows folder picker"
                >
                  📂 {browsingTempFolder ? "Opening..." : "Browse..."}
                </button>
                <button
                  className={`rounded-lg border px-4 py-2 text-sm font-semibold transition disabled:opacity-60 ${
                    theme === "light" ? "border-rose-300 bg-rose-50 text-rose-800 hover:bg-rose-100" : "border-rose-800 bg-rose-950/60 text-rose-100 hover:bg-rose-900"
                  }`}
                  disabled={clearingTempData}
                  onClick={clearTempData}
                  title="Delete all unsaved temporary working data"
                >
                  🧹 {clearingTempData ? "Clearing..." : "Clear temporary data"}
                </button>
                <button
                  className={`rounded-lg border px-4 py-2 text-sm font-semibold transition disabled:opacity-60 ${
                    theme === "light" ? "border-indigo-300 bg-indigo-50 text-indigo-800 hover:bg-indigo-100" : "border-indigo-700 bg-indigo-950 text-indigo-100 hover:bg-indigo-900"
                  }`}
                  disabled={savingFolder || !tempDataFolder.trim()}
                  onClick={saveResumeFolder}
                >
                  💾 {savingFolder ? "Applying..." : "Apply temp folder"}
                </button>
              </div>
              <p className="mt-2 text-xs text-slate-500">Cleanup never deletes saved workspaces from the resume folder or completed exports.</p>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
