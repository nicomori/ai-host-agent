/**
 * Test Suite: RBAC (Role-Based Access Control)
 * =============================================
 * Verifica que cada rol (reader, writer, admin) ve los controles correctos.
 * Tag: @smoke
 */
import { test, expect } from "../../fixtures/base.fixture";
import { evidence } from "../../helpers/evidence";

test.describe("RBAC @smoke", () => {

  test("TC-UI-027: reader NO ve botones de escritura", async ({ loginAs, dashboardPage, page }) => {
    await loginAs("reader");

    await evidence(page, test.info(), "01-reader-dashboard");

    await expect(dashboardPage.newReservationBtn).not.toBeVisible();

    await evidence(page, test.info(), "02-reader-no-write-buttons");
  });

  test("TC-UI-028: writer SI ve botones de escritura", async ({ loginAs, dashboardPage, page }) => {
    await loginAs("writer");

    await evidence(page, test.info(), "01-writer-dashboard");

    await expect(dashboardPage.newReservationBtn).toBeVisible();

    await evidence(page, test.info(), "02-writer-write-buttons-visible");
  });

  test("TC-UI-026: admin ve la config de confirmation calls", async ({ loginAs, dashboardPage, page }) => {
    await loginAs("admin");

    await evidence(page, test.info(), "01-admin-dashboard");

    await test.step("Abrir menu de usuario", async () => {
      await dashboardPage.openUserMenu();
    });

    await evidence(page, test.info(), "02-user-menu-opened");

    await test.step("Verificar que aparece la seccion 'Confirmation call config'", async () => {
      await expect(page.locator("text=Confirmation call config").first()).toBeVisible({ timeout: 3_000 });
    });

    await evidence(page, test.info(), "03-confirmation-call-config-visible");
  });
});
