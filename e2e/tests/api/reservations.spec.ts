/**
 * Test Suite: Reservas API
 * ========================
 * CRUD completo + paginacion + filtros + SSE.
 * Tag: @api @smoke
 */
import { test, expect } from "../../fixtures/base.fixture";
import { uniqueGuest, futureDate } from "../../helpers/test-data";

test.describe("Reservas API @api @smoke", () => {

  test("TC-BE-008: crear reserva retorna UUID y status confirmed", async ({ api }) => {
    const res = await api.createReservation({
      guest_name: uniqueGuest("API"),
      guest_phone: "5551234567",
      date: futureDate(1),
      time: "20:00",
      party_size: 4,
    });
    expect(res.ok()).toBeTruthy();

    const body = await res.json();
    expect(body.reservation_id).toBeTruthy();
    expect(body.status).toBe("confirmed");
    expect(body).toHaveProperty("confirmation_call_scheduled_at");
  });

  test("TC-BE-009: crear sin nombre retorna 422", async ({ api }) => {
    const res = await api.createReservation({
      guest_name: "",
      guest_phone: "5551234567",
      date: futureDate(1),
      time: "20:00",
      party_size: 2,
    });
    expect(res.status()).toBe(422);
  });

  test("TC-BE-010: listar con paginacion respeta page_size", async ({ api }) => {
    const res = await api.listReservations({ page: 1, page_size: 5 });
    expect(res.ok()).toBeTruthy();

    const body = await res.json();
    expect(body).toHaveProperty("reservations");
    expect(body).toHaveProperty("total");
    expect(body.page).toBe(1);
    expect(body.page_size).toBe(5);
    expect(body.reservations.length).toBeLessThanOrEqual(5);
  });

  test("TC-BE-011: filtrar por status retorna solo ese status", async ({ api }) => {
    const res = await api.listReservations({ status: "confirmed" });
    expect(res.ok()).toBeTruthy();

    const body = await res.json();
    for (const r of body.reservations) {
      expect(r.status).toBe("confirmed");
    }
  });

  test("TC-BE-012: obtener reserva por UUID retorna datos completos", async ({ api }) => {
    // Crear para obtener un UUID valido
    const createRes = await api.createReservation({
      guest_name: uniqueGuest("Get"),
      guest_phone: "5559999999",
      date: futureDate(1),
      time: "19:30",
      party_size: 2,
    });
    const { reservation_id } = await createRes.json();

    const res = await api.getReservation(reservation_id);
    expect(res.ok()).toBeTruthy();

    const body = await res.json();
    expect(body.reservation_id).toBe(reservation_id);
  });

  test("TC-BE-013: UUID inexistente retorna 404", async ({ api }) => {
    const res = await api.getReservation("00000000-0000-0000-0000-000000000000");
    expect(res.status()).toBe(404);
  });

  test("TC-BE-014: PATCH status a seated", async ({ api }) => {
    const createRes = await api.createReservation({
      guest_name: uniqueGuest("Seat"),
      guest_phone: "5558888888",
      date: futureDate(1),
      time: "21:00",
      party_size: 3,
    });
    const { reservation_id } = await createRes.json();

    const res = await api.updateStatus(reservation_id, "seated");
    expect(res.ok()).toBeTruthy();
    expect((await res.json()).status).toBe("seated");
  });

  test("TC-BE-016: DELETE cancela reserva", async ({ api }) => {
    const createRes = await api.createReservation({
      guest_name: uniqueGuest("Del"),
      guest_phone: "5557777777",
      date: futureDate(1),
      time: "18:00",
      party_size: 2,
    });
    const { reservation_id } = await createRes.json();

    const res = await api.cancelReservation(reservation_id, "E2E test cancel");
    expect(res.ok()).toBeTruthy();
    expect((await res.json()).status).toBe("cancelled");
  });

  test("TC-BE-017: PATCH confirmation status", async ({ api }) => {
    const createRes = await api.createReservation({
      guest_name: uniqueGuest("Confirm"),
      guest_phone: "5556666666",
      date: futureDate(1),
      time: "20:30",
      party_size: 4,
    });
    const { reservation_id } = await createRes.json();

    const res = await api.updateConfirmation(reservation_id, "confirmed");
    expect(res.ok()).toBeTruthy();
    expect((await res.json()).confirmation_status).toBe("confirmed");
  });

  test("TC-BE-018: SSE stream snapshot retorna datos", async ({ api }) => {
    const res = await api.getReservationsSnapshot();
    expect(res.ok()).toBeTruthy();
  });
});
