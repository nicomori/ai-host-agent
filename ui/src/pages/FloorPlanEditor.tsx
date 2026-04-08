import { type ReactElement, type ReactNode, useState, useEffect, useRef, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft, Save, ChevronDown, ChevronRight } from "lucide-react";
import Konva from "konva";
import {
  Stage,
  Layer,
  Rect,
  Circle,
  Text,
  Line,
  Arc,
  Transformer,
} from "react-konva";
import { getFloorPlan, saveFloorPlan } from "../lib/api";

// ─── Types ───────────────────────────────────────────────────────────────────

type ItemKind =
  | "table_rect"
  | "table_round"
  | "window"
  | "window_v"
  | "door"
  | "bathroom"
  | "zone_indoor"
  | "zone_outdoor";

interface CanvasItem {
  id: string;
  kind: ItemKind;
  x: number;
  y: number;
  width: number;
  height: number;
  label: string;
  seats?: number;
  section?: string;
}

// ─── Colors ──────────────────────────────────────────────────────────────────

const C: Record<ItemKind, { fill: string; stroke: string; text: string }> & {
  selected: string;
} = {
  zone_indoor:  { fill: "rgba(200,169,110,0.07)", stroke: "#c8a96e", text: "#c8a96e" },
  zone_outdoor: { fill: "rgba(126,184,200,0.07)", stroke: "#7eb8c8", text: "#7eb8c8" },
  table_rect:   { fill: "#1a2535", stroke: "#4a7fa5", text: "#e8e6e0" },
  table_round:  { fill: "#1a2535", stroke: "#4a7fa5", text: "#e8e6e0" },
  window:       { fill: "#0d2030", stroke: "#7eb8c8", text: "#7eb8c8" },
  window_v:     { fill: "#0d2030", stroke: "#7eb8c8", text: "#7eb8c8" },
  door:         { fill: "#221800", stroke: "#c8a96e", text: "#c8a96e" },
  bathroom:     { fill: "#14141e", stroke: "#9988cc", text: "#9988cc" },
  selected:     "#c8a96e",
};

// ─── Snap ────────────────────────────────────────────────────────────────────

const snap = (v: number) => Math.round(v / 20) * 20;

// ─── Default dimensions ──────────────────────────────────────────────────────

const DEFAULT_DIMS: Record<ItemKind, { width: number; height: number }> = {
  table_rect:   { width: 90,  height: 60  },
  table_round:  { width: 70,  height: 70  },
  window:       { width: 140, height: 18  },
  window_v:     { width: 18,  height: 140 },
  door:         { width: 60,  height: 80  },
  bathroom:     { width: 70,  height: 70  },
  zone_indoor:  { width: 400, height: 300 },
  zone_outdoor: { width: 400, height: 300 },
};

// ─── Dot Grid ────────────────────────────────────────────────────────────────

function DotGrid({
  width,
  height,
  scale,
  offsetX,
  offsetY,
}: {
  width: number;
  height: number;
  scale: number;
  offsetX: number;
  offsetY: number;
}) {
  const GRID = 20;
  const dots: ReactElement[] = [];
  const startX = Math.floor(-offsetX / scale / GRID) * GRID;
  const startY = Math.floor(-offsetY / scale / GRID) * GRID;
  const endX = startX + width / scale + GRID * 2;
  const endY = startY + height / scale + GRID * 2;

  for (let x = startX; x < endX; x += GRID) {
    for (let y = startY; y < endY; y += GRID) {
      dots.push(
        <Rect
          key={`${x},${y}`}
          x={x}
          y={y}
          width={1.5}
          height={1.5}
          fill="#2a2a35"
          listening={false}
        />
      );
    }
  }
  return <>{dots}</>;
}

// ─── Canvas Item Renderer ────────────────────────────────────────────────────

function CanvasItemShape({
  item,
  isSelected,
  onSelect,
  onChange,
  onDblClick,
}: {
  item: CanvasItem;
  isSelected: boolean;
  onSelect: (id: string) => void;
  onChange: (id: string, patch: Partial<CanvasItem>) => void;
  onDblClick: (id: string) => void;
}) {
  const stroke = isSelected ? C.selected : C[item.kind].stroke;
  const strokeWidth = isSelected ? 2 : 1.5;

  const commonProps = {
    x: item.x,
    y: item.y,
    onClick: () => onSelect(item.id),
    onTap: () => onSelect(item.id),
    onDblClick: () => onDblClick(item.id),
    draggable: true,
    onDragEnd: (e: Konva.KonvaEventObject<DragEvent>) => {
      onChange(item.id, { x: snap(e.target.x()), y: snap(e.target.y()) });
    },
  };

  if (item.kind === "zone_indoor" || item.kind === "zone_outdoor") {
    return (
      <>
        <Rect
          {...commonProps}
          width={item.width}
          height={item.height}
          fill={C[item.kind].fill}
          stroke={stroke}
          strokeWidth={strokeWidth}
          dash={[10, 5]}
          cornerRadius={4}
          id={item.id}
          onTransformEnd={(e) => {
            const node = e.target;
            const scaleX = node.scaleX();
            const scaleY = node.scaleY();
            node.scaleX(1);
            node.scaleY(1);
            onChange(item.id, {
              x: snap(node.x()),
              y: snap(node.y()),
              width: snap(Math.max(60, item.width * scaleX)),
              height: snap(Math.max(60, item.height * scaleY)),
            });
          }}
        />
        <Text
          x={item.x + 12}
          y={item.y + 10}
          text={item.label}
          fontSize={13}
          fontFamily="monospace"
          fill={C[item.kind].text}
          listening={false}
        />
      </>
    );
  }

  if (item.kind === "table_rect") {
    return (
      <>
        <Rect
          {...commonProps}
          width={item.width}
          height={item.height}
          fill={C.table_rect.fill}
          stroke={stroke}
          strokeWidth={strokeWidth}
          cornerRadius={6}
        />
        <Text
          x={item.x}
          y={item.y + item.height / 2 - 12}
          width={item.width}
          text={item.label}
          fontSize={11}
          fontFamily="monospace"
          fill={C.table_rect.text}
          align="center"
          listening={false}
          onClick={() => onSelect(item.id)}
        />
        {item.seats !== undefined && (
          <Text
            x={item.x}
            y={item.y + item.height / 2 + 2}
            width={item.width}
            text={item.section ? `${item.seats}p · ${item.section}` : `${item.seats} seats`}
            fontSize={9}
            fontFamily="monospace"
            fill="#6a8a9a"
            align="center"
            listening={false}
          />
        )}
      </>
    );
  }

  if (item.kind === "table_round") {
    const cx = item.x + item.width / 2;
    const cy = item.y + item.height / 2;
    const r = item.width / 2 - 2;
    return (
      <>
        <Circle
          x={cx}
          y={cy}
          radius={r}
          fill={C.table_round.fill}
          stroke={stroke}
          strokeWidth={strokeWidth}
          onClick={() => onSelect(item.id)}
          onTap={() => onSelect(item.id)}
          onDblClick={() => onDblClick(item.id)}
          draggable
          onDragEnd={(e: Konva.KonvaEventObject<DragEvent>) => {
            const nx = snap(e.target.x() - item.width / 2);
            const ny = snap(e.target.y() - item.height / 2);
            onChange(item.id, { x: nx, y: ny });
            e.target.x(nx + item.width / 2);
            e.target.y(ny + item.height / 2);
          }}
        />
        <Text
          x={cx - 40}
          y={cy - 12}
          width={80}
          text={item.label}
          fontSize={11}
          fontFamily="monospace"
          fill={C.table_round.text}
          align="center"
          listening={false}
        />
        {item.seats !== undefined && (
          <Text
            x={cx - 40}
            y={cy + 2}
            width={80}
            text={item.section ? `${item.seats}p · ${item.section}` : `${item.seats} seats`}
            fontSize={9}
            fontFamily="monospace"
            fill="#6a8a9a"
            align="center"
            listening={false}
          />
        )}
      </>
    );
  }

  if (item.kind === "window") {
    const lines = [0.25, 0.45, 0.65, 0.82].map((ratio) => ({
      sx: item.x + item.width * ratio,
      sy: item.y + 2,
      ey: item.y + item.height - 2,
    }));
    return (
      <>
        <Rect
          {...commonProps}
          width={item.width}
          height={item.height}
          fill={C.window.fill}
          stroke={stroke}
          strokeWidth={strokeWidth}
          cornerRadius={2}
        />
        {lines.map((l, i) => (
          <Line key={i} points={[l.sx, l.sy, l.sx, l.ey]}
            stroke={C.window.stroke} strokeWidth={0.8} opacity={0.5} listening={false} />
        ))}
      </>
    );
  }

  if (item.kind === "window_v") {
    const lines = [0.25, 0.45, 0.65, 0.82].map((ratio) => ({
      sx: item.x + 2,
      ex: item.x + item.width - 2,
      sy: item.y + item.height * ratio,
    }));
    return (
      <>
        <Rect
          {...commonProps}
          width={item.width}
          height={item.height}
          fill={C.window_v.fill}
          stroke={stroke}
          strokeWidth={strokeWidth}
          cornerRadius={2}
        />
        {lines.map((l, i) => (
          <Line key={i} points={[l.sx, l.sy, l.ex, l.sy]}
            stroke={C.window_v.stroke} strokeWidth={0.8} opacity={0.5} listening={false} />
        ))}
      </>
    );
  }

  if (item.kind === "door") {
    return (
      <>
        <Rect
          {...commonProps}
          width={item.width}
          height={item.height}
          fill={C.door.fill}
          stroke={stroke}
          strokeWidth={strokeWidth}
          cornerRadius={2}
        />
        <Arc
          x={item.x + 4}
          y={item.y + item.height - 4}
          innerRadius={0}
          outerRadius={item.width - 8}
          angle={90}
          rotation={-90}
          fill="rgba(200,169,110,0.12)"
          stroke={C.door.stroke}
          strokeWidth={1}
          listening={false}
        />
        <Text
          x={item.x}
          y={item.y + item.height / 2 - 8}
          width={item.width}
          text="DOOR"
          fontSize={9}
          fontFamily="monospace"
          fill={C.door.text}
          align="center"
          listening={false}
        />
      </>
    );
  }

  if (item.kind === "bathroom") {
    return (
      <>
        <Rect
          {...commonProps}
          width={item.width}
          height={item.height}
          fill={C.bathroom.fill}
          stroke={stroke}
          strokeWidth={strokeWidth}
          cornerRadius={4}
        />
        <Text
          x={item.x}
          y={item.y + item.height / 2 - 10}
          width={item.width}
          text="WC"
          fontSize={16}
          fontFamily="monospace"
          fontStyle="bold"
          fill={C.bathroom.text}
          align="center"
          listening={false}
        />
      </>
    );
  }

  return null;
}

// ─── Table Modal ─────────────────────────────────────────────────────────────

const TABLE_SECTIONS = ["", "Patio", "Window", "Private", "Bar", "Quiet", "Near Kitchen", "Near Bathroom", "Booth"];

function TableModal({
  initial,
  onConfirm,
  onCancel,
  title,
}: {
  initial?: { label: string; seats: number; section?: string };
  onConfirm: (label: string, seats: number, section: string) => void;
  onCancel: () => void;
  title: string;
}) {
  const [label, setLabel] = useState(initial?.label ?? "Mesa");
  const [seats, setSeats] = useState(String(initial?.seats ?? 4));
  const [section, setSection] = useState(initial?.section ?? "");

  const confirm = () => onConfirm(label, parseInt(seats) || 4, section);

  return (
    <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50">
      <div className="bg-card border border-border rounded-2xl w-full max-w-xs shadow-2xl p-6">
        <h3 className="text-sm font-semibold text-foreground mb-4 font-mono">{title}</h3>
        <div className="space-y-3">
          <div>
            <label className="text-xs text-muted-foreground font-mono block mb-1">Nombre</label>
            <input
              autoFocus
              className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm text-foreground font-mono outline-none focus:border-primary/50"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") confirm(); if (e.key === "Escape") onCancel(); }}
            />
          </div>
          <div>
            <label className="text-xs text-muted-foreground font-mono block mb-1">Capacidad</label>
            <input
              type="number" min={1} max={20}
              className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm text-foreground font-mono outline-none focus:border-primary/50"
              value={seats}
              onChange={(e) => setSeats(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") confirm(); if (e.key === "Escape") onCancel(); }}
            />
          </div>
          <div>
            <label className="text-xs text-muted-foreground font-mono block mb-1">Zona / Característica</label>
            <select
              className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm text-foreground font-mono outline-none focus:border-primary/50"
              value={section}
              onChange={(e) => setSection(e.target.value)}
            >
              <option value="">Sin zona</option>
              {TABLE_SECTIONS.filter(Boolean).map(s => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </div>
        </div>
        <div className="flex gap-2 mt-5">
          <button
            className="flex-1 px-3 py-2 border border-border rounded-lg text-xs text-muted-foreground font-mono hover:border-primary/30 transition-colors"
            onClick={onCancel}
          >
            Cancelar
          </button>
          <button
            className="flex-1 px-3 py-2 bg-primary/10 border border-primary/30 rounded-lg text-xs text-primary font-mono hover:bg-primary/20 transition-colors"
            onClick={confirm}
          >
            Agregar
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Sidebar Section ─────────────────────────────────────────────────────────

function SidebarSection({
  title,
  children,
  defaultOpen = true,
}: {
  title: string;
  children: ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="mb-1">
      <button
        className="w-full flex items-center justify-between px-3 py-2 text-xs font-semibold text-muted-foreground uppercase tracking-widest font-mono hover:text-foreground transition-colors"
        onClick={() => setOpen((v) => !v)}
      >
        {title}
        {open ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
      </button>
      {open && <div className="px-2 pb-1 space-y-1">{children}</div>}
    </div>
  );
}

function SidebarBtn({
  label,
  onClick,
  icon,
  danger,
}: {
  label: string;
  onClick: () => void;
  icon?: string;
  danger?: boolean;
}) {
  return (
    <button
      className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-mono transition-colors text-left
        ${
          danger
            ? "text-red-400 hover:bg-red-500/10 border border-transparent hover:border-red-500/20"
            : "text-foreground hover:bg-white/5 border border-transparent hover:border-border"
        }`}
      onClick={onClick}
    >
      {icon && <span className="text-sm">{icon}</span>}
      {label}
    </button>
  );
}

// ─── Save/Load helpers ────────────────────────────────────────────────────────

type ApiFloorPlan = {
  tables?: Array<{
    id: string;
    label: string;
    shape: "rect" | "round";
    seats: number;
    x: number;
    y: number;
    section?: string;
  }>;
  elements?: Array<{
    id: string;
    kind: "window" | "window_v" | "door" | "bathroom";
    x: number;
    y: number;
    width: number;
    height: number;
    label: string;
  }>;
  zones?: Array<{
    id: string;
    kind: "zone_indoor" | "zone_outdoor";
    x: number;
    y: number;
    width: number;
    height: number;
    label: string;
  }>;
};

function itemsToPayload(items: CanvasItem[]): ApiFloorPlan {
  const tables = items
    .filter((i) => i.kind === "table_rect" || i.kind === "table_round")
    .map((i) => ({
      id: i.id,
      label: i.label,
      shape: (i.kind === "table_rect" ? "rect" : "round") as "rect" | "round",
      seats: i.seats ?? 4,
      x: i.x,
      y: i.y,
      section: i.section ?? "",
    }));

  const elements = items
    .filter((i) => i.kind === "window" || i.kind === "window_v" || i.kind === "door" || i.kind === "bathroom")
    .map((i) => ({
      id: i.id,
      kind: i.kind as "window" | "window_v" | "door" | "bathroom",
      x: i.x,
      y: i.y,
      width: i.width,
      height: i.height,
      label: i.label,
    }));

  const zones = items
    .filter((i) => i.kind === "zone_indoor" || i.kind === "zone_outdoor")
    .map((i) => ({
      id: i.id,
      kind: i.kind as "zone_indoor" | "zone_outdoor",
      x: i.x,
      y: i.y,
      width: i.width,
      height: i.height,
      label: i.label,
    }));

  return { tables, elements, zones };
}

function payloadToItems(data: ApiFloorPlan): CanvasItem[] {
  const items: CanvasItem[] = [];

  (data.zones ?? []).forEach((z) => {
    const dims = DEFAULT_DIMS[z.kind];
    items.push({
      id: z.id,
      kind: z.kind,
      x: z.x,
      y: z.y,
      width: z.width ?? dims.width,
      height: z.height ?? dims.height,
      label: z.label,
    });
  });

  (data.tables ?? []).forEach((t) => {
    const kind: ItemKind = t.shape === "rect" ? "table_rect" : "table_round";
    const dims = DEFAULT_DIMS[kind];
    items.push({
      id: t.id,
      kind,
      x: t.x,
      y: t.y,
      width: dims.width,
      height: dims.height,
      label: t.label,
      seats: t.seats,
      section: (t as any).section ?? "",
    });
  });

  (data.elements ?? []).forEach((el) => {
    items.push({
      id: el.id,
      kind: el.kind,
      x: el.x,
      y: el.y,
      width: el.width,
      height: el.height,
      label: el.label,
    });
  });

  return items;
}

// ─── Kind label helper ────────────────────────────────────────────────────────

function kindDefaultLabel(kind: ItemKind): string {
  const map: Record<ItemKind, string> = {
    table_rect:   "Mesa",
    table_round:  "Mesa",
    window:       "Ventana H",
    window_v:     "Ventana V",
    door:         "Entrada",
    bathroom:     "Baño",
    zone_indoor:  "Interior",
    zone_outdoor: "Exterior",
  };
  return map[kind];
}

// ─── Main Component ───────────────────────────────────────────────────────────

export default function FloorPlanEditor() {
  const navigate = useNavigate();
  const containerRef = useRef<HTMLDivElement>(null);
  const stageRef = useRef<Konva.Stage | null>(null);
  const transformerRef = useRef<Konva.Transformer | null>(null);

  const [canvasSize, setCanvasSize] = useState({ width: 800, height: 600 });
  const [scale, setScale] = useState(1);
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const [isPanning, setIsPanning] = useState(false);
  const [spaceDown, setSpaceDown] = useState(false);
  const [items, setItems] = useState<CanvasItem[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [showTableModal, setShowTableModal] = useState(false);
  const [pendingKind, setPendingKind] = useState<"table_rect" | "table_round" | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  // ─── Canvas resize ─────────────────────────────────────────────────────

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => {
      setCanvasSize({ width: el.offsetWidth, height: el.offsetHeight });
    });
    ro.observe(el);
    setCanvasSize({ width: el.offsetWidth, height: el.offsetHeight });
    return () => ro.disconnect();
  }, []);

  // ─── Load floor plan ────────────────────────────────────────────────────

  useEffect(() => {
    getFloorPlan()
      .then((res) => {
        const data = res.data as ApiFloorPlan;
        const loaded = payloadToItems(data);
        if (loaded.length > 0) setItems(loaded);
      })
      .catch(() => {/* start empty */});
  }, []);

  // ─── Transformer attach ─────────────────────────────────────────────────

  useEffect(() => {
    const tr = transformerRef.current;
    const stage = stageRef.current;
    if (!tr || !stage) return;

    const selectedItem = items.find((i) => i.id === selectedId);
    const isZone = selectedItem?.kind === "zone_indoor" || selectedItem?.kind === "zone_outdoor";

    if (selectedId && isZone) {
      const node = stage.findOne(`#${selectedId}`);
      if (node) {
        tr.nodes([node]);
        tr.getLayer()?.batchDraw();
        return;
      }
    }
    tr.nodes([]);
    tr.getLayer()?.batchDraw();
  }, [selectedId, items]);

  // ─── Keyboard ──────────────────────────────────────────────────────────

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.code === "Space" && !e.repeat) {
        setSpaceDown(true);
        e.preventDefault();
      }
      if ((e.key === "Delete" || e.key === "Backspace") && selectedId) {
        const target = e.target as HTMLElement;
        if (target.tagName === "INPUT" || target.tagName === "TEXTAREA") return;
        setItems((prev) => prev.filter((i) => i.id !== selectedId));
        setSelectedId(null);
      }
      if (e.key === "Escape") {
        setSelectedId(null);
      }
    };
    const onKeyUp = (e: KeyboardEvent) => {
      if (e.code === "Space") setSpaceDown(false);
    };
    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("keyup", onKeyUp);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("keyup", onKeyUp);
    };
  }, [selectedId]);

  // ─── Zoom ──────────────────────────────────────────────────────────────

  const handleWheel = useCallback(
    (e: Konva.KonvaEventObject<WheelEvent>) => {
      e.evt.preventDefault();
      const stage = stageRef.current;
      if (!stage) return;
      const oldScale = scale;
      const pointer = stage.getPointerPosition();
      if (!pointer) return;
      const direction = e.evt.deltaY > 0 ? -1 : 1;
      const factor = 1.08;
      const newScale = direction > 0
        ? Math.min(oldScale * factor, 4)
        : Math.max(oldScale / factor, 0.2);
      const mousePointTo = {
        x: (pointer.x - offset.x) / oldScale,
        y: (pointer.y - offset.y) / oldScale,
      };
      setOffset({
        x: pointer.x - mousePointTo.x * newScale,
        y: pointer.y - mousePointTo.y * newScale,
      });
      setScale(newScale);
    },
    [scale, offset]
  );

  // ─── Pan ───────────────────────────────────────────────────────────────

  const handleStageMouseDown = useCallback(
    (e: Konva.KonvaEventObject<MouseEvent>) => {
      if (spaceDown) {
        setIsPanning(true);
        e.evt.preventDefault();
      }
    },
    [spaceDown]
  );

  const handleStageMouseMove = useCallback(
    (e: Konva.KonvaEventObject<MouseEvent>) => {
      if (!isPanning) return;
      setOffset((prev) => ({
        x: prev.x + e.evt.movementX,
        y: prev.y + e.evt.movementY,
      }));
    },
    [isPanning]
  );

  const handleStageMouseUp = useCallback(() => {
    setIsPanning(false);
  }, []);

  const handleStageClick = useCallback(
    (e: Konva.KonvaEventObject<MouseEvent | TouchEvent>) => {
      if (e.target === stageRef.current) {
        setSelectedId(null);
      }
    },
    []
  );

  // ─── Add item ──────────────────────────────────────────────────────────

  const addItem = useCallback(
    (kind: ItemKind, label?: string, seats?: number, section?: string) => {
      const dims = DEFAULT_DIMS[kind];
      const cx = (canvasSize.width / 2 - offset.x) / scale;
      const cy = (canvasSize.height / 2 - offset.y) / scale;
      const newItem: CanvasItem = {
        id: `${kind}_${Date.now()}`,
        kind,
        x: snap(cx - dims.width / 2),
        y: snap(cy - dims.height / 2),
        width: dims.width,
        height: dims.height,
        label: label ?? kindDefaultLabel(kind),
        seats,
        section,
      };
      setItems((prev) => [...prev, newItem]);
      setSelectedId(newItem.id);
    },
    [canvasSize, offset, scale]
  );

  const handleSidebarClick = (kind: ItemKind) => {
    if (kind === "table_rect" || kind === "table_round") {
      setPendingKind(kind);
      setShowTableModal(true);
    } else {
      addItem(kind);
    }
  };

  const handleTableModalConfirm = (label: string, seats: number, section: string) => {
    if (pendingKind) addItem(pendingKind, label, seats, section);
    setShowTableModal(false);
    setPendingKind(null);
  };

  const handleTableModalCancel = () => {
    setShowTableModal(false);
    setPendingKind(null);
  };

  // ─── Edit table (dblclick) ─────────────────────────────────────────────

  const handleDblClick = (id: string) => {
    const item = items.find((i) => i.id === id);
    if (!item) return;
    if (item.kind === "table_rect" || item.kind === "table_round") {
      setEditingId(id);
    }
  };

  const handleEditConfirm = (label: string, seats: number, section: string) => {
    if (!editingId) return;
    setItems((prev) =>
      prev.map((i) => (i.id === editingId ? { ...i, label, seats, section } : i))
    );
    setEditingId(null);
  };

  // ─── Change item ───────────────────────────────────────────────────────

  const handleChange = useCallback(
    (id: string, patch: Partial<CanvasItem>) => {
      setItems((prev) => prev.map((i) => (i.id === id ? { ...i, ...patch } : i)));
    },
    []
  );

  // ─── Save ──────────────────────────────────────────────────────────────

  const handleSave = async () => {
    setSaving(true);
    try {
      const payload = itemsToPayload(items);
      await saveFloorPlan(payload as Record<string, unknown>);
      setToast("Plano guardado");
      setTimeout(() => setToast(null), 2500);
    } catch {
      setToast("Error al guardar");
      setTimeout(() => setToast(null), 2500);
    } finally {
      setSaving(false);
    }
  };

  // ─── Clear all ─────────────────────────────────────────────────────────

  const handleClear = () => {
    if (window.confirm("¿Eliminar todos los elementos del plano?")) {
      setItems([]);
      setSelectedId(null);
    }
  };

  // ─── Sorted items (zones first) ────────────────────────────────────────

  const sortedItems = [
    ...items.filter((i) => i.kind === "zone_indoor" || i.kind === "zone_outdoor"),
    ...items.filter((i) => i.kind !== "zone_indoor" && i.kind !== "zone_outdoor"),
  ];

  const editingItem = editingId ? items.find((i) => i.id === editingId) : null;

  // ─── Render ────────────────────────────────────────────────────────────

  return (
    <div className="flex h-screen bg-background text-foreground overflow-hidden select-none">
      {/* Sidebar */}
      <aside
        className="flex-none flex flex-col bg-card border-r border-border"
        style={{ width: 220 }}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-3 py-3 border-b border-border gap-2">
          <button
            className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors font-mono"
            onClick={() => navigate("/dashboard")}
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            Volver
          </button>
          <button
            className="flex items-center gap-1.5 px-3 py-1.5 bg-primary/10 border border-primary/30 rounded-lg text-xs text-primary font-mono hover:bg-primary/20 transition-colors disabled:opacity-50"
            onClick={handleSave}
            disabled={saving}
          >
            <Save className="w-3 h-3" />
            {saving ? "..." : "Guardar"}
          </button>
        </div>

        {/* Sections */}
        <div className="flex-1 overflow-y-auto py-2">
          <SidebarSection title="Zonas">
            <SidebarBtn icon="🏠" label="Interior" onClick={() => handleSidebarClick("zone_indoor")} />
            <SidebarBtn icon="🌿" label="Exterior" onClick={() => handleSidebarClick("zone_outdoor")} />
          </SidebarSection>

          <SidebarSection title="Mesas">
            <SidebarBtn icon="⬛" label="Rectangular" onClick={() => handleSidebarClick("table_rect")} />
            <SidebarBtn icon="⭕" label="Redonda" onClick={() => handleSidebarClick("table_round")} />
          </SidebarSection>

          <SidebarSection title="Estructura">
            <SidebarBtn icon="━━" label="Ventana H" onClick={() => handleSidebarClick("window")} />
            <SidebarBtn icon="┃" label="Ventana V" onClick={() => handleSidebarClick("window_v")} />
            <SidebarBtn icon="🚪" label="Puerta" onClick={() => handleSidebarClick("door")} />
            <SidebarBtn icon="🚻" label="Baño" onClick={() => handleSidebarClick("bathroom")} />
          </SidebarSection>

          <SidebarSection title="Herramientas">
            <SidebarBtn
              icon="🗑️"
              label="Limpiar todo"
              onClick={handleClear}
              danger
            />
          </SidebarSection>
        </div>

        {/* Info footer */}
        <div className="px-3 py-2 border-t border-border">
          <p className="text-xs text-muted-foreground font-mono opacity-50">
            {items.length} elementos
          </p>
          <p className="text-xs text-muted-foreground font-mono opacity-40 mt-0.5">
            Scroll=zoom · Space+drag=pan
          </p>
        </div>
      </aside>

      {/* Canvas */}
      <div
        ref={containerRef}
        className="flex-1 relative"
        style={{
          background: "#0f0f11",
          cursor: spaceDown ? (isPanning ? "grabbing" : "grab") : "default",
        }}
      >
        <Stage
          ref={stageRef}
          width={canvasSize.width}
          height={canvasSize.height}
          scaleX={scale}
          scaleY={scale}
          x={offset.x}
          y={offset.y}
          onWheel={handleWheel}
          onMouseDown={handleStageMouseDown}
          onMouseMove={handleStageMouseMove}
          onMouseUp={handleStageMouseUp}
          onClick={handleStageClick}
          onTap={handleStageClick}
          style={{ display: "block" }}
        >
          {/* Background grid layer */}
          <Layer listening={false}>
            <DotGrid
              width={canvasSize.width}
              height={canvasSize.height}
              scale={scale}
              offsetX={offset.x}
              offsetY={offset.y}
            />
          </Layer>

          {/* Items layer */}
          <Layer>
            {sortedItems.map((item) => (
              <CanvasItemShape
                key={item.id}
                item={item}
                isSelected={item.id === selectedId}
                onSelect={setSelectedId}
                onChange={handleChange}
                onDblClick={handleDblClick}
              />
            ))}
            <Transformer
              ref={transformerRef}
              boundBoxFunc={(oldBox, newBox) => {
                if (newBox.width < 60 || newBox.height < 60) return oldBox;
                return newBox;
              }}
              rotateEnabled={false}
              borderStroke={C.selected}
              anchorStroke={C.selected}
              anchorFill="#0f0f11"
            />
          </Layer>
        </Stage>

        {/* Zoom indicator */}
        <div className="absolute bottom-4 left-4 text-xs text-muted-foreground font-mono opacity-50 pointer-events-none">
          {Math.round(scale * 100)}%
        </div>
      </div>

      {/* Table modal (add) */}
      {showTableModal && (
        <TableModal
          title={pendingKind === "table_rect" ? "Nueva Mesa Rectangular" : "Nueva Mesa Redonda"}
          onConfirm={handleTableModalConfirm}
          onCancel={handleTableModalCancel}
        />
      )}

      {/* Table modal (edit) */}
      {editingItem && (
        <TableModal
          title="Editar Mesa"
          initial={{ label: editingItem.label, seats: editingItem.seats ?? 4, section: editingItem.section ?? "" }}
          onConfirm={handleEditConfirm}
          onCancel={() => setEditingId(null)}
        />
      )}

      {/* Toast */}
      {toast && (
        <div className="fixed bottom-6 right-6 z-50 px-4 py-2.5 bg-card border border-border rounded-xl text-sm font-mono text-foreground shadow-xl animate-in fade-in slide-in-from-bottom-2 duration-200">
          {toast}
        </div>
      )}
    </div>
  );
}
