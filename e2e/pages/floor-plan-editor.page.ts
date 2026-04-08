/**
 * Page Object: Floor Plan Editor
 * ===============================
 * Representa la pagina /floor-plan-editor de HostAI.
 * Es una app de canvas (React Konva) con sidebar y modals propios.
 *
 * Nota: Los textos estan en espanol (Guardar, Agregar, Nombre, Capacidad).
 */
import { type Locator, type Page, expect } from "@playwright/test";

export class FloorPlanEditorPage {
  readonly canvas: Locator;
  readonly saveBtn: Locator;
  readonly backBtn: Locator;

  // Sidebar: agregar elementos
  readonly addRectTable: Locator;
  readonly addRoundTable: Locator;

  constructor(private page: Page) {
    this.canvas = page.locator("canvas, .konvajs-content").first();
    this.saveBtn = page.locator("button:has-text('Guardar')");
    this.backBtn = page.locator("button:has(.lucide-arrow-left)").first();

    this.addRectTable = page.locator("button:has-text('Rectangular')").first();
    this.addRoundTable = page.locator("button:has-text('Redonda'), button:has-text('Rounded')").first();
  }

  // ── Navegacion ─────────────────────────────────────────────────────────────

  /** Navega a /floor-plan-editor */
  async goto() {
    await this.page.goto("/floor-plan-editor");
  }

  /** Click en "Back" para volver al dashboard */
  async goBack() {
    await this.backBtn.click();
    await this.page.waitForURL("**/dashboard");
  }

  // ── Acciones ───────────────────────────────────────────────────────────────

  /**
   * Agrega una mesa nueva al plano.
   * Flujo: click sidebar → modal → llenar nombre/capacidad/seccion → Agregar
   * @param type    - "rect" para rectangular, "round" para redonda
   * @param name    - Nombre de la mesa (ej: "Mesa 10")
   * @param capacity - Cantidad de asientos (1-20)
   * @param section  - Seccion opcional (Patio, Window, Bar, etc.)
   */
  async addTable(type: "rect" | "round", name: string, capacity: number, section?: string) {
    // 1. Click en el tipo de mesa en el sidebar
    if (type === "rect") {
      await this.addRectTable.click();
    } else {
      await this.addRoundTable.click();
    }

    // 2. Esperar el modal (overlay oscuro con inputs)
    const modal = this.page.locator(".fixed.inset-0.bg-black\\/70");
    await expect(modal).toBeVisible({ timeout: 3_000 });

    // 3. Llenar el formulario
    await modal.locator("input").first().fill(name);               // Nombre
    await modal.locator("input[type='number']").first().fill(String(capacity)); // Capacidad
    if (section) {
      await modal.locator("select").first().selectOption(section); // Zona
    }

    // 4. Confirmar
    await modal.locator("button:has-text('Agregar')").click();
  }

  /** Guarda el plano actual haciendo click en "Guardar" */
  async save() {
    await this.saveBtn.click();
  }

  // ── Assertions ─────────────────────────────────────────────────────────────

  /** Verifica que aparece el toast de guardado exitoso */
  async expectSaveSuccess() {
    const toast = this.page.locator(".fixed.bottom-6.right-6");
    await expect(toast).toBeVisible({ timeout: 5_000 });
  }
}
