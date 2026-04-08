/**
 * Test Suite: Autenticacion UI
 * ============================
 * Cubre login exitoso/fallido, loading state, responsive, logout y rutas protegidas.
 * Tag: @smoke — se ejecuta en cada PR.
 */
import { test, expect } from "../../fixtures/base.fixture";

test.describe("Autenticacion @smoke", () => {

  test("TC-UI-001: login exitoso redirige al dashboard", async ({ loginPage, page }) => {
    await test.step("Completar formulario con credenciales validas", async () => {
      await loginPage.loginAndWait("admin", "1234");
    });

    await test.step("Verificar redireccion y token en localStorage", async () => {
      expect(page.url()).toContain("/dashboard");
      const token = await page.evaluate(() => localStorage.getItem("ha_token"));
      expect(token).toBeTruthy();
    });
  });

  test("TC-UI-002: login con password incorrecto muestra error", async ({ loginPage }) => {
    await test.step("Intentar login con password incorrecto", async () => {
      await loginPage.login("admin", "wrong_password");
    });

    await test.step("Verificar que se muestra alerta de error", async () => {
      await loginPage.expectError();
    });
  });

  test("TC-UI-003: boton muestra loading state durante autenticacion", async ({ loginPage, page }) => {
    await test.step("Interceptar request para simular latencia de red", async () => {
      await page.route("**/auth/token", async (route) => {
        await new Promise((r) => setTimeout(r, 2000));
        await route.continue();
      });
    });

    await test.step("Completar formulario y enviar", async () => {
      await loginPage.username.fill("admin");
      await loginPage.password.fill("1234");
      await loginPage.signInBtn.click();
    });

    await test.step("Verificar que el boton esta disabled con texto 'Signing in...'", async () => {
      await loginPage.expectLoadingState();
    });
  });

  test("TC-UI-005: en mobile el video se oculta y el form es full-width", async ({ loginPage, page }) => {
    await test.step("Cambiar viewport a iPhone (375x812)", async () => {
      await page.setViewportSize({ width: 375, height: 812 });
    });

    await test.step("Verificar que el video se oculta y los inputs son visibles", async () => {
      await expect(loginPage.videoPanel).not.toBeVisible();
      await expect(loginPage.username).toBeVisible();
      await expect(loginPage.password).toBeVisible();
    });
  });

  test("TC-UI-006: logout limpia token y redirige a login", async ({ loginPage, page }) => {
    await test.step("Login como admin", async () => {
      await loginPage.loginAndWait("admin", "1234");
    });

    await test.step("Abrir menu de usuario y hacer sign out", async () => {
      await page.locator("button:has(.rounded-full)").last().click();
      await page.locator("button:has(.lucide-log-out), button.text-destructive").first().click();
    });

    await test.step("Verificar redireccion a /login y token borrado", async () => {
      await page.waitForURL("**/login");
      const token = await page.evaluate(() => localStorage.getItem("ha_token"));
      expect(token).toBeNull();
    });
  });

  test("TC-UI-007: ruta protegida redirige a login sin token", async ({ page }) => {
    await test.step("Limpiar localStorage en el origin correcto", async () => {
      await page.goto("/login");
      await page.evaluate(() => {
        localStorage.removeItem("ha_token");
        localStorage.removeItem("ha_username");
        localStorage.removeItem("ha_role");
      });
    });

    await test.step("Navegar a /dashboard y verificar redireccion a /login", async () => {
      await page.goto("/dashboard");
      await page.waitForURL("**/login");
    });
  });
});
