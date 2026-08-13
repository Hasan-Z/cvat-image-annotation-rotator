import { useState } from "react";
import { useDatasetStore } from "../store/useDatasetStore";

type ExportFormat =
  | "app_bundle"
  | "cvat_for_images_1_1"
  | "cvat_for_images_1_1_image_paths"
  | "coco"
  | "yolo"
  | "pascal_voc"
  | "modelarts_pascal_voc"
  | "labelme"
  | "datumaro"
  | "segmentation_mask"
  | "kitti"
  | "open_images"
  | "image_classification";

type ToolbarProps = {
  datasetLoaded: boolean;
  onOpenSettings: () => void;
  onOpenAbout: () => void;
  onOpenHelp: () => void;
  onOpenLog: () => void;
  onStartOver: () => void;
};

export function Toolbar({ datasetLoaded, onOpenSettings, onOpenAbout, onOpenHelp, onOpenLog, onStartOver }: ToolbarProps) {
  const saveDataset = useDatasetStore((state) => state.saveDataset);
  const exportDataset = useDatasetStore((state) => state.exportDataset);
  const applyImageRotations = useDatasetStore((state) => state.applyImageRotations);
  const applySourceChanges = useDatasetStore((state) => state.applySourceChanges);
  const toggleTheme = useDatasetStore((state) => state.toggleTheme);
  const datasetId = useDatasetStore((state) => state.datasetId);
  const datasetFormat = useDatasetStore((state) => state.datasetFormat);
  const editableSource = useDatasetStore((state) => state.editableSource);
  const sourceFolder = useDatasetStore((state) => state.sourceFolder);
  const theme = useDatasetStore((state) => state.theme);
  const [startIndex, setStartIndex] = useState<string>("");
  const [endIndex, setEndIndex] = useState<string>("");
  const [exportFormat, setExportFormat] = useState<ExportFormat>("cvat_for_images_1_1");

  const shellClass =
    theme === "light"
      ? "border-b border-slate-200 bg-white/90 text-slate-900 shadow-sm backdrop-blur"
      : "border-b border-slate-800 bg-slate-950/80 text-slate-100 shadow-2xl shadow-black/20 backdrop-blur";
  const inputClass = theme === "light" ? "h-8 w-20 rounded-lg border border-slate-300 bg-white px-2 text-xs text-slate-900" : "h-8 w-20 rounded-lg border border-slate-700 bg-slate-800 px-2 text-xs text-slate-100";
  const baseButton = "inline-flex h-8 items-center justify-center gap-1.5 rounded-lg px-2.5 text-xs font-semibold leading-none transition shadow-sm";
  const neutralButton =
    theme === "light"
      ? `${baseButton} border border-slate-300 bg-white text-slate-700 hover:border-slate-400 hover:bg-slate-50`
      : `${baseButton} border border-slate-700 bg-slate-900 text-slate-100 hover:border-slate-600 hover:bg-slate-800`;
  const actionButton =
    theme === "light"
      ? `${baseButton} border border-emerald-300 bg-emerald-50 text-emerald-800 hover:bg-emerald-100`
      : `${baseButton} border border-emerald-600 bg-emerald-700 text-white hover:bg-emerald-600`;
  const saveButton =
    theme === "light"
      ? `${baseButton} border border-indigo-300 bg-indigo-50 text-indigo-800 hover:bg-indigo-100`
      : `${baseButton} border border-indigo-600 bg-indigo-700 text-white hover:bg-indigo-600`;
  const selectClass = theme === "light" ? "h-8 rounded-lg border border-slate-300 bg-white px-2 text-xs text-slate-900" : "h-8 rounded-lg border border-slate-600 bg-slate-800 px-2 text-xs text-slate-100";

  return (
    <div className={`flex max-h-[34vh] flex-wrap items-center gap-2 overflow-y-auto px-4 py-2 ${shellClass}`}>
      <div className="mr-2 min-w-[240px]">
        <div className="flex items-center gap-2">
          <span className="rounded-lg bg-indigo-500 px-2 py-1 text-xs font-black text-white shadow-lg shadow-indigo-500/30">CVAT</span>
          <span className="text-base font-bold tracking-tight">Dataset Rotation Tool</span>
        </div>
        <div className={`mt-0.5 text-xs ${theme === "light" ? "text-slate-500" : "text-slate-400"}`}>Correct rotation, inspect coordinates, export clean datasets.</div>
      </div>
      <button className={neutralButton} title="Toggle dark/light mode" onClick={() => toggleTheme()}>
        {theme === "dark" ? "☀️ Light Mode" : "🌙 Dark Mode"}
      </button>
      <button className={neutralButton} title="Open settings" onClick={onOpenSettings}>
        ⚙️ Settings
      </button>
      <button className={neutralButton} title="About this project" onClick={onOpenAbout}>
        ℹ️ About
      </button>
      <button className={neutralButton} title="Open help and usage guide" onClick={onOpenHelp}>
        ❓ Help
      </button>
      <button className={neutralButton} title="Open activity and status log" onClick={onOpenLog}>
        📋 Logs
      </button>
      {datasetLoaded ? (
        <button className={neutralButton} title="Save, export, or discard this workspace and return to upload" onClick={onStartOver}>
          🔁 Start Over
        </button>
      ) : null}
      {datasetId ? (
        <div className={`ml-auto flex flex-wrap items-center gap-2 rounded-xl border px-2 py-1.5 ${theme === "light" ? "border-slate-300 bg-slate-50/90" : "border-slate-700 bg-slate-950/90"}`}>
          <span className={`text-xs uppercase tracking-wide ${theme === "light" ? "text-slate-500" : "text-slate-400"}`}>Export format</span>
          <select
            className={selectClass}
            title="Choose the export format for full and range exports"
            value={exportFormat}
            onChange={(event) => setExportFormat(event.target.value as ExportFormat)}
          >
            <option value="cvat_for_images_1_1">CVAT for images 1.1</option>
            <option value="cvat_for_images_1_1_image_paths">CVAT for images 1.1 (image path names)</option>
            <option value="coco">COCO</option>
            <option value="yolo">YOLO / Ultralytics</option>
            <option value="pascal_voc">Pascal VOC</option>
            <option value="modelarts_pascal_voc">ModelArts Pascal VOC</option>
            <option value="labelme">LabelMe</option>
            <option value="datumaro">Datumaro</option>
            <option value="segmentation_mask">Segmentation Mask</option>
            <option value="kitti">KITTI</option>
            <option value="open_images">Open Images</option>
            <option value="image_classification">Image Classification</option>
            <option value="app_bundle">App bundle</option>
          </select>
          {datasetLoaded ? (
            <button className={saveButton} title="Save current workspace for later resume (Ctrl+S)" onClick={() => saveDataset()}>
              💾 Save
            </button>
          ) : null}
          {datasetFormat === "image_folder" ? (
            <button
              className={saveButton}
              title="Apply pending rotations to the uploaded workspace image files. This updates the app copy, not your original local folder."
              onClick={() => applyImageRotations()}
            >
              💽 Apply Rotations
            </button>
          ) : null}
          {editableSource && (datasetFormat === "pascal_voc" || datasetFormat === "image_folder") ? (
            <button
              className={saveButton}
              title={`Back up and overwrite rotated source files in ${sourceFolder ?? "the selected source folder"}`}
              onClick={() => {
                const confirmed = window.confirm(
                  `Apply pending rotations directly to the original source folder?\n\nA backup ZIP will be created first.\n\n${sourceFolder ?? ""}`,
                );
                if (confirmed) void applySourceChanges();
              }}
            >
              🧰 Apply to Source
            </button>
          ) : null}
          <button className={actionButton} title={`Export the full dataset as ${exportFormat}`} onClick={() => exportDataset(null, null, exportFormat)}>
            📦 Export Dataset
          </button>
          <div className={`h-5 w-px ${theme === "light" ? "bg-slate-300" : "bg-slate-700"}`} />
          <span className={`text-xs uppercase tracking-wide ${theme === "light" ? "text-slate-500" : "text-slate-400"}`}>Export range</span>
            <input
              className={inputClass}
              type="number"
              min="0"
              placeholder="Start"
              value={startIndex}
              onChange={(event) => setStartIndex(event.target.value)}
            />
            <input
              className={inputClass}
              type="number"
              min="0"
              placeholder="End"
              value={endIndex}
              onChange={(event) => setEndIndex(event.target.value)}
            />
            <button
              className={theme === "light" ? `${baseButton} border border-emerald-300 bg-emerald-50 text-emerald-800 hover:bg-emerald-100` : `${baseButton} border border-emerald-600 bg-emerald-600 text-white hover:bg-emerald-500`}
              title={`Export only the selected image range as ${exportFormat}`}
              onClick={() =>
                exportDataset(
                  startIndex === "" ? null : Number(startIndex),
                  endIndex === "" ? null : Number(endIndex),
                  exportFormat,
                )
              }
            >
              📤 Export Range
            </button>
        </div>
      ) : null}
    </div>
  );
}
