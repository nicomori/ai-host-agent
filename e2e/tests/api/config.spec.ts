/**
 * Test Suite: Configuracion API
 * =============================
 * Confirmation call config + CORS + error handling.
 * Tag: @api
 */
import { test, expect } from "../../fixtures/base.fixture";

const API_BASE = process.env.API_URL ?? "http://localhost:8000";

test.describe("Configuracion API @api", () => {

  test("TC-BE-045: GET confirmation config retorna numero", async ({ apiAsAdmin }) => {
    const res = await apiAsAdmin.getConfirmationConfig();
    expect(res.ok()).toBeTruthy();

    const body = await res.json();
    expect(body).toHaveProperty("confirmation_call_minutes_before");
    expect(typeof body.confirmation_call_minutes_before).toBe("number");
  });

  test("TC-BE-045b: PATCH confirmation config actualiza el valor", async ({ apiAsAdmin }) => {
    const res = await apiAsAdmin.setConfirmationConfig(45);
    expect(res.ok()).toBeTruthy();
    expect((await res.json()).confirmation_call_minutes_before).toBe(45);

    // Reset al default
    await apiAsAdmin.setConfirmationConfig(60);
  });

  test("TC-BE-046: valor menor al minimo (5) es rechazado", async ({ apiAsAdmin }) => {
    const res = await apiAsAdmin.setConfirmationConfig(3);
    expect(res.ok()).toBeFalsy();
  });

  test("TC-BE-049: CORS responde sin error 5xx", async ({ request }) => {
    const res = await request.fetch(`${API_BASE}/health`, {
      method: "OPTIONS",
      headers: { Origin: "http://localhost:5173" },
    });
    expect(res.status()).toBeLessThan(500);
  });

  test("TC-BE-050: endpoint inexistente retorna 404/405 o 200 (SPA catch-all)", async ({ request }) => {
    const res = await request.get(`${API_BASE}/api/v1/nonexistent`);
    // SPA catch-all may serve index.html with 200 for unknown routes
    expect([200, 404, 405]).toContain(res.status());
  });
});
