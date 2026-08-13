import { useEffect } from "react";
import { useDatasetStore } from "../store/useDatasetStore";

type DeleteImageModalProps = {
  open: boolean;
  filename: string | null;
  imageNumber: number;
  onCancel: () => void;
  onConfirm: () => void;
};

export function DeleteImageModal({ open, filename, imageNumber, onCancel, onConfirm }: DeleteImageModalProps) {
  const theme = useDatasetStore((state) => state.theme);

  useEffect(() => {
    if (!open) return;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Enter") {
        event.preventDefault();
        onConfirm();
      }
      if (event.key === "Escape") {
        event.preventDefault();
        onCancel();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onCancel, onConfirm, open]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/70 p-4 backdrop-blur-sm">
      <section className={`w-full max-w-lg overflow-hidden rounded-3xl border shadow-2xl ${theme === "light" ? "border-slate-200 bg-white text-slate-900" : "border-slate-800 bg-slate-950 text-slate-100"}`}>
        <div className={`border-b px-6 py-5 ${theme === "light" ? "border-slate-200 bg-slate-50" : "border-slate-800 bg-slate-900"}`}>
          <div className="text-xs font-semibold uppercase tracking-[0.25em] text-rose-400">Confirm Delete</div>
          <h2 className="mt-2 text-2xl font-black tracking-tight">Remove this image from export?</h2>
          <p className={`mt-2 text-sm ${theme === "light" ? "text-slate-600" : "text-slate-400"}`}>
            This marks image {imageNumber} as deleted in the current workspace. Saved source files stay on disk, but this image will be excluded from export.
          </p>
        </div>
        <div className="space-y-4 p-6">
          <div className={`rounded-2xl border px-4 py-3 text-sm ${theme === "light" ? "border-rose-200 bg-rose-50 text-rose-900" : "border-rose-900/70 bg-rose-950/30 text-rose-100"}`}>
            🖼️ {filename ?? `Image ${imageNumber}`}
          </div>
          <div className="flex flex-wrap justify-end gap-3">
            <button
              className={`rounded-xl border px-4 py-2 text-sm font-semibold transition ${
                theme === "light" ? "border-slate-300 bg-white text-slate-700 hover:bg-slate-100" : "border-slate-700 bg-slate-900 text-slate-100 hover:bg-slate-800"
              }`}
              onClick={onCancel}
            >
              Cancel
            </button>
            <button
              className={`rounded-xl border px-4 py-2 text-sm font-semibold transition ${
                theme === "light" ? "border-rose-300 bg-rose-50 text-rose-800 hover:bg-rose-100" : "border-rose-800 bg-rose-950/70 text-rose-100 hover:bg-rose-900"
              }`}
              onClick={onConfirm}
            >
              🗑️ Delete from export
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}
