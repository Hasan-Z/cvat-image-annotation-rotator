import { useEffect, useMemo, useRef, useState } from "react";
import { Stage, Layer, Group, Image as KonvaImage, Rect, Line, Circle, Ellipse as KonvaEllipse, Text } from "react-konva";
import useImage from "use-image";
import { Stage as KonvaStage } from "konva/lib/Stage";
import { useDatasetStore } from "../store/useDatasetStore";
import type { Annotation } from "../types";
import {
  formatAnnotationGeometry,
  getRotatedDimensions,
  isAnnotationWithinBounds,
  normalizeRotation,
  rectangleDirectionDot,
  rotateAnnotationForDisplay,
} from "../utils/geometry";

function labelColor(label: string): string {
  const hash = Array.from(label).reduce((accumulator, character) => accumulator + character.charCodeAt(0), 0);
  const colors = ["#38bdf8", "#f472b6", "#34d399", "#f59e0b", "#a78bfa", "#fb7185"];
  return colors[hash % colors.length];
}

function getRotationLayout(stageWidth: number, stageHeight: number, imageWidth: number, imageHeight: number, rotation: number) {
  const normalized = normalizeRotation(rotation);
  return {
    stageWidth,
    stageHeight,
    groupX: stageWidth / 2,
    groupY: stageHeight / 2,
    groupOffsetX: imageWidth / 2,
    groupOffsetY: imageHeight / 2,
    groupRotation: normalized,
  };
}

function AnnotationShape({ annotation }: { annotation: Annotation }) {
  const color = labelColor(annotation.label);
  if (annotation.type === "rectangle" || annotation.type === "rotated_rectangle") {
    if (annotation.type === "rotated_rectangle" && Array.isArray(annotation.geometry.points)) {
      const points = (annotation.geometry.points as number[][]).flat();
      return <Line points={points} closed stroke={color} strokeWidth={2} />;
    }
    const { x1, y1, x2, y2, angle = 0, display_angle } = annotation.geometry as { x1: number; y1: number; x2: number; y2: number; angle?: number; display_angle?: number };
    const rectWidth = x2 - x1;
    const rectHeight = y2 - y1;
    return (
      <Rect
        x={(x1 + x2) / 2}
        y={(y1 + y2) / 2}
        width={rectWidth}
        height={rectHeight}
        offsetX={rectWidth / 2}
        offsetY={rectHeight / 2}
        rotation={display_angle ?? angle}
        stroke={color}
        strokeWidth={2}
      />
    );
  }
  if (annotation.type === "polygon" || annotation.type === "polyline") {
    const points = (annotation.geometry.points as number[][]).flat();
    return <Line points={points} closed={annotation.type === "polygon"} stroke={color} strokeWidth={2} />;
  }
  if (annotation.type === "points") {
    const points = annotation.geometry.points as number[][];
    return (
      <>
        {points.map(([x, y], index) => (
          <Circle key={index} x={x} y={y} radius={4} fill={color} />
        ))}
      </>
    );
  }
  if (annotation.type === "ellipse") {
    const { cx, cy, rx, ry } = annotation.geometry as { cx: number; cy: number; rx: number; ry: number };
    return <KonvaEllipse x={cx} y={cy} radiusX={rx} radiusY={ry} stroke={color} strokeWidth={2} />;
  }
  if (annotation.type === "cuboid" && Array.isArray(annotation.geometry.faces)) {
    const firstFace = annotation.geometry.faces[0] as number[][];
    return <Line points={firstFace.flat()} closed stroke={color} strokeWidth={2} />;
  }
  if (annotation.type === "skeleton" && annotation.geometry.nodes) {
    const nodes = annotation.geometry.nodes as Record<string, [number, number]>;
    const edges = (annotation.geometry.edges as [string, string][]) ?? [];
    return (
      <>
        {edges.map(([from, to], index) => {
          const start = nodes[from];
          const end = nodes[to];
          if (!start || !end) {
            return null;
          }
          return <Line key={index} points={[start[0], start[1], end[0], end[1]]} stroke={color} strokeWidth={2} />;
        })}
        {Object.values(nodes).map(([x, y], index) => (
          <Circle key={index} x={x} y={y} radius={4} fill={color} />
        ))}
      </>
    );
  }
  return null;
}

function rectangleCornersForGeometry(geometry: Record<string, unknown>): number[][] {
  const x1 = Number(geometry.x1);
  const y1 = Number(geometry.y1);
  const x2 = Number(geometry.x2);
  const y2 = Number(geometry.y2);
  const angle = normalizeRotation(Number(geometry.display_angle ?? geometry.angle ?? 0));
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
  const radians = (angle * Math.PI) / 180;
  const cosAngle = Math.cos(radians);
  const sinAngle = Math.sin(radians);
  return corners.map(([localX, localY]) => [
    centerX + localX * cosAngle - localY * sinAngle,
    centerY + localX * sinAngle + localY * cosAngle,
  ]);
}

function visualTopEdgeDot(points: number[][]): { x: number; y: number } {
  const edges = points.map((point, index) => {
    const next = points[(index + 1) % points.length];
    return {
      midpoint: { x: (point[0] + next[0]) / 2, y: (point[1] + next[1]) / 2 },
      averageY: (point[1] + next[1]) / 2,
    };
  });
  return edges.reduce((topEdge, edge) => (edge.averageY < topEdge.averageY ? edge : topEdge)).midpoint;
}

function visualTopEdgeFirstCorner(points: number[][]): number {
  const edges = points.map((point, index) => {
    const nextIndex = (index + 1) % points.length;
    const next = points[nextIndex];
    const firstIndex = point[0] <= next[0] ? index : nextIndex;
    return {
      averageY: (point[1] + next[1]) / 2,
      firstIndex,
    };
  });
  return edges.reduce((topEdge, edge) => (edge.averageY < topEdge.averageY ? edge : topEdge)).firstIndex;
}

function displayAngleFirstCornerIndex(angle: number): number {
  const normalized = normalizeRotation(angle);
  if (normalized === 90) return 1;
  if (normalized === 180) return 2;
  if (normalized === 270) return 3;
  return 0;
}

function orientedDiagonalCorners(points: number[][], forceVisualTopEdge: boolean): { first: number[]; second: number[] } | null {
  if (points.length < 3) return null;
  if (!forceVisualTopEdge) {
    return { first: points[0], second: points[2] };
  }
  const firstIndex = visualTopEdgeFirstCorner(points);
  const secondIndex = (firstIndex + 2) % points.length;
  return { first: points[firstIndex], second: points[secondIndex] };
}

function resetDotDiagonalCorners(points: number[][], previousDisplayAngle: number): { first: number[]; second: number[] } | null {
  if (points.length < 3) return null;
  const previousFirstIndex = displayAngleFirstCornerIndex(previousDisplayAngle);
  const firstIndex = (previousFirstIndex + 3) % points.length;
  const secondIndex = (firstIndex + 2) % points.length;
  return { first: points[firstIndex], second: points[secondIndex] };
}

function formatCoordinate(value: number): string {
  const rounded = Number(value.toFixed(2));
  return Number.isInteger(rounded) ? String(rounded) : rounded.toFixed(2);
}

function transformImagePointToStage(x: number, y: number, width: number, height: number, rotation: number): { x: number; y: number } {
  const normalized = normalizeRotation(rotation);
  const rotatedDimensions = getRotatedDimensions(width, height, normalized);
  const groupX = rotatedDimensions.width / 2;
  const groupY = rotatedDimensions.height / 2;
  const localX = x - width / 2;
  const localY = y - height / 2;
  if (normalized === 90) {
    return { x: groupX - localY, y: groupY + localX };
  }
  if (normalized === 180) {
    return { x: groupX - localX, y: groupY - localY };
  }
  if (normalized === 270) {
    return { x: groupX + localY, y: groupY - localX };
  }
  return { x: groupX + localX, y: groupY + localY };
}

function displayTransform(width: number, height: number, rotation: number): { originX: number; originY: number; width: number; height: number } {
  const corners = [
    transformImagePointToStage(0, 0, width, height, rotation),
    transformImagePointToStage(width, 0, width, height, rotation),
    transformImagePointToStage(width, height, width, height, rotation),
    transformImagePointToStage(0, height, width, height, rotation),
  ];
  const xs = corners.map((point) => point.x);
  const ys = corners.map((point) => point.y);
  return {
    originX: Math.min(...xs),
    originY: Math.min(...ys),
    width: Math.max(...xs) - Math.min(...xs),
    height: Math.max(...ys) - Math.min(...ys),
  };
}

function boundsFromPoints(points: number[][]): { minX: number; minY: number; maxX: number; maxY: number } | null {
  if (points.length === 0) return null;
  const xs = points.map(([x]) => Number(x));
  const ys = points.map(([, y]) => Number(y));
  return {
    minX: Math.min(...xs),
    minY: Math.min(...ys),
    maxX: Math.max(...xs),
    maxY: Math.max(...ys),
  };
}

function annotationBounds(annotation: Annotation): { x1: number; y1: number; x2: number; y2: number } | null {
  const geometry = annotation.geometry as Record<string, unknown>;
  if (annotation.type === "rectangle") {
    return {
      x1: Number(geometry.x1),
      y1: Number(geometry.y1),
      x2: Number(geometry.x2),
      y2: Number(geometry.y2),
    };
  }
  if (annotation.type === "rotated_rectangle" && Array.isArray(geometry.points)) {
    const bounds = boundsFromPoints(geometry.points as number[][]);
    return bounds ? { x1: bounds.minX, y1: bounds.minY, x2: bounds.maxX, y2: bounds.maxY } : null;
  }
  if ((annotation.type === "polygon" || annotation.type === "polyline" || annotation.type === "points") && Array.isArray(geometry.points)) {
    const bounds = boundsFromPoints(geometry.points as number[][]);
    return bounds ? { x1: bounds.minX, y1: bounds.minY, x2: bounds.maxX, y2: bounds.maxY } : null;
  }
  if (annotation.type === "ellipse") {
    const cx = Number(geometry.cx);
    const cy = Number(geometry.cy);
    const rx = Number(geometry.rx ?? 0);
    const ry = Number(geometry.ry ?? 0);
    return {
      x1: cx - rx,
      y1: cy - ry,
      x2: cx + rx,
      y2: cy + ry,
    };
  }
  if (annotation.type === "cuboid" && Array.isArray(geometry.faces)) {
    const bounds = boundsFromPoints((geometry.faces as number[][][]).flat());
    return bounds ? { x1: bounds.minX, y1: bounds.minY, x2: bounds.maxX, y2: bounds.maxY } : null;
  }
  if (annotation.type === "skeleton" && geometry.nodes) {
    const bounds = boundsFromPoints(Object.values(geometry.nodes as Record<string, [number, number]>));
    return bounds ? { x1: bounds.minX, y1: bounds.minY, x2: bounds.maxX, y2: bounds.maxY } : null;
  }
  return null;
}

function coordinateLabelEndpoints(
  originalAnnotation: Annotation,
  displayAnnotation: Annotation,
  imageWidth: number,
  imageHeight: number,
  rotation: number,
): { first: { stageX: number; stageY: number; imageX: number; imageY: number }; second: { stageX: number; stageY: number; imageX: number; imageY: number } } | null {
  const transform = displayTransform(imageWidth, imageHeight, rotation);
  if (originalAnnotation.type === "rectangle") {
    const renderedCorners = rectangleCornersForGeometry(originalAnnotation.geometry);
    const endpoints =
      originalAnnotation.geometry.dot_reset === true
        ? resetDotDiagonalCorners(renderedCorners, Number(originalAnnotation.geometry.display_angle ?? 0))
        : orientedDiagonalCorners(renderedCorners, false);
    if (!endpoints) return null;
    const firstStagePoint = transformImagePointToStage(endpoints.first[0], endpoints.first[1], imageWidth, imageHeight, rotation);
    const secondStagePoint = transformImagePointToStage(endpoints.second[0], endpoints.second[1], imageWidth, imageHeight, rotation);
    return {
      first: {
        stageX: firstStagePoint.x,
        stageY: firstStagePoint.y,
        imageX: firstStagePoint.x - transform.originX,
        imageY: firstStagePoint.y - transform.originY,
      },
      second: {
        stageX: secondStagePoint.x,
        stageY: secondStagePoint.y,
        imageX: secondStagePoint.x - transform.originX,
        imageY: secondStagePoint.y - transform.originY,
      },
    };
  }
  if (originalAnnotation.type === "rotated_rectangle" && Array.isArray(originalAnnotation.geometry.points)) {
    const points = originalAnnotation.geometry.points as number[][];
    const endpoints =
      originalAnnotation.geometry.dot_reset === true
        ? resetDotDiagonalCorners(points, Number(originalAnnotation.geometry.display_angle ?? originalAnnotation.geometry.angle ?? 0))
        : orientedDiagonalCorners(points, false);
    if (!endpoints) return null;
    const firstStagePoint = transformImagePointToStage(endpoints.first[0], endpoints.first[1], imageWidth, imageHeight, rotation);
    const secondStagePoint = transformImagePointToStage(endpoints.second[0], endpoints.second[1], imageWidth, imageHeight, rotation);
    return {
      first: {
        stageX: firstStagePoint.x,
        stageY: firstStagePoint.y,
        imageX: firstStagePoint.x - transform.originX,
        imageY: firstStagePoint.y - transform.originY,
      },
      second: {
        stageX: secondStagePoint.x,
        stageY: secondStagePoint.y,
        imageX: secondStagePoint.x - transform.originX,
        imageY: secondStagePoint.y - transform.originY,
      },
    };
  }
  const bounds = annotationBounds(displayAnnotation);
  if (!bounds) return null;
  return {
    first: {
      stageX: transform.originX + bounds.x1,
      stageY: transform.originY + bounds.y1,
      imageX: bounds.x1,
      imageY: bounds.y1,
    },
    second: {
      stageX: transform.originX + bounds.x2,
      stageY: transform.originY + bounds.y2,
      imageX: bounds.x2,
      imageY: bounds.y2,
    },
  };
}

function formatEndpointPair(endpoints: NonNullable<ReturnType<typeof coordinateLabelEndpoints>>): string {
  return `(x1,y1)=(${formatCoordinate(endpoints.first.imageX)}, ${formatCoordinate(endpoints.first.imageY)}), (x2,y2)=(${formatCoordinate(endpoints.second.imageX)}, ${formatCoordinate(endpoints.second.imageY)})`;
}

function CoordinateLabelLayer({
  annotations,
  imageWidth,
  imageHeight,
  rotation,
  zoom,
  fontSize,
  theme,
}: {
  annotations: Annotation[];
  imageWidth: number;
  imageHeight: number;
  rotation: number;
  zoom: number;
  fontSize: number;
  theme: "dark" | "light";
}) {
  const displayAnnotations = useMemo(
    () => annotations.map((annotation) => rotateAnnotationForDisplay(annotation, imageWidth, imageHeight, rotation)),
    [annotations, imageHeight, imageWidth, rotation],
  );
  const scaledFontSize = Math.max(3, fontSize / Math.max(zoom, 0.1));
  const strokeWidth = 0.6 / Math.max(zoom, 0.1);
  const stroke = theme === "light" ? "#ffffff" : "#020617";

  return (
    <>
      {displayAnnotations.flatMap((annotation, index) => {
        const endpoints = coordinateLabelEndpoints(annotations[index], annotation, imageWidth, imageHeight, rotation);
        if (!endpoints) return [];
        const color = labelColor(annotation.label);
        const firstLabel = `${annotation.label} (x1,y1)=(${formatCoordinate(endpoints.first.imageX)}, ${formatCoordinate(endpoints.first.imageY)})`;
        const secondLabel = `${annotation.label} (x2,y2)=(${formatCoordinate(endpoints.second.imageX)}, ${formatCoordinate(endpoints.second.imageY)})`;
        return [
          <Text
            key={`${annotation.id}-${rotation}-${formatCoordinate(endpoints.first.stageX)}-${formatCoordinate(endpoints.first.stageY)}-x1-y1`}
            x={endpoints.first.stageX}
            y={endpoints.first.stageY}
            text={firstLabel}
            fontSize={scaledFontSize}
            fontStyle="normal"
            fill={color}
            stroke={stroke}
            strokeWidth={strokeWidth}
            listening={false}
          />,
          <Text
            key={`${annotation.id}-${rotation}-${formatCoordinate(endpoints.second.stageX)}-${formatCoordinate(endpoints.second.stageY)}-x2-y2`}
            x={endpoints.second.stageX}
            y={endpoints.second.stageY}
            text={secondLabel}
            fontSize={scaledFontSize}
            fontStyle="normal"
            fill={color}
            stroke={stroke}
            strokeWidth={strokeWidth}
            listening={false}
          />,
        ];
      })}
    </>
  );
}

function CrosshairLayer({
  position,
  imageWidth,
  imageHeight,
  rotation,
  zoom,
  theme,
}: {
  position: { x: number; y: number } | null;
  imageWidth: number;
  imageHeight: number;
  rotation: number;
  zoom: number;
  theme: "dark" | "light";
}) {
  if (!position) return null;
  const transform = displayTransform(imageWidth, imageHeight, rotation);
  const imageX = Math.min(Math.max(position.x - transform.originX, 0), transform.width);
  const imageY = Math.min(Math.max(position.y - transform.originY, 0), transform.height);
  const stageX = transform.originX + imageX;
  const stageY = transform.originY + imageY;
  const stroke = theme === "light" ? "#0f172a" : "#e2e8f0";
  const labelFill = theme === "light" ? "#ffffff" : "#020617";
  const textFill = theme === "light" ? "#0f172a" : "#e2e8f0";
  const scaleSafe = Math.max(zoom, 0.1);
  const fontSize = 11 / scaleSafe;
  const padding = 4 / scaleSafe;
  const labelText = `x=${formatCoordinate(imageX)} y=${formatCoordinate(imageY)}`;
  const labelWidth = Math.max(82 / scaleSafe, labelText.length * fontSize * 0.58 + padding * 2);
  const labelHeight = fontSize + padding * 2;
  const labelX = Math.min(stageX + 8 / scaleSafe, Math.max(transform.originX, transform.originX + transform.width - labelWidth - 2 / scaleSafe));
  const labelY = Math.min(stageY + 8 / scaleSafe, Math.max(transform.originY, transform.originY + transform.height - labelHeight - 2 / scaleSafe));

  return (
    <>
      <Line points={[stageX, transform.originY, stageX, transform.originY + transform.height]} stroke={stroke} strokeWidth={1 / scaleSafe} dash={[6 / scaleSafe, 4 / scaleSafe]} listening={false} />
      <Line points={[transform.originX, stageY, transform.originX + transform.width, stageY]} stroke={stroke} strokeWidth={1 / scaleSafe} dash={[6 / scaleSafe, 4 / scaleSafe]} listening={false} />
      <Rect
        x={labelX}
        y={labelY}
        width={labelWidth}
        height={labelHeight}
        cornerRadius={4 / scaleSafe}
        fill={labelFill}
        opacity={0.88}
        listening={false}
      />
      <Text
        x={labelX + padding}
        y={labelY + padding}
        text={labelText}
        fontSize={fontSize}
        fill={textFill}
        listening={false}
      />
    </>
  );
}

function AnnotationInspector({
  annotations,
  imageWidth,
  imageHeight,
  rotation,
  theme,
}: {
  annotations: Annotation[];
  imageWidth: number;
  imageHeight: number;
  rotation: number;
  theme: "dark" | "light";
}) {
  const rotatedDimensions = useMemo(() => getRotatedDimensions(imageWidth, imageHeight, rotation), [imageHeight, imageWidth, rotation]);
  const rotatedAnnotations = useMemo(
    () => annotations.map((annotation) => rotateAnnotationForDisplay(annotation, imageWidth, imageHeight, rotation)),
    [annotations, imageHeight, imageWidth, rotation],
  );

  return (
    <aside
      className={`flex h-full w-[420px] shrink-0 flex-col overflow-y-auto rounded-xl border text-sm ${
        theme === "light" ? "border-slate-200 bg-white text-slate-800" : "border-slate-800 bg-slate-950 text-slate-200"
      }`}
    >
      <div className={`${theme === "light" ? "border-b border-slate-200" : "border-b border-slate-800"} px-4 py-3`}>
        <div className="text-xs uppercase tracking-wide text-slate-500">Rotation Inspector</div>
        <div className={`mt-1 text-base font-semibold ${theme === "light" ? "text-slate-900" : "text-slate-100"}`}>Dimensions, export geometry, and on-image X/Y</div>
        <div className="mt-3 grid grid-cols-2 gap-2">
          <div className={`rounded-lg border px-3 py-2 ${theme === "light" ? "border-slate-200 bg-slate-50" : "border-slate-800 bg-slate-900"}`}>
            <div className="text-[11px] uppercase tracking-wide text-slate-500">Original image</div>
            <div className={`mt-1 text-base font-semibold ${theme === "light" ? "text-slate-900" : "text-slate-100"}`}>
              {imageWidth} × {imageHeight}
            </div>
          </div>
          <div className={`rounded-lg border px-3 py-2 ${theme === "light" ? "border-slate-200 bg-slate-50" : "border-slate-800 bg-slate-900"}`}>
            <div className="text-[11px] uppercase tracking-wide text-slate-500">Rotated image</div>
            <div className={`mt-1 text-base font-semibold ${theme === "light" ? "text-slate-900" : "text-slate-100"}`}>
              {rotatedDimensions.width} × {rotatedDimensions.height}
            </div>
          </div>
        </div>
      </div>
      <div className={`${theme === "light" ? "border-b border-slate-200 text-slate-500" : "border-b border-slate-800 text-slate-400"} px-4 py-3 text-xs`}>
        Export geometry is checked against the rotated image edges. On-image X/Y follows the same coordinate system as the crosshair.
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto p-3">
        {annotations.length === 0 ? (
          <div className={`rounded-lg border border-dashed px-3 py-6 text-center ${theme === "light" ? "border-slate-200 text-slate-500" : "border-slate-800 text-slate-500"}`}>
            No annotations on this image.
          </div>
        ) : (
          <div className="space-y-2">
            {annotations.map((annotation, index) => {
              const rotatedAnnotation = rotatedAnnotations[index];
              const fits = isAnnotationWithinBounds(rotatedAnnotation, rotatedDimensions.width, rotatedDimensions.height);
              const endpoints = coordinateLabelEndpoints(annotation, rotatedAnnotation, imageWidth, imageHeight, rotation);
              return (
                <div key={annotation.id} className={`rounded-lg border p-3 ${theme === "light" ? "border-slate-200 bg-slate-50" : "border-slate-800 bg-slate-900/70"}`}>
                  <div className="flex items-center justify-between gap-3">
                    <div className="min-w-0">
                      <div className={`truncate text-sm font-semibold ${theme === "light" ? "text-slate-900" : "text-slate-100"}`}>{annotation.label}</div>
                      <div className="text-[11px] uppercase tracking-wide text-slate-500">{annotation.type}</div>
                    </div>
                    <div
                      className={`rounded-full px-2 py-1 text-[11px] font-medium ${
                        fits ? "bg-emerald-500/15 text-emerald-300" : "bg-amber-500/15 text-amber-300"
                      }`}
                    >
                      {fits ? "fits" : "check edges"}
                    </div>
                  </div>
                  <div className={`mt-2 grid gap-2 text-xs ${theme === "light" ? "text-slate-700" : "text-slate-300"}`}>
                    <div>
                      <span className="text-slate-500">Original geometry:</span> {formatAnnotationGeometry(annotation)}
                    </div>
                    <div>
                      <span className="text-slate-500">Export geometry:</span> {formatAnnotationGeometry(rotatedAnnotation)}
                    </div>
                    {endpoints ? (
                      <div>
                        <span className="text-slate-500">On-image X/Y:</span> {formatEndpointPair(endpoints)}
                      </div>
                    ) : null}
                    <div>
                      <span className="text-slate-500">Dot rule:</span> {annotation.geometry.dot_reset === true ? "reset to visual top edge; export rotation 0" : "follows annotation orientation"}
                    </div>
                    <div className="text-slate-500">
                      Label color: <span style={{ color: labelColor(annotation.label) }}>{labelColor(annotation.label)}</span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </aside>
  );
}

function DirectionMarkerLayer({
  annotations,
  imageWidth,
  imageHeight,
  rotation,
}: {
  annotations: Annotation[];
  imageWidth: number;
  imageHeight: number;
  rotation: number;
}) {
  const markerAnnotations = useMemo(
    () =>
      annotations.map((annotation) => ({
        original: annotation,
        display: rotateAnnotationForDisplay(annotation, imageWidth, imageHeight, rotation),
      })),
    [annotations, imageHeight, imageWidth, rotation],
  );
  return (
    <>
      {markerAnnotations.map(({ original, display }) => {
        const annotation = display;
        const isDotReset = original.geometry.dot_reset === true;
        if (annotation.type === "rotated_rectangle" && Array.isArray(annotation.geometry.points)) {
          const points = annotation.geometry.points as number[][];
          const dot = isDotReset ? visualTopEdgeDot(points) : { x: (points[0][0] + points[1][0]) / 2, y: (points[0][1] + points[1][1]) / 2 };
          return <Circle key={annotation.id} x={dot.x} y={dot.y} radius={4} fill="#ffffff" stroke="#111827" strokeWidth={1} />;
        }
        if (annotation.type === "rectangle") {
          const dot = isDotReset ? visualTopEdgeDot(rectangleCornersForGeometry(annotation.geometry)) : rectangleDirectionDot(annotation.geometry);
          return <Circle key={annotation.id} x={dot.x} y={dot.y} radius={4} fill="#ffffff" stroke="#111827" strokeWidth={1} />;
        }
        return null;
      })}
    </>
  );
}

export function AnnotationCanvas() {
  const currentImage = useDatasetStore((state) => state.currentImage);
  const numImages = useDatasetStore((state) => state.numImages);
  const zoom = useDatasetStore((state) => state.zoom);
  const panX = useDatasetStore((state) => state.panX);
  const panY = useDatasetStore((state) => state.panY);
  const showInspector = useDatasetStore((state) => state.showInspector);
  const showCoordinateLabels = useDatasetStore((state) => state.showCoordinateLabels);
  const coordinateLabelFontSize = useDatasetStore((state) => state.coordinateLabelFontSize);
  const showCrosshairCursor = useDatasetStore((state) => state.showCrosshairCursor);
  const theme = useDatasetStore((state) => state.theme);
  const setZoom = useDatasetStore((state) => state.setZoom);
  const setPan = useDatasetStore((state) => state.setPan);
  const rotateAnnotationOrientation = useDatasetStore((state) => state.rotateAnnotationOrientation);
  const setClassificationLabel = useDatasetStore((state) => state.setClassificationLabel);
  const [orientationLabel, setOrientationLabel] = useState<string>("__all__");
  const [classificationLabel, setClassificationLabelInput] = useState<string>("");
  const [crosshairPosition, setCrosshairPosition] = useState<{ x: number; y: number } | null>(null);
  const stageRef = useRef<KonvaStage | null>(null);
  const [image] = useImage(currentImage?.image_url ?? "");
  const originalWidth = currentImage?.width ?? 0;
  const originalHeight = currentImage?.height ?? 0;
  const imageWidth = image?.width ?? originalWidth;
  const imageHeight = image?.height ?? originalHeight;
  const rotation = currentImage?.rotation ?? 0;
  const stageWidth = rotation === 90 || rotation === 270 ? originalHeight : originalWidth;
  const stageHeight = rotation === 90 || rotation === 270 ? originalWidth : originalHeight;
  const layout = useMemo(
    () => getRotationLayout(stageWidth, stageHeight, imageWidth, imageHeight, rotation),
    [imageHeight, imageWidth, rotation, stageHeight, stageWidth],
  );
  const annotations = useMemo(() => currentImage?.annotations ?? [], [currentImage]);
  const orientationLabels = useMemo(
    () => Array.from(new Set(annotations.filter((annotation) => ["rectangle", "rotated_rectangle", "ellipse"].includes(annotation.type)).map((annotation) => annotation.label))).sort(),
    [annotations],
  );
  const orientationTarget = orientationLabel === "__all__" ? null : orientationLabel;
  const availableLabels = useMemo(
    () => Array.from(new Set([...(currentImage?.labels ?? []), ...annotations.map((annotation) => annotation.label)].filter(Boolean))).sort(),
    [annotations, currentImage?.labels],
  );

  useEffect(() => {
    if (orientationLabel !== "__all__" && !orientationLabels.includes(orientationLabel)) {
      setOrientationLabel("__all__");
    }
  }, [orientationLabel, orientationLabels]);

  useEffect(() => {
    setClassificationLabelInput(currentImage?.classification_label ?? "");
  }, [currentImage?.classification_label, currentImage?.index]);

  useEffect(() => {
    const handleWheel = (event: WheelEvent) => {
      if (!event.ctrlKey) return;
      event.preventDefault();
      const nextZoom = event.deltaY > 0 ? Math.max(0.1, zoom / 1.1) : Math.min(8, zoom * 1.1);
      setZoom(nextZoom);
    };
    window.addEventListener("wheel", handleWheel, { passive: false });
    return () => window.removeEventListener("wheel", handleWheel);
  }, [setZoom, zoom]);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (!(event.shiftKey && !event.ctrlKey && !event.metaKey && !event.altKey)) return;
      if (event.target instanceof HTMLElement && (["INPUT", "TEXTAREA", "SELECT"].includes(event.target.tagName) || event.target.isContentEditable)) return;
      const key = event.key.toLowerCase();
      if (key === "q") {
        event.preventDefault();
        rotateAnnotationOrientation("left", orientationTarget);
      } else if (key === "e") {
        event.preventDefault();
        rotateAnnotationOrientation("right", orientationTarget);
      } else if (key === "r") {
        event.preventDefault();
        rotateAnnotationOrientation("180", orientationTarget);
      } else if (key === "0" || event.code === "Digit0") {
        event.preventDefault();
        rotateAnnotationOrientation("reset", orientationTarget);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [orientationTarget, rotateAnnotationOrientation]);

  if (!currentImage) {
    return <div className="flex h-full items-center justify-center text-slate-400">Upload or resume a dataset to begin.</div>;
  }

  const updateCrosshairPosition = () => {
    if (!showCrosshairCursor) return;
    const pointer = stageRef.current?.getPointerPosition();
    if (!pointer) return;
    const x = (pointer.x - panX) / Math.max(zoom, 0.1);
    const y = (pointer.y - panY) / Math.max(zoom, 0.1);
    setCrosshairPosition({ x, y });
  };

  return (
    <div className="flex h-full w-full flex-col gap-3">
      <div className={`rounded-2xl border px-4 py-3 text-sm shadow-xl ${theme === "light" ? "border-slate-200 bg-white/90 text-slate-700" : "border-slate-800 bg-slate-900/90 text-slate-300"}`}>
        <div className="flex flex-wrap items-center gap-2">
          <div className="min-w-0">
            <div className={`truncate text-base font-semibold ${theme === "light" ? "text-slate-900" : "text-slate-100"}`}>{currentImage.filename}</div>
            <div className="mt-0.5 text-xs text-slate-500">
              Image {currentImage.index + 1} / {numImages} · image rotation {currentImage.rotation}° · {currentImage.annotations.length} annotations
            </div>
          </div>
          <div className={`ml-auto flex flex-wrap items-center gap-2 rounded-lg border px-2 py-1 ${theme === "light" ? "border-slate-200 bg-slate-50" : "border-slate-800 bg-slate-900"}`}>
            <span className="text-xs uppercase tracking-wide text-slate-500">Classification</span>
            <input
              className={`w-36 rounded border px-2 py-1 text-xs ${theme === "light" ? "border-slate-300 bg-white text-slate-800" : "border-slate-700 bg-slate-950 text-slate-100"}`}
              list="classification-label-options"
              value={classificationLabel}
              onChange={(event) => setClassificationLabelInput(event.target.value)}
              placeholder="Image label"
              title="Image-level class label for classification exports"
            />
            <datalist id="classification-label-options">
              {availableLabels.map((label) => (
                <option key={label} value={label} />
              ))}
            </datalist>
            <button
              className={`rounded border px-2 py-1 text-xs ${theme === "light" ? "border-slate-300 bg-white hover:bg-slate-100" : "border-slate-700 bg-slate-950 hover:bg-slate-800"}`}
              title="Assign this image-level class label to the current image"
              onClick={() => setClassificationLabel(classificationLabel, false)}
            >
              🏷️ Set image
            </button>
            <button
              className={`rounded border px-2 py-1 text-xs font-medium ${theme === "light" ? "border-emerald-300 bg-emerald-50 text-emerald-800 hover:bg-emerald-100" : "border-emerald-700 bg-emerald-950 text-emerald-100 hover:bg-emerald-900"}`}
              title="Assign this image-level class label to every non-deleted image"
              onClick={() => setClassificationLabel(classificationLabel, true)}
            >
              🧲 Apply all
            </button>
            <span className={`h-5 w-px ${theme === "light" ? "bg-slate-300" : "bg-slate-700"}`} />
            <span className="text-xs uppercase tracking-wide text-slate-500">Annotation dot</span>
            <select
              className={`rounded border px-2 py-1 text-xs ${theme === "light" ? "border-slate-300 bg-white text-slate-800" : "border-slate-700 bg-slate-950 text-slate-100"}`}
              value={orientationLabel}
              onChange={(event) => setOrientationLabel(event.target.value)}
              title="Choose which labels receive dot-direction changes"
            >
              <option value="__all__">All labels</option>
              {orientationLabels.map((label) => (
                <option key={label} value={label}>
                  {label}
                </option>
              ))}
            </select>
            <button
              className={`rounded border px-2 py-1 text-xs ${theme === "light" ? "border-slate-300 bg-white hover:bg-slate-100" : "border-slate-700 bg-slate-950 hover:bg-slate-800"}`}
              title="Rotate selected/all annotation dots left without moving boxes (Shift+Q)"
              onClick={() => rotateAnnotationOrientation("left", orientationTarget)}
            >
              ◀️ Dot left <span className="text-slate-500">⇧Q</span>
            </button>
            <button
              className={`rounded border px-2 py-1 text-xs ${theme === "light" ? "border-slate-300 bg-white hover:bg-slate-100" : "border-slate-700 bg-slate-950 hover:bg-slate-800"}`}
              title="Rotate selected/all annotation dots right without moving boxes (Shift+E)"
              onClick={() => rotateAnnotationOrientation("right", orientationTarget)}
            >
              ▶️ Dot right <span className="text-slate-500">⇧E</span>
            </button>
            <button
              className={`rounded border px-2 py-1 text-xs ${theme === "light" ? "border-slate-300 bg-white hover:bg-slate-100" : "border-slate-700 bg-slate-950 hover:bg-slate-800"}`}
              title="Rotate selected/all annotation dots 180° without moving boxes (Shift+R)"
              onClick={() => rotateAnnotationOrientation("180", orientationTarget)}
            >
              🔄 Dot 180 <span className="text-slate-500">⇧R</span>
            </button>
            <button
              className={`rounded border px-2 py-1 text-xs font-medium ${
                theme === "light" ? "border-indigo-300 bg-indigo-50 text-indigo-800 hover:bg-indigo-100" : "border-indigo-700 bg-indigo-950 text-indigo-100 hover:bg-indigo-900"
              }`}
              title="Reset selected/all white dots to the visual top edge and export rotation 0 (Shift+0)"
              onClick={() => rotateAnnotationOrientation("reset", orientationTarget)}
            >
              🎯 Reset dot <span className="text-slate-500">⇧0</span>
            </button>
          </div>
        </div>
      </div>
      <div className="flex min-h-0 flex-1 gap-3 overflow-hidden">
        <div className={`min-w-0 flex-1 overflow-hidden rounded-2xl border shadow-2xl ${showCrosshairCursor ? "cursor-crosshair" : ""} ${theme === "light" ? "border-slate-200 bg-white/95" : "border-slate-800 bg-slate-950/95"}`}>
          <Stage
            ref={stageRef}
            width={Math.max(layout.stageWidth, 640)}
            height={Math.max(layout.stageHeight, 480)}
            scaleX={zoom}
            scaleY={zoom}
            x={panX}
            y={panY}
            draggable
            onDragMove={(event) => setPan(event.target.x(), event.target.y())}
            onMouseMove={updateCrosshairPosition}
            onMouseLeave={() => setCrosshairPosition(null)}
          >
            <Layer>
              <Group
                x={layout.groupX}
                y={layout.groupY}
                offsetX={layout.groupOffsetX}
                offsetY={layout.groupOffsetY}
                rotation={layout.groupRotation}
              >
                {image ? <KonvaImage image={image} width={imageWidth} height={imageHeight} /> : null}
                {annotations.map((annotation) => (
                  <AnnotationShape key={annotation.id} annotation={annotation} />
                ))}
              </Group>
              <DirectionMarkerLayer annotations={annotations} imageWidth={imageWidth} imageHeight={imageHeight} rotation={rotation} />
              {showCoordinateLabels ? (
                <CoordinateLabelLayer
                  annotations={annotations}
                  imageWidth={imageWidth}
                  imageHeight={imageHeight}
                  rotation={rotation}
                  zoom={zoom}
                  fontSize={coordinateLabelFontSize}
                  theme={theme}
                />
              ) : null}
              {showCrosshairCursor ? (
                <CrosshairLayer position={crosshairPosition} imageWidth={imageWidth} imageHeight={imageHeight} rotation={rotation} zoom={zoom} theme={theme} />
              ) : null}
            </Layer>
          </Stage>
        </div>
        {showInspector ? <AnnotationInspector annotations={annotations} imageWidth={imageWidth} imageHeight={imageHeight} rotation={rotation} theme={theme} /> : null}
      </div>
    </div>
  );
}
