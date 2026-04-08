/**
 * Playwright Config
 * =================
 * Funciona en dos modos:
 *   - LOCAL:  levanta el frontend con webServer, usa localhost
 *   - CI:     no levanta nada, se conecta via BASE_URL/API_URL (env vars)
 *
 * Variables de entorno:
 *   CI        → "true" en Drone (desactiva webServer)
 *   BASE_URL  → URL del frontend (default: http://localhost:5173)
 *   API_URL   → URL del backend  (default: http://localhost:8000)
 */
import { defineConfig, devices } from "@playwright/test";

const isCI = !!process.env.CI;

export default defineConfig({
  testDir: "./tests",
  fullyParallel: true,
  forbidOnly: isCI,
  retries: isCI ? 2 : 0,
  workers: isCI ? 1 : undefined,
  reporter: [
    ["list"],
    ["html", { open: isCI ? "never" : "on-failure" }],
  ],
  timeout: 30_000,
  expect: { timeout: 5_000 },

  use: {
    baseURL: process.env.BASE_URL ?? "http://localhost:5173",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },

  projects: [
    { name: "setup", testMatch: /global-setup\.ts/ },
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
      dependencies: ["setup"],
    },
    {
      name: "mobile",
      use: { ...devices["iPhone 14"] },
      dependencies: ["setup"],
    },
  ],

  // En CI la app ya esta corriendo; en local la levantamos con Vite
  ...(isCI
    ? {}
    : {
        webServer: [
          {
            command: "cd ../ui && npm run dev",
            url: "http://localhost:5173",
            reuseExistingServer: true,
            timeout: 30_000,
          },
        ],
      }),
});
