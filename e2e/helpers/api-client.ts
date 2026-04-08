/**
 * API Client
 * ==========
 * Cliente HTTP tipado para todos los endpoints del backend de HostAI.
 * Se usa tanto en tests de API como en fixtures de UI que necesitan setup via API.
 *
 * Uso tipico:
 *   const api = new ApiClient(request);
 *   await api.login("admin", "1234");
 *   const res = await api.createReservation({ ... });
 */
import { APIRequestContext, APIResponse } from "@playwright/test";
import type { ApiReservationPayload } from "./test-data";

const API_BASE = process.env.API_URL ?? "http://localhost:8000";
const API_KEY = process.env.API_KEY ?? "dev-secret-key";

export class ApiClient {
  private token: string | null = null;

  constructor(private request: APIRequestContext) {}

  // ═══════════════════════════════════════════════════════════════════════════
  // Autenticacion
  // ═══════════════════════════════════════════════════════════════════════════

  /**
   * Autentica un usuario y almacena el JWT para requests posteriores.
   * @throws Error si las credenciales son invalidas
   */
  async login(username = "admin", password = "1234"): Promise<string> {
    const res = await this.request.post(`${API_BASE}/api/v1/auth/token`, {
      form: { username, password, grant_type: "password" },
    });
    if (!res.ok()) {
      throw new Error(`Login failed for ${username}: ${res.status()} ${await res.text()}`);
    }
    const body = await res.json();
    this.token = body.access_token;
    return this.token!;
  }

  /** Devuelve los headers de autenticacion (API Key + JWT si hay) */
  private headers(): Record<string, string> {
    const h: Record<string, string> = { "X-API-Key": API_KEY };
    if (this.token) h["Authorization"] = `Bearer ${this.token}`;
    return h;
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // Health
  // ═══════════════════════════════════════════════════════════════════════════

  /** GET /health — Verifica que el backend este corriendo */
  async health(): Promise<APIResponse> {
    return this.request.get(`${API_BASE}/health`);
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // Reservas
  // ═══════════════════════════════════════════════════════════════════════════

  /** POST /reservations — Crea una nueva reserva */
  async createReservation(data: ApiReservationPayload): Promise<APIResponse> {
    return this.request.post(`${API_BASE}/api/v1/reservations`, {
      headers: this.headers(),
      data,
    });
  }

  /** GET /reservations — Lista reservas con paginacion y filtro opcional */
  async listReservations(params?: {
    page?: number;
    page_size?: number;
    status?: string;
  }): Promise<APIResponse> {
    return this.request.get(`${API_BASE}/api/v1/reservations`, {
      headers: this.headers(),
      params,
    });
  }

  /** GET /reservations/:id — Obtiene una reserva por UUID */
  async getReservation(id: string): Promise<APIResponse> {
    return this.request.get(`${API_BASE}/api/v1/reservations/${id}`, {
      headers: this.headers(),
    });
  }

  /** PATCH /reservations/:id/status — Cambia el estado (confirmed, seated, no_show, cancelled) */
  async updateStatus(id: string, status: string): Promise<APIResponse> {
    return this.request.patch(`${API_BASE}/api/v1/reservations/${id}/status`, {
      headers: this.headers(),
      data: { status },
    });
  }

  /** DELETE /reservations/:id — Cancela una reserva con razon opcional */
  async cancelReservation(id: string, reason?: string): Promise<APIResponse> {
    return this.request.delete(`${API_BASE}/api/v1/reservations/${id}`, {
      headers: this.headers(),
      data: { reason },
    });
  }

  /** PATCH /reservations/:id/confirmation — Actualiza estado de llamada de confirmacion */
  async updateConfirmation(id: string, status: string): Promise<APIResponse> {
    return this.request.patch(`${API_BASE}/api/v1/reservations/${id}/confirmation`, {
      headers: this.headers(),
      data: { status },
    });
  }

  /** GET /reservations/stream?once=true — Obtiene snapshot SSE */
  async getReservationsSnapshot(): Promise<APIResponse> {
    return this.request.get(`${API_BASE}/api/v1/reservations/stream?once=true`, {
      headers: this.headers(),
    });
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // Agente de Chat
  // ═══════════════════════════════════════════════════════════════════════════

  /** POST /agent/chat — Envia un mensaje al agente conversacional */
  async agentChat(message: string, sessionId?: string): Promise<APIResponse> {
    return this.request.post(`${API_BASE}/api/v1/agent/chat`, {
      headers: this.headers(),
      data: { message, session_id: sessionId },
    });
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // Floor Plan
  // ═══════════════════════════════════════════════════════════════════════════

  /** GET /floor-plan — Carga el plano del restaurante */
  async getFloorPlan(): Promise<APIResponse> {
    return this.request.get(`${API_BASE}/api/v1/floor-plan`, {
      headers: this.headers(),
    });
  }

  /** PUT /floor-plan — Guarda el plano del restaurante (requiere admin/can_edit) */
  async saveFloorPlan(layout: object): Promise<APIResponse> {
    return this.request.put(`${API_BASE}/api/v1/floor-plan`, {
      headers: this.headers(),
      data: layout,
    });
  }

  /** GET /floor-plan/assignments — Obtiene asignaciones mesa-reserva para una fecha */
  async getAssignments(date: string, hour?: string): Promise<APIResponse> {
    const params: Record<string, string> = { date };
    if (hour) params.hour = hour;
    return this.request.get(`${API_BASE}/api/v1/floor-plan/assignments`, {
      headers: this.headers(),
      params,
    });
  }

  /** POST /floor-plan/assignments — Asigna una mesa a una reserva */
  async assignTable(data: {
    table_id: string;
    reservation_id: string;
    date: string;
    hour: string;
  }): Promise<APIResponse> {
    return this.request.post(`${API_BASE}/api/v1/floor-plan/assignments`, {
      headers: this.headers(),
      data,
    });
  }

  /** DELETE /floor-plan/assignments/:id — Desasigna una mesa */
  async unassignTable(reservationId: string, date: string, hour: string): Promise<APIResponse> {
    return this.request.delete(`${API_BASE}/api/v1/floor-plan/assignments/${reservationId}`, {
      headers: this.headers(),
      params: { date, hour },
    });
  }

  /** GET /floor-plan/availability — Consulta mesas disponibles */
  async getAvailability(date: string, hour: string, partySize = 2, section?: string): Promise<APIResponse> {
    const params: Record<string, string | number> = { date, hour, party_size: partySize };
    if (section) params.section = section;
    return this.request.get(`${API_BASE}/api/v1/floor-plan/availability`, {
      headers: this.headers(),
      params,
    });
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // Configuracion
  // ═══════════════════════════════════════════════════════════════════════════

  /** GET /config/confirmation — Lee la config de llamadas de confirmacion */
  async getConfirmationConfig(): Promise<APIResponse> {
    return this.request.get(`${API_BASE}/api/v1/config/confirmation`, {
      headers: this.headers(),
    });
  }

  /** PATCH /config/confirmation — Actualiza minutos antes de la llamada (requiere admin) */
  async setConfirmationConfig(minutes: number): Promise<APIResponse> {
    return this.request.patch(`${API_BASE}/api/v1/config/confirmation`, {
      headers: this.headers(),
      data: { confirmation_call_minutes_before: minutes },
    });
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // Usuarios
  // ═══════════════════════════════════════════════════════════════════════════

  /** GET /auth/users — Lista todos los usuarios (requiere admin) */
  async listUsers(): Promise<APIResponse> {
    return this.request.get(`${API_BASE}/api/v1/auth/users`, {
      headers: this.headers(),
    });
  }

  /** POST /auth/users — Crea o actualiza un usuario (requiere admin) */
  async createUser(username: string, password: string, role = "reader"): Promise<APIResponse> {
    return this.request.post(`${API_BASE}/api/v1/auth/users`, {
      headers: this.headers(),
      data: { username, password, role },
    });
  }

  /** PATCH /auth/users/:username/permissions — Actualiza permisos */
  async updatePermissions(username: string, canEditFloorPlan: boolean): Promise<APIResponse> {
    return this.request.patch(`${API_BASE}/api/v1/auth/users/${username}/permissions`, {
      headers: this.headers(),
      data: { can_edit_floor_plan: canEditFloorPlan },
    });
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // Voz
  // ═══════════════════════════════════════════════════════════════════════════

  /** POST /voice/outbound/:id — Dispara una llamada de confirmacion manual */
  async triggerOutboundCall(reservationId: string): Promise<APIResponse> {
    return this.request.post(`${API_BASE}/api/v1/voice/outbound/${reservationId}`, {
      headers: this.headers(),
    });
  }
}
