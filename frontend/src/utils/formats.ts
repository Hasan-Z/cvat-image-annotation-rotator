const formatLabels: Record<string, string> = {
  app_bundle: "App Bundle",
  coco: "COCO",
  cvat_xml: "CVAT for images 1.1",
  cvat_for_images_1_1: "CVAT for images 1.1",
  datumaro: "Datumaro",
  kitti: "KITTI",
  image_folder: "Image folder",
  image_classification: "Image Classification",
  labelme: "LabelMe",
  merged: "Merged jobs",
  modelarts_pascal_voc: "ModelArts Pascal VOC",
  open_images: "Open Images",
  pascal_voc: "Pascal VOC",
  segmentation_mask: "Segmentation Mask",
  yolo: "YOLO / Ultralytics",
  unknown: "Unknown",
};

export function formatDatasetFormat(format: string | null | undefined): string {
  if (!format) return "Unknown";
  return formatLabels[format] ?? format;
}
