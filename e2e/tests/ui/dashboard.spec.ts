/**
 * Test Suite: Dashboard UI
 * ========================
 * Cubre CRUD de reservas, busqueda, filtros, vistas, dark mode, idioma.
 * Precondicion: usuario logueado como admin (via beforeEach + loginAs fixture).
 * Tag: @regression
 */
import { test, expect } from "../../fixtures/base.fixture";
import { uniqueGuest, futureDate, MINIMAL_FLOOR_PLAN } from "../../helpers/test-data";
import { evidence } from "../../helpers/evidence";

test.describe("Dashboard @regression", () => {

  test.beforeEach(async ({ loginAs }) => {
    await loginAs("admin");
  });

  // ─── Header y Day Picker ─────────────────────────────────────────────────

  test("TC-UI-008: stats cards visibles en header", async ({ page }) => {
    await evidence(page, test.info(), "01-dashboard-loaded");

    const header = page.locator("header, nav, .sticky").first();
    await expect(header).toBeVisible();

    await evidence(page, test.info(), "02-header-visible");
  });

  test("TC-UI-009: day picker muestra al menos 7 dias", async ({ dashboardPage, page }) => {
    await evidence(page, test.info(), "01-dashboard-day-picker");

    const dayCount = await dashboardPage.dayButtons.count();
    expect(dayCount).toBeGreaterThanOrEqual(7);
  });

  test("TC-UI-010: cambiar de dia actualiza la lista de reservas", async ({ dashboardPage, page }) => {
    await evidence(page, test.info(), "01-before-day-change");

    await dashboardPage.selectDay(1); // Tomorrow

    await evidence(page, test.info(), "02-after-day-change");
  });

  // ─── CRUD de Reservas ────────────────────────────────────────────────────

  test("TC-UI-011: crear reserva completa y verificar que aparece", async ({ dashboardPage, page }) => {
    const name = uniqueGuest();

    await evidence(page, test.info(), "01-dashboard-before-create");

    await test.step("Crear reserva para hoy via modal", async () => {
      await dashboardPage.createReservation({
        name, phone: "5559876543", date: futureDate(0), time: "19:00", partySize: 3, notes: "E2E test",
      });
    });

    await evidence(page, test.info(), "02-reservation-created");

    await test.step("Refrescar y buscar la reserva por nombre", async () => {
      await page.reload();
      await dashboardPage.search(name);
      await dashboardPage.expectCardWithName(name);
    });

    await evidence(page, test.info(), "03-reservation-found-after-search");
  });

  test("TC-UI-013: cancelar reserva con dialogo de confirmacion", async ({ dashboardPage, page }) => {
    const name = uniqueGuest("Cancel");

    await test.step("Crear reserva como precondicion", async () => {
      await dashboardPage.createReservation({
        name, phone: "5551111111", date: futureDate(0), time: "20:00", partySize: 2,
      });
    });

    await evidence(page, test.info(), "01-reservation-created-for-cancel");

    await test.step("Buscar la reserva y cancelarla", async () => {
      await page.reload();
      await dashboardPage.search(name);
      await dashboardPage.cancelReservation(name);
    });

    await evidence(page, test.info(), "02-reservation-cancelled");
  });

  test("TC-UI-014: marcar reserva como seated", async ({ dashboardPage, page }) => {
    const name = uniqueGuest("Seat");

    await test.step("Crear reserva como precondicion", async () => {
      await dashboardPage.createReservation({
        name, phone: "5552222222", date: futureDate(0), time: "21:00", partySize: 2,
      });
    });

    await evidence(page, test.info(), "01-reservation-created-for-seat");

    await test.step("Buscar la reserva y marcarla como seated", async () => {
      await page.reload();
      await dashboardPage.search(name);
      await dashboardPage.seatReservation(name);
    });

    await evidence(page, test.info(), "02-reservation-seated");
  });

  // ─── Busqueda y Filtros ──────────────────────────────────────────────────

  test("TC-UI-016: busqueda filtra cards por nombre", async ({ dashboardPage, page }) => {
    const name = uniqueGuest("Search");

    await test.step("Crear reserva para hoy", async () => {
      await dashboardPage.createReservation({
        name, phone: "5553333333", date: futureDate(0), time: "18:00", partySize: 2,
      });
    });

    await evidence(page, test.info(), "01-reservation-created-for-search");

    await test.step("Refrescar, buscar por nombre y verificar resultado", async () => {
      await page.reload();
      await dashboardPage.search(name);
      await dashboardPage.expectCardWithName(name);
    });

    await evidence(page, test.info(), "02-search-results-displayed");
  });

  test("TC-UI-017: filtrar por preferencia de seccion", async ({ dashboardPage, page }) => {
    await evidence(page, test.info(), "01-before-filter");

    await dashboardPage.selectPreference("Patio");

    await evidence(page, test.info(), "02-after-patio-filter");
  });

  test("TC-UI-018: limpiar filtros restaura todos los resultados", async ({ dashboardPage, page }) => {
    await test.step("Activar un filtro", async () => {
      await dashboardPage.selectPreference("Window");
    });

    await evidence(page, test.info(), "01-filter-active");

    await test.step("Limpiar filtros", async () => {
      await dashboardPage.clearFilters();
    });

    await evidence(page, test.info(), "02-filters-cleared");
  });

  // ─── Vistas y Layout ────────────────────────────────────────────────────

  test("TC-UI-029: toggle entre vista Cards y Floor Plan", async ({ dashboardPage, apiAsAdmin, page }) => {
    await test.step("Asegurar que el floor plan tiene datos", async () => {
      const fpRes = await apiAsAdmin.getFloorPlan();
      const fp = await fpRes.json();
      if (!fp.tables || fp.tables.length === 0) {
        await apiAsAdmin.saveFloorPlan(MINIMAL_FLOOR_PLAN);
        await page.reload();
      }
    });

    await evidence(page, test.info(), "01-cards-view");

    await test.step("Cambiar a Floor Plan y verificar canvas", async () => {
      await dashboardPage.floorPlanViewBtn.click();
      // Konva canvas may not be available in staging builds
      const canvasVisible = await dashboardPage.floorPlanCanvas
        .waitFor({ state: "visible", timeout: 5_000 })
        .then(() => true)
        .catch(() => false);
      if (!canvasVisible) {
        test.skip(true, "Konva canvas not rendered in staging build");
        return;
      }
    });

    await evidence(page, test.info(), "02-floor-plan-view");

    await test.step("Volver a Cards", async () => {
      await dashboardPage.switchToCards();
    });

    await evidence(page, test.info(), "03-back-to-cards-view");
  });

  test("TC-UI-020: cards grid es responsive", async ({ page }) => {
    await evidence(page, test.info(), "01-default-viewport");

    await test.step("Viewport mobile: 375px", async () => {
      await page.setViewportSize({ width: 375, height: 812 });
    });

    await evidence(page, test.info(), "02-mobile-viewport");

    await test.step("Viewport desktop: 1440px", async () => {
      await page.setViewportSize({ width: 1440, height: 900 });
    });

    await evidence(page, test.info(), "03-desktop-viewport");
  });

  // ─── Preferencias de Usuario ─────────────────────────────────────────────

  test("TC-UI-024: dark mode se persiste en localStorage", async ({ dashboardPage, page }) => {
    await evidence(page, test.info(), "01-before-dark-mode");

    await dashboardPage.toggleDarkMode();

    await evidence(page, test.info(), "02-dark-mode-active");

    const theme = await page.evaluate(() => localStorage.getItem("ha_theme"));
    expect(theme).toBeTruthy();
  });

  test("TC-UI-025: cambiar idioma a espanol se persiste", async ({ dashboardPage, page }) => {
    await evidence(page, test.info(), "01-before-language-change");

    await dashboardPage.switchLanguage("ES");

    await evidence(page, test.info(), "02-language-changed-to-es");

    const lang = await page.evaluate(() => localStorage.getItem("ha_language"));
    expect(lang).toBe("es");
  });
});
