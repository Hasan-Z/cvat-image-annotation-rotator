import { useEffect, useRef } from "react";
import { useDatasetStore } from "../store/useDatasetStore";
import { formatDatasetFormat } from "../utils/formats";

type FolderUploadFile = File & {
  relativePath?: string;
  webkitRelativePath?: string;
};

type BrowserFileHandle = {
  kind: "file";
  name: string;
  getFile: () => Promise<File>;
};

type BrowserDirectoryHandle = {
  kind: "directory";
  name: string;
  values: () => AsyncIterable<BrowserFileHandle | BrowserDirectoryHandle>;
};

async function collectDirectoryFiles(directory: BrowserDirectoryHandle, prefix = directory.name): Promise<FolderUploadFile[]> {
  const files: FolderUploadFile[] = [];
  for await (const entry of directory.values()) {
    const relativePath = `${prefix}/${entry.name}`;
    if (entry.kind === "file") {
      const file = (await entry.getFile()) as FolderUploadFile;
      Object.defineProperty(file, "relativePath", { value: relativePath });
      files.push(file);
    } else {
      files.push(...(await collectDirectoryFiles(entry, relativePath)));
    }
  }
  return files;
}

export function UploadDropzone() {
  const zipInputRef = useRef<HTMLInputElement>(null);
  const mergeZipInputRef = useRef<HTMLInputElement>(null);
  const folderInputRef = useRef<HTMLInputElement>(null);
  const uploadDataset = useDatasetStore((state) => state.uploadDataset);
  const uploadMultipleDatasets = useDatasetStore((state) => state.uploadMultipleDatasets);
  const uploadDatasetFolder = useDatasetStore((state) => state.uploadDatasetFolder);
  const openLocalEditableFolder = useDatasetStore((state) => state.openLocalEditableFolder);
  const loadSavedDatasets = useDatasetStore((state) => state.loadSavedDatasets);
  const resumeDataset = useDatasetStore((state) => state.resumeDataset);
  const savedDatasets = useDatasetStore((state) => state.savedDatasets);
  const loading = useDatasetStore((state) => state.loading);
  const theme = useDatasetStore((state) => state.theme);
  const primaryButton =
    theme === "light"
      ? "rounded border border-indigo-300 bg-indigo-50 px-4 py-2 font-medium text-indigo-800 hover:bg-indigo-100"
      : "rounded bg-indigo-600 px-4 py-2 font-medium text-white";

  useEffect(() => {
    loadSavedDatasets();
  }, [loadSavedDatasets]);

  useEffect(() => {
    folderInputRef.current?.setAttribute("webkitdirectory", "");
    folderInputRef.current?.setAttribute("directory", "");
  }, []);

  const chooseFolder = async () => {
    const windowWithDirectoryPicker = window as Window & {
      showDirectoryPicker?: () => Promise<BrowserDirectoryHandle>;
    };
    if (windowWithDirectoryPicker.showDirectoryPicker) {
      try {
        const directory = await windowWithDirectoryPicker.showDirectoryPicker();
        const files = await collectDirectoryFiles(directory);
        if (files.length > 0) {
          await uploadDatasetFolder(files);
        }
      } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError") return;
      }
      return;
    }
    folderInputRef.current?.click();
  };

  return (
    <div className="h-full min-h-0 overflow-y-auto pr-1 [scrollbar-gutter:stable]">
      <div className="flex min-h-full flex-col gap-4">
      <div className={`flex flex-col items-center justify-center gap-4 rounded-3xl border border-dashed p-12 text-center shadow-2xl ${theme === "light" ? "border-indigo-200 bg-white/90 text-slate-900" : "border-indigo-900 bg-slate-900/80 text-slate-100"}`}>
        <div className="rounded-2xl bg-indigo-500 px-4 py-2 text-sm font-black uppercase tracking-[0.35em] text-white shadow-lg shadow-indigo-500/30">CVAT</div>
        <h1 className="text-4xl font-black tracking-tight">CVAT Dataset Rotation Tool</h1>
        <p className={`max-w-xl ${theme === "light" ? "text-slate-600" : "text-slate-300"}`}>
          Upload a dataset ZIP or folder, correct rotated images, inspect coordinates and dot orientation, then export in your preferred CVAT-compatible format.
        </p>
        <input
          ref={zipInputRef}
          className="hidden"
          type="file"
          accept=".zip"
          onChange={async (event) => {
            const file = event.target.files?.[0];
            if (file) {
              await uploadDataset(file);
            }
          }}
        />
        <input
          ref={folderInputRef}
          className="hidden"
          type="file"
          multiple
          onChange={async (event) => {
            const files = Array.from(event.target.files ?? []) as FolderUploadFile[];
            if (files.length > 0) {
              await uploadDatasetFolder(files);
            }
            event.target.value = "";
          }}
        />
        <input
          ref={mergeZipInputRef}
          className="hidden"
          type="file"
          accept=".zip"
          multiple
          onChange={async (event) => {
            const files = Array.from(event.target.files ?? []);
            if (files.length > 0) {
              await uploadMultipleDatasets(files);
            }
            event.target.value = "";
          }}
        />
        <div className="flex flex-wrap justify-center gap-3">
        <button className={primaryButton} title="Choose a ZIP dataset to upload" onClick={() => zipInputRef.current?.click()} disabled={loading}>
          {loading ? "⏳ Loading dataset..." : "📁 Choose dataset ZIP"}
        </button>
        <button className={primaryButton} title="Choose multiple ZIP datasets/jobs and merge them into one workspace" onClick={() => mergeZipInputRef.current?.click()} disabled={loading}>
          {loading ? "⏳ Loading dataset..." : "🧬 Merge ZIP jobs"}
        </button>
        <button className={primaryButton} title="Choose an extracted dataset folder to upload" onClick={chooseFolder} disabled={loading}>
          {loading ? "⏳ Loading dataset..." : "🗂️ Choose dataset folder"}
        </button>
        <button
          className={primaryButton}
          title="Open a local dataset folder directly. Pascal VOC and image-only folders can be written back to the source folder."
          onClick={() => openLocalEditableFolder()}
          disabled={loading}
        >
          {loading ? "⏳ Loading dataset..." : "🛠️ Open local folder"}
        </button>
        </div>
        {savedDatasets.length > 0 ? (
          <div className={`mt-2 w-full max-w-2xl rounded-2xl border p-4 text-left ${theme === "light" ? "border-slate-200 bg-slate-50" : "border-slate-800 bg-slate-950/70"}`}>
            <div className={`text-sm font-semibold ${theme === "light" ? "text-slate-900" : "text-slate-100"}`}>Saved workspaces</div>
            <div className={`mt-1 text-xs ${theme === "light" ? "text-slate-500" : "text-slate-400"}`}>Resume a dataset saved with Save or Save workspace and start over.</div>
            <div className="mt-3 grid gap-2">
              {savedDatasets.map((dataset) => (
                <button
                  key={dataset.dataset_id}
                  className={`flex items-center justify-between gap-3 rounded-xl border px-3 py-2 text-left transition ${
                    theme === "light" ? "border-slate-200 bg-white hover:border-indigo-300 hover:bg-indigo-50" : "border-slate-800 bg-slate-900 hover:border-indigo-700 hover:bg-slate-800"
                  }`}
                  onClick={() => resumeDataset(dataset.dataset_id)}
                  disabled={loading}
                  title="Resume saved workspace"
                >
                  <span className="min-w-0">
                    <span className="block truncate text-sm font-medium">{dataset.dataset_id}</span>
                    <span className={`block text-xs ${theme === "light" ? "text-slate-500" : "text-slate-400"}`}>
                      {dataset.num_images} images · {formatDatasetFormat(dataset.format)}
                    </span>
                  </span>
                  <span className="shrink-0 text-xs font-semibold text-indigo-400">Resume workspace →</span>
                </button>
              ))}
            </div>
          </div>
        ) : null}
      </div>

      <div className={`w-full rounded-3xl border p-6 text-left shadow-2xl ${theme === "light" ? "border-slate-200 bg-white/90 text-slate-700" : "border-slate-800 bg-slate-900/90 text-slate-300"}`}>
        <div className="grid gap-4 md:grid-cols-3">
          <div className="rounded-2xl border border-indigo-500/20 p-4">
            <div className="flex items-center gap-3">
              <span className="flex h-8 w-8 items-center justify-center rounded-full bg-indigo-500 text-sm font-black text-white">1</span>
              <span className="text-2xl">📁</span>
            </div>
            <h2 className={`mt-2 font-bold ${theme === "light" ? "text-slate-900" : "text-slate-100"}`}>Upload</h2>
            <p className="mt-1 text-sm text-slate-400">Choose a supported ZIP, upload an extracted folder, or resume a saved workspace.</p>
          </div>
          <div className="rounded-2xl border border-indigo-500/20 p-4">
            <div className="flex items-center gap-3">
              <span className="flex h-8 w-8 items-center justify-center rounded-full bg-indigo-500 text-sm font-black text-white">2</span>
              <span className="text-2xl">🔄</span>
            </div>
            <h2 className={`mt-2 font-bold ${theme === "light" ? "text-slate-900" : "text-slate-100"}`}>Correct</h2>
            <p className="mt-1 text-sm text-slate-400">Rotate images, verify X/Y overlays, and adjust white-dot direction.</p>
          </div>
          <div className="rounded-2xl border border-indigo-500/20 p-4">
            <div className="flex items-center gap-3">
              <span className="flex h-8 w-8 items-center justify-center rounded-full bg-indigo-500 text-sm font-black text-white">3</span>
              <span className="text-2xl">📦</span>
            </div>
            <h2 className={`mt-2 font-bold ${theme === "light" ? "text-slate-900" : "text-slate-100"}`}>Export</h2>
            <p className="mt-1 text-sm text-slate-400">Export the full dataset or a selected image range in the format you need.</p>
          </div>
        </div>
        <p className="mt-5 text-center text-sm text-slate-400">Open <strong>❓ Help</strong> for supported formats, coordinate rules, export behavior, and shortcuts.</p>
      </div>
      </div>
    </div>
  );
}
