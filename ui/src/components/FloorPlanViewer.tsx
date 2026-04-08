import { Stage, Layer, Rect, Circle, Text, Group, Line, Arc } from "react-konva";
import { useEffect, useRef, useState, useCallback } from "react";
import type Konva from "konva";
import type { FloorPlanTable, FloorPlanElement, FloorPlanZone, Reservation, TableAssignment } from "../lib/api";

interface Props {
  tables: FloorPlanTable[];
  elements?: FloorPlanElement[];
  zones?: FloorPlanZone[];
  assignments: TableAssignment[];
  reservations: Reservation[];
  onTableClick: (reservation: Reservation | null, tableId?: string) => void;
  selectedTableId?: string | null;
}

const COLORS = {
  occupied: { fill: "#c8b590", stroke: "#a08050", text: "#3a2e1e" },  // Dark cream — assigned
  seated:   { fill: "#1a2535", stroke: "#2196f3", text: "#e3f2fd" },  // Blue — seated
  free:     { fill: "#2e7d32", stroke: "#66bb6a", text: "#ffffff" },  // Green — free
  selected: { fill: "#2a2515", stroke: "#ffd54f", text: "#fff8e1" },  // Gold — selected
};

const EL = {
  window:   { fill: "#0d2030", stroke: "#7eb8c8" },
  window_v: { fill: "#0d2030", stroke: "#7eb8c8" },
  door:     { fill: "#221800", stroke: "#c8a96e" },
  bathroom: { fill: "#14141e", stroke: "#9988cc" },
};
const ZONE = {
  zone_indoor:  { fill: "rgba(200,169,110,0.07)", stroke: "#c8a96e", text: "#c8a96e" },
  zone_outdoor: { fill: "rgba(126,184,200,0.07)", stroke: "#7eb8c8", text: "#7eb8c8" },
};

export default function FloorPlanViewer({
  tables, elements = [], zones = [],
  assignments, reservations, onTableClick, selectedTableId,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const stageRef = useRef<Konva.Stage>(null);
  const [size, setSize] = useState({ width: 800, height: 500 });
  const [fitScale, setFitScale] = useState(1);
  const [stagePos, setStagePos] = useState({ x: 0, y: 0 });

  useEffect(() => {
    const update = () => {
      if (containerRef.current) {
        setSize({ width: containerRef.current.offsetWidth, height: containerRef.current.offsetHeight });
      }
    };
    update();
    window.addEventListener("resize", update);
    return () => window.removeEventListener("resize", update);
  }, []);

  // Auto-fit: compute bounding box of all content and scale to fit
  useEffect(() => {
    if (tables.length === 0 && elements.length === 0 && zones.length === 0) return;
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;

    zones.forEach(z => {
      minX = Math.min(minX, z.x);
      minY = Math.min(minY, z.y);
      maxX = Math.max(maxX, z.x + z.width);
      maxY = Math.max(maxY, z.y + z.height);
    });
    tables.forEach(t => {
      const W = t.shape === "round" ? 70 : 90;
      const H = t.shape === "round" ? 70 : 60;
      minX = Math.min(minX, t.x - W / 2);
      minY = Math.min(minY, t.y - H / 2);
      maxX = Math.max(maxX, t.x + W / 2);
      maxY = Math.max(maxY, t.y + H / 2);
    });
    elements.forEach(el => {
      minX = Math.min(minX, el.x);
      minY = Math.min(minY, el.y);
      maxX = Math.max(maxX, el.x + el.width);
      maxY = Math.max(maxY, el.y + el.height);
    });

    const pad = 40;
    const contentW = maxX - minX + pad * 2;
    const contentH = maxY - minY + pad * 2;
    const baseSc = Math.min(size.width / contentW, size.height / contentH, 1.2);
    const sc = baseSc * 1.4; // 40% larger
    const offX = (-minX + pad) * sc + Math.max(0, (size.width - contentW * sc) / 2);
    const offY = (-minY + pad) * sc + Math.max(0, (size.height - contentH * sc) / 2);
    setFitScale(sc);
    setStagePos({ x: offX, y: offY });
  }, [tables, elements, zones, size]);

  const handleWheel = useCallback((e: Konva.KonvaEventObject<WheelEvent>) => {
    e.evt.preventDefault();
    const stage = stageRef.current;
    if (!stage) return;
    const dx = e.evt.deltaX;
    const dy = e.evt.deltaY;
    const newPos = { x: stage.x() - dx, y: stage.y() - dy };
    stage.position(newPos);
    setStagePos(newPos);
  }, []);

  const handleDragEnd = useCallback((e: Konva.KonvaEventObject<DragEvent>) => {
    setStagePos({ x: e.target.x(), y: e.target.y() });
  }, []);

  const [tooltip, setTooltip] = useState<{ x: number; y: number; text: string } | null>(null);

  const assignmentMap = new Map<string, Reservation>();
  for (const a of assignments) {
    const res = reservations.find(r => r.reservation_id === a.reservation_id);
    if (res) assignmentMap.set(a.table_id, res);
  }

  function getTableColors(table: FloorPlanTable) {
    if (table.id === selectedTableId) return COLORS.selected;
    const res = assignmentMap.get(table.id);
    if (!res) return COLORS.free;
    if (res.status === "seated") return COLORS.seated;
    return COLORS.occupied;
  }

  return (
    <div ref={containerRef} style={{ width: "100%", height: "100%", overflow: "hidden", cursor: "grab", position: "relative" }}>
      <Stage
        ref={stageRef}
        width={size.width}
        height={size.height}
        scaleX={fitScale}
        scaleY={fitScale}
        x={stagePos.x}
        y={stagePos.y}
        draggable
        onDragEnd={handleDragEnd}
        onWheel={handleWheel}
      >
        <Layer listening={false}>
          {/* Zones (background) */}
          {zones.map(z => {
            const zc = ZONE[z.kind as keyof typeof ZONE] ?? ZONE.zone_indoor;
            return (
              <Group key={z.id}>
                <Rect x={z.x} y={z.y} width={z.width} height={z.height}
                  fill={zc.fill} stroke={zc.stroke} strokeWidth={1.5}
                  dash={[10, 5]} cornerRadius={4} />
                <Text x={z.x + 10} y={z.y + 8} text={z.label}
                  fontSize={12} fontFamily="monospace" fill={zc.text} />
              </Group>
            );
          })}
          {/* Elements (windows, doors, bathrooms) */}
          {elements.map(el => {
            const ec = EL[el.kind as keyof typeof EL] ?? EL.window;
            if (el.kind === "window" || el.kind === "window_v") {
              const isV = el.kind === "window_v";
              const panes = isV
                ? [0.25, 0.45, 0.65, 0.82].map(r => ({
                    x1: el.x + 2, y1: el.y + el.height * r,
                    x2: el.x + el.width - 2, y2: el.y + el.height * r,
                  }))
                : [0.25, 0.45, 0.65, 0.82].map(r => ({
                    x1: el.x + el.width * r, y1: el.y + 2,
                    x2: el.x + el.width * r, y2: el.y + el.height - 2,
                  }));
              return (
                <Group key={el.id}>
                  <Rect x={el.x} y={el.y} width={el.width} height={el.height}
                    fill={ec.fill} stroke={ec.stroke} strokeWidth={1.5} cornerRadius={2} />
                  {panes.map((p, i) => (
                    <Line key={i} points={[p.x1, p.y1, p.x2, p.y2]}
                      stroke={ec.stroke} strokeWidth={0.8} opacity={0.5} />
                  ))}
                </Group>
              );
            }
            if (el.kind === "door") {
              return (
                <Group key={el.id}>
                  <Rect x={el.x} y={el.y} width={el.width} height={el.height}
                    fill={ec.fill} stroke={ec.stroke} strokeWidth={1.5} cornerRadius={2} />
                  <Arc x={el.x + 4} y={el.y + el.height - 4}
                    innerRadius={0} outerRadius={el.width - 8}
                    angle={90} rotation={-90}
                    fill="rgba(200,169,110,0.12)" stroke={ec.stroke} strokeWidth={1} />
                  <Text x={el.x} y={el.y + el.height / 2 - 6} width={el.width}
                    text="DOOR" fontSize={8} fontFamily="monospace" fill={ec.stroke} align="center" />
                </Group>
              );
            }
            if (el.kind === "bathroom") {
              return (
                <Group key={el.id}>
                  <Rect x={el.x} y={el.y} width={el.width} height={el.height}
                    fill={ec.fill} stroke={ec.stroke} strokeWidth={1.5} cornerRadius={4} />
                  <Text x={el.x} y={el.y + el.height / 2 - 10} width={el.width}
                    text="WC" fontSize={14} fontStyle="bold" fontFamily="monospace" fill={ec.stroke} align="center" />
                </Group>
              );
            }
            return null;
          })}
        </Layer>

        <Layer>
          {/* Tables (interactive) */}
          {tables.map(table => {
            const c = getTableColors(table);
            const res = assignmentMap.get(table.id);
            const isRound = table.shape === "round";
            const W = isRound ? 70 : 90;
            const H = isRound ? 70 : 60;
            return (
              <Group key={table.id} x={table.x} y={table.y}
                onClick={() => onTableClick(res ?? null, table.id)}
                onTap={() => onTableClick(res ?? null, table.id)}
                onMouseEnter={(e) => {
                  if (!res) return;
                  const stage = e.target.getStage();
                  if (!stage) return;
                  const pos = stage.getPointerPosition();
                  if (pos) setTooltip({ x: pos.x, y: pos.y, text: `${res.guest_name} — ${res.party_size}p` });
                }}
                onMouseLeave={() => setTooltip(null)}
              >
                {isRound ? (
                  <Circle x={0} y={0} radius={W / 2} fill={c.fill} stroke={c.stroke} strokeWidth={2} />
                ) : (
                  <Rect x={-W / 2} y={-H / 2} width={W} height={H}
                    fill={c.fill} stroke={c.stroke} strokeWidth={2} cornerRadius={6} />
                )}
                <Text x={-W / 2} y={-12} width={W} text={table.label}
                  fontSize={11} fontFamily="DM Mono, monospace" fill={c.text} align="center" />
                <Text x={-W / 2} y={3} width={W}
                  text={res ? res.guest_name.split(" ")[0] : `${table.seats}p`}
                  fontSize={9} fontFamily="DM Mono, monospace" fill={c.text} align="center" opacity={0.7} />
              </Group>
            );
          })}
        </Layer>
      </Stage>
      {tooltip && (
        <div
          style={{ position: "absolute", left: tooltip.x + 12, top: tooltip.y - 10, pointerEvents: "none" }}
          className="bg-foreground text-background text-xs px-2 py-1 rounded shadow-lg whitespace-nowrap z-50"
        >
          {tooltip.text}
        </div>
      )}
    </div>
  );
}
