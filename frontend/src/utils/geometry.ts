import type { Annotation } from "../types";

export function normalizeRotation(rotation: number): number {
  return ((rotation % 360) + 360) % 360;
}

export function getRotatedDimensions(width: number, height: number, rotation: number): { width: number; height: number } {
  const normalized = normalizeRotation(rotation);
  if (normalized === 90 || normalized === 270) {
    return { width: height, height: width };
  }
  return { width, height };
}

function rotatePoint(x: number, y: number, width: number, height: number, rotation: number): [number, number] {
  const normalized = normalizeRotation(rotation);
  if (normalized === 90) {
    return [height - y, x];
  }
  if (normalized === 180) {
    return [width - x, height - y];
  }
  if (normalized === 270) {
    return [y, width - x];
  }
  return [x, y];
}

function rotatePoints(points: number[][], width: number, height: number, rotation: number): number[][] {
  return points.map(([x, y]) => rotatePoint(x, y, width, height, rotation).map((value) => Number(value)));
}

export function rectangleDirectionDot(geometry: Record<string, unknown>): { x: number; y: number } {
  const x1 = Number(geometry.x1);
  const y1 = Number(geometry.y1);
  const x2 = Number(geometry.x2);
  const y2 = Number(geometry.y2);
  const angle = normalizeRotation(Number(geometry.angle ?? 0));
  const centerX = (x1 + x2) / 2;
  const centerY = (y1 + y2) / 2;
  const halfHeight = Math.abs(y2 - y1) / 2;
  const radians = (angle * Math.PI) / 180;
  return {
    x: centerX + Math.sin(radians) * halfHeight,
    y: centerY - Math.cos(radians) * halfHeight,
  };
}

function rectanglePoints(geometry: Record<string, unknown>): number[][] {
  const x1 = Number(geometry.x1);
  const y1 = Number(geometry.y1);
  const x2 = Number(geometry.x2);
  const y2 = Number(geometry.y2);
  const angle = normalizeRotation(Number(geometry.angle ?? 0));
  const centerX = (x1 + x2) / 2;
  const centerY = (y1 + y2) / 2;
  const halfWidth = (x2 - x1) / 2;
  const halfHeight = (y2 - y1) / 2;
  const corners = [
    [-halfWidth, -halfHeight],
    [halfWidth, -halfHeight],
    [halfWidth, halfHeight],
    [-halfWidth, halfHeight],
  ];
  if (angle === 0) {
    return [
      [x1, y1],
      [x2, y1],
      [x2, y2],
      [x1, y2],
    ];
  }
  const radians = (angle * Math.PI) / 180;
  const cosAngle = Math.cos(radians);
  const sinAngle = Math.sin(radians);
  return corners.map(([localX, localY]) => [
    centerX + localX * cosAngle - localY * sinAngle,
    centerY + localX * sinAngle + localY * cosAngle,
  ]);
}

export function rotateAnnotationForDisplay(annotation: Annotation, width: number, height: number, rotation: number): Annotation {
  const normalized = normalizeRotation(rotation);
  if (normalized === 0) {
    return annotation;
  }

  const geometry = annotation.geometry as Record<string, unknown>;
  switch (annotation.type) {
    case "rectangle": {
      const x1 = Number(geometry.x1);
      const y1 = Number(geometry.y1);
      const x2 = Number(geometry.x2);
      const y2 = Number(geometry.y2);
      const [centerX, centerY] = rotatePoint((x1 + x2) / 2, (y1 + y2) / 2, width, height, normalized);
      const boxWidth = x2 - x1;
      const boxHeight = y2 - y1;
      return {
        ...annotation,
        geometry: {
          ...geometry,
          x1: centerX - boxWidth / 2,
          y1: centerY - boxHeight / 2,
          x2: centerX + boxWidth / 2,
          y2: centerY + boxHeight / 2,
          angle: normalizeRotation(Number(geometry.angle ?? 0) + normalized),
          display_angle:
            geometry.display_angle === undefined
              ? undefined
              : normalizeRotation(Number(geometry.display_angle ?? 0) + normalized),
        },
      };
    }
    case "polygon":
    case "polyline":
    case "points":
      return { ...annotation, geometry: { ...geometry, points: rotatePoints(geometry.points as number[][], width, height, normalized) } };
    case "ellipse": {
      const [cx, cy] = rotatePoint(Number(geometry.cx), Number(geometry.cy), width, height, normalized);
      return { ...annotation, geometry: { ...geometry, cx, cy, angle: ((Number(geometry.angle ?? 0) + normalized) % 360 + 360) % 360 } };
    }
    case "rotated_rectangle":
      return {
        ...annotation,
        geometry: {
          ...geometry,
          points: rotatePoints(geometry.points as number[][], width, height, normalized),
          angle: ((Number(geometry.angle ?? 0) + normalized) % 360 + 360) % 360,
        },
      };
    case "cuboid":
      return {
        ...annotation,
        geometry: {
          ...geometry,
          faces: (geometry.faces as number[][][] | undefined)?.map((face) => rotatePoints(face, width, height, normalized)) ?? [],
        },
      };
    case "skeleton": {
      const nodes = geometry.nodes as Record<string, [number, number]> | undefined;
      const rotatedNodes = Object.fromEntries(
        Object.entries(nodes ?? {}).map(([key, point]) => [key, rotatePoint(point[0], point[1], width, height, normalized)]),
      );
      return { ...annotation, geometry: { ...geometry, nodes: rotatedNodes } };
    }
    default:
      return annotation;
  }
}

function formatNumber(value: number): string {
  const rounded = Number(value.toFixed(2));
  return Number.isInteger(rounded) ? String(rounded) : rounded.toFixed(2).replace(/\.00$/, "");
}

function formatPointList(points: number[][]): string {
  return points.map(([x, y]) => `(${formatNumber(x)}, ${formatNumber(y)})`).join(", ");
}

export function formatAnnotationGeometry(annotation: Annotation): string {
  const geometry = annotation.geometry as Record<string, unknown>;
  switch (annotation.type) {
    case "rectangle":
      return `x1=${formatNumber(Number(geometry.x1))}, y1=${formatNumber(Number(geometry.y1))}, x2=${formatNumber(Number(geometry.x2))}, y2=${formatNumber(Number(geometry.y2))}, angle=${formatNumber(Number(geometry.angle ?? 0))}°`;
    case "polygon":
    case "polyline":
    case "points":
      return formatPointList(geometry.points as number[][]);
    case "ellipse":
      return `cx=${formatNumber(Number(geometry.cx))}, cy=${formatNumber(Number(geometry.cy))}, rx=${formatNumber(Number(geometry.rx))}, ry=${formatNumber(Number(geometry.ry))}`;
    case "rotated_rectangle":
      return `points=${formatPointList(geometry.points as number[][])}`;
    case "cuboid":
      return `faces=${(geometry.faces as number[][][] | undefined)?.length ?? 0}`;
    case "skeleton":
      return `nodes=${Object.keys((geometry.nodes as Record<string, [number, number]> | undefined) ?? {}).length}`;
    case "mask":
      return "mask";
    default:
      return JSON.stringify(annotation.geometry);
  }
}

function getAnnotationBounds(annotation: Annotation): { minX: number; minY: number; maxX: number; maxY: number } | null {
  const geometry = annotation.geometry as Record<string, unknown>;
  if (annotation.type === "rectangle") {
    const points = rectanglePoints(geometry);
    const xs = points.map(([x]) => x);
    const ys = points.map(([, y]) => y);
    return {
      minX: Math.min(...xs),
      minY: Math.min(...ys),
      maxX: Math.max(...xs),
      maxY: Math.max(...ys),
    };
  }
  if (annotation.type === "ellipse") {
    const cx = Number(geometry.cx);
    const cy = Number(geometry.cy);
    const rx = Number(geometry.rx);
    const ry = Number(geometry.ry);
    return {
      minX: cx - rx,
      minY: cy - ry,
      maxX: cx + rx,
      maxY: cy + ry,
    };
  }
  const points = annotation.type === "cuboid" ? ((geometry.faces as number[][][] | undefined) ?? []).flat() : (geometry.points as number[][] | undefined);
  if (!points || points.length === 0) {
    const nodes = geometry.nodes as Record<string, [number, number]> | undefined;
    if (!nodes) return null;
    const nodePoints = Object.values(nodes);
    if (nodePoints.length === 0) return null;
    const xs = nodePoints.map(([x]) => x);
    const ys = nodePoints.map(([, y]) => y);
    return {
      minX: Math.min(...xs),
      minY: Math.min(...ys),
      maxX: Math.max(...xs),
      maxY: Math.max(...ys),
    };
  }
  const xs = points.map(([x]) => x);
  const ys = points.map(([, y]) => y);
  return {
    minX: Math.min(...xs),
    minY: Math.min(...ys),
    maxX: Math.max(...xs),
    maxY: Math.max(...ys),
  };
}

export function isAnnotationWithinBounds(annotation: Annotation, width: number, height: number): boolean {
  const bounds = getAnnotationBounds(annotation);
  if (!bounds) {
    return true;
  }
  const epsilon = 0.01;
  return bounds.minX >= -epsilon && bounds.minY >= -epsilon && bounds.maxX <= width + epsilon && bounds.maxY <= height + epsilon;
}
