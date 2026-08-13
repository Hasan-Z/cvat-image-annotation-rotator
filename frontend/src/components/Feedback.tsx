import { useDatasetStore } from "../store/useDatasetStore";

function ProgressBar() {
  const progress = useDatasetStore((state) => state.progress);
  if (!progress) {
    return null;
  }
  return (
    <div className="border-b border-slate-800 bg-slate-950 px-4 py-2">
      <div className="mb-1 flex items-center justify-between text-xs text-slate-300">
        <span>{progress.label}</span>
        <span>{progress.percent === null ? "Working..." : `${progress.percent}%`}</span>
      </div>
      <div className="h-2 overflow-hidden rounded bg-slate-800">
        {progress.percent === null ? (
          <div className="h-full w-1/3 animate-progress-indeterminate rounded bg-indigo-500" />
        ) : (
          <div className="h-full rounded bg-indigo-500 transition-all" style={{ width: `${progress.percent}%` }} />
        )}
      </div>
    </div>
  );
}

function Toasts() {
  const notifications = useDatasetStore((state) => state.notifications);
  const clearNotification = useDatasetStore((state) => state.clearNotification);
  return (
    <div className="pointer-events-none fixed right-3 top-3 z-50 flex w-72 max-w-[calc(100vw-1.5rem)] flex-col gap-2">
      {notifications.map((notification) => {
        const colors: Record<string, string> = {
          info: "border-sky-500 bg-slate-900 text-slate-100",
          success: "border-emerald-500 bg-slate-900 text-slate-100",
          warning: "border-amber-500 bg-slate-900 text-slate-100",
          error: "border-rose-500 bg-slate-900 text-slate-100",
        };
        return (
          <div key={notification.id} className={`pointer-events-auto rounded-lg border p-2.5 shadow-xl ${colors[notification.level]}`}>
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <div className="truncate text-sm font-semibold">{notification.title}</div>
                <div className="mt-0.5 text-xs leading-snug text-slate-300">{notification.message}</div>
              </div>
              <button className="shrink-0 text-xs text-slate-400 hover:text-white" onClick={() => clearNotification(notification.id)}>
                ✖️
              </button>
            </div>
          </div>
        );
      })}
    </div>
  );
}

export function Feedback() {
  return (
    <>
      <ProgressBar />
      <Toasts />
    </>
  );
}
