/**
 * Test Suite: Chat Widget
 * =======================
 * Verifica el widget de chat con el agente conversacional.
 * Nota: El agente tarda ~3-5s en responder (usa Claude Haiku).
 * Tag: @regression
 */
import { test, expect } from "../../fixtures/base.fixture";
import { evidence } from "../../helpers/evidence";

test.describe("Chat Widget @regression", () => {

  test.beforeEach(async ({ loginAs }) => {
    await loginAs("admin");
  });

  test("TC-UI-040: toggle del chat abre y muestra el panel", async ({ dashboardPage, page }) => {
    await evidence(page, test.info(), "01-dashboard-before-chat");

    await dashboardPage.openChat();

    await evidence(page, test.info(), "02-chat-panel-opened");

    await expect(dashboardPage.chatPanel).toBeVisible();
  });

  test("TC-UI-041: enviar mensaje recibe respuesta del agente", async ({ dashboardPage, page }) => {
    await test.step("Abrir chat y enviar mensaje", async () => {
      await dashboardPage.openChat();
      await evidence(page, test.info(), "01-chat-opened");

      await dashboardPage.sendChatMessage("Hola, quiero reservar una mesa para 4");
    });

    await evidence(page, test.info(), "02-message-sent");

    await test.step("Esperar respuesta del agente (hasta 10s)", async () => {
      // El agente tarda unos segundos en responder via Claude Haiku
      await expect(
        page.locator(".fixed").filter({ hasText: /mesa|reserv|ayud/i }).first()
      ).toBeVisible({ timeout: 10_000 });
    });

    await evidence(page, test.info(), "03-agent-response-received");
  });

  test("TC-UI-042: mensaje enviado aparece visible en el chat", async ({ dashboardPage, page }) => {
    await test.step("Abrir chat y enviar mensaje", async () => {
      await dashboardPage.openChat();
      await evidence(page, test.info(), "01-chat-opened");

      await dashboardPage.sendChatMessage("Primera pregunta");
    });

    await evidence(page, test.info(), "02-message-sent");

    await test.step("Verificar que el mensaje se muestra en el panel", async () => {
      await expect(
        page.locator(".fixed").filter({ hasText: /Primera pregunta/ }).first()
      ).toBeVisible({ timeout: 10_000 });
    });

    await evidence(page, test.info(), "03-message-visible-in-chat");
  });
});
