import { useDatasetStore } from "../store/useDatasetStore";

const levelStyles = {
  info: "border-sky-400 bg-sky-500/10 text-sky-700 dark:text-sky-200",
  success: "border-emerald-400 bg-emerald-500/10 text-emerald-700 dark:text-emerald-200",
  warning: "border-amber-400 bg-amber-500/10 text-amber-700 dark:text-amber-200",
  error: "border-rose-400 bg-rose-500/10 text-rose-700 dark:text-rose-200",
};

type ActivityLogProps = {
  open: boolean;
  onClose: () => void;
};

export function ActivityLog({ open, onClose }: ActivityLogProps) {
  const messageLog = useDatasetStore((state) => state.messageLog);
  const clearMessageLog = useDatasetStore((state) => state.clearMessageLog);
  const theme = useDatasetStore((state) => state.theme);

  if (!open) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-40">
      <button className="absolute inset-0 cursor-default bg-slate-950/40 backdrop-blur-sm" aria-label="Close activity log" onClick={onClose} />
      <section
        className={`absolute bottom-4 right-4 top-4 flex w-[440px] max-w-[calc(100vw-2rem)] flex-col overflow-hidden rounded-3xl border shadow-2xl ${
          theme === "light" ? "border-slate-200 bg-white text-slate-900" : "border-slate-800 bg-slate-950 text-slate-100"
        }`}
      >
        <div className={`border-b px-5 py-4 ${theme === "light" ? "border-slate-200 bg-slate-50" : "border-slate-800 bg-slate-900"}`}>
          <div className="flex items-start justify-between gap-3">
            <div>
              <div className="text-xs font-semibold uppercase tracking-[0.25em] text-indigo-400">Activity Journal</div>
              <div className={`mt-1 text-xl font-bold ${theme === "light" ? "text-slate-950" : "text-white"}`}>Activity log</div>
              <div className={`mt-1 text-sm ${theme === "light" ? "text-slate-500" : "text-slate-400"}`}>Upload, save, rotation, dot, export, and folder messages stay here.</div>
            </div>
            <button
              className={`rounded-xl border px-3 py-2 text-sm transition ${
                theme === "light" ? "border-slate-300 bg-white text-slate-700 hover:bg-slate-100" : "border-slate-700 bg-slate-950 text-slate-300 hover:bg-slate-800"
              }`}
              title="Close activity log"
              onClick={onClose}
            >
              ✖️
            </button>
          </div>
          <div className="mt-4 flex items-center justify-between gap-3">
            <div className={`rounded-full px-3 py-1 text-xs ${theme === "light" ? "bg-indigo-50 text-indigo-700" : "bg-indigo-500/10 text-indigo-200"}`}>
              {messageLog.length} message{messageLog.length === 1 ? "" : "s"}
            </div>
            <button
              className={`rounded-xl border px-3 py-2 text-xs transition ${
                theme === "light" ? "border-slate-300 bg-white text-slate-700 hover:bg-slate-100" : "border-slate-700 bg-slate-950 text-slate-300 hover:bg-slate-800"
              }`}
              title="Clear activity log"
              onClick={() => clearMessageLog()}
            >
              🧹 Clear log
            </button>
          </div>
        </div>
        <div className="min-h-0 flex-1 space-y-3 overflow-y-auto p-4">
          {messageLog.length === 0 ? (
            <div className={`rounded-2xl border border-dashed px-4 py-10 text-center text-sm ${theme === "light" ? "border-slate-200 text-slate-500" : "border-slate-800 text-slate-500"}`}>
              No activity yet. Upload or resume a dataset to begin.
            </div>
          ) : (
            messageLog.map((entry) => (
              <article key={`${entry.id}-${entry.timestamp}`} className={`rounded-2xl border px-4 py-3 text-sm shadow-sm ${levelStyles[entry.level]}`}>
                <div className="flex items-center justify-between gap-2">
                  <span className="font-semibold">{entry.title}</span>
                  <span className="shrink-0 text-xs opacity-70">{entry.timestamp}</span>
                </div>
                <div className={`mt-1 text-sm ${theme === "light" ? "text-slate-600" : "text-slate-300"}`}>{entry.message}</div>
              </article>
            ))
          )}
        </div>
      </section>
    </div>
  );
}
