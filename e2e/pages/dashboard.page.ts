/**
 * Page Object: Dashboard
 * ======================
 * Representa la pagina principal /dashboard de HostAI.
 * Incluye: header, day picker, toolbar, cards, modals, chat, floor plan.
 *
 * Convenciones:
 *   - Metodos de accion:  verbos (create, cancel, search, switch...)
 *   - Metodos de lectura:  getters (getCardCount, getDayCount)
 *   - Assertions:          prefijo "expect" (expectCardWithName, expectEmptyState)
 *
 * Los modals no usan role="dialog" sino divs con clase .fixed.inset-0.
 * Cada modal se identifica por un texto unico en su contenido.
 */
import { type Locator, type Page, expect } from "@playwright/test";
import type { ReservationData } from "../helpers/test-data";

export class DashboardPage {
  // ── Header ─────────────────────────────────────────────────────────────────
  readonly newReservationBtn: Locator;
  readonly chatToggle: Locator;
  readonly userMenuTrigger: Locator;

  // ── Day Picker ─────────────────────────────────────────────────────────────
  /** Botones de dia dentro del contenedor scrollable .day-scroll */
  readonly dayButtons: Locator;

  // ── Toolbar ────────────────────────────────────────────────────────────────
  readonly cardsViewBtn: Locator;
  readonly floorPlanViewBtn: Locator;
  readonly searchInput: Locator;
  readonly clearFiltersBtn: Locator;

  // ── Cards ──────────────────────────────────────────────────────────────────
  readonly reservationCards: Locator;
  readonly emptyState: Locator;

  // ── Modals ─────────────────────────────────────────────────────────────────
  /** Modal "New Reservation" — se identifica por su titulo h2 */
  readonly createModal: Locator;
  /** Dialog de confirmacion de cancelacion — tiene h2 "Cancel reservation?" */
  readonly confirmDialog: Locator;

  // ── Chat ───────────────────────────────────────────────────────────────────
  readonly chatPanel: Locator;
  readonly chatInput: Locator;
  readonly chatSendBtn: Locator;

  // ── Floor Plan ─────────────────────────────────────────────────────────────
  readonly floorPlanCanvas: Locator;

  constructor(private page: Page) {
    // Header
    this.newReservationBtn = page.locator("button:has-text('New Reservation')");
    this.chatToggle = page.locator("button:has-text('Chat')");
    this.userMenuTrigger = page.locator("button:has(.rounded-full)").last();

    // Day picker
    this.dayButtons = page.locator(".day-scroll > button");

    // Toolbar
    this.cardsViewBtn = page.locator("button:has-text('Cards')");
    this.floorPlanViewBtn = page.locator("button:has-text('Floor Plan')");
    this.searchInput = page.locator("input[placeholder*='Search']");
    this.clearFiltersBtn = page.locator("button.underline:has-text('Clear')");

    // Cards
    this.reservationCards = page.locator(".rounded-xl.border.bg-card");
    this.emptyState = page.locator("text=No reservations");

    // Modals
    this.createModal = page.locator(".fixed.inset-0:has(h2:has-text('New Reservation'))");
    this.confirmDialog = page.locator(".fixed.inset-0:has(h2:has-text('Cancel reservation?'))");

    // Chat
    this.chatPanel = page.locator(".fixed.bottom-4, .fixed.right-4").first();
    this.chatInput = page.locator("input[placeholder*='message'], input[placeholder*='Type'], input[placeholder*='escrib']").last();
    this.chatSendBtn = page.locator("button:has(.lucide-send)").last();

    // Floor plan
    this.floorPlanCanvas = page.locator("canvas, .konvajs-content").first();
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // Reservas — Crear
  // ═══════════════════════════════════════════════════════════════════════════

  /**
   * Flujo completo: abre modal → llena formulario → envia → espera cierre.
   * Ideal para tests que necesitan una reserva como precondicion.
   */
  async createReservation(data: ReservationData) {
    await this.newReservationBtn.click();
    await expect(this.createModal).toBeVisible({ timeout: 5_000 });

    const modal = this.createModal;
    await modal.locator("input[placeholder='Ana García']").fill(data.name);
    await modal.locator("input[type='tel']").fill(data.phone);
    await modal.locator("input[type='date']").fill(data.date);
    await modal.locator("input[type='time']").fill(data.time);
    await modal.locator("input[type='number']").fill(String(data.partySize));
    if (data.notes) {
      await modal.locator("input[placeholder='Window table preferred']").fill(data.notes);
    }

    await modal.locator("button:has-text('Create')").click();
    await expect(this.createModal).not.toBeVisible({ timeout: 10_000 });
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // Reservas — Acciones desde Card Detail
  // ═══════════════════════════════════════════════════════════════════════════
  //
  //  Flujo: click en card → abre card detail modal → ejecutar accion.
  //  El card detail modal tiene botones: "Call to Confirm", "Seat", "Cancel".

  /**
   * Abre el detalle de una reserva y la cancela con confirmacion.
   * Flujo: card → detail → Cancel → ConfirmDialog → "Cancel reservation"
   */
  async cancelReservation(guestName: string) {
    await this._openCardDetail(guestName);
    const detail = this.page.locator(".fixed.inset-0").last();
    await detail.locator("button:has-text('Cancel')").last().click();

    await expect(this.confirmDialog).toBeVisible({ timeout: 3_000 });
    await this.confirmDialog.locator("button:has-text('Cancel reservation')").click();
  }

  /** Abre el detalle y marca la reserva como seated */
  async seatReservation(guestName: string) {
    await this._openCardDetail(guestName);
    const detail = this.page.locator(".fixed.inset-0").last();
    await detail.locator("button:has-text('Seat')").click();
  }

  /** Abre el detalle y dispara la llamada de confirmacion */
  async callToConfirm(guestName: string) {
    await this._openCardDetail(guestName);
    const detail = this.page.locator(".fixed.inset-0").last();
    await detail.locator("button:has-text('Call to Confirm'), button:has-text('Retry Call')").first().click();
  }

  /** Helper interno: click en la card para abrir el modal de detalle */
  private async _openCardDetail(guestName: string) {
    const card = this.reservationCards.filter({ hasText: guestName }).first();
    await card.click();
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // Busqueda y Filtros
  // ═══════════════════════════════════════════════════════════════════════════

  /** Escribe en el input de busqueda (filtra por nombre, telefono, notas) */
  async search(text: string) {
    await this.searchInput.fill(text);
  }

  /** Click en un boton de preferencia (Window, Patio, Booth, Bar, Private, Quiet) */
  async selectPreference(pref: string) {
    await this.page.getByRole("button", { name: pref, exact: true }).click();
  }

  /** Limpia todos los filtros de preferencia activos */
  async clearFilters() {
    await this.clearFiltersBtn.click();
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // Day Picker
  // ═══════════════════════════════════════════════════════════════════════════

  /** Selecciona un dia por indice (0 = Today, 1 = Tomorrow, ...) */
  async selectDay(index: number) {
    await this.dayButtons.nth(index).click();
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // Vista: Cards / Floor Plan
  // ═══════════════════════════════════════════════════════════════════════════

  /** Cambia a la vista de Floor Plan y espera que el canvas Konva sea visible */
  async switchToFloorPlan() {
    await this.floorPlanViewBtn.click();
    await expect(this.floorPlanCanvas).toBeVisible({ timeout: 10_000 });
  }

  /** Cambia a la vista de Cards */
  async switchToCards() {
    await this.cardsViewBtn.click();
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // Chat Widget
  // ═══════════════════════════════════════════════════════════════════════════

  /** Abre el panel de chat y espera que sea visible */
  async openChat() {
    await this.chatToggle.click();
    await expect(this.chatPanel).toBeVisible();
  }

  /** Escribe un mensaje y lo envia al agente */
  async sendChatMessage(text: string) {
    await this.chatInput.fill(text);
    await this.chatSendBtn.click();
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // User Menu
  // ═══════════════════════════════════════════════════════════════════════════

  /** Abre el dropdown del menu de usuario */
  async openUserMenu() {
    await this.userMenuTrigger.click();
  }

  /** Alterna entre dark mode y light mode */
  async toggleDarkMode() {
    await this.openUserMenu();
    await this.page.locator("button:has(.lucide-moon), button:has(.lucide-sun)").first().click();
  }

  /** Cambia el idioma de la UI ("EN" o "ES") */
  async switchLanguage(lang: "EN" | "ES") {
    await this.openUserMenu();
    await this.page.getByRole("button", { name: lang, exact: true }).click();
  }

  /** Cierra sesion y espera redireccion a /login */
  async signOut() {
    await this.openUserMenu();
    await this.page.locator("button:has(.lucide-log-out), button.text-destructive").first().click();
    await this.page.waitForURL("**/login");
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // Assertions
  // ═══════════════════════════════════════════════════════════════════════════

  /** Verifica que existe una card con el nombre dado visible en pantalla */
  async expectCardWithName(name: string) {
    await expect(
      this.reservationCards.filter({ hasText: name }).first()
    ).toBeVisible({ timeout: 5_000 });
  }

  /** Verifica que se muestra el estado vacio "No reservations" */
  async expectEmptyState() {
    await expect(this.emptyState).toBeVisible();
  }
}
