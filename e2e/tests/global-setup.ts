/**
 * Global Setup
 * ============
 * Se ejecuta ANTES de todos los tests. Verifica que la infraestructura este lista.
 * Si falla aca, no tiene sentido correr ningun test.
 */
import { test as setup, expect } from "@playwright/test";
import { ApiClient } from "../helpers/api-client";

setup("Backend esta corriendo y responde /health", async ({ request }) => {
  const api = new ApiClient(request);
  const res = await api.health();
  expect(res.ok()).toBeTruthy();

  const body = await res.json();
  expect(body.status).toBe("ok");
});

setup("Usuarios default (admin, writer, reader) pueden autenticarse", async ({ request }) => {
  const api = new ApiClient(request);
  // Retry login with backoff — API may still be seeding users after restart
  for (const role of ["admin", "writer", "reader"] as const) {
    let token: string | null = null;
    for (let attempt = 1; attempt <= 10; attempt++) {
      try {
        token = await api.login(role, "1234");
        break;
      } catch {
        if (attempt === 10) throw new Error(`Login failed for ${role} after 10 attempts`);
        await new Promise((r) => setTimeout(r, 3000));
      }
    }
    expect(token).toBeTruthy();
  }
});
