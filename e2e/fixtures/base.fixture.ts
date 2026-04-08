/**
 * Base Fixture
 * ============
 * Extiende el `test` de Playwright con fixtures personalizados para HostAI.
 *
 * Uso en tests:
 *   import { test, expect } from "../../fixtures/base.fixture";
 *
 * Fixtures disponibles:
 *   - api:           ApiClient autenticado (usa API key, sin login)
 *   - apiAsAdmin:    ApiClient autenticado como admin via JWT
 *   - loginPage:     Page Object de Login (ya navegado a /login)
 *   - dashboardPage: Page Object de Dashboard
 *   - editorPage:    Page Object del Floor Plan Editor
 *   - loginAs:       Funcion helper para login rapido por rol
 *
 * Ejemplo:
 *   test("mi test", async ({ loginAs, dashboardPage }) => {
 *     await loginAs("writer");
 *     await dashboardPage.createReservation({ ... });
 *   });
 */
import { test as base } from "@playwright/test";
import { ApiClient } from "../helpers/api-client";
import { LoginPage } from "../pages/login.page";
import { DashboardPage } from "../pages/dashboard.page";
import { FloorPlanEditorPage } from "../pages/floor-plan-editor.page";
import type { Role } from "../helpers/test-data";

// ---------------------------------------------------------------------------
// Tipos de los fixtures
// ---------------------------------------------------------------------------

type HostAIFixtures = {
  /** ApiClient con API key (sin JWT). Util para la mayoria de los API tests. */
  api: ApiClient;

  /** ApiClient autenticado como admin via JWT. Util para operaciones protegidas. */
  apiAsAdmin: ApiClient;

  /** Page Object de Login, ya navegado a /login. */
  loginPage: LoginPage;

  /** Page Object de Dashboard (requiere login previo). */
  dashboardPage: DashboardPage;

  /** Page Object del Floor Plan Editor (requiere login previo como admin). */
  editorPage: FloorPlanEditorPage;

  /** Helper para hacer login rapido con cualquier rol. */
  loginAs: (role?: Role) => Promise<void>;
};

// ---------------------------------------------------------------------------
// Definicion de fixtures
// ---------------------------------------------------------------------------

export const test = base.extend<HostAIFixtures>({

  api: async ({ request }, use) => {
    await use(new ApiClient(request));
  },

  apiAsAdmin: async ({ request }, use) => {
    const api = new ApiClient(request);
    await api.login("admin", "1234");
    await use(api);
  },

  loginPage: async ({ page }, use) => {
    const loginPage = new LoginPage(page);
    await loginPage.goto();
    await use(loginPage);
  },

  dashboardPage: async ({ page }, use) => {
    await use(new DashboardPage(page));
  },

  editorPage: async ({ page }, use) => {
    await use(new FloorPlanEditorPage(page));
  },

  loginAs: async ({ page }, use) => {
    const fn = async (role: Role = "admin") => {
      await page.goto("/login");
      await page.locator("#fl-username").fill(role);
      await page.locator("#fl-password").fill("1234");
      await page.getByRole("button", { name: /sign in/i }).click();
      await page.waitForURL("**/dashboard");
    };
    await use(fn);
  },
});

export { expect } from "@playwright/test";
