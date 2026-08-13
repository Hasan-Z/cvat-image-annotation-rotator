export type AnnotationType =
  | "rectangle"
  | "polygon"
  | "polyline"
  | "points"
  | "ellipse"
  | "cuboid"
  | "skeleton"
  | "mask"
  | "rotated_rectangle";

export type Annotation = {
  id: string;
  type: AnnotationType;
  label: string;
  attributes: Record<string, unknown>;
  geometry: Record<string, unknown>;
};

export type DatasetImage = {
  image_url: string;
  width: number;
  height: number;
  rotation: number;
  annotations: Annotation[];
  filename: string;
  index: number;
  format: string;
  editable_source: boolean;
  source_folder: string | null;
  classification_label: string | null;
  labels: string[];
};

export type DatasetImageSummary = Pick<
  DatasetImage,
  "image_url" | "width" | "height" | "rotation" | "filename" | "index" | "format" | "editable_source" | "source_folder" | "classification_label"
> & {
  annotation_count: number;
};

export type DuplicateImageItem = {
  index: number;
  filename: string;
  width: number;
  height: number;
  image_url: string;
};

export type DuplicateImageGroup = {
  md5: string;
  images: DuplicateImageItem[];
};

export type UploadResponse = {
  dataset_id: string;
  num_images: number;
  format: string;
  editable_source: boolean;
  source_folder: string | null;
};

export type SavedDataset = UploadResponse;

export type NotificationLevel = "info" | "success" | "warning" | "error";

export type Notification = {
  id: string;
  level: NotificationLevel;
  title: string;
  message: string;
};

export type MessageLogEntry = Notification & {
  timestamp: string;
};

export type ProgressState = {
  label: string;
  percent: number | null;
};
