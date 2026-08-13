from __future__ import annotations

from pathlib import Path

from lxml import etree

from backend.app.models import Annotation, AnnotationType, DatasetManifest, ImageInfo


def parse_cvat_xml(xml_path: Path, image_root: Path) -> DatasetManifest:
    tree = etree.parse(str(xml_path))
    root = tree.getroot()
    images: list[ImageInfo] = []
    annotations: dict[str, list[Annotation]] = {}
    labels = sorted(
        {
            label_node.findtext("name", default="").strip()
            for label_node in root.findall(".//meta//label")
            if label_node.findtext("name", default="").strip()
        }
    )

    for image_node in root.findall(".//image"):
        filename = image_node.get("name", "")
        width = int(image_node.get("width", "0"))
        height = int(image_node.get("height", "0"))
        images.append(ImageInfo(filename=filename, width=width, height=height))

        parsed_annotations: list[Annotation] = []
        for child in image_node:
            tag = child.tag
            if tag == "box":
                xtl = float(child.get("xtl", "0"))
                ytl = float(child.get("ytl", "0"))
                xbr = float(child.get("xbr", "0"))
                ybr = float(child.get("ybr", "0"))
                rotation = float(child.get("rotation", "0") or 0)
                parsed_annotations.append(
                    Annotation(
                        id=child.get("id", ""),
                        type=AnnotationType.rectangle,
                        label=child.get("label", ""),
                        attributes={},
                        geometry={"x1": xtl, "y1": ytl, "x2": xbr, "y2": ybr, "angle": rotation},
                    )
                )
            elif tag == "polygon":
                points = [
                    [float(coord.split(",")[0]), float(coord.split(",")[1])]
                    for coord in child.get("points", "").split(";")
                    if coord
                ]
                parsed_annotations.append(
                    Annotation(
                        id=child.get("id", ""),
                        type=AnnotationType.polygon,
                        label=child.get("label", ""),
                        attributes={},
                        geometry={"points": points},
                    )
                )
            elif tag == "polyline":
                points = [
                    [float(coord.split(",")[0]), float(coord.split(",")[1])]
                    for coord in child.get("points", "").split(";")
                    if coord
                ]
                parsed_annotations.append(
                    Annotation(
                        id=child.get("id", ""),
                        type=AnnotationType.polyline,
                        label=child.get("label", ""),
                        attributes={},
                        geometry={"points": points},
                    )
                )
            elif tag == "points":
                points = [
                    [float(coord.split(",")[0]), float(coord.split(",")[1])]
                    for coord in child.get("points", "").split(";")
                    if coord
                ]
                parsed_annotations.append(
                    Annotation(
                        id=child.get("id", ""),
                        type=AnnotationType.points,
                        label=child.get("label", ""),
                        attributes={},
                        geometry={"points": points},
                    )
                )
        annotations[filename] = parsed_annotations

    inferred_labels = sorted({annotation.label for items in annotations.values() for annotation in items if annotation.label})
    return DatasetManifest(format="cvat_xml", images=images, annotations=annotations, labels=labels or inferred_labels)
