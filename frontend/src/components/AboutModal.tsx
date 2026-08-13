import { useDatasetStore } from "../store/useDatasetStore";

type AboutModalProps = {
  open: boolean;
  onClose: () => void;
};

export function AboutModal({ open, onClose }: AboutModalProps) {
  const theme = useDatasetStore((state) => state.theme);

  if (!open) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/75 px-4 py-6 backdrop-blur-sm">
      <div className={`w-full max-w-2xl overflow-hidden rounded-2xl shadow-2xl ${theme === "light" ? "border border-slate-200 bg-slate-50" : "border border-slate-700 bg-slate-900"}`}>
        <div className={`flex items-center justify-between border-b px-6 py-4 ${theme === "light" ? "border-slate-200" : "border-slate-800"}`}>
          <div>
            <div className="text-xs uppercase tracking-[0.24em] text-slate-500">About</div>
            <h2 className={`mt-1 text-xl font-semibold ${theme === "light" ? "text-slate-900" : "text-slate-50"}`}>CVAT Dataset Rotation Tool</h2>
          </div>
          <button className={`rounded-md px-3 py-2 text-sm ${theme === "light" ? "text-slate-600 hover:bg-slate-100 hover:text-slate-900" : "text-slate-300 hover:bg-slate-800 hover:text-white"}`} onClick={onClose}>
            ✖️ Close
          </button>
        </div>
        <div className={`space-y-4 p-6 text-sm leading-6 ${theme === "light" ? "text-slate-700" : "text-slate-300"}`}>
          <p>
            This app corrects rotated computer-vision datasets while keeping annotations, X/Y coordinates, and CVAT white-dot orientation understandable and exportable.
          </p>
          <p>
            It supports full or range exports, resumable workspaces, configurable storage folders, dark/light mode, and multiple CVAT import/export formats.
          </p>
          <div className={`rounded-xl border p-4 text-center ${theme === "light" ? "border-slate-200 bg-white text-slate-700" : "border-slate-800 bg-slate-950/70"}`}>
            <div className="text-xs uppercase tracking-wide text-slate-500">Contact</div>
            <div className={`mt-2 font-medium ${theme === "light" ? "text-slate-900" : "text-slate-100"}`}>Eng. Hasan Zemzem | hasan.zamzam@gmail.com</div>
          </div>
        </div>
      </div>
    </div>
  );
}
