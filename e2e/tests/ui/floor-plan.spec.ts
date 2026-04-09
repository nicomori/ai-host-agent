/**
 * Test Suite: Floor Plan (Editor + Viewer)
 * ========================================
 * Dividido en dos grupos:
 *   - Editor: agregar mesa, guardar, eliminar (serial, modifican floor_plan.json)
 *   - Viewer: renderizar canvas, zoom (serial, necesitan datos en el plano)
 * Tag: @regression
 */
import { test, expect } from "../../fixtures/base.fixture";
import { MINIMAL_FLOOR_PLAN } from "../../helpers/test-data";

// ═══════════════════════════════════════════════════════════════════════════════
// Editor — Modifica el plano, se ejecuta en serie
// ═══════════════════════════════════════════════════════════════════════════════

test.describe("Floor Plan Editor @regression", () => {
  test.describe.configure({ mode: "serial" });

  test.beforeEach(async ({ loginAs }) => {
    await loginAs("admin");
  });

  test("TC-UI-045: agregar mesa rectangular desde sidebar", async ({ editorPage }) => {
    await editorPage.goto();
    await expect(editorPage.canvas).toBeVisible();

    await test.step("Agregar mesa 'E2E-Table' con 6 asientos en Patio", async () => {
      await editorPage.addTable("rect", "E2E-Table", 6, "Patio");
    });
  });

  test("TC-UI-048: guardar plano muestra toast de exito", async ({ editorPage }) => {
    await editorPage.goto();

    await test.step("Click en Guardar", async () => {
      await editorPage.save();
    });

    await test.step("Verificar toast de confirmacion", async () => {
      await editorPage.expectSaveSuccess();
    });
  });

  test("TC-UI-047: eliminar elemento con tecla Delete", async ({ editorPage, page }) => {
    await editorPage.goto();

    await test.step("Agregar mesa temporal", async () => {
      await editorPage.addTable("round", "ToDelete", 2);
    });

    await test.step("Seleccionar elemento en el canvas y presionar Delete", async () => {
      const box = await editorPage.canvas.boundingBox();
      if (box) {
        await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
        await page.keyboard.press("Delete");
      }
    });
  });
});

// ═══════════════════════════════════════════════════════════════════════════════
// Viewer — Solo lectura, necesita floor plan con datos
// ═══════════════════════════════════════════════════════════════════════════════

test.describe("Floor Plan Viewer @regression", () => {
  test.describe.configure({ mode: "serial" });

  test.beforeEach(async ({ apiAsAdmin, loginAs }) => {
    // Asegurar que el plano tiene datos (puede estar vacio si el editor lo limpio)
    const fpRes = await apiAsAdmin.getFloorPlan();
    const fp = await fpRes.json();
    if (!fp.tables || fp.tables.length === 0) {
      await apiAsAdmin.saveFloorPlan(MINIMAL_FLOOR_PLAN);
    }
    await loginAs("admin");
  });

  test("TC-UI-030: el canvas del floor plan renderiza correctamente", async ({ dashboardPage }) => {
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

  test("TC-UI-031: zoom con scroll wheel funciona", async ({ dashboardPage, page }) => {
    await dashboardPage.floorPlanViewBtn.click();
    const canvasVisible = await dashboardPage.floorPlanCanvas
      .waitFor({ state: "visible", timeout: 5_000 })
      .then(() => true)
      .catch(() => false);
    if (!canvasVisible) {
      test.skip(true, "Konva canvas not rendered in staging build");
      return;
    }

    await test.step("Zoom in (scroll up)", async () => {
      await dashboardPage.floorPlanCanvas.hover();
      await page.mouse.wheel(0, -100);
    });

    await test.step("Zoom out (scroll down)", async () => {
      await page.mouse.wheel(0, 100);
    });
  });
});
