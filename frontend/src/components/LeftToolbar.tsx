import { useDatasetStore } from "../store/useDatasetStore";

type LeftToolbarProps = {
  onOpenSettings: () => void;
  onRequestDelete: () => void;
};

export function LeftToolbar({ onOpenSettings, onRequestDelete }: LeftToolbarProps) {
  const rotateCurrent = useDatasetStore((state) => state.rotateCurrent);
  const resetCurrent = useDatasetStore((state) => state.resetCurrent);
  const loadPreviousImage = useDatasetStore((state) => state.loadPreviousImage);
  const loadNextImage = useDatasetStore((state) => state.loadNextImage);
  const fitToScreen = useDatasetStore((state) => state.fitToScreen);
  const theme = useDatasetStore((state) => state.theme);

  const buttonClass =
    theme === "light"
      ? "flex h-10 w-full items-center justify-center rounded-xl border border-slate-300 bg-white text-lg leading-none text-slate-700 transition hover:border-indigo-500 hover:bg-slate-50"
      : "flex h-10 w-full items-center justify-center rounded-xl border border-slate-800 bg-slate-900 text-lg leading-none text-slate-200 transition hover:border-indigo-500 hover:bg-slate-800";

  return (
    <aside className={`flex h-full w-16 shrink-0 flex-col gap-1.5 overflow-y-auto rounded-2xl border p-1.5 shadow-2xl ${theme === "light" ? "border-slate-200 bg-white/90" : "border-slate-800 bg-slate-950/90"}`}>
      <button className={buttonClass} title="Rotate image 90° left (Q)" onClick={() => rotateCurrent("left")}>
        <span>↶</span>
        <span className="sr-only">Left</span>
      </button>
      <button className={buttonClass} title="Rotate image 90° right (E)" onClick={() => rotateCurrent("right")}>
        <span>↷</span>
        <span className="sr-only">Right</span>
      </button>
      <button className={buttonClass} title="Rotate image 180° (R)" onClick={() => rotateCurrent("180")}>
        <span>⟲</span>
        <span className="sr-only">180°</span>
      </button>
      <button className={buttonClass} title="Reset image rotation to 0° (Esc)" onClick={() => resetCurrent()}>
        <span>↺</span>
        <span className="sr-only">Reset</span>
      </button>
      <button className={buttonClass} title="Previous visible image (Left Arrow)" onClick={() => loadPreviousImage()}>
        <span>←</span>
        <span className="sr-only">Prev</span>
      </button>
      <button className={buttonClass} title="Next visible image (Right Arrow)" onClick={() => loadNextImage()}>
        <span>→</span>
        <span className="sr-only">Next</span>
      </button>
      <button className={buttonClass} title="Fit current image to screen (F)" onClick={() => fitToScreen()}>
        <span>⊞</span>
        <span className="sr-only">Fit</span>
      </button>
      <button className={`flex h-10 w-full items-center justify-center rounded-xl border text-lg leading-none transition hover:border-rose-500 ${theme === "light" ? "border-slate-300 bg-white text-slate-700 hover:bg-slate-50" : "border-slate-800 bg-slate-900 text-slate-200 hover:bg-slate-800"}`} title="Delete current image (D)" onClick={onRequestDelete}>
        <span>🗑</span>
        <span className="sr-only">Delete</span>
      </button>
      <button className={buttonClass} title="Open settings" onClick={onOpenSettings}>
        <span>⚙</span>
        <span className="sr-only">Settings</span>
      </button>
    </aside>
  );
}
