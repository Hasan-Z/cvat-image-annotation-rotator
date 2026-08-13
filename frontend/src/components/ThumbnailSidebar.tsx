import { useEffect, useMemo, useState } from "react";
import { useDatasetStore } from "../store/useDatasetStore";
import { formatDatasetFormat } from "../utils/formats";

export function ThumbnailSidebar() {
  const thumbnails = useDatasetStore((state) => state.thumbnails);
  const duplicateGroups = useDatasetStore((state) => state.duplicateGroups);
  const loadImage = useDatasetStore((state) => state.loadImage);
  const loadDuplicates = useDatasetStore((state) => state.loadDuplicates);
  const deleteDuplicateImages = useDatasetStore((state) => state.deleteDuplicateImages);
  const currentIndex = useDatasetStore((state) => state.currentIndex);
  const datasetFormat = useDatasetStore((state) => state.datasetFormat);
  const theme = useDatasetStore((state) => state.theme);
  const [selectedDuplicates, setSelectedDuplicates] = useState<Set<number>>(new Set());
  const [selectedNoLabelImages, setSelectedNoLabelImages] = useState<Set<number>>(new Set());
  const [duplicatesExpanded, setDuplicatesExpanded] = useState(false);
  const [noLabelsExpanded, setNoLabelsExpanded] = useState(false);
  const duplicateIndexes = useMemo(() => new Set(duplicateGroups.flatMap((group) => group.images.map((image) => image.index))), [duplicateGroups]);
  const noLabelImages = useMemo(
    () => thumbnails.filter((image) => image.annotation_count === 0 && !image.classification_label),
    [thumbnails],
  );
  const noLabelIndexes = useMemo(() => new Set(noLabelImages.map((image) => image.index)), [noLabelImages]);

  useEffect(() => {
    setSelectedDuplicates((current) => new Set([...current].filter((index) => duplicateIndexes.has(index))));
  }, [duplicateIndexes]);

  useEffect(() => {
    setSelectedNoLabelImages((current) => new Set([...current].filter((index) => noLabelIndexes.has(index))));
  }, [noLabelIndexes]);

  const toggleDuplicate = (index: number) => {
    setSelectedDuplicates((current) => {
      const next = new Set(current);
      if (next.has(index)) next.delete(index);
      else next.add(index);
      return next;
    });
  };

  const selectAllButFirst = () => {
    setSelectedDuplicates(new Set(duplicateGroups.flatMap((group) => group.images.slice(1).map((image) => image.index))));
  };

  const selectedDuplicateIndexes = [...selectedDuplicates];
  const selectedNoLabelIndexes = [...selectedNoLabelImages];

  return (
    <section className={`min-h-0 flex-1 overflow-y-auto ${theme === "light" ? "bg-white" : "bg-slate-900"}`}>
      <div className={`border-b px-4 py-3 ${theme === "light" ? "border-slate-200 text-slate-900" : "border-slate-800 text-slate-100"}`}>
        <div className="text-sm font-medium">Thumbnails</div>
        <div className={`mt-1 text-xs ${theme === "light" ? "text-slate-500" : "text-slate-400"}`}>
          Input format: <span className={theme === "light" ? "font-medium text-slate-700" : "font-medium text-slate-200"}>{formatDatasetFormat(datasetFormat)}</span>
        </div>
      </div>
      <div className={`border-b p-2 ${theme === "light" ? "border-slate-200" : "border-slate-800"}`}>
        <div className={`rounded-xl border p-3 ${theme === "light" ? "border-amber-200 bg-amber-50/70 text-slate-800" : "border-amber-900/60 bg-amber-950/20 text-slate-200"}`}>
          <div className="flex items-center justify-between gap-2">
            <button className="min-w-0 flex-1 text-left" onClick={() => setDuplicatesExpanded((value) => !value)} title="Collapse or expand duplicate images">
              <div className="text-sm font-semibold">{duplicatesExpanded ? "▾" : "▸"} 🧬 Duplicate images</div>
              <div className={`mt-0.5 text-xs ${theme === "light" ? "text-slate-600" : "text-slate-400"}`}>
                {duplicateGroups.length} MD5 group{duplicateGroups.length === 1 ? "" : "s"} found.
              </div>
            </button>
            <button
              className={`rounded-lg border px-2 py-1 text-xs font-semibold ${theme === "light" ? "border-slate-300 bg-white text-slate-700 hover:bg-slate-100" : "border-slate-700 bg-slate-950 text-slate-200 hover:bg-slate-800"}`}
              onClick={() => loadDuplicates()}
              title="Rescan original images for MD5 duplicates"
            >
              🔄 Scan
            </button>
          </div>
          {!duplicatesExpanded ? (
            <div className={`mt-3 rounded-lg border border-dashed px-3 py-2 text-xs ${theme === "light" ? "border-slate-300 text-slate-500" : "border-slate-700 text-slate-400"}`}>
              Collapsed. Expand to review and remove duplicate images.
            </div>
          ) : duplicateGroups.length === 0 ? (
            <div className={`mt-3 rounded-lg border border-dashed px-3 py-2 text-xs ${theme === "light" ? "border-slate-300 text-slate-500" : "border-slate-700 text-slate-400"}`}>
              No duplicate MD5 groups found.
            </div>
          ) : (
            <div className="mt-3 space-y-3">
              <div className="flex flex-wrap gap-2">
                <button
                  className={`rounded-lg border px-2 py-1 text-xs font-semibold ${theme === "light" ? "border-amber-300 bg-white text-amber-800 hover:bg-amber-100" : "border-amber-800 bg-amber-950/40 text-amber-100 hover:bg-amber-900"}`}
                  onClick={selectAllButFirst}
                >
                  Select all but first
                </button>
                <button
                  className={`rounded-lg border px-2 py-1 text-xs font-semibold ${theme === "light" ? "border-slate-300 bg-white text-slate-700 hover:bg-slate-100" : "border-slate-700 bg-slate-950 text-slate-200 hover:bg-slate-800"}`}
                  onClick={() => setSelectedDuplicates(new Set())}
                >
                  Clear
                </button>
              </div>
              {duplicateGroups.map((group, groupIndex) => (
                <div key={group.md5} className={`rounded-lg border p-2 ${theme === "light" ? "border-amber-200 bg-white" : "border-amber-900/40 bg-slate-950/60"}`}>
                  <div className="mb-2 flex items-center justify-between gap-2 text-xs">
                    <span className="font-semibold">Group {groupIndex + 1}</span>
                    <span className="truncate text-slate-500">{group.md5.slice(0, 10)}…</span>
                  </div>
                  <div className="space-y-1">
                    {group.images.map((image) => (
                      <label key={image.index} className={`flex cursor-pointer items-center gap-2 rounded-md border px-2 py-1.5 text-xs ${theme === "light" ? "border-slate-200 bg-slate-50" : "border-slate-800 bg-slate-900"}`}>
                        <input
                          type="checkbox"
                          checked={selectedDuplicates.has(image.index)}
                          onChange={() => toggleDuplicate(image.index)}
                        />
                        <img src={image.image_url} alt={image.filename} className="h-8 w-8 rounded object-cover" />
                        <span className="min-w-0 flex-1 truncate">{image.index + 1}. {image.filename}</span>
                        <span className="shrink-0 text-slate-500">{image.width}×{image.height}</span>
                      </label>
                    ))}
                  </div>
                </div>
              ))}
              <button
                className={`w-full rounded-lg border px-3 py-2 text-xs font-bold transition disabled:opacity-50 ${theme === "light" ? "border-rose-300 bg-rose-50 text-rose-800 hover:bg-rose-100" : "border-rose-800 bg-rose-950/70 text-rose-100 hover:bg-rose-900"}`}
                disabled={selectedDuplicateIndexes.length === 0}
                onClick={() => deleteDuplicateImages(selectedDuplicateIndexes)}
              >
                🗑️ Remove selected duplicates ({selectedDuplicateIndexes.length})
              </button>
            </div>
          )}
        </div>
      </div>
      <div className={`border-b p-2 ${theme === "light" ? "border-slate-200" : "border-slate-800"}`}>
        <div className={`rounded-xl border p-3 ${theme === "light" ? "border-sky-200 bg-sky-50/70 text-slate-800" : "border-sky-900/60 bg-sky-950/20 text-slate-200"}`}>
          <div className="flex items-center justify-between gap-2">
            <button className="min-w-0 flex-1 text-left" onClick={() => setNoLabelsExpanded((value) => !value)} title="Collapse or expand images with no labels">
              <div className="text-sm font-semibold">{noLabelsExpanded ? "▾" : "▸"} 🏷️ Images with no labels</div>
              <div className={`mt-0.5 text-xs ${theme === "light" ? "text-slate-600" : "text-slate-400"}`}>
                {noLabelImages.length} visible image{noLabelImages.length === 1 ? "" : "s"} currently have no annotations or classification label.
              </div>
            </button>
          </div>
          {!noLabelsExpanded ? (
            <div className={`mt-3 rounded-lg border border-dashed px-3 py-2 text-xs ${theme === "light" ? "border-slate-300 text-slate-500" : "border-slate-700 text-slate-400"}`}>
              Collapsed. Expand to review and remove images with no annotations or classification label.
            </div>
          ) : noLabelImages.length === 0 ? (
            <div className={`mt-3 rounded-lg border border-dashed px-3 py-2 text-xs ${theme === "light" ? "border-slate-300 text-slate-500" : "border-slate-700 text-slate-400"}`}>
              No unlabeled visible images found.
            </div>
          ) : (
            <div className="mt-3 space-y-3">
              <div className="flex flex-wrap gap-2">
                <button
                  className={`rounded-lg border px-2 py-1 text-xs font-semibold ${theme === "light" ? "border-sky-300 bg-white text-sky-800 hover:bg-sky-100" : "border-sky-800 bg-sky-950/40 text-sky-100 hover:bg-sky-900"}`}
                  onClick={() => setSelectedNoLabelImages(new Set(noLabelImages.map((image) => image.index)))}
                >
                  Select all
                </button>
                <button
                  className={`rounded-lg border px-2 py-1 text-xs font-semibold ${theme === "light" ? "border-slate-300 bg-white text-slate-700 hover:bg-slate-100" : "border-slate-700 bg-slate-950 text-slate-200 hover:bg-slate-800"}`}
                  onClick={() => setSelectedNoLabelImages(new Set())}
                >
                  Clear
                </button>
              </div>
              <div className="max-h-80 space-y-1 overflow-y-auto pr-1">
                {noLabelImages.map((image) => (
                  <label key={image.index} className={`flex cursor-pointer items-center gap-2 rounded-md border px-2 py-1.5 text-xs ${theme === "light" ? "border-slate-200 bg-white" : "border-slate-800 bg-slate-900"}`}>
                    <input
                      type="checkbox"
                      checked={selectedNoLabelImages.has(image.index)}
                      onChange={() =>
                        setSelectedNoLabelImages((current) => {
                          const next = new Set(current);
                          if (next.has(image.index)) next.delete(image.index);
                          else next.add(image.index);
                          return next;
                        })
                      }
                    />
                    <img src={image.image_url} alt={image.filename} className="h-8 w-8 rounded object-cover" />
                    <span className="min-w-0 flex-1 truncate">{image.index + 1}. {image.filename}</span>
                    <span className="shrink-0 text-slate-500">{image.width}×{image.height}</span>
                  </label>
                ))}
              </div>
              <button
                className={`w-full rounded-lg border px-3 py-2 text-xs font-bold transition disabled:opacity-50 ${theme === "light" ? "border-rose-300 bg-rose-50 text-rose-800 hover:bg-rose-100" : "border-rose-800 bg-rose-950/70 text-rose-100 hover:bg-rose-900"}`}
                disabled={selectedNoLabelIndexes.length === 0}
                onClick={() => deleteDuplicateImages(selectedNoLabelIndexes)}
              >
                🗑️ Remove selected no-label images ({selectedNoLabelIndexes.length})
              </button>
            </div>
          )}
        </div>
      </div>
      <div className="space-y-2 p-2">
        {thumbnails.map((image) => (
          <button
            key={image.index}
            className={`w-full rounded border p-2 text-left ${
              image.index === currentIndex
                ? theme === "light"
                  ? "border-indigo-500 bg-indigo-50 shadow-sm"
                  : "border-indigo-500 bg-slate-800"
                : theme === "light"
                  ? "border-slate-200 bg-slate-50"
                  : "border-slate-700 bg-slate-900"
            }`}
            onClick={() => loadImage(image.index)}
          >
            <div className={`mb-2 flex h-24 items-center justify-center overflow-hidden rounded ${theme === "light" ? "bg-slate-100" : "bg-slate-950"}`}>
              <img
                src={image.image_url}
                alt={image.filename}
                className="max-h-full max-w-full object-contain"
                style={{ transform: `rotate(${image.rotation}deg)`, transformOrigin: "center center" }}
              />
            </div>
            <div className={`text-xs ${theme === "light" ? "text-slate-500" : "text-slate-400"}`}>🖼️ Image {image.index + 1}</div>
            <div className={`truncate text-sm ${theme === "light" ? "text-slate-900" : "text-slate-100"}`}>{image.filename}</div>
            <div className={`text-xs ${theme === "light" ? "text-slate-500" : "text-slate-400"}`}>image rotation: {image.rotation}°</div>
          </button>
        ))}
      </div>
    </section>
  );
}
