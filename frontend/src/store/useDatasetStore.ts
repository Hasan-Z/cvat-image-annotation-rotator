import { create } from "zustand";
import { api } from "../api/client";
import { downloadBlobUrl } from "../api/client";
import type { DatasetImage, DatasetImageSummary, DuplicateImageGroup, MessageLogEntry, Notification, ProgressState, SavedDataset, UploadResponse } from "../types";
import { formatDatasetFormat } from "../utils/formats";

const storedTheme = typeof window !== "undefined" ? window.localStorage.getItem("theme") : null;
const initialTheme = storedTheme === "light" ? "light" : "dark";

function createId(): string {
  return globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function describeError(error: unknown, fallback: string): string {
  if (error instanceof Error) {
    const response = (error as Error & { response?: { data?: { detail?: unknown } } }).response;
    if (typeof response?.data?.detail === "string") return response.data.detail;
    return error.message;
  }
  return fallback;
}

type FolderUploadFile = File & {
  relativePath?: string;
  webkitRelativePath?: string;
};

function isImageFile(file: File): boolean {
  return /\.(jpe?g|png|bmp|webp|tiff?|gif)$/i.test(file.name);
}

function folderUploadLabel(files: File[]): string {
  const imageCount = files.filter(isImageFile).length;
  const fileCount = files.length;
  if (imageCount === fileCount) {
    return `Uploading ${imageCount} image${imageCount === 1 ? "" : "s"}`;
  }
  return `Uploading folder: ${imageCount} image${imageCount === 1 ? "" : "s"} + ${fileCount - imageCount} annotation/metadata file${fileCount - imageCount === 1 ? "" : "s"}`;
}

type State = {
  datasetId: string | null;
  datasetFormat: string | null;
  editableSource: boolean;
  sourceFolder: string | null;
  numImages: number;
  currentIndex: number;
  currentImage: DatasetImage | null;
  thumbnails: DatasetImageSummary[];
  duplicateGroups: DuplicateImageGroup[];
  savedDatasets: SavedDataset[];
  zoom: number;
  panX: number;
  panY: number;
  loading: boolean;
  error: string | null;
  notifications: Notification[];
  messageLog: MessageLogEntry[];
  progress: ProgressState | null;
  theme: "dark" | "light";
  showInspector: boolean;
  showCoordinateLabels: boolean;
  coordinateLabelFontSize: number;
  showCrosshairCursor: boolean;
  autoFitOnImageChange: boolean;
  uploadDataset: (file: File) => Promise<void>;
  uploadMultipleDatasets: (files: File[]) => Promise<void>;
  uploadDatasetFolder: (files: FolderUploadFile[]) => Promise<void>;
  openLocalEditableFolder: () => Promise<void>;
  loadSavedDatasets: () => Promise<void>;
  resumeDataset: (datasetId: string) => Promise<void>;
  loadImage: (index: number) => Promise<void>;
  loadPreviousImage: () => Promise<void>;
  loadNextImage: () => Promise<void>;
  rotateCurrent: (direction: "left" | "right" | "180") => Promise<void>;
  rotateAnnotationOrientation: (direction: "left" | "right" | "180" | "reset", label: string | null) => Promise<void>;
  setClassificationLabel: (label: string, applyToAll: boolean) => Promise<void>;
  resetCurrent: () => Promise<void>;
  deleteCurrent: () => Promise<void>;
  loadImages: () => Promise<DatasetImageSummary[]>;
  loadDuplicates: () => Promise<DuplicateImageGroup[]>;
  deleteDuplicateImages: (imageIndexes: number[]) => Promise<void>;
  applyImageRotations: () => Promise<void>;
  applySourceChanges: () => Promise<void>;
  saveDataset: () => Promise<void>;
  startOver: (mode: "save" | "export" | "discard") => Promise<void>;
  fitToScreen: () => void;
  exportDataset: (
    startIndex: number | null,
    endIndex: number | null,
    exportFormat:
      | "app_bundle"
      | "cvat_for_images_1_1"
      | "cvat_for_images_1_1_image_paths"
      | "coco"
      | "yolo"
      | "pascal_voc"
      | "modelarts_pascal_voc"
      | "labelme"
      | "datumaro"
      | "segmentation_mask"
      | "kitti"
      | "open_images"
      | "image_classification",
  ) => Promise<void>;
  setZoom: (zoom: number) => void;
  setPan: (panX: number, panY: number) => void;
  setCurrentIndex: (index: number) => void;
  setTheme: (theme: "dark" | "light") => void;
  toggleTheme: () => void;
  setShowInspector: (enabled: boolean) => void;
  setShowCoordinateLabels: (enabled: boolean) => void;
  setCoordinateLabelFontSize: (fontSize: number) => void;
  setShowCrosshairCursor: (enabled: boolean) => void;
  setAutoFitOnImageChange: (enabled: boolean) => void;
  pushNotification: (level: Notification["level"], title: string, message: string) => void;
  clearNotification: (id: string) => void;
  clearMessageLog: () => void;
  setProgress: (progress: ProgressState | null) => void;
};

function emptyDatasetState() {
  return {
    datasetId: null,
    datasetFormat: null,
    editableSource: false,
    sourceFolder: null,
    numImages: 0,
    currentIndex: 0,
    currentImage: null,
    thumbnails: [],
    duplicateGroups: [],
    savedDatasets: [],
    zoom: 1,
    panX: 0,
    panY: 0,
    loading: false,
    error: null,
    progress: null,
  };
}

export const useDatasetStore = create<State>((set, get) => ({
  datasetId: null,
  datasetFormat: null,
  editableSource: false,
  sourceFolder: null,
  numImages: 0,
  currentIndex: 0,
  currentImage: null,
  thumbnails: [],
  duplicateGroups: [],
  savedDatasets: [],
  zoom: 1,
  panX: 0,
  panY: 0,
  loading: false,
  error: null,
  notifications: [],
  messageLog: [],
  progress: null,
  theme: initialTheme,
  showInspector: true,
  showCoordinateLabels: false,
  coordinateLabelFontSize: 5,
  showCrosshairCursor: false,
  autoFitOnImageChange: true,
  pushNotification(level, title, message) {
    const id = createId();
    const timestamp = new Date().toLocaleTimeString();
    set((state) => ({
      notifications: [...state.notifications, { id, level, title, message }],
      messageLog: [{ id, level, title, message, timestamp }, ...state.messageLog].slice(0, 100),
    }));
    window.setTimeout(() => {
      get().clearNotification(id);
    }, 4500);
  },
  clearNotification(id) {
    set((state) => ({
      notifications: state.notifications.filter((notification) => notification.id !== id),
    }));
  },
  clearMessageLog() {
    set({ messageLog: [] });
  },
  setProgress(progress) {
    set({ progress });
  },
  async uploadDataset(file: File) {
    set({ loading: true, error: null });
    get().setProgress({ label: `Uploading ${file.name}`, percent: 0 });
    try {
      const form = new FormData();
      form.append("file", file);
      const response = await api.post<UploadResponse>("/api/upload", form, {
        headers: { "Content-Type": "multipart/form-data" },
        onUploadProgress: (event) => {
          if (!event.total) return;
          const percent = Math.round((event.loaded / event.total) * 100);
          get().setProgress({
            label: percent >= 100 ? "Upload complete — extracting and parsing dataset" : `Uploading ${file.name}`,
            percent: percent >= 100 ? null : percent,
          });
        },
      });
      const datasetId = response.data.dataset_id;
      get().setProgress({ label: "Loading image list", percent: null });
      set({
        datasetId,
        datasetFormat: response.data.format,
        editableSource: response.data.editable_source,
        sourceFolder: response.data.source_folder,
        numImages: response.data.num_images,
        currentIndex: 0,
        thumbnails: [],
      });
      const images = await get().loadImages();
      if (images[0]) {
        await get().loadImage(images[0].index);
      }
      await get().loadSavedDatasets();
      get().pushNotification("success", "Dataset loaded", `${response.data.num_images} images detected as ${formatDatasetFormat(response.data.format)}.`);
      window.setTimeout(() => void get().loadDuplicates(), 100);
    } catch (error) {
      set({ error: error instanceof Error ? error.message : "Upload failed" });
      get().pushNotification("error", "Upload failed", error instanceof Error ? error.message : "Unable to upload or parse this dataset ZIP.");
    } finally {
      set({ loading: false });
      get().setProgress(null);
    }
  },
  async uploadMultipleDatasets(files) {
    if (files.length < 2) {
      get().pushNotification("warning", "Select multiple ZIP files", "Choose at least two dataset ZIP files to merge.");
      return;
    }
    set({ loading: true, error: null });
    get().setProgress({ label: `Uploading and merging ${files.length} ZIP files`, percent: 0 });
    try {
      const form = new FormData();
      for (const file of files) {
        form.append("files", file, file.name);
      }
      const response = await api.post<UploadResponse>("/api/upload-multiple", form, {
        headers: { "Content-Type": "multipart/form-data" },
        onUploadProgress: (event) => {
          if (!event.total) return;
          const percent = Math.round((event.loaded / event.total) * 100);
          get().setProgress({
            label: percent >= 100 ? "Upload complete — parsing and merging jobs" : `Uploading ${files.length} ZIP files`,
            percent: percent >= 100 ? null : percent,
          });
        },
      });
      const datasetId = response.data.dataset_id;
      get().setProgress({ label: "Loading merged image list", percent: null });
      set({
        datasetId,
        datasetFormat: response.data.format,
        editableSource: response.data.editable_source,
        sourceFolder: response.data.source_folder,
        numImages: response.data.num_images,
        currentIndex: 0,
        thumbnails: [],
        duplicateGroups: [],
      });
      const images = await get().loadImages();
      if (images[0]) {
        await get().loadImage(images[0].index);
      }
      await get().loadSavedDatasets();
      get().pushNotification("success", "Datasets merged", `${response.data.num_images} images loaded from ${files.length} ZIP files as one workspace.`);
      window.setTimeout(() => void get().loadDuplicates(), 100);
    } catch (error) {
      const message = describeError(error, "Unable to upload or merge these ZIP datasets.");
      set({ error: message });
      get().pushNotification("error", "Merge upload failed", message);
    } finally {
      set({ loading: false });
      get().setProgress(null);
    }
  },
  async uploadDatasetFolder(files) {
    if (files.length === 0) {
      get().pushNotification("warning", "Folder is empty", "Choose a dataset folder that contains images and annotations.");
      return;
    }
    set({ loading: true, error: null });
    const totalBytes = files.reduce((total, file) => total + file.size, 0);
    const uploadLabel = folderUploadLabel(files);
    get().setProgress({ label: uploadLabel, percent: totalBytes > 0 ? 0 : null });
    try {
      const form = new FormData();
      for (const file of files) {
        const relativePath = file.relativePath || file.webkitRelativePath || file.name;
        form.append("files", file, relativePath);
      }
      const response = await api.post<UploadResponse>("/api/upload-folder", form, {
        headers: { "Content-Type": "multipart/form-data" },
        onUploadProgress: (event) => {
          if (!event.total) return;
          const percent = Math.round((event.loaded / event.total) * 100);
          get().setProgress({
            label: percent >= 100 ? "Upload complete — parsing selected folder" : uploadLabel,
            percent: percent >= 100 ? null : percent,
          });
        },
      });
      const datasetId = response.data.dataset_id;
      get().setProgress({ label: "Loading image list", percent: null });
      set({
        datasetId,
        datasetFormat: response.data.format,
        editableSource: response.data.editable_source,
        sourceFolder: response.data.source_folder,
        numImages: response.data.num_images,
        currentIndex: 0,
        thumbnails: [],
        duplicateGroups: [],
      });
      const images = await get().loadImages();
      if (images[0]) {
        await get().loadImage(images[0].index);
      }
      await get().loadSavedDatasets();
      get().pushNotification("success", "Dataset folder loaded", `${response.data.num_images} images detected as ${formatDatasetFormat(response.data.format)}.`);
      window.setTimeout(() => void get().loadDuplicates(), 100);
    } catch (error) {
      const message = describeError(error, "Unable to upload or parse this dataset folder.");
      set({ error: message });
      get().pushNotification("error", "Folder upload failed", message);
    } finally {
      set({ loading: false });
      get().setProgress(null);
    }
  },
  async openLocalEditableFolder() {
    set({ loading: true, error: null });
    get().setProgress({ label: "Waiting for local folder selection", percent: null });
    try {
      const response = await api.post<UploadResponse>("/api/open-local-folder");
      const datasetId = response.data.dataset_id;
      get().setProgress({ label: "Loading editable source folder", percent: null });
      set({
        datasetId,
        datasetFormat: response.data.format,
        editableSource: response.data.editable_source,
        sourceFolder: response.data.source_folder,
        numImages: response.data.num_images,
        currentIndex: 0,
        thumbnails: [],
        duplicateGroups: [],
      });
      const images = await get().loadImages();
      if (images[0]) {
        await get().loadImage(images[0].index);
      }
      get().pushNotification(
        "success",
        response.data.editable_source ? "Editable local folder opened" : "Local folder opened",
        response.data.editable_source
          ? `${response.data.num_images} image${response.data.num_images === 1 ? "" : "s"} detected as ${formatDatasetFormat(response.data.format)}. Source write-back is available.`
          : `${response.data.num_images} image${response.data.num_images === 1 ? "" : "s"} detected as ${formatDatasetFormat(response.data.format)}. Use Export Dataset for this format.`,
      );
      window.setTimeout(() => void get().loadDuplicates(), 100);
    } catch (error) {
      const message = describeError(error, "Unable to open this local Pascal VOC folder.");
      set({ error: message });
      get().pushNotification("error", "Local folder open failed", message);
    } finally {
      set({ loading: false });
      get().setProgress(null);
    }
  },
  async loadSavedDatasets() {
    try {
      const response = await api.get<SavedDataset[]>("/api/datasets");
      set({ savedDatasets: response.data });
    } catch {
      set({ savedDatasets: [] });
    }
  },
  async resumeDataset(datasetId) {
    set({ loading: true, error: null });
    get().setProgress({ label: "Resuming saved workspace", percent: null });
    try {
      set({ datasetId, currentIndex: 0, currentImage: null, thumbnails: [] });
      const images = await get().loadImages();
      await get().loadDuplicates();
      const firstImage = images[0];
      if (firstImage) {
        await get().loadImage(firstImage.index);
      }
      get().pushNotification("success", "Workspace resumed", "Saved rotations, deletes, and annotation-dot edits were loaded.");
    } catch (error) {
      set(emptyDatasetState());
      get().pushNotification("error", "Resume failed", error instanceof Error ? error.message : "Unable to resume the saved workspace.");
    } finally {
      set({ loading: false });
      get().setProgress(null);
    }
  },
  async loadImage(index: number) {
    const datasetId = get().datasetId;
    if (!datasetId) return;
    set({ loading: true, error: null });
    get().setProgress({ label: `Loading image ${index + 1}`, percent: null });
    try {
      const response = await api.get<DatasetImage>(`/api/dataset/${datasetId}/image/${index}`);
      set((state) => ({
        currentIndex: index,
        currentImage: response.data,
        datasetFormat: response.data.format,
        editableSource: response.data.editable_source,
        sourceFolder: response.data.source_folder,
        thumbnails: state.thumbnails.some((item) => item.index === index)
          ? state.thumbnails.map((item) =>
              item.index === index
                ? {
                    ...item,
                    image_url: response.data.image_url,
                    width: response.data.width,
                    height: response.data.height,
                    rotation: response.data.rotation,
                    filename: response.data.filename,
                    format: response.data.format,
                    editable_source: response.data.editable_source,
                    source_folder: response.data.source_folder,
                    classification_label: response.data.classification_label,
                    annotation_count: response.data.annotations.length,
                  }
                : item,
            )
          : [
              ...state.thumbnails,
              {
                image_url: response.data.image_url,
                width: response.data.width,
                height: response.data.height,
                rotation: response.data.rotation,
                filename: response.data.filename,
                index: response.data.index,
                format: response.data.format,
                editable_source: response.data.editable_source,
                source_folder: response.data.source_folder,
                classification_label: response.data.classification_label,
                annotation_count: response.data.annotations.length,
              },
            ],
      }));
    } catch (error) {
      set({ error: error instanceof Error ? error.message : "Image load failed" });
    } finally {
      set({ loading: false });
      get().setProgress(null);
    }
  },
  async loadPreviousImage() {
    const { thumbnails, currentIndex } = get();
    const previousImage = [...thumbnails].reverse().find((image) => image.index < currentIndex) ?? thumbnails[0];
    if (previousImage) await get().loadImage(previousImage.index);
  },
  async loadNextImage() {
    const { thumbnails, currentIndex } = get();
    const nextImage = thumbnails.find((image) => image.index > currentIndex) ?? thumbnails[thumbnails.length - 1];
    if (nextImage) await get().loadImage(nextImage.index);
  },
  async rotateCurrent(direction) {
    const datasetId = get().datasetId;
    const currentIndex = get().currentIndex;
    if (!datasetId) return;
    get().setProgress({ label: "Rotating image and refreshing annotations", percent: null });
    await api.post(`/api/dataset/${datasetId}/rotate`, {
      image_index: currentIndex,
      direction,
    });
    await get().loadImage(currentIndex);
    if (get().autoFitOnImageChange) {
      get().fitToScreen();
    }
    get().pushNotification("info", "Image rotation updated", `Image ${currentIndex + 1} rotated ${direction}; annotations were refreshed for the new view.`);
    get().setProgress(null);
  },
  async rotateAnnotationOrientation(direction, label) {
    const datasetId = get().datasetId;
    const currentIndex = get().currentIndex;
    if (!datasetId) return;
    get().setProgress({ label: "Updating annotation dot direction", percent: null });
    try {
      const response = await api.post<{ updated: number }>(`/api/dataset/${datasetId}/annotation-orientation`, {
        image_index: currentIndex,
        direction,
        label,
      });
      await get().loadImage(currentIndex);
      const target = label ?? "all labels";
      const action = direction === "reset" ? "reset to the visual top edge" : `rotated ${direction}`;
      get().pushNotification("success", "Dot direction updated", `${response.data.updated} annotation dot(s) ${action} for ${target}.`);
    } catch (error) {
      get().pushNotification("error", "Dot update failed", error instanceof Error ? error.message : "Unable to update annotation dot direction.");
      throw error;
    } finally {
      get().setProgress(null);
    }
  },
  async setClassificationLabel(label, applyToAll) {
    const datasetId = get().datasetId;
    const currentIndex = get().currentIndex;
    const normalizedLabel = label.trim();
    if (!datasetId || !normalizedLabel) {
      get().pushNotification("warning", "Classification label required", "Type or choose a label before applying it.");
      return;
    }
    get().setProgress({ label: applyToAll ? "Applying classification label to all images" : "Applying classification label", percent: null });
    try {
      const response = await api.post<{ updated: number; label: string }>(`/api/dataset/${datasetId}/classification-label`, {
        image_index: currentIndex,
        label: normalizedLabel,
        apply_to_all: applyToAll,
      });
      const images = await get().loadImages();
      const currentImage = images.find((image) => image.index === currentIndex);
      if (currentImage) {
        await get().loadImage(currentImage.index);
      }
      get().pushNotification(
        "success",
        "Classification label applied",
        `${response.data.label} assigned to ${response.data.updated} image${response.data.updated === 1 ? "" : "s"}.`,
      );
    } catch (error) {
      get().pushNotification("error", "Classification update failed", describeError(error, "Unable to update classification labels."));
    } finally {
      get().setProgress(null);
    }
  },
  async resetCurrent() {
    const datasetId = get().datasetId;
    const currentIndex = get().currentIndex;
    if (!datasetId) return;
    get().setProgress({ label: "Resetting image rotation", percent: null });
    await api.post(`/api/dataset/${datasetId}/reset-rotation`, {
      image_index: currentIndex,
      direction: "180",
    });
    await get().loadImage(currentIndex);
    if (get().autoFitOnImageChange) {
      get().fitToScreen();
    }
    get().pushNotification("info", "Image rotation reset", `Image ${currentIndex + 1} returned to 0°.`);
    get().setProgress(null);
  },
  async deleteCurrent() {
    const datasetId = get().datasetId;
    const currentIndex = get().currentIndex;
    if (!datasetId) return;
    get().setProgress({ label: "Deleting image", percent: null });
    await api.post(`/api/dataset/${datasetId}/delete`, {
      image_index: currentIndex,
      direction: "180",
    });
    const images = await get().loadImages();
    await get().loadDuplicates();
    const nextImage = images.find((image) => image.index > currentIndex) ?? images[images.length - 1] ?? null;
    if (nextImage) {
      await get().loadImage(nextImage.index);
      if (get().autoFitOnImageChange) {
        get().fitToScreen();
      }
    }
    get().pushNotification("warning", "Image removed from export", `Image ${currentIndex + 1} was marked deleted for this workspace.`);
    get().setProgress(null);
  },
  async loadImages() {
    const datasetId = get().datasetId;
    if (!datasetId) return [];
    const response = await api.get<DatasetImageSummary[]>(`/api/dataset/${datasetId}/images`);
    set((state) => ({
      thumbnails: response.data,
      numImages: response.data.length,
      datasetFormat: response.data[0]?.format ?? state.datasetFormat,
      editableSource: response.data[0]?.editable_source ?? state.editableSource,
      sourceFolder: response.data[0]?.source_folder ?? state.sourceFolder,
    }));
    return response.data;
  },
  async loadDuplicates() {
    const datasetId = get().datasetId;
    if (!datasetId) return [];
    get().setProgress({ label: "Calculating duplicate image hashes", percent: null });
    try {
      const response = await api.get<DuplicateImageGroup[]>(`/api/dataset/${datasetId}/duplicates`);
      set({ duplicateGroups: response.data });
      if (response.data.length > 0) {
        const duplicateCount = response.data.reduce((total, group) => total + group.images.length, 0);
        get().pushNotification("warning", "Duplicate images found", `${duplicateCount} images share MD5 hashes across ${response.data.length} duplicate group${response.data.length === 1 ? "" : "s"}.`);
      }
      return response.data;
    } catch (error) {
      get().pushNotification("error", "Duplicate scan failed", error instanceof Error ? error.message : "Unable to calculate image MD5 hashes.");
      return [];
    } finally {
      get().setProgress(null);
    }
  },
  async deleteDuplicateImages(imageIndexes) {
    const datasetId = get().datasetId;
    if (!datasetId || imageIndexes.length === 0) return;
    get().setProgress({ label: "Removing selected duplicates", percent: null });
    try {
      await api.post(`/api/dataset/${datasetId}/delete-images`, { image_indexes: imageIndexes });
      const images = await get().loadImages();
      await get().loadDuplicates();
      const currentIndex = get().currentIndex;
      if (!images.some((image) => image.index === currentIndex)) {
        const nextImage = images[0];
        if (nextImage) await get().loadImage(nextImage.index);
      }
      get().pushNotification("warning", "Images removed from export", `${imageIndexes.length} selected image${imageIndexes.length === 1 ? "" : "s"} excluded from this workspace.`);
    } catch (error) {
      get().pushNotification("error", "Duplicate removal failed", error instanceof Error ? error.message : "Unable to remove selected duplicates.");
    } finally {
      get().setProgress(null);
    }
  },
  async applyImageRotations() {
    const datasetId = get().datasetId;
    if (!datasetId) return;
    get().setProgress({ label: "Applying rotations to workspace image files", percent: null });
    try {
      const response = await api.post<{ updated: number }>(`/api/dataset/${datasetId}/apply-image-rotations`);
      const images = await get().loadImages();
      await get().loadDuplicates();
      const currentIndex = get().currentIndex;
      const currentImage = images.find((image) => image.index === currentIndex) ?? images[0];
      if (currentImage) {
        await get().loadImage(currentImage.index);
      }
      get().pushNotification(
        response.data.updated > 0 ? "success" : "info",
        "Rotations applied",
        response.data.updated > 0
          ? `${response.data.updated} workspace image file${response.data.updated === 1 ? "" : "s"} updated and image rotations reset to 0°.`
          : "No pending image rotations were found.",
      );
    } catch (error) {
      get().pushNotification("error", "Apply rotations failed", error instanceof Error ? error.message : "Unable to apply rotations to workspace image files.");
    } finally {
      get().setProgress(null);
    }
  },
  async applySourceChanges() {
    const datasetId = get().datasetId;
    if (!datasetId) return;
    get().setProgress({ label: "Applying pending rotations to the source folder", percent: null });
    try {
      const response = await api.post<{ updated: number; backup_path: string | null }>(`/api/dataset/${datasetId}/apply-to-source`);
      const images = await get().loadImages();
      await get().loadDuplicates();
      const currentIndex = get().currentIndex;
      const currentImage = images.find((image) => image.index === currentIndex) ?? images[0];
      if (currentImage) {
        await get().loadImage(currentImage.index);
      }
      get().pushNotification(
        response.data.updated > 0 ? "success" : "info",
        "Source folder updated",
        response.data.updated > 0
          ? `${response.data.updated} source file set${response.data.updated === 1 ? "" : "s"} updated. Backup: ${response.data.backup_path}`
          : "No pending source-folder rotations were found.",
      );
    } catch (error) {
      get().pushNotification("error", "Apply to source failed", describeError(error, "Unable to update the original Pascal VOC folder."));
    } finally {
      get().setProgress(null);
    }
  },
  async saveDataset() {
    const datasetId = get().datasetId;
    if (!datasetId) return;
    get().setProgress({ label: "Saving workspace state", percent: null });
    try {
      await api.post(`/api/dataset/${datasetId}/save`);
      get().pushNotification("success", "Workspace saved", "Rotations, deleted images, and annotation-dot edits were saved for resume.");
    } catch (error) {
      get().pushNotification("error", "Save failed", error instanceof Error ? error.message : "Unable to save this workspace.");
      throw error;
    } finally {
      get().setProgress(null);
    }
  },
  async startOver(mode) {
    const datasetId = get().datasetId;
    if (!datasetId) {
      set(emptyDatasetState());
      return;
    }
    try {
      if (mode === "save") {
        await get().saveDataset();
        set(emptyDatasetState());
        await get().loadSavedDatasets();
        get().pushNotification("success", "Started over", "Workspace was saved. You can upload or resume another dataset.");
        return;
      }
      if (mode === "export") {
        get().setProgress({ label: "Exporting CVAT ZIP before start over", percent: null });
        const settingsResponse = await api.get<{ export_mode: "ask" | "folder" }>("/api/settings");
        if (settingsResponse.data.export_mode === "folder") {
          await api.post(`/api/dataset/${datasetId}/export-to-folder?export_format=cvat_for_images_1_1`);
        } else {
          const response = await api.get(`/api/dataset/${datasetId}/download?export_format=cvat_for_images_1_1`, {
            responseType: "blob",
            onDownloadProgress: (event) => {
              if (!event.total) return;
              get().setProgress({
                label: "Downloading export",
                percent: Math.round((event.loaded / event.total) * 100),
              });
            },
          });
          const objectUrl = downloadBlobUrl(response.data);
          const anchor = document.createElement("a");
          anchor.href = objectUrl;
          anchor.download = `${datasetId}-cvat_for_images_1_1.zip`;
          anchor.click();
          window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1500);
        }
      }
      get().setProgress({ label: "Clearing current workspace", percent: null });
      await api.delete(`/api/dataset/${datasetId}`);
      set(emptyDatasetState());
      await get().loadSavedDatasets();
      get().pushNotification(mode === "export" ? "success" : "warning", "Started over", mode === "export" ? "CVAT ZIP was exported and the workspace was cleared." : "Temporary workspace was discarded.");
    } catch (error) {
      get().pushNotification("error", "Start over failed", error instanceof Error ? error.message : "Unable to save, export, or discard this workspace.");
      throw error;
    } finally {
      get().setProgress(null);
    }
  },
  setZoom(zoom) {
    set({ zoom });
  },
  setPan(panX, panY) {
    set({ panX, panY });
  },
  setCurrentIndex(index) {
    set({ currentIndex: index });
  },
  setTheme(theme) {
    set({ theme });
    window.localStorage.setItem("theme", theme);
  },
  toggleTheme() {
    const nextTheme = get().theme === "dark" ? "light" : "dark";
    set({ theme: nextTheme });
    window.localStorage.setItem("theme", nextTheme);
  },
  setShowInspector(enabled) {
    set({ showInspector: enabled });
  },
  setShowCoordinateLabels(enabled) {
    set({ showCoordinateLabels: enabled });
  },
  setCoordinateLabelFontSize(fontSize) {
    set({ coordinateLabelFontSize: Math.min(24, Math.max(3, fontSize)) });
  },
  setShowCrosshairCursor(enabled) {
    set({ showCrosshairCursor: enabled });
  },
  setAutoFitOnImageChange(enabled) {
    set({ autoFitOnImageChange: enabled });
  },
  fitToScreen() {
    const currentImage = get().currentImage;
    if (!currentImage) return;
    const availableWidth = Math.max(window.innerWidth - 320 - 48, 640);
    const availableHeight = Math.max(window.innerHeight - 180 - 48, 480);
    const rotation = ((currentImage.rotation % 360) + 360) % 360;
    const displayWidth = rotation === 90 || rotation === 270 ? currentImage.height : currentImage.width;
    const displayHeight = rotation === 90 || rotation === 270 ? currentImage.width : currentImage.height;
    const zoom = Math.min(availableWidth / displayWidth, availableHeight / displayHeight, 1);
    set({ zoom, panX: 0, panY: 0 });
  },
  async exportDataset(startIndex, endIndex, exportFormat) {
    const datasetId = get().datasetId;
    if (!datasetId) return;
    const params = new URLSearchParams();
    params.set("export_format", exportFormat);
    if (startIndex !== null) {
      params.set("start_index", String(startIndex));
    }
    if (endIndex !== null) {
      params.set("end_index", String(endIndex));
    }
    const url = `/api/dataset/${datasetId}/download?${params.toString()}`;
    get().setProgress({ label: "Preparing dataset export", percent: null });
    try {
      const settingsResponse = await api.get<{ export_mode: "ask" | "folder" }>("/api/settings");
      if (settingsResponse.data.export_mode === "folder") {
        const response = await api.post<{ filename: string; path: string }>(
          `/api/dataset/${datasetId}/export-to-folder?${params.toString()}`,
        );
        get().pushNotification("success", "Export saved to folder", response.data.path);
        return;
      }
      const response = await api.get(url, {
        responseType: "blob",
        onDownloadProgress: (event) => {
          if (!event.total) return;
          get().setProgress({
            label: "Downloading export",
            percent: Math.round((event.loaded / event.total) * 100),
          });
        },
      });
      const objectUrl = downloadBlobUrl(response.data);
      const anchor = document.createElement("a");
      anchor.href = objectUrl;
      anchor.download = `${datasetId}-${exportFormat}.zip`;
      anchor.click();
      window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1500);
      get().pushNotification("success", "Export ready", "Your corrected dataset ZIP has been downloaded.");
    } catch (error) {
      get().pushNotification("error", "Export failed", error instanceof Error ? error.message : "Unable to export the corrected dataset.");
    } finally {
      get().setProgress(null);
    }
  },
}));
