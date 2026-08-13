import { useState } from "react";
import { useDatasetStore } from "../store/useDatasetStore";

type StartOverModalProps = {
  open: boolean;
  onClose: () => void;
};

export function StartOverModal({ open, onClose }: StartOverModalProps) {
  const startOver = useDatasetStore((state) => state.startOver);
  const theme = useDatasetStore((state) => state.theme);
  const [workingMode, setWorkingMode] = useState<"save" | "export" | "discard" | null>(null);

  if (!open) {
    return null;
  }

  const runAction = async (mode: "save" | "export" | "discard") => {
    setWorkingMode(mode);
    try {
      await startOver(mode);
      onClose();
    } finally {
      setWorkingMode(null);
    }
  };

  const buttonClass =
    theme === "light"
      ? "rounded-xl border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 disabled:opacity-60"
      : "rounded-xl border border-slate-700 bg-slate-900 px-4 py-2 text-sm font-semibold text-slate-100 transition hover:bg-slate-800 disabled:opacity-60";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/60 p-4 backdrop-blur-sm">
      <section className={`w-full max-w-xl overflow-hidden rounded-3xl border shadow-2xl ${theme === "light" ? "border-slate-200 bg-white text-slate-900" : "border-slate-800 bg-slate-950 text-slate-100"}`}>
        <div className={`border-b px-6 py-5 ${theme === "light" ? "border-slate-200 bg-slate-50" : "border-slate-800 bg-slate-900"}`}>
          <div className="text-xs font-semibold uppercase tracking-[0.25em] text-indigo-400">Start Over</div>
          <h2 className="mt-2 text-2xl font-black tracking-tight">What should happen before returning home?</h2>
          <p className={`mt-2 text-sm ${theme === "light" ? "text-slate-600" : "text-slate-400"}`}>
            Save this workspace for later, export a corrected CVAT ZIP first, or discard the current temporary workspace.
          </p>
        </div>
        <div className="grid gap-3 p-6">
          <button className={buttonClass} disabled={workingMode !== null} onClick={() => runAction("save")}>
            💾 {workingMode === "save" ? "Saving workspace..." : "Save workspace and start over"}
          </button>
          <button
            className={`rounded-xl border px-4 py-2 text-sm font-semibold transition disabled:opacity-60 ${
              theme === "light" ? "border-emerald-300 bg-emerald-50 text-emerald-800 hover:bg-emerald-100" : "border-emerald-700 bg-emerald-900/60 text-emerald-100 hover:bg-emerald-900"
            }`}
            disabled={workingMode !== null}
            onClick={() => runAction("export")}
          >
            📦 {workingMode === "export" ? "Exporting CVAT ZIP..." : "Export CVAT ZIP and start over"}
          </button>
          <button
            className={`rounded-xl border px-4 py-2 text-sm font-semibold transition disabled:opacity-60 ${
              theme === "light" ? "border-rose-300 bg-rose-50 text-rose-800 hover:bg-rose-100" : "border-rose-800 bg-rose-950/70 text-rose-100 hover:bg-rose-900"
            }`}
            disabled={workingMode !== null}
            onClick={() => runAction("discard")}
          >
            🗑️ {workingMode === "discard" ? "Discarding workspace..." : "Discard temporary workspace"}
          </button>
        </div>
        <div className={`flex justify-end border-t px-6 py-4 ${theme === "light" ? "border-slate-200 bg-slate-50" : "border-slate-800 bg-slate-900"}`}>
          <button className={buttonClass} disabled={workingMode !== null} onClick={onClose}>
            Cancel
          </button>
        </div>
      </section>
    </div>
  );
}
