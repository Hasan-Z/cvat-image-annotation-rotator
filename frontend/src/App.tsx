import { useEffect, useState } from "react";
import { Feedback } from "./components/Feedback";
import { ActivityLog } from "./components/ActivityLog";
import { AnnotationCanvas } from "./components/AnnotationCanvas";
import { AboutModal } from "./components/AboutModal";
import { DeleteImageModal } from "./components/DeleteImageModal";
import { LeftToolbar } from "./components/LeftToolbar";
import { HelpModal } from "./components/HelpModal";
import { ThumbnailSidebar } from "./components/ThumbnailSidebar";
import { Toolbar } from "./components/Toolbar";
import { SettingsModal } from "./components/SettingsModal";
import { StartOverModal } from "./components/StartOverModal";
import { UploadDropzone } from "./components/UploadDropzone";
import { useDatasetStore } from "./store/useDatasetStore";

function isEditableShortcutTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  return ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName) || target.isContentEditable;
}

export default function App() {
  const datasetId = useDatasetStore((state) => state.datasetId);
  const currentIndex = useDatasetStore((state) => state.currentIndex);
  const currentImage = useDatasetStore((state) => state.currentImage);
  const loadPreviousImage = useDatasetStore((state) => state.loadPreviousImage);
  const loadNextImage = useDatasetStore((state) => state.loadNextImage);
  const rotateCurrent = useDatasetStore((state) => state.rotateCurrent);
  const resetCurrent = useDatasetStore((state) => state.resetCurrent);
  const deleteCurrent = useDatasetStore((state) => state.deleteCurrent);
  const fitToScreen = useDatasetStore((state) => state.fitToScreen);
  const autoFitOnImageChange = useDatasetStore((state) => state.autoFitOnImageChange);
  const theme = useDatasetStore((state) => state.theme);
  const setZoom = useDatasetStore((state) => state.setZoom);
  const zoom = useDatasetStore((state) => state.zoom);
  const saveDataset = useDatasetStore((state) => state.saveDataset);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [aboutOpen, setAboutOpen] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);
  const [logOpen, setLogOpen] = useState(false);
  const [startOverOpen, setStartOverOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
    document.documentElement.dataset.theme = theme;
    document.body.dataset.theme = theme;
  }, [theme]);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (isEditableShortcutTarget(event.target)) return;
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s") {
        event.preventDefault();
        saveDataset();
      }
      if (event.key === "q") rotateCurrent("left");
      if (event.key === "e") rotateCurrent("right");
      if (event.key === "r") rotateCurrent("180");
      if (event.key === "ArrowLeft") loadPreviousImage();
      if (event.key === "ArrowRight") loadNextImage();
      if (event.key.toLowerCase() === "d" && datasetId) setDeleteOpen(true);
      if (event.key === "f") fitToScreen();
      if (event.key === "+") setZoom(Math.min(8, zoom * 1.1));
      if (event.key === "-") setZoom(Math.max(0.1, zoom / 1.1));
      if (event.key === "Escape") resetCurrent();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [currentIndex, datasetId, fitToScreen, loadNextImage, loadPreviousImage, resetCurrent, rotateCurrent, saveDataset, setZoom, zoom]);

  useEffect(() => {
    if (datasetId && currentIndex >= 0 && autoFitOnImageChange) {
      fitToScreen();
    }
  }, [autoFitOnImageChange, currentIndex, datasetId, fitToScreen]);

  return (
    <div
      className={`flex h-full flex-col ${
        theme === "light"
          ? "bg-[radial-gradient(circle_at_top_left,_#e0e7ff,_#f8fafc_42%,_#e2e8f0)] text-slate-900"
          : "bg-[radial-gradient(circle_at_top_left,_#1e1b4b,_#020617_45%,_#0f172a)] text-slate-100"
      }`}
    >
      <Feedback />
      <Toolbar
        datasetLoaded={Boolean(datasetId)}
        onOpenSettings={() => setSettingsOpen(true)}
        onOpenAbout={() => setAboutOpen(true)}
        onOpenHelp={() => setHelpOpen(true)}
        onOpenLog={() => setLogOpen(true)}
        onStartOver={() => setStartOverOpen(true)}
      />
      <div className="grid flex-1 overflow-hidden p-3 pt-0" style={datasetId ? { gridTemplateColumns: "64px minmax(0,1fr) 320px" } : { gridTemplateColumns: "1fr" }}>
        {datasetId ? <LeftToolbar onOpenSettings={() => setSettingsOpen(true)} onRequestDelete={() => setDeleteOpen(true)} /> : null}
        <main className={`min-h-0 overflow-hidden ${datasetId ? "p-3" : "p-4"}`}>{datasetId ? <AnnotationCanvas /> : <UploadDropzone />}</main>
        {datasetId ? (
          <aside className={`flex min-h-0 flex-col overflow-hidden rounded-2xl border shadow-2xl ${theme === "light" ? "border-slate-200 bg-white/90" : "border-slate-800 bg-slate-900/90"}`}>
            <ThumbnailSidebar />
          </aside>
        ) : null}
      </div>
      <SettingsModal open={settingsOpen} onClose={() => setSettingsOpen(false)} />
      <AboutModal open={aboutOpen} onClose={() => setAboutOpen(false)} />
      <HelpModal open={helpOpen} onClose={() => setHelpOpen(false)} />
      <ActivityLog open={logOpen} onClose={() => setLogOpen(false)} />
      <StartOverModal open={startOverOpen} onClose={() => setStartOverOpen(false)} />
      <DeleteImageModal
        open={deleteOpen}
        filename={currentImage?.filename ?? null}
        imageNumber={currentIndex + 1}
        onCancel={() => setDeleteOpen(false)}
        onConfirm={async () => {
          setDeleteOpen(false);
          await deleteCurrent();
        }}
      />
    </div>
  );
}
