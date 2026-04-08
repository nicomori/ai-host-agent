/**
 * Page Object: Login
 * ==================
 * Representa la pagina /login de HostAI.
 *
 * Selectores clave:
 *   - Username: input#fl-username (floating label, placeholder=" ")
 *   - Password: input#fl-password (floating label, placeholder=" ")
 *   - Submit:   button[type="submit"] con texto "Sign in" / "Signing in..."
 */
import { type Locator, type Page, expect } from "@playwright/test";

export class LoginPage {
  // ── Elementos ──────────────────────────────────────────────────────────────
  readonly username: Locator;
  readonly password: Locator;
  readonly signInBtn: Locator;
  readonly errorAlert: Locator;
  readonly videoPanel: Locator;

  constructor(private page: Page) {
    this.username = page.locator("#fl-username");
    this.password = page.locator("#fl-password");
    this.signInBtn = page.getByRole("button", { name: /sign in/i });
    this.errorAlert = page.locator("[role='alert'], .text-destructive").first();
    this.videoPanel = page.locator("video").first();
  }

  // ── Navegacion ─────────────────────────────────────────────────────────────

  /** Navega a /login */
  async goto() {
    await this.page.goto("/login");
  }

  // ── Acciones ───────────────────────────────────────────────────────────────

  /** Completa el formulario y hace click en Sign in (sin esperar redireccion) */
  async login(user: string, pass: string) {
    await this.username.fill(user);
    await this.password.fill(pass);
    await this.signInBtn.click();
  }

  /** Login completo: llena formulario, envia, y espera redireccion a /dashboard */
  async loginAndWait(user = "admin", pass = "1234") {
    await this.login(user, pass);
    await this.page.waitForURL("**/dashboard");
  }

  // ── Assertions ─────────────────────────────────────────────────────────────

  /** Verifica que se muestra el error de login. Opcionalmente chequea el texto. */
  async expectError(text?: string) {
    await expect(this.errorAlert).toBeVisible();
    if (text) await expect(this.errorAlert).toContainText(text);
  }

  /** Verifica que el boton esta deshabilitado con texto "Signing in..." */
  async expectLoadingState() {
    const submitBtn = this.page.locator("button[type='submit']");
    await expect(submitBtn).toBeDisabled({ timeout: 2_000 });
    await expect(submitBtn).toContainText(/signing/i);
  }
}
