import axios from "axios";

const BASE = "/api/v1";
export const apiClient = axios.create({ baseURL: BASE });

// JWT Bearer token
export function setAuthToken(token: string) {
  apiClient.defaults.headers.common["Authorization"] = `Bearer ${token}`;
}

// Legacy alias
export function setApiKey(key: string) {
  apiClient.defaults.headers.common["X-API-Key"] = key;
}

// Auto-restore from localStorage
const storedToken = localStorage.getItem("ha_token");
if (storedToken) setAuthToken(storedToken);

// Types
export type ReservationStatus = "confirmed" | "cancelled" | "no_show" | "seated";

export type ConfirmationStatus = "pending" | "confirmed" | "declined" | "no_answer" | "failed";

export interface Reservation {
  reservation_id: string;
  guest_name: string;
  guest_phone: string;
  date: string;
  time: string;
  party_size: number;
  status: ReservationStatus;
  notes: string | null;
  preference: string | null;
  special_requests: string | null;
  confirmation_status: ConfirmationStatus;
  confirmation_called_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface CreateReservationPayload {
  guest_name: string;
  guest_phone: string;
  date: string;
  time: string;
  party_size: number;
  notes?: string;
}

// API
export const getHealth = () => apiClient.get("/../../health");

export const listReservations = (
  page = 1,
  pageSize = 50,
  status?: ReservationStatus
) =>
  apiClient.get<{ reservations: Reservation[]; total: number; page: number; page_size: number }>(
    "/reservations",
    { params: { page, page_size: pageSize, ...(status ? { status } : {}) } }
  );

export const createReservation = (data: CreateReservationPayload) =>
  apiClient.post<{ reservation_id: string; status: string; message: string; confirmation_call_scheduled_at: string }>(
    "/reservations",
    data
  );

export const getReservation = (id: string) =>
  apiClient.get<Reservation>(`/reservations/${id}`);

export const cancelReservation = (id: string, reason?: string) =>
  apiClient.request<{ reservation_id: string; status: string; message: string }>({
    method: "DELETE",
    url: `/reservations/${id}`,
    data: { reason },
    headers: { "Content-Type": "application/json" },
  });

export const updateReservationStatus = (id: string, status: ReservationStatus) =>
  apiClient.patch<{ reservation_id: string; status: string }>(`/reservations/${id}/status`, { status });

export const triggerConfirmationCall = (id: string) =>
  apiClient.post<{ reservation_id: string; call_sid: string; status: string; message: string }>(
    `/voice/outbound/${id}`
  );

export const updateConfirmationStatus = (id: string, status: ConfirmationStatus) =>
  apiClient.patch<{ reservation_id: string; confirmation_status: string }>(
    `/reservations/${id}/confirmation`,
    { status }
  );

export const getConfirmationConfig = () =>
  apiClient.get<{ confirmation_call_minutes_before: number }>("/config/confirmation");

export const updateConfirmationConfig = (minutes: number) =>
  apiClient.patch<{ confirmation_call_minutes_before: number; message: string }>(
    "/config/confirmation",
    { confirmation_call_minutes_before: minutes }
  );

export const agentChat = (session_id: string, message: string) =>
  apiClient.post<{ session_id: string; final_response: string; intent: string | null; reservation_data: Record<string, unknown> | null }>(
    "/agent/chat",
    { session_id, message }
  );

// ─── Floor Plan ───────────────────────────────────────────────────────────────

export interface FloorPlanTable {
  id: string;
  label: string;
  shape: "rect" | "round";
  seats: number;
  x: number;
  y: number;
  section?: string;
}

export interface FloorPlanElement {
  id: string;
  kind: "window" | "window_v" | "door" | "bathroom";
  x: number;
  y: number;
  width: number;
  height: number;
  label: string;
}

export interface FloorPlanZone {
  id: string;
  kind: "zone_indoor" | "zone_outdoor";
  x: number;
  y: number;
  width: number;
  height: number;
  label: string;
}

export interface FloorPlanLayout {
  tables: FloorPlanTable[];
  elements?: FloorPlanElement[];
  zones?: FloorPlanZone[];
}

export interface TableAssignment {
  table_id: string;
  reservation_id: string;
  date: string;
  hour: string;
}

export interface AssignmentsForHour {
  date: string;
  hour: string;
  assignments: TableAssignment[];
}

export const getFloorPlan = () =>
  apiClient.get<FloorPlanLayout>("/floor-plan");

export const saveFloorPlan = (layout: Record<string, unknown>) =>
  apiClient.put<{ message: string; tables: number }>("/floor-plan", layout);

export const getAssignments = (date: string, hour?: string) =>
  apiClient.get<AssignmentsForHour>("/floor-plan/assignments", { params: hour ? { date, hour } : { date } });

export const assignTable = (data: { table_id: string; reservation_id: string; date: string; hour: string }) =>
  apiClient.post<{ message: string; assignment: TableAssignment }>("/floor-plan/assignments", data);

export const unassignTable = (reservation_id: string, date: string, hour: string) =>
  apiClient.delete(`/floor-plan/assignments/${reservation_id}`, { params: { date, hour } });
