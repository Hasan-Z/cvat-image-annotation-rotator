import { useDatasetStore } from "../store/useDatasetStore";

type HelpModalProps = {
  open: boolean;
  onClose: () => void;
};

const inputFormats = [
  "CVAT XML (Images 1.1)",
  "CVAT App Bundle (Data + annotations.json + task.json)",
  "Pascal VOC",
  "COCO boxes, polygons, and keypoints",
  "YOLO / Ultralytics detection, segmentation, pose, and OBB",
  "LabelMe",
  "Datumaro",
  "Segmentation masks",
  "KITTI",
  "Open Images",
  "Image-only folders (no labels)",
  "Image classification folders (one class folder per label)",
  "Merged multi-ZIP jobs from the upload screen",
];

const exportFormats = [
  "CVAT XML (Images 1.1)",
  "CVAT App Bundle",
  "COCO",
  "YOLO / Ultralytics",
  "Pascal VOC",
  "ModelArts Pascal VOC (flat data folder with images and XML files)",
  "LabelMe",
  "Datumaro",
  "Segmentation masks",
  "KITTI",
  "Open Images",
  "Image Classification (class folders + labels.csv)",
];

export function HelpModal({ open, onClose }: HelpModalProps) {
  const theme = useDatasetStore((state) => state.theme);

  if (!open) return null;

  const cardClass = theme === "light" ? "border-slate-200 bg-slate-50" : "border-slate-800 bg-slate-900/80";
  const headingClass = theme === "light" ? "text-slate-900" : "text-slate-100";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/70 p-4 backdrop-blur-sm">
      <section className={`flex h-[90vh] max-h-[900px] w-full max-w-4xl flex-col overflow-hidden rounded-3xl border shadow-2xl ${theme === "light" ? "border-slate-200 bg-white text-slate-800" : "border-slate-800 bg-slate-950 text-slate-200"}`}>
        <header className={`flex shrink-0 items-center justify-between border-b px-6 py-4 ${theme === "light" ? "border-slate-200 bg-slate-50" : "border-slate-800 bg-slate-900"}`}>
          <div>
            <div className="text-xs font-semibold uppercase tracking-[0.25em] text-indigo-400">Help Center</div>
            <h2 className={`mt-1 text-2xl font-black ${headingClass}`}>Rotate, inspect, save, and export safely</h2>
          </div>
          <button className={`rounded-xl border px-3 py-2 text-sm ${theme === "light" ? "border-slate-300 bg-white hover:bg-slate-100" : "border-slate-700 bg-slate-950 hover:bg-slate-800"}`} onClick={onClose}>
            ✖️ Close
          </button>
        </header>

        <div className="min-h-0 flex-1 space-y-5 overflow-y-scroll p-6 [scrollbar-gutter:stable]">
          <div className="grid gap-5 md:grid-cols-2">
            <section className={`rounded-2xl border p-5 ${cardClass}`}>
              <h3 className={`text-lg font-bold ${headingClass}`}>📥 Supported input formats</h3>
              <ul className="mt-3 space-y-2 text-sm">
                {inputFormats.map((format) => <li key={format}>• {format}</li>)}
              </ul>
            </section>
            <section className={`rounded-2xl border p-5 ${cardClass}`}>
              <h3 className={`text-lg font-bold ${headingClass}`}>📤 Supported export formats</h3>
              <ul className="mt-3 space-y-2 text-sm">
                {exportFormats.map((format) => <li key={format}>• {format}</li>)}
              </ul>
            </section>
          </div>

          <section className={`rounded-2xl border p-5 ${cardClass}`}>
            <h3 className={`text-lg font-bold ${headingClass}`}>🧭 Workflow</h3>
            <ol className="mt-3 grid gap-3 text-sm md:grid-cols-4">
              <li className="rounded-xl border border-indigo-500/20 p-3"><strong>1.</strong> Upload a dataset ZIP/folder or resume a workspace.</li>
              <li className="rounded-xl border border-indigo-500/20 p-3"><strong>2.</strong> Rotate images; annotations transform instantly.</li>
              <li className="rounded-xl border border-indigo-500/20 p-3"><strong>3.</strong> Inspect X/Y overlays and reset dot orientation when needed.</li>
              <li className="rounded-xl border border-indigo-500/20 p-3"><strong>4.</strong> Save the workspace or export all/range images.</li>
            </ol>
          </section>

          <section className={`rounded-2xl border p-5 ${cardClass}`}>
            <h3 className={`text-lg font-bold ${headingClass}`}>🏷️ Image classification</h3>
            <ul className="mt-3 space-y-2 text-sm">
              <li>• Image-only folders with class subfolders are detected as classification datasets.</li>
              <li>• Use the Classification controls above the canvas to set the current image label or apply one label to all images.</li>
              <li>• Image Classification export writes images into class-named folders and includes a labels.csv manifest.</li>
              <li>• Detection/segmentation annotations can still be exported normally; image-level labels are only used by classification-aware exports.</li>
            </ul>
          </section>

          <section className={`rounded-2xl border p-5 ${cardClass}`}>
            <h3 className={`text-lg font-bold ${headingClass}`}>🧬 Merge multiple jobs</h3>
            <ul className="mt-3 space-y-2 text-sm">
              <li>• Use Merge ZIP jobs on the home screen to select multiple exported CVAT/job ZIP files at once.</li>
              <li>• The app prefixes filenames internally by job number, then shows all images together as one merged workspace.</li>
              <li>• Exporting the merged workspace creates one combined dataset in the selected output format.</li>
            </ul>
          </section>

          <section className={`rounded-2xl border p-5 ${cardClass}`}>
            <h3 className={`text-lg font-bold ${headingClass}`}>🧩 Importing back into CVAT</h3>
            <ul className="mt-3 space-y-2 text-sm">
              <li>• Uploading a ZIP as task data in CVAT loads images only; annotations are applied in a second step.</li>
              <li>• After the task images are created, open the task and use <strong>Actions → Upload annotations</strong>.</li>
              <li>• Select the same ZIP again and choose the matching annotation format, such as CVAT for Images 1.1 or Pascal VOC 1.1.</li>
              <li>• Task labels must already exist with the same names. The project/task name itself does not control label matching.</li>
            </ul>
          </section>

          <section className={`rounded-2xl border p-5 ${cardClass}`}>
            <h3 className={`text-lg font-bold ${headingClass}`}>🎯 Coordinate and dot rules</h3>
            <ul className="mt-3 space-y-2 text-sm">
              <li>• Image rotation changes exported image dimensions when needed, for example 800×600 becomes 600×800 after a 90° turn.</li>
              <li>• On-image X/Y labels use the same rotated-image coordinate system as the crosshair cursor.</li>
              <li>• Dot left/right/180 changes annotation orientation metadata without moving the visible box.</li>
              <li>• Reset dot sets the white dot to the visual top edge and exports CVAT rotation as 0 where the format supports it.</li>
              <li>• Formats without rotated-box metadata export the closest supported geometry, usually boxes or polygons.</li>
              <li>• For image-only folders, Apply Rotations writes pending rotations into the app workspace copy. Browsers do not allow overwriting the original local folder directly.</li>
              <li>• Sidebar review panels can find MD5 duplicates and images with no labels; expand a panel, select images, then remove them from export.</li>
            </ul>
          </section>

          <section className={`rounded-2xl border p-5 ${cardClass}`}>
            <h3 className={`text-lg font-bold ${headingClass}`}>⌨️ Keyboard shortcuts</h3>
            <div className="mt-3 grid gap-2 text-sm sm:grid-cols-2 lg:grid-cols-3">
              {["Q — Rotate left", "E — Rotate right", "R — Rotate 180°", "← / → — Navigate images", "Ctrl+S — Save", "D — Delete image", "F — Fit to screen", "+ / − — Zoom"].map((shortcut) => (
                <div key={shortcut} className="rounded-xl border border-slate-500/20 px-3 py-2">{shortcut}</div>
              ))}
              {["Shift+Q — Dot left", "Shift+E — Dot right", "Shift+R — Dot 180°", "Shift+0 — Reset dot"].map((shortcut) => (
                <div key={shortcut} className="rounded-xl border border-indigo-500/20 px-3 py-2">{shortcut}</div>
              ))}
            </div>
          </section>
        </div>
      </section>
    </div>
  );
}
