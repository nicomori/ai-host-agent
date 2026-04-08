/**
 * Test Data Helpers
 * =================
 * Funciones utilitarias para generar datos de prueba aislados.
 * Cada test debe usar datos unicos para evitar colisiones entre ejecuciones paralelas.
 */

// ---------------------------------------------------------------------------
// Tipos reutilizables
// ---------------------------------------------------------------------------

/** Payload para crear una reserva via UI o API */
export interface ReservationData {
  name: string;
  phone: string;
  date: string;
  time: string;
  partySize: number;
  preference?: string;
  notes?: string;
}

/** Payload para crear una reserva via API (snake_case) */
export interface ApiReservationPayload {
  guest_name: string;
  guest_phone: string;
  date: string;
  time: string;
  party_size: number;
  preference?: string;
  notes?: string;
}

/** Roles disponibles en HostAI */
export type Role = "admin" | "writer" | "reader";

// ---------------------------------------------------------------------------
// Generadores
// ---------------------------------------------------------------------------

/**
 * Retorna una fecha en formato YYYY-MM-DD, N dias en el futuro.
 * @param daysAhead - Cantidad de dias a sumar (0 = hoy)
 * @example futureDate(0) → "2026-04-08" (hoy)
 * @example futureDate(3) → "2026-04-11"
 */
export function futureDate(daysAhead = 1): string {
  const d = new Date();
  d.setDate(d.getDate() + daysAhead);
  return d.toISOString().split("T")[0];
}

/**
 * Genera un nombre de guest unico para aislar datos entre tests.
 * Usa timestamp base-36 para que sea corto pero unico.
 * @param prefix - Prefijo descriptivo (ej: "Cancel", "Search")
 * @example uniqueGuest("Cancel") → "Cancel-Guest-m4k2qr"
 */
export function uniqueGuest(prefix = "E2E"): string {
  const ts = Date.now().toString(36);
  return `${prefix}-Guest-${ts}`;
}

// ---------------------------------------------------------------------------
// Datos de ejemplo
// ---------------------------------------------------------------------------

/** Reserva de ejemplo lista para usar en tests rapidos */
export const SAMPLE_RESERVATION: ReservationData = {
  name: "E2E Test Guest",
  phone: "5551234567",
  date: futureDate(1),
  time: "20:00",
  partySize: 4,
  preference: "Patio",
  notes: "E2E test reservation",
};

/** Floor plan minimo para tests que requieren mesas */
export const MINIMAL_FLOOR_PLAN = {
  tables: [
    { id: "t1", label: "Mesa 1", shape: "rect", seats: 4, x: 100, y: 100, section: "Patio" },
    { id: "t2", label: "Mesa 2", shape: "circle", seats: 2, x: 250, y: 100, section: "Window" },
  ],
  elements: [],
  zones: [],
};
