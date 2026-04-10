import { useState, useEffect, useRef, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useI18n } from "../contexts/i18nContext";
import {
  Plus, LogOut, X, Users, Phone, Clock, AlertTriangle, CalendarX, Loader2,
  Search, Utensils, MessageSquare, Send, Bot, LayoutGrid, Map, Sun, Moon, Calendar, Zap,
} from "lucide-react";
import {
  listReservations,
  createReservation,
  cancelReservation,
  updateReservationStatus,
  triggerConfirmationCall,
  getConfirmationConfig,
  updateConfirmationConfig,
  agentChat,
  setAuthToken,
  getFloorPlan,
  getAssignments,
  assignTable,
  unassignTable,
  type Reservation,
  type ReservationStatus,
  type CreateReservationPayload,
  type FloorPlanTable,
} from "../lib/api";
import FloorPlanViewer from "../components/FloorPlanViewer";
import HourTimeline from "../components/HourTimeline";

// ─── Helpers ────────────────────────────────────────────────────────────────

function getDays() {
  const days = [];
  for (let i = 0; i < 10; i++) {
    const d = new Date();
    d.setDate(d.getDate() + i);
    days.push(d);
  }
  return days;
}

function formatDate(d: Date) {
  return d.toISOString().split("T")[0];
}

function formatDayLabel(d: Date) {
  const today = new Date();
  if (formatDate(d) === formatDate(today)) return "Today";
  if (formatDate(d) === formatDate(new Date(today.getTime() + 86400000))) return "Tomorrow";
  return d.toLocaleDateString("en-US", { weekday: "short", day: "numeric" });
}

// ─── Constants ───────────────────────────────────────────────────────────────

const STATUS_COLORS: Record<ReservationStatus, string> = {
  confirmed: "bg-emerald-500/15 text-emerald-600 border-emerald-500/25",
  cancelled:  "bg-red-500/15 text-red-500 border-red-500/25",
  no_show:    "bg-gray-500/15 text-gray-500 border-gray-400/25",
  seated:     "bg-blue-500/15 text-blue-500 border-blue-500/25",
};

const STATUS_LABELS: Record<ReservationStatus, string> = {
  confirmed: "Confirmed",
  cancelled:  "Cancelled",
  no_show:    "No show",
  seated:     "Seated",
};

const TABLE_PREFS = ["Window", "Patio", "Booth", "Bar", "Private", "Quiet"];

const HOURS: string[] = [];
for (let h = 12; h <= 23; h++) {
  HOURS.push(`${String(h).padStart(2, "0")}:00`);
  HOURS.push(`${String(h).padStart(2, "0")}:30`);
}

// ─── CutleryIcon ─────────────────────────────────────────────────────────────

function CutleryIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
      <g transform="translate(16,16)" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <line x1="-4" y1="-11" x2="-4" y2="11"/>
        <line x1="-6" y1="-11" x2="-6" y2="-5"/>
        <line x1="-2" y1="-11" x2="-2" y2="-5"/>
        <path d="M-6 -5 Q-4 -2 -2 -5"/>
        <line x1="4" y1="-11" x2="4" y2="11"/>
        <path d="M4 -11 Q7 -8 4 -4"/>
      </g>
    </svg>
  );
}

// ─── UserMenu ────────────────────────────────────────────────────────────────

function UserMenu({ user, role, isDark, onToggleDark, onLogout }: { user: string; role: string; isDark: boolean; onToggleDark: () => void; onLogout: () => void }) {
  const { language, setLanguage, t } = useI18n();
  const [isOpen, setIsOpen] = useState(false);
  const [showConfirmConfig, setShowConfirmConfig] = useState(false);
  const [confirmMinutes, setConfirmMinutes] = useState(60);
  const [configSaving, setConfigSaving] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <div ref={menuRef} className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-border text-foreground hover:bg-muted transition-colors"
      >
        <div className="w-6 h-6 rounded-full bg-primary/20 flex items-center justify-center text-primary font-bold text-xs uppercase">
          {user[0]}
        </div>
        <span className="text-sm font-medium hidden sm:inline">{user}</span>
        <span className="text-xs font-medium hidden sm:inline opacity-60">({role})</span>
      </button>

      {isOpen && (
        <div className="absolute right-0 mt-2 w-48 bg-card border border-border rounded-lg shadow-lg overflow-hidden z-40">
          <div className="px-3 py-2 border-b border-border">
            <p className="text-xs text-muted-foreground">{t("header.loggedInAs")}</p>
            <p className="text-sm font-semibold text-foreground">{user}</p>
          </div>

          <button
            onClick={() => {
              onToggleDark();
              setIsOpen(false);
            }}
            className="w-full flex items-center justify-between px-3 py-2 text-sm text-foreground hover:bg-muted transition-colors"
          >
            <span>{isDark ? t("header.lightMode") : t("header.darkMode")}</span>
            {isDark ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
          </button>

          <div className="border-t border-border" />

          <div className="px-3 py-2">
            <p className="text-xs text-muted-foreground mb-2">{t("header.language")}</p>
            <div className="flex gap-2">
              <button
                onClick={() => {
                  setLanguage("en");
                  setIsOpen(false);
                }}
                className={`flex-1 py-1 rounded text-xs font-medium transition-colors ${
                  language === "en"
                    ? "bg-primary/20 text-primary border border-primary/30"
                    : "border border-border text-muted-foreground hover:bg-muted"
                }`}
              >
                EN
              </button>
              <button
                onClick={() => {
                  setLanguage("es");
                  setIsOpen(false);
                }}
                className={`flex-1 py-1 rounded text-xs font-medium transition-colors ${
                  language === "es"
                    ? "bg-primary/20 text-primary border border-primary/30"
                    : "border border-border text-muted-foreground hover:bg-muted"
                }`}
              >
                ES
              </button>
            </div>
          </div>

          {role === "admin" && (
            <>
              <div className="border-t border-border" />
              <div className="px-3 py-2">
                <button
                  onClick={async () => {
                    if (!showConfirmConfig) {
                      try {
                        const res = await getConfirmationConfig();
                        setConfirmMinutes(res.data.confirmation_call_minutes_before);
                      } catch { /* use default */ }
                    }
                    setShowConfirmConfig(!showConfirmConfig);
                  }}
                  className="w-full text-left text-xs font-medium text-foreground hover:text-primary transition-colors"
                >
                  Confirmation call config
                </button>
                {showConfirmConfig && (
                  <div className="mt-2 flex items-center gap-2">
                    <input
                      type="number"
                      min={5}
                      value={confirmMinutes}
                      onChange={(e) => setConfirmMinutes(Number(e.target.value))}
                      className="w-16 px-2 py-1 rounded border border-border text-xs bg-background text-foreground"
                    />
                    <span className="text-xs text-muted-foreground">min before</span>
                    <button
                      disabled={configSaving}
                      onClick={async () => {
                        setConfigSaving(true);
                        try {
                          await updateConfirmationConfig(confirmMinutes);
                          setShowConfirmConfig(false);
                        } catch { /* ignore */ }
                        setConfigSaving(false);
                      }}
                      className="px-2 py-1 rounded text-xs font-medium bg-primary text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-40"
                    >
                      {configSaving ? "..." : "Save"}
                    </button>
                  </div>
                )}
              </div>
            </>
          )}

          <div className="border-t border-border" />

          <button
            onClick={() => {
              onLogout();
              setIsOpen(false);
            }}
            className="w-full flex items-center gap-2 px-3 py-2 text-sm text-destructive hover:bg-destructive/10 transition-colors"
          >
            <LogOut className="w-4 h-4" />
            {t("header.signOut")}
          </button>
        </div>
      )}
    </div>
  );
}

// ─── ConfirmDialog ───────────────────────────────────────────────────────────

function ConfirmDialog({ onConfirm, onCancel }: { onConfirm: () => void; onCancel: () => void }) {
  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="bg-card border border-border rounded-2xl w-full max-w-sm shadow-2xl p-6">
        <div className="flex items-start gap-4 mb-5">
          <div className="w-10 h-10 rounded-full bg-destructive/10 flex items-center justify-center flex-shrink-0 mt-0.5">
            <AlertTriangle className="w-5 h-5 text-destructive" />
          </div>
          <div>
            <h2 className="font-semibold text-foreground">Cancel reservation?</h2>
            <p className="text-sm text-muted-foreground mt-0.5">This action cannot be undone.</p>
          </div>
        </div>
        <div className="flex gap-2">
          <button
            onClick={onCancel}
            className="flex-1 py-2 border border-border rounded-lg text-sm text-foreground hover:bg-muted transition-colors"
          >
            Keep it
          </button>
          <button
            onClick={onConfirm}
            className="flex-1 py-2 bg-destructive text-destructive-foreground rounded-lg text-sm font-medium hover:bg-destructive/90 transition-colors"
          >
            Cancel reservation
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── ReservationCard ─────────────────────────────────────────────────────────

const CONFIRM_COLORS: Record<string, string> = {
  pending: "bg-yellow-500/10 text-yellow-600 border-yellow-500/30",
  confirmed: "bg-emerald-500/10 text-emerald-600 border-emerald-500/30",
  declined: "bg-red-500/10 text-red-600 border-red-500/30",
  no_answer: "bg-gray-500/10 text-gray-500 border-gray-500/30",
  failed: "bg-red-500/10 text-red-600 border-red-500/30",
};
const CONFIRM_LABELS: Record<string, string> = {
  pending: "Not called",
  confirmed: "Confirmed",
  declined: "Declined",
  no_answer: "No answer",
  failed: "Call failed",
};

function ReservationCard({
  r,
  onCancel,
  onSeat,
  onCall,
  onClick,
  isCancelling,
  isSeating,
  isCalling,
  canWrite,
  assignedTable,
}: {
  r: Reservation;
  onCancel: (id: string) => void;
  onSeat: (id: string) => void;
  onCall: (id: string) => void;
  onClick: () => void;
  isCancelling: boolean;
  isSeating: boolean;
  isCalling: boolean;
  canWrite: boolean;
  assignedTable?: string | null;
}) {
  const cs = r.confirmation_status || "pending";
  return (
    <div className="bg-card border border-border rounded-xl p-4 hover:border-primary/40 transition-colors flex flex-col gap-3 cursor-pointer" onClick={onClick}>
      {/* Guest name + status */}
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-foreground truncate">{r.guest_name}</p>
          <div className="flex items-center gap-1.5 mt-1 flex-wrap">
            <span
              className={`inline-flex text-xs px-2 py-0.5 rounded-full border font-medium ${STATUS_COLORS[r.status]}`}
            >
              {STATUS_LABELS[r.status]}
            </span>
            <span
              className={`inline-flex text-xs px-2 py-0.5 rounded-full border font-medium ${CONFIRM_COLORS[cs] || CONFIRM_COLORS.pending}`}
            >
              {CONFIRM_LABELS[cs] || cs}
            </span>
          </div>
        </div>
        {r.status === "confirmed" && canWrite && (
          <button
            onClick={() => onCancel(r.reservation_id)}
            disabled={isCancelling}
            className="flex-shrink-0 p-1.5 text-muted-foreground hover:text-destructive hover:bg-destructive/10 rounded-lg transition-colors disabled:opacity-40"
            title="Cancel reservation"
            aria-label={`Cancel reservation for ${r.guest_name}`}
          >
            {isCancelling ? <Loader2 className="w-4 h-4 animate-spin" /> : <X className="w-4 h-4" />}
          </button>
        )}
      </div>

      {/* Details */}
      <div className="flex flex-col gap-1.5">
        <div className="flex items-center gap-3 text-xs text-muted-foreground">
          <span className="flex items-center gap-1">
            <Clock className="w-3 h-3 flex-shrink-0" />
            {r.time}
          </span>
          <span className="flex items-center gap-1">
            <Users className="w-3 h-3 flex-shrink-0" />
            {r.party_size} {r.party_size === 1 ? "guest" : "guests"}
          </span>
        </div>
        <div className="flex items-center gap-1 text-xs text-muted-foreground">
          <Phone className="w-3 h-3 flex-shrink-0" />
          <span className="truncate">{r.guest_phone}</span>
        </div>
        <div className="flex items-center gap-1 text-xs text-muted-foreground">
          <Map className="w-3 h-3 flex-shrink-0" />
          <span>{assignedTable ? `Table: ${assignedTable}` : "No table assigned"}</span>
        </div>
        {r.confirmation_called_at && (
          <p className="text-xs text-muted-foreground">
            Called: {new Date(r.confirmation_called_at).toLocaleString()}
          </p>
        )}
        {r.notes && (
          <p className="text-xs text-muted-foreground italic border-t border-border/60 pt-2 mt-0.5">
            "{r.notes}"
          </p>
        )}
      </div>

      {/* Actions */}
      <div className="flex gap-2">
        {r.status === "confirmed" && canWrite && (cs === "pending" || cs === "failed" || cs === "no_answer") && (
          <button
            onClick={() => onCall(r.reservation_id)}
            disabled={isCalling}
            className="flex items-center justify-center gap-1.5 flex-1 py-1.5 rounded-lg text-xs font-medium border border-emerald-500/30 text-emerald-600 hover:bg-emerald-500/10 transition-colors disabled:opacity-40"
          >
            {isCalling ? <Loader2 className="w-3 h-3 animate-spin" /> : <Phone className="w-3 h-3" />}
            {cs === "failed" || cs === "no_answer" ? "Retry Call" : "Call to Confirm"}
          </button>
        )}
        {r.status === "confirmed" && canWrite && (
          <button
            onClick={() => onSeat(r.reservation_id)}
            disabled={isSeating}
            className="flex items-center justify-center gap-1.5 flex-1 py-1.5 rounded-lg text-xs font-medium border border-blue-500/30 text-blue-500 hover:bg-blue-500/10 transition-colors disabled:opacity-40"
          >
            {isSeating ? <Loader2 className="w-3 h-3 animate-spin" /> : <Utensils className="w-3 h-3" />}
            Mark as Seated
          </button>
        )}
      </div>
    </div>
  );
}

// ─── CreateModal ─────────────────────────────────────────────────────────────

function CreateModal({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [form, setForm] = useState<CreateReservationPayload>({
    guest_name: "",
    guest_phone: "",
    date: formatDate(new Date()),
    time: "20:00",
    party_size: 2,
    notes: "",
  });
  const [error, setError] = useState("");

  const mut = useMutation({
    mutationFn: () => createReservation(form),
    onSuccess: () => { onCreated(); onClose(); },
    onError: (e: unknown) => {
      setError(e instanceof Error ? e.message : "Failed to create reservation");
    },
  });

  const field = (key: keyof CreateReservationPayload, value: string | number) =>
    setForm((f) => ({ ...f, [key]: value }));

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="bg-card border border-border rounded-2xl w-full max-w-md shadow-2xl">
        <div className="flex items-center justify-between p-5 border-b border-border">
          <h2 className="font-semibold text-foreground">New Reservation</h2>
          <button
            onClick={onClose}
            className="text-muted-foreground hover:text-foreground transition-colors"
            aria-label="Close"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
        <div className="p-5 space-y-3">
          {[
            { label: "Guest Name", key: "guest_name" as const, type: "text", placeholder: "Ana García" },
            { label: "Phone", key: "guest_phone" as const, type: "tel", placeholder: "+5491155551234" },
            { label: "Date", key: "date" as const, type: "date" },
            { label: "Time", key: "time" as const, type: "time" },
          ].map(({ label, key, type, placeholder }) => (
            <div key={key}>
              <label className="block text-xs font-medium text-muted-foreground mb-1">{label}</label>
              <input
                type={type}
                value={String(form[key])}
                placeholder={placeholder}
                onChange={(e) => field(key, e.target.value)}
                className="w-full px-3 py-2 bg-input border border-border rounded-lg text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/50 transition-shadow"
              />
            </div>
          ))}
          <div>
            <label className="block text-xs font-medium text-muted-foreground mb-1">Party Size</label>
            <input
              type="number"
              min={1}
              max={20}
              value={form.party_size}
              onChange={(e) => field("party_size", parseInt(e.target.value) || 1)}
              className="w-full px-3 py-2 bg-input border border-border rounded-lg text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary/50 transition-shadow"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-muted-foreground mb-1">Notes</label>
            <input
              type="text"
              value={form.notes ?? ""}
              placeholder="Window table preferred"
              onChange={(e) => field("notes", e.target.value)}
              className="w-full px-3 py-2 bg-input border border-border rounded-lg text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/50 transition-shadow"
            />
          </div>
          {error && <p className="text-destructive text-xs">{error}</p>}
        </div>
        <div className="flex gap-2 p-5 border-t border-border">
          <button
            onClick={onClose}
            className="flex-1 py-2 border border-border rounded-lg text-sm text-foreground hover:bg-muted transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={() => mut.mutate()}
            disabled={mut.isPending}
            className="flex-1 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90 transition-colors disabled:opacity-50"
          >
            {mut.isPending ? "Creating…" : "Create"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── ChatPanel ───────────────────────────────────────────────────────────────

type ChatMsg = { role: "user" | "agent"; text: string; isError?: boolean };

function ChatPanel({ onClose }: { onClose: () => void }) {
  const sessionId = useRef(`chat-${Date.now()}`);
  const [msgs, setMsgs] = useState<ChatMsg[]>([
    { role: "agent", text: "Ciao! I'm HostAI. How can I help you?" },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [msgs]);

  const send = async () => {
    const text = input.trim();
    if (!text || loading) return;
    setInput("");
    setMsgs((m) => [...m, { role: "user", text }]);
    setLoading(true);
    try {
      const res = await agentChat(sessionId.current, text);
      setMsgs((m) => [...m, { role: "agent", text: res.data.final_response || "…" }]);
    } catch {
      setMsgs((m) => [...m, { role: "agent", text: "Error contacting agent.", isError: true }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed bottom-4 right-4 z-50 w-80 bg-card border border-border rounded-2xl shadow-2xl flex flex-col overflow-hidden" style={{ height: "420px" }}>
      <div className="flex items-center justify-between px-4 py-3 border-b border-border bg-primary/5">
        <div className="flex items-center gap-2">
          <Bot className="w-4 h-4 text-primary" />
          <span className="text-sm font-semibold text-foreground">HostAI Chat</span>
        </div>
        <button onClick={onClose} className="text-muted-foreground hover:text-foreground transition-colors">
          <X className="w-4 h-4" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-3 flex flex-col gap-2">
        {msgs.map((m, i) => (
          <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
            <div
              className={`max-w-[85%] text-xs px-3 py-2 rounded-xl whitespace-pre-wrap ${
                m.role === "user"
                  ? "bg-primary text-primary-foreground rounded-br-sm"
                  : m.isError
                    ? "bg-red-500/20 text-red-600 border border-red-500/30 rounded-bl-sm"
                    : "bg-muted text-foreground rounded-bl-sm"
              }`}
            >
              {m.text}
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex justify-start">
            <div className="bg-muted rounded-xl rounded-bl-sm px-3 py-2">
              <Loader2 className="w-3 h-3 animate-spin text-muted-foreground" />
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <div className="border-t border-border p-2 flex gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
          placeholder="Type a message…"
          className="flex-1 text-xs px-3 py-2 bg-input border border-border rounded-lg text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary/50"
        />
        <button
          onClick={send}
          disabled={!input.trim() || loading}
          className="p-2 bg-primary text-primary-foreground rounded-lg disabled:opacity-40 hover:bg-primary/90 transition-colors"
        >
          <Send className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  );
}


// ─── Dashboard ───────────────────────────────────────────────────────────────

export default function Dashboard() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { t } = useI18n();
  const days = useMemo(() => getDays(), []);
  const [selectedDay, setSelectedDay] = useState(formatDate(days[0]));
  const [selectedPrefs, setSelectedPrefs] = useState<Set<string>>(new Set());
  const [search, setSearch] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [showChat, setShowChat] = useState(false);
  const [confirmCancelId, setConfirmCancelId] = useState<string | null>(null);
  const [toast, setToast] = useState<{ msg: string; ok: boolean } | null>(null);
  const dayScrollRef = useRef<HTMLDivElement>(null);
  const sseRef = useRef<EventSource | null>(null);

  const currentUser = localStorage.getItem("ha_username") ?? "user";
  const currentRole = localStorage.getItem("ha_role") ?? "reader";
  const isWriter = currentRole === "admin" || currentRole === "writer";

  // ─── Dark mode ────────────────────────────────────────────────────────────
  const [isDark, setIsDark] = useState(() => localStorage.getItem("ha_theme") === "dark");

  useEffect(() => {
    document.documentElement.classList.toggle("dark", isDark);
    localStorage.setItem("ha_theme", isDark ? "dark" : "light");
  }, [isDark]);

  const [viewMode, setViewMode] = useState<"cards" | "floorplan">("cards");
  const [selectedHour, setSelectedHour] = useState<string>(() => {
    const now = new Date();
    return `${String(now.getHours()).padStart(2, "0")}:00`;
  });
  const [selectedReservationId, setSelectedReservationId] = useState<string | null>(null);
  const [selectedTableId, setSelectedTableId] = useState<string | null>(null);
  const [showFloorPlanModal, setShowFloorPlanModal] = useState(false);
  const [isAutoAssigning, setIsAutoAssigning] = useState(false);
  const [showAssignModal, setShowAssignModal] = useState(false);
  const [cardHourFilter, setCardHourFilter] = useState<string>("all");
  const [cardDetailReservation, setCardDetailReservation] = useState<Reservation | null>(null);

  const canEditFloorPlan = localStorage.getItem("ha_can_edit_floor_plan") === "true" || currentRole === "admin";

  // Restore JWT token
  useEffect(() => {
    const token = localStorage.getItem("ha_token");
    if (!token) { navigate("/login"); return; }
    setAuthToken(token);
  }, [navigate]);

  // Auto-scroll day picker to today on mount
  useEffect(() => {
    const el = dayScrollRef.current?.querySelector("[data-today='true']") as HTMLElement | null;
    el?.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "center" });
  }, []);

  // SSE live updates
  useEffect(() => {
    const es = new EventSource("/api/v1/reservations/stream");
    sseRef.current = es;
    es.onmessage = () => qc.invalidateQueries({ queryKey: ["reservations"] });
    return () => es.close();
  }, [qc]);

  const toastTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const showToast = (msg: string, ok = true) => {
    if (toastTimerRef.current) clearTimeout(toastTimerRef.current);
    setToast({ msg, ok });
    toastTimerRef.current = setTimeout(() => setToast(null), 3000);
  };
  useEffect(() => () => { if (toastTimerRef.current) clearTimeout(toastTimerRef.current); }, []);

  const { data, isLoading } = useQuery({
    queryKey: ["reservations"],
    queryFn: () => listReservations(1, 500).then((r) => r.data),
    refetchInterval: 60_000,
  });

  const { data: floorPlanData } = useQuery({
    queryKey: ["floor-plan"],
    queryFn: () => getFloorPlan().then(r => r.data),
    enabled: viewMode === "floorplan",
  });

  const { data: assignmentsData } = useQuery({
    queryKey: ["floor-plan-assignments", selectedDay],
    queryFn: () => getAssignments(selectedDay).then(r => r.data),
    refetchInterval: 30_000,
  });

  const cancelMut = useMutation({
    mutationFn: (id: string) => cancelReservation(id, "Cancelled via dashboard"),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["reservations"] });
      showToast("Reservation cancelled");
    },
    onError: () => showToast("Cancel failed", false),
  });

  const seatMut = useMutation({
    mutationFn: (id: string) => updateReservationStatus(id, "seated"),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["reservations"] });
      showToast("Guest seated");
    },
    onError: () => showToast("Update failed", false),
  });

  const callConfirmMut = useMutation({
    mutationFn: (id: string) => triggerConfirmationCall(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["reservations"] });
      showToast("Confirmation call initiated");
    },
    onError: () => showToast("Confirmation call failed", false),
  });

  const unassignMut = useMutation({
    mutationFn: (params: { reservation_id: string; date: string; hour: string }) =>
      unassignTable(params.reservation_id, params.date, params.hour),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["floor-plan-assignments"] });
      setShowFloorPlanModal(false);
      setSelectedTableId(null);
      showToast("Table unassigned");
    },
    onError: () => showToast("Unassign failed", false),
  });

  // Auto-assign logic
  const handleAutoAssign = async () => {
    if (isAutoAssigning || !floorPlanData) return;
    setIsAutoAssigning(true);
    try {
      const tables = (floorPlanData.tables || []) as FloorPlanTable[];
      const assignedIds = new Set((assignmentsData?.assignments || []).map(a => a.reservation_id));
      const hourReservations = dayReservations.filter(r => {
        const [rH] = r.time.split(":");
        const [sH] = selectedHour.split(":");
        return rH === sH;
      });
      const unassigned = hourReservations.filter(r => !assignedIds.has(r.reservation_id));

      // Sort: reservations with preferences first
      const withPrefs = unassigned.filter(r => r.preference);
      const noPrefs = unassigned.filter(r => !r.preference);
      const sorted = [...withPrefs, ...noPrefs];

      let usedTables = new Set(assignmentsData?.assignments.map(a => a.table_id) || []);
      let assigned = 0;

      for (const res of sorted) {
        // Find best matching table
        let bestTable: FloorPlanTable | null = null;

        // First, try tables whose section matches the reservation preference
        if (res.preference) {
          const pref = res.preference.toLowerCase();
          for (const table of tables) {
            if (usedTables.has(table.id) || table.seats < res.party_size) continue;
            const section = (table.section || "").toLowerCase();
            if (!section) continue;
            if (pref.includes(section) || section.includes(pref.split(" ")[0])) {
              bestTable = table;
              break;
            }
          }
        }

        // If no preference match, find smallest available table that fits
        if (!bestTable) {
          let smallestFit: FloorPlanTable | null = null;
          for (const table of tables) {
            if (usedTables.has(table.id) || table.seats < res.party_size) continue;
            if (!smallestFit || table.seats < smallestFit.seats) {
              smallestFit = table;
            }
          }
          bestTable = smallestFit;
        }

        // Assign if found
        if (bestTable) {
          try {
            await assignTable({
              table_id: bestTable.id,
              reservation_id: res.reservation_id,
              date: selectedDay,
              hour: selectedHour,
            });
            usedTables.add(bestTable.id);
            assigned++;
          } catch (e) {
            console.error("Failed to assign table:", e);
          }
        }
      }

      qc.invalidateQueries({ queryKey: ["floor-plan-assignments"] });
      showToast(`Auto-assigned ${assigned}/${unassigned.length} reservations`);
    } finally {
      setIsAutoAssigning(false);
    }
  };

  const allReservations = data?.reservations ?? [];

  const dayReservations = useMemo(
    () => allReservations.filter((r) => r.date === selectedDay && r.status !== "cancelled"),
    [allReservations, selectedDay]
  );

  const filteredReservations = useMemo(
    () =>
      dayReservations.filter((r) => {
        const matchesHour =
          cardHourFilter === "all" ||
          r.time.startsWith(cardHourFilter.split(":")[0]);
        const matchesPref =
          selectedPrefs.size === 0 ||
          Array.from(selectedPrefs).some((p) =>
            (r.preference && r.preference.toLowerCase().includes(p.toLowerCase())) ||
            (r.notes && r.notes.toLowerCase().includes(p.toLowerCase()))
          );
        const s = search.trim().toLowerCase();
        const matchesSearch =
          !s ||
          r.guest_name.toLowerCase().includes(s) ||
          r.guest_phone.includes(s) ||
          (r.notes && r.notes.toLowerCase().includes(s));
        return matchesHour && matchesPref && matchesSearch;
      }),
    [dayReservations, selectedPrefs, search, cardHourFilter]
  );

  const floorPlanFilteredReservations = useMemo(
    () =>
      dayReservations.filter((r) => {
        const matchesPref =
          selectedPrefs.size === 0 ||
          Array.from(selectedPrefs).some((p) =>
            (r.preference && r.preference.toLowerCase().includes(p.toLowerCase())) ||
            (r.notes && r.notes.toLowerCase().includes(p.toLowerCase()))
          );
        const s = search.trim().toLowerCase();
        const matchesSearch =
          !s ||
          r.guest_name.toLowerCase().includes(s) ||
          r.guest_phone.includes(s) ||
          (r.notes && r.notes.toLowerCase().includes(s));
        return matchesPref && matchesSearch;
      }),
    [dayReservations, selectedPrefs, search]
  );

  const togglePref = (p: string) =>
    setSelectedPrefs((prev) => {
      const n = new Set(prev);
      n.has(p) ? n.delete(p) : n.add(p);
      return n;
    });

  const logout = () => {
    localStorage.removeItem("ha_token");
    localStorage.removeItem("ha_username");
    localStorage.removeItem("ha_role");
    navigate("/login");
  };

  // Today's stats
  const todayStr = formatDate(days[0]);
  const todayAll = allReservations.filter((r) => r.date === todayStr);
  const todayTotal   = todayAll.length;
  const todaySeated  = todayAll.filter((r) => r.status === "seated").length;
  const todayPending = todayAll.filter((r) => r.status === "confirmed").length;

  return (
    <div className="flex h-screen bg-background overflow-hidden flex-col">
      {/* ─── Header ──────────────────────────────────────────────────────── */}
      <header className="bg-card border-b border-border px-6 py-3 flex items-center justify-between gap-4">
        {/* Brand */}
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-xl flex items-center justify-center" style={{background:"#1a1208", border:"1px solid rgba(232,213,163,0.2)"}}>
            <CutleryIcon className="w-4 h-4 text-[#e8d5a3]" />
          </div>
          <span className="font-semibold text-sm text-foreground">{t("app.title")}</span>
        </div>

        {/* Stats */}
        <div className="flex items-center gap-6 text-sm">
          <div className="text-center">
            <p className="text-xl font-bold text-foreground">{todayTotal}</p>
            <p className="text-xs text-muted-foreground">{t("header.today")}</p>
          </div>
          <div className="text-center">
            <p className="text-xl font-bold text-emerald-500">{todaySeated}</p>
            <p className="text-xs text-muted-foreground">{t("header.seated")}</p>
          </div>
          <div className="text-center">
            <p className="text-xl font-bold text-amber-500">{todayPending}</p>
            <p className="text-xs text-muted-foreground">{t("header.incoming")}</p>
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-3">
          <button
            onClick={() => setShowChat((v) => !v)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium border transition-colors ${
              showChat
                ? "bg-primary/20 text-primary border-primary/30"
                : "border-border text-muted-foreground hover:bg-muted hover:text-foreground"
            }`}
            title={t("header.chat")}
          >
            <MessageSquare className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">{t("header.chat")}</span>
          </button>
          {isWriter && (
            <button
              onClick={() => setShowCreate(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90 transition-colors"
            >
              <Plus className="w-3.5 h-3.5" />
              {t("header.newReservation")}
            </button>
          )}
          <UserMenu
            user={currentUser}
            role={currentRole}
            isDark={isDark}
            onToggleDark={() => setIsDark((v) => !v)}
            onLogout={logout}
          />
        </div>
      </header>

      {/* ─── Day picker ──────────────────────────────────────────────────── */}
      <div className="bg-card border-b border-border flex items-center flex-shrink-0">
        <div ref={dayScrollRef} className="flex-1 px-4 py-1.5 flex gap-1 overflow-x-auto day-scroll min-w-0">
          {days.map((d) => {
            const ds = formatDate(d);
            const isToday = ds === formatDate(days[0]);
            const count = allReservations.filter((r) => r.date === ds && r.status !== "cancelled").length;
            const active = ds === selectedDay;
            return (
              <button
                key={ds}
                data-today={isToday ? "true" : undefined}
                onClick={() => setSelectedDay(ds)}
                className={`flex-shrink-0 flex flex-col items-center px-3 py-1.5 rounded-xl text-xs transition-colors ${
                  active
                    ? "bg-primary/20 text-primary font-medium"
                    : "text-muted-foreground hover:bg-muted hover:text-foreground"
                }`}
              >
                <span>{formatDayLabel(d)}</span>
                <span className="text-[10px] opacity-60">
                  {d.toLocaleDateString("en-US", { month: "short" })}
                </span>
                {count > 0 && (
                  <span className={`mt-0.5 w-5 h-5 rounded-full flex items-center justify-center text-xs font-medium ${
                    active ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"
                  }`}>
                    {count}
                  </span>
                )}
              </button>
            );
          })}
        </div>
        {/* Auto-assign + Hour selector — only in floor plan mode, pinned right */}
        {viewMode === "floorplan" && (
          <div className="flex-shrink-0 px-3 border-l border-border flex items-center gap-3">
            {/* Auto-assign button (left) */}
            {(() => {
              const assignedIds = new Set((assignmentsData?.assignments || []).map(a => a.reservation_id));
              const hourRes = dayReservations.filter(r => {
                const [rH] = r.time.split(":");
                const [sH] = selectedHour.split(":");
                return rH === sH && r.status !== "cancelled";
              });
              const unassignedCount = hourRes.filter(r => !assignedIds.has(r.reservation_id)).length;
              if (unassignedCount === 0) return null;
              return (
                <button
                  onClick={handleAutoAssign}
                  disabled={isAutoAssigning}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-primary/20 text-primary border border-primary/30 hover:bg-primary/30 transition-colors disabled:opacity-50"
                >
                  <Zap className="w-3 h-3" />
                  {isAutoAssigning ? "…" : `Auto-assign (${unassignedCount})`}
                </button>
              );
            })()}
            {/* Hour selector with title */}
            <div className="flex flex-col items-start">
              <span className="text-[10px] text-muted-foreground font-medium mb-0.5">Selección de hora</span>
              <select
                value={selectedHour}
                onChange={(e) => setSelectedHour(e.target.value)}
                className="px-2 py-1 bg-input border border-border rounded-lg text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary/50"
              >
                {HOURS.map(h => {
                  const hh = h.split(":")[0];
                  const cnt = dayReservations.filter(r => r.time.startsWith(hh + ":") && r.status !== "cancelled").length;
                  return (
                    <option key={h} value={h}>
                      {h}{cnt > 0 ? `  ●  ${cnt} reservas` : ""}
                    </option>
                  );
                })}
              </select>
            </div>
          </div>
        )}
      </div>

      {/* ─── Unified toolbar: View toggle (left) | Preference filters (center) | Search (right) ──── */}
      <div className="bg-card border-b border-border px-4 py-2 flex items-center gap-3 flex-shrink-0">
        {/* Left: View toggle + optional hour selector for cards */}
        <div className="flex items-center gap-2 flex-shrink-0">
          <button
            onClick={() => setViewMode("cards")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${
              viewMode === "cards"
                ? "bg-primary/20 text-primary border-primary/30"
                : "border-border text-muted-foreground hover:bg-muted"
            }`}
          >
            <LayoutGrid className="w-3.5 h-3.5" />
            {t("view.cards")}
          </button>
          <button
            onClick={() => setViewMode("floorplan")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${
              viewMode === "floorplan"
                ? "bg-primary/20 text-primary border-primary/30"
                : "border-border text-muted-foreground hover:bg-muted"
            }`}
          >
            <Map className="w-3.5 h-3.5" />
            {t("view.floorPlan")}
          </button>
          {viewMode === "cards" && (
            <div className="flex items-center gap-1.5 border-l border-border pl-3">
              <Calendar className="w-3.5 h-3.5 text-muted-foreground flex-shrink-0" />
              <select
                value={cardHourFilter}
                onChange={(e) => setCardHourFilter(e.target.value)}
                className="px-2 py-1 bg-input border border-border rounded-lg text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary/50"
              >
                <option value="all">All hours</option>
                {HOURS.map(h => {
                  const hh = h.split(":")[0];
                  const cnt = dayReservations.filter(r => r.time.startsWith(hh + ":")).length;
                  return (
                    <option key={h} value={h}>
                      {h}{cnt > 0 ? ` · ${cnt}` : ""}
                    </option>
                  );
                })}
              </select>
            </div>
          )}
        </div>

        {/* Center: Preference filters (horizontal scroll, no wrap) */}
        <div className="flex items-center gap-2 flex-1 overflow-x-auto min-w-0 py-0.5">
          <span className="text-xs text-muted-foreground whitespace-nowrap flex-shrink-0">{t("view.filter")}:</span>
          {TABLE_PREFS.map((p) => (
            <button
              key={p}
              onClick={() => togglePref(p)}
              className={`flex-shrink-0 px-2.5 py-1 rounded-full text-xs font-medium border transition-colors ${
                selectedPrefs.has(p)
                  ? "bg-primary/20 text-primary border-primary/30"
                  : "border-border text-muted-foreground hover:bg-muted hover:text-foreground"
              }`}
            >
              {p}
            </button>
          ))}
          {selectedPrefs.size > 0 && (
            <button
              onClick={() => setSelectedPrefs(new Set())}
              className="flex-shrink-0 text-xs text-muted-foreground hover:text-foreground underline transition-colors"
            >
              Clear
            </button>
          )}
        </div>

        {/* Right: Search */}
        <div className="relative flex-shrink-0 w-44">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground pointer-events-none" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search…"
            className="w-full pl-8 pr-3 py-1.5 text-xs bg-input border border-border rounded-lg text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary/50"
          />
        </div>
      </div>

      {/* ─── Main content ───────────────────────────────────────────────── */}
      {viewMode === "cards" ? (
        <main className="flex-1 min-h-0 overflow-y-auto p-6">
          {isLoading ? (
            <div className="flex items-center justify-center h-32 gap-2 text-muted-foreground text-sm">
              <Loader2 className="w-4 h-4 animate-spin" />
              Loading…
            </div>
          ) : filteredReservations.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-48 gap-3 text-muted-foreground">
              <CalendarX className="w-10 h-10 opacity-30" />
              <p className="text-sm">
                No reservations for {selectedDay === formatDate(days[0]) ? "today" : selectedDay}
                {selectedPrefs.size > 0 && " matching the selected filters"}
              </p>
              {isWriter && selectedPrefs.size === 0 && (
                <button
                  onClick={() => setShowCreate(true)}
                  className="flex items-center gap-1.5 text-sm text-primary hover:underline"
                >
                  <Plus className="w-3.5 h-3.5" />
                  Create one
                </button>
              )}
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
              {filteredReservations.map((r) => (
                <ReservationCard
                  key={r.reservation_id}
                  r={r}
                  canWrite={isWriter}
                  onCancel={(id) => setConfirmCancelId(id)}
                  onSeat={(id) => seatMut.mutate(id)}
                  onCall={(id) => callConfirmMut.mutate(id)}
                  onClick={() => setCardDetailReservation(r)}
                  isCancelling={cancelMut.isPending && cancelMut.variables === r.reservation_id}
                  isSeating={seatMut.isPending && seatMut.variables === r.reservation_id}
                  isCalling={callConfirmMut.isPending && callConfirmMut.variables === r.reservation_id}
                  assignedTable={(assignmentsData?.assignments ?? []).find(a => a.reservation_id === r.reservation_id)?.table_id}
                />
              ))}
            </div>
          )}
        </main>
      ) : (
        <div className="flex flex-1 min-h-0 overflow-hidden">
          {/* Left panel — Hour Timeline */}
          <div className="w-64 flex-shrink-0 border-r border-border bg-card overflow-hidden flex flex-col" style={{minHeight:0}}>
            <HourTimeline
              reservations={floorPlanFilteredReservations}
              assignments={assignmentsData?.assignments ?? []}
              selectedHour={selectedHour}
              onHourChange={setSelectedHour}
              onReservationClick={(r) => {
                setSelectedReservationId(r.reservation_id);
                const assignment = assignmentsData?.assignments.find(
                  a => a.reservation_id === r.reservation_id && a.hour === selectedHour
                );
                setSelectedTableId(assignment?.table_id ?? null);
                setShowFloorPlanModal(true);
                if (!assignment) setShowAssignModal(true);
              }}
              selectedReservationId={selectedReservationId}
            />
          </div>

          {/* Center panel — Blueprint */}
          <div className="flex-1 relative overflow-hidden bg-background">
            {!floorPlanData || floorPlanData.tables.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full gap-3 text-muted-foreground">
                <Map className="w-10 h-10 opacity-20" />
                <p className="text-sm">No floor plan configured yet</p>
                {canEditFloorPlan && (
                  <p className="text-xs opacity-60">Use the Edit button to set up the floor plan</p>
                )}
              </div>
            ) : (
              <FloorPlanViewer
                tables={floorPlanData.tables}
                elements={floorPlanData.elements}
                zones={floorPlanData.zones}
                assignments={(assignmentsData?.assignments ?? []).filter(a => a.hour === selectedHour)}
                reservations={floorPlanFilteredReservations}
                selectedTableId={selectedTableId}
                onTableClick={(_reservation, tableId) => {
                  setSelectedTableId(tableId ?? null);
                  setSelectedReservationId(_reservation?.reservation_id ?? null);
                  setShowFloorPlanModal(!!tableId);
                }}
              />
            )}

            {/* Edit button — only if canEditFloorPlan */}
            {canEditFloorPlan && (
              <button
                className="absolute bottom-4 right-4 flex items-center gap-1.5 px-4 py-2 bg-card border border-border rounded-xl text-xs font-medium text-muted-foreground hover:border-primary/40 hover:text-primary transition-colors shadow-lg"
                onClick={() => navigate("/floor-plan-editor")}
              >
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125" />
                </svg>
                Editar Plano
              </button>
            )}
          </div>
        </div>
      )}

      {/* ─── Modals ──────────────────────────────────────────────────────── */}
      {showCreate && (
        <CreateModal
          onClose={() => setShowCreate(false)}
          onCreated={() => qc.invalidateQueries({ queryKey: ["reservations"] })}
        />
      )}

      {confirmCancelId && (
        <ConfirmDialog
          onCancel={() => setConfirmCancelId(null)}
          onConfirm={() => {
            cancelMut.mutate(confirmCancelId);
            setConfirmCancelId(null);
          }}
        />
      )}

      {/* ─── Chat ────────────────────────────────────────────────────────── */}
      {showChat && <ChatPanel onClose={() => setShowChat(false)} />}

      {/* ─── Card Detail Modal ──────────────────────────────────────────── */}
      {cardDetailReservation && (() => {
        const rd = cardDetailReservation;
        const cs = rd.confirmation_status || "pending";
        const tableAssignment = (assignmentsData?.assignments ?? []).find(
          a => a.reservation_id === rd.reservation_id
        );
        const tableInfo = tableAssignment ? (floorPlanData?.tables ?? []).find(t => t.id === tableAssignment.table_id) : null;
        return (
          <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4" onClick={() => setCardDetailReservation(null)}>
            <div className="bg-card border border-border rounded-2xl w-full max-w-md shadow-2xl p-5" onClick={e => e.stopPropagation()}>
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-semibold text-foreground text-lg">{rd.guest_name}</h3>
                <button onClick={() => setCardDetailReservation(null)} className="p-1 rounded-lg hover:bg-muted transition-colors">
                  <X className="w-4 h-4" />
                </button>
              </div>
              <div className="space-y-2 text-sm">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className={`inline-flex text-xs px-2 py-0.5 rounded-full border font-medium ${STATUS_COLORS[rd.status]}`}>{STATUS_LABELS[rd.status]}</span>
                  <span className={`inline-flex text-xs px-2 py-0.5 rounded-full border font-medium ${CONFIRM_COLORS[cs] || CONFIRM_COLORS.pending}`}>{CONFIRM_LABELS[cs] || cs}</span>
                </div>
                <p className="text-muted-foreground"><Clock className="w-3.5 h-3.5 inline mr-1" />{rd.date} at {rd.time}</p>
                <p className="text-muted-foreground"><Users className="w-3.5 h-3.5 inline mr-1" />{rd.party_size} guests</p>
                <p className="text-muted-foreground"><Phone className="w-3.5 h-3.5 inline mr-1" />{rd.guest_phone}</p>
                {tableAssignment ? (
                  <div className="flex items-center gap-2">
                    <p className="text-muted-foreground"><Map className="w-3.5 h-3.5 inline mr-1" />Table: {tableInfo?.label || tableAssignment.table_id}{tableInfo?.section ? ` (${tableInfo.section})` : ""} — {tableAssignment.hour}</p>
                    {isWriter && (
                      <button
                        onClick={async () => {
                          await unassignTable(rd.reservation_id, tableAssignment.date, tableAssignment.hour);
                          qc.invalidateQueries({ queryKey: ["floor-plan-assignments"] });
                          setCardDetailReservation({ ...rd });
                          showToast("Table unassigned");
                        }}
                        className="text-xs px-2 py-0.5 rounded border border-red-500/30 text-red-500 hover:bg-red-500/10 transition-colors"
                      >
                        Unassign
                      </button>
                    )}
                  </div>
                ) : (
                  <p className="text-muted-foreground"><Map className="w-3.5 h-3.5 inline mr-1" />No table assigned</p>
                )}
                {rd.preference && <p className="text-muted-foreground">Preference: {rd.preference}</p>}
                {rd.special_requests && <p className="text-muted-foreground">Special: {rd.special_requests}</p>}
                {rd.notes && <p className="text-muted-foreground italic">"{rd.notes}"</p>}
                {rd.confirmation_called_at && <p className="text-xs text-muted-foreground">Called: {new Date(rd.confirmation_called_at).toLocaleString()}</p>}
                <p className="text-xs text-muted-foreground">Created: {new Date(rd.created_at).toLocaleString()}</p>
              </div>
              {rd.status === "confirmed" && isWriter && (
                <div className="flex flex-wrap gap-2 mt-4">
                  {(cs === "pending" || cs === "failed" || cs === "no_answer") && (
                    <button
                      onClick={() => { callConfirmMut.mutate(rd.reservation_id); setCardDetailReservation(null); }}
                      className="flex-1 flex items-center justify-center gap-1.5 py-2 rounded-lg text-xs font-medium border border-emerald-500/30 text-emerald-600 hover:bg-emerald-500/10 transition-colors"
                    >
                      <Phone className="w-3 h-3" /> {cs === "failed" || cs === "no_answer" ? "Retry Call" : "Call to Confirm"}
                    </button>
                  )}
                  <button
                    onClick={() => { seatMut.mutate(rd.reservation_id); setCardDetailReservation(null); }}
                    className="flex-1 flex items-center justify-center gap-1.5 py-2 rounded-lg text-xs font-medium border border-blue-500/30 text-blue-500 hover:bg-blue-500/10 transition-colors"
                  >
                    <Utensils className="w-3 h-3" /> Seat
                  </button>
                  <button
                    onClick={() => { setConfirmCancelId(rd.reservation_id); setCardDetailReservation(null); }}
                    className="flex-1 flex items-center justify-center gap-1.5 py-2 rounded-lg text-xs font-medium border border-red-500/30 text-red-500 hover:bg-red-500/10 transition-colors"
                  >
                    <X className="w-3 h-3" /> Cancel
                  </button>
                </div>
              )}
            </div>
          </div>
        );
      })()}

      {/* ─── Floor Plan Table Modal (occupied table or table details) ──── */}
      {showFloorPlanModal && selectedTableId && !showAssignModal && (() => {
        const tableInfo = floorPlanData?.tables.find(t => t.id === selectedTableId);
        const assignment = assignmentsData?.assignments.find(a => a.table_id === selectedTableId && a.hour === selectedHour);
        const res = assignment
          ? dayReservations.find(r => r.reservation_id === assignment.reservation_id) ?? null
          : null;
        const closeModal = () => { setShowFloorPlanModal(false); setSelectedTableId(null); setSelectedReservationId(null); };

        // Unassigned reservations for current hour (for assigning to free table)
        const assignedIds = new Set((assignmentsData?.assignments ?? []).filter(a => a.hour === selectedHour).map(a => a.reservation_id));
        const hourReservations = dayReservations.filter(r => {
          const [rH] = r.time.split(":");
          const [sH] = selectedHour.split(":");
          return rH === sH && r.status !== "cancelled";
        });
        const unassignedReservations = hourReservations.filter(r => !assignedIds.has(r.reservation_id));

        return (
          <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
            <div className="bg-card border border-border rounded-2xl w-full max-w-sm shadow-2xl overflow-hidden">
              {/* Header */}
              <div className="flex items-start justify-between p-5 border-b border-border">
                <div>
                  <div className="flex items-center gap-2">
                    <p className="font-semibold text-foreground">{tableInfo?.label ?? selectedTableId}</p>
                    <span className="text-xs text-muted-foreground border border-border rounded px-1.5 py-0.5">{tableInfo?.seats ?? "?"} seats</span>
                  </div>
                  {res ? (
                    <span className={`inline-flex mt-1.5 text-xs px-2 py-0.5 rounded-full border font-medium ${STATUS_COLORS[res.status]}`}>
                      {STATUS_LABELS[res.status]}
                    </span>
                  ) : (
                    <span className="inline-flex mt-1.5 text-xs px-2 py-0.5 rounded-full border font-medium bg-emerald-500/10 text-emerald-500 border-emerald-500/30">
                      Available
                    </span>
                  )}
                </div>
                <button onClick={closeModal} className="text-muted-foreground hover:text-foreground transition-colors">
                  <X className="w-5 h-5" />
                </button>
              </div>

              {res ? (
                <>
                  {/* Reservation details */}
                  <div className="p-5 space-y-3">
                    <div>
                      <p className="text-base font-semibold text-foreground">{res.guest_name}</p>
                    </div>
                    <div className="grid grid-cols-2 gap-2 text-sm">
                      <div className="flex items-center gap-2 text-muted-foreground">
                        <Clock className="w-4 h-4 flex-shrink-0" />
                        <span>{res.time}</span>
                      </div>
                      <div className="flex items-center gap-2 text-muted-foreground">
                        <Users className="w-4 h-4 flex-shrink-0" />
                        <span>{res.party_size} guests</span>
                      </div>
                      <div className="flex items-center gap-2 text-muted-foreground col-span-2">
                        <Phone className="w-4 h-4 flex-shrink-0" />
                        <span>{res.guest_phone}</span>
                      </div>
                      <div className="flex items-center gap-2 text-muted-foreground col-span-2">
                        <Calendar className="w-4 h-4 flex-shrink-0" />
                        <span>Reserved on {new Date(res.created_at).toLocaleDateString("en-US", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}</span>
                      </div>
                    </div>
                    {res.preference && (
                      <div className="flex items-center gap-1.5">
                        <span className="text-xs text-muted-foreground">Preference:</span>
                        <span className="text-xs px-2 py-0.5 rounded-full bg-primary/10 text-primary border border-primary/20 font-medium">{res.preference}</span>
                      </div>
                    )}
                    {res.notes && (
                      <p className="text-xs text-muted-foreground italic border-t border-border pt-2 mt-1">"{res.notes}"</p>
                    )}
                    {assignment && (
                      <div className="text-xs text-muted-foreground border-t border-border pt-2">
                        Table assigned for <span className="font-medium text-foreground">{assignment.hour}</span>
                      </div>
                    )}
                  </div>

                  {/* Actions */}
                  {isWriter && (
                    <div className="flex flex-col gap-2 p-5 border-t border-border">
                      {res.status === "confirmed" && (
                        <button
                          onClick={() => { seatMut.mutate(res.reservation_id); closeModal(); }}
                          disabled={seatMut.isPending}
                          className="w-full flex items-center justify-center gap-1.5 py-2 rounded-lg text-xs font-medium border border-blue-500/30 text-blue-500 hover:bg-blue-500/10 transition-colors disabled:opacity-50"
                        >
                          <Utensils className="w-3 h-3" />
                          Mark as Seated
                        </button>
                      )}
                      {res.status === "confirmed" && (
                        <button
                          onClick={() => { setConfirmCancelId(res.reservation_id); closeModal(); }}
                          className="w-full flex items-center justify-center gap-1.5 py-2 rounded-lg text-xs font-medium border border-destructive/30 text-destructive hover:bg-destructive/10 transition-colors"
                        >
                          <X className="w-3 h-3" />
                          Cancel Reservation
                        </button>
                      )}
                      {assignment && (
                        <button
                          onClick={() => unassignMut.mutate({ reservation_id: assignment.reservation_id, date: assignment.date, hour: assignment.hour })}
                          disabled={unassignMut.isPending}
                          className="w-full flex items-center justify-center gap-1.5 py-2 rounded-lg text-xs font-medium border border-amber-500/30 text-amber-500 hover:bg-amber-500/10 transition-colors disabled:opacity-50"
                        >
                          {unassignMut.isPending ? <Loader2 className="w-3 h-3 animate-spin" /> : <Map className="w-3 h-3" />}
                          Unassign Table
                        </button>
                      )}
                    </div>
                  )}
                </>
              ) : (
                <div className="p-5">
                  <p className="text-sm text-muted-foreground mb-3">No reservation assigned for <span className="font-medium text-foreground">{selectedHour}</span></p>
                  {isWriter && unassignedReservations.length > 0 ? (
                    <div className="space-y-1.5">
                      <p className="text-xs text-muted-foreground font-medium mb-2">Assign a reservation:</p>
                      <div className="max-h-48 overflow-y-auto space-y-1">
                        {unassignedReservations.map(r => (
                          <button
                            key={r.reservation_id}
                            onClick={async () => {
                              try {
                                const resHour = r.time.split(":")[0] + ":00";
                                await assignTable({ table_id: selectedTableId!, reservation_id: r.reservation_id, date: selectedDay, hour: resHour });
                                qc.invalidateQueries({ queryKey: ["floor-plan-assignments"] });
                                showToast(`${r.guest_name} → ${tableInfo?.label ?? selectedTableId}`);
                                closeModal();
                              } catch { showToast("Assign failed", false); }
                            }}
                            className="w-full text-left p-2.5 rounded-lg border border-border hover:border-primary/40 hover:bg-primary/5 transition-colors"
                          >
                            <p className="text-xs font-medium text-foreground">{r.guest_name}</p>
                            <div className="flex items-center gap-2 mt-0.5 text-xs text-muted-foreground">
                              <span>{r.time}</span>
                              <span>·</span>
                              <span>{r.party_size}p</span>
                              {r.preference && <span className="px-1.5 py-0.5 rounded bg-primary/10 text-primary text-[10px]">{r.preference}</span>}
                            </div>
                          </button>
                        ))}
                      </div>
                    </div>
                  ) : isWriter ? (
                    <p className="text-xs text-muted-foreground opacity-60">No unassigned reservations at this hour</p>
                  ) : null}
                </div>
              )}
            </div>
          </div>
        );
      })()}

      {/* ─── Assign Table Modal (reservation without table) ────────────── */}
      {showAssignModal && selectedReservationId && (() => {
        const res = dayReservations.find(r => r.reservation_id === selectedReservationId);
        if (!res) return null;
        const hourAssignments = (assignmentsData?.assignments ?? []).filter(a => a.hour === selectedHour);
        const usedTableIds = new Set(hourAssignments.map(a => a.table_id));
        const freeTables = (floorPlanData?.tables ?? []).filter(t => !usedTableIds.has(t.id) && t.seats >= res.party_size);
        const closeModal = () => { setShowAssignModal(false); setSelectedReservationId(null); setSelectedTableId(null); setShowFloorPlanModal(false); };

        return (
          <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
            <div className="bg-card border border-border rounded-2xl w-full max-w-sm shadow-2xl overflow-hidden">
              {/* Header */}
              <div className="flex items-start justify-between p-5 border-b border-border">
                <div>
                  <p className="font-semibold text-foreground">{res.guest_name}</p>
                  <div className="flex items-center gap-2 mt-1 text-xs text-muted-foreground">
                    <Clock className="w-3 h-3" /><span>{res.time}</span>
                    <Users className="w-3 h-3 ml-1" /><span>{res.party_size}p</span>
                  </div>
                  {res.preference && (
                    <span className="inline-flex mt-1.5 text-xs px-2 py-0.5 rounded-full bg-primary/10 text-primary border border-primary/20 font-medium">{res.preference}</span>
                  )}
                </div>
                <button onClick={closeModal} className="text-muted-foreground hover:text-foreground transition-colors">
                  <X className="w-5 h-5" />
                </button>
              </div>

              {/* Free tables list */}
              <div className="p-5">
                {freeTables.length > 0 ? (
                  <div className="space-y-1.5">
                    <p className="text-xs text-muted-foreground font-medium mb-2">Choose a table:</p>
                    <div className="max-h-48 overflow-y-auto space-y-1">
                      {freeTables
                        .sort((a, b) => a.seats - b.seats)
                        .map(t => (
                        <button
                          key={t.id}
                          onClick={async () => {
                            try {
                              await assignTable({ table_id: t.id, reservation_id: res.reservation_id, date: selectedDay, hour: selectedHour });
                              qc.invalidateQueries({ queryKey: ["floor-plan-assignments"] });
                              showToast(`${res.guest_name} → ${t.label}`);
                              closeModal();
                            } catch { showToast("Assign failed", false); }
                          }}
                          className={`w-full text-left p-2.5 rounded-lg border transition-colors ${
                            t.seats >= res.party_size
                              ? "border-border hover:border-primary/40 hover:bg-primary/5"
                              : "border-destructive/20 opacity-50"
                          }`}
                        >
                          <div className="flex items-center justify-between">
                            <p className="text-xs font-medium text-foreground">{t.label}</p>
                            <span className="text-xs text-muted-foreground">{t.section || "General"}</span>
                            <span className={`text-xs ${t.seats >= res.party_size ? "text-muted-foreground" : "text-destructive"}`}>{t.seats} seats</span>
                          </div>
                        </button>
                      ))}
                    </div>
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground text-center py-4">No free tables available</p>
                )}
              </div>
            </div>
          </div>
        );
      })()}

      {/* ─── Toast ───────────────────────────────────────────────────────── */}
      {toast && (
        <div
          className={`fixed bottom-4 right-4 px-4 py-3 rounded-xl text-sm font-medium shadow-lg transition-opacity ${
            toast.ok ? "bg-emerald-600 text-white" : "bg-destructive text-destructive-foreground"
          }`}
        >
          {toast.msg}
        </div>
      )}
    </div>
  );
}
