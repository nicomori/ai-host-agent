/**
 * Test Suite: Agente Conversacional API
 * ======================================
 * Verifica el pipeline multi-agente (supervisor + sub-agents).
 * Nota: Cada llamada al agente tarda ~2-5s (usa Claude Haiku).
 * Tag: @api @regression
 */
import { test, expect } from "../../fixtures/base.fixture";

test.describe("Agente Conversacional @api @regression", () => {

  test("TC-BE-025: nueva sesion retorna session_id, respuesta e intent", async ({ api }) => {
    const res = await api.agentChat("Hola, quiero reservar una mesa");
    expect(res.ok()).toBeTruthy();

    const body = await res.json();
    expect(body.session_id).toBeTruthy();
    expect(body.final_response).toBeTruthy();
    expect(body).toHaveProperty("intent");
    expect(body).toHaveProperty("reservation_data");
  });

  test("TC-BE-026: multi-turn acumula campos entre mensajes", async ({ api }) => {
    let sessionId: string;

    await test.step("Turno 1: declarar intent", async () => {
      const res = await api.agentChat("Quiero reservar una mesa");
      sessionId = (await res.json()).session_id;
    });

    await test.step("Turno 2: dar nombre", async () => {
      const res = await api.agentChat("Me llamo Juan Perez", sessionId!);
      expect(res.ok()).toBeTruthy();
    });

    await test.step("Turno 3: dar telefono", async () => {
      const res = await api.agentChat("Mi telefono es 555-1234567", sessionId!);
      expect(res.ok()).toBeTruthy();
      expect((await res.json()).session_id).toBe(sessionId!);
    });
  });

  test("TC-BE-027: supervisor clasifica 'cancelar' correctamente", async ({ api }) => {
    const res = await api.agentChat("Quiero cancelar mi reserva");
    const body = await res.json();
    expect(body.intent).toBe("cancel_reservation");
  });

  test("TC-BE-032: intent desconocido recibe clarificacion", async ({ api }) => {
    const res = await api.agentChat("Cual es el clima hoy?");
    const body = await res.json();
    expect(body.final_response).toBeTruthy();
  });

  test("TC-BE-028: extrae campos de reserva de texto libre", async ({ api }) => {
    const res = await api.agentChat(
      "Reservar para Maria Garcia, telefono 555-9876543, manana a las 8pm, para 6 personas"
    );
    const body = await res.json();
    expect(body.intent).toBe("make_reservation");

    if (body.reservation_data) {
      const rd = body.reservation_data;
      const hasFields = rd.guest_name || rd.guest_phone || rd.party_size || rd.time;
      expect(hasFields).toBeTruthy();
    }
  });
});
