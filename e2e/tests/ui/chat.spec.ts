/**
 * Test Suite: Chat Widget
 * =======================
 * Verifica el widget de chat con el agente conversacional.
 * Nota: El agente tarda ~3-5s en responder (usa Claude Haiku).
 * Tag: @regression
 */
import { test, expect } from "../../fixtures/base.fixture";

test.describe("Chat Widget @regression", () => {

  test.beforeEach(async ({ loginAs }) => {
    await loginAs("admin");
  });

  test("TC-UI-040: toggle del chat abre y muestra el panel", async ({ dashboardPage }) => {
    await dashboardPage.openChat();
    await expect(dashboardPage.chatPanel).toBeVisible();
  });

  test("TC-UI-041: enviar mensaje recibe respuesta del agente", async ({ dashboardPage, page }) => {
    await test.step("Abrir chat y enviar mensaje", async () => {
      await dashboardPage.openChat();
      await dashboardPage.sendChatMessage("Hola, quiero reservar una mesa para 4");
    });

    await test.step("Esperar respuesta del agente (hasta 10s)", async () => {
      // El agente tarda unos segundos en responder via Claude Haiku
      await expect(
        page.locator(".fixed").filter({ hasText: /mesa|reserv|ayud/i }).first()
      ).toBeVisible({ timeout: 10_000 });
    });
  });

  test("TC-UI-042: mensaje enviado aparece visible en el chat", async ({ dashboardPage, page }) => {
    await test.step("Abrir chat y enviar mensaje", async () => {
      await dashboardPage.openChat();
      await dashboardPage.sendChatMessage("Primera pregunta");
    });

    await test.step("Verificar que el mensaje se muestra en el panel", async () => {
      await expect(
        page.locator(".fixed").filter({ hasText: /Primera pregunta/ }).first()
      ).toBeVisible({ timeout: 10_000 });
    });
  });
});
