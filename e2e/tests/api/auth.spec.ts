/**
 * Test Suite: Autenticacion API
 * =============================
 * Cubre JWT login, API key, RBAC, user CRUD.
 * Tag: @api @smoke
 */
import { test, expect } from "../../fixtures/base.fixture";

const API_BASE = process.env.API_URL ?? "http://localhost:8000";

test.describe("Autenticacion API @api @smoke", () => {

  test("TC-BE-002: login exitoso retorna JWT con role y username", async ({ request }) => {
    const res = await request.post(`${API_BASE}/api/v1/auth/token`, {
      form: { username: "admin", password: "1234" },
    });
    expect(res.ok()).toBeTruthy();

    const body = await res.json();
    expect(body.access_token).toBeTruthy();
    expect(body.token_type).toBe("bearer");
    expect(body.role).toBe("admin");
    expect(body.username).toBe("admin");
  });

  test("TC-BE-003: password incorrecto retorna 401", async ({ request }) => {
    const res = await request.post(`${API_BASE}/api/v1/auth/token`, {
      form: { username: "admin", password: "wrong" },
    });
    expect(res.status()).toBe(401);
  });

  test("TC-BE-005: request sin auth retorna 401 o 403", async ({ request }) => {
    const res = await request.post(`${API_BASE}/api/v1/reservations`, {
      data: { guest_name: "Test", guest_phone: "555", date: "2026-04-15", time: "20:00", party_size: 2 },
    });
    expect([401, 403]).toContain(res.status());
  });

  test("TC-BE-004: API Key en header X-API-Key autentica correctamente", async ({ api }) => {
    const res = await api.listReservations({ page: 1, page_size: 1 });
    expect(res.ok()).toBeTruthy();
  });

  test("TC-BE-006: admin puede listar usuarios", async ({ apiAsAdmin }) => {
    const res = await apiAsAdmin.listUsers();
    expect(res.ok()).toBeTruthy();

    const body = await res.json();
    const users = body.users ?? body;
    expect(Array.isArray(users)).toBeTruthy();
  });

  test("TC-BE-007: reader puede autenticarse con permisos limitados", async ({ api }) => {
    const token = await api.login("reader", "1234");
    expect(token).toBeTruthy();
  });

  test("TC-BE-048: usuarios default (admin, writer, reader) existen", async ({ apiAsAdmin }) => {
    const res = await apiAsAdmin.listUsers();
    const body = await res.json();
    const users = body.users ?? body;
    const usernames = users.map((u: { username: string }) => u.username);

    expect(usernames).toContain("admin");
    expect(usernames).toContain("writer");
    expect(usernames).toContain("reader");
  });

  test("TC-BE-047: admin puede crear usuario nuevo", async ({ apiAsAdmin }) => {
    const username = `e2e_user_${Date.now()}`;
    const res = await apiAsAdmin.createUser(username, "test123", "writer");
    expect(res.ok()).toBeTruthy();
  });
});
