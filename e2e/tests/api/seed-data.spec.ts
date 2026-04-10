/**
 * Test Suite: Seed Data Validation
 * =================================
 * Verifica que las reservas de seed están correctamente cargadas:
 * - 150 reservas distribuidas en 10 días
 * - Todas con el teléfono correcto
 * - Variedad de preferencias y horarios
 * Tag: @api @regression
 */
import { test, expect } from "../../fixtures/base.fixture";
import { readFileSync } from "fs";
import { resolve } from "path";

const seedPath = resolve(__dirname, "../../fixtures/seed-reservations.json");
const seedData: Array<Record<string, unknown>> = JSON.parse(readFileSync(seedPath, "utf-8"));

test.describe("Seed Data Validation @api @regression", () => {

  test("TC-SEED-001: fixture JSON has exactly 150 reservations", async () => {
    expect(seedData).toHaveLength(150);
  });

  test("TC-SEED-002: all reservations use correct phone number", async () => {
    const data = seedData as Array<{ guest_phone: string }>;
    for (const r of data) {
      expect(r.guest_phone).toBe("+4915750441601");
    }
  });

  test("TC-SEED-003: reservations span 10 days from 2026-04-09 to 2026-04-18", async () => {
    const data = seedData as Array<{ date: string }>;
    const dates = new Set(data.map(r => r.date));
    expect(dates.size).toBe(10);

    const expectedDates = [
      "2026-04-09", "2026-04-10", "2026-04-11", "2026-04-12", "2026-04-13",
      "2026-04-14", "2026-04-15", "2026-04-16", "2026-04-17", "2026-04-18",
    ];
    for (const d of expectedDates) {
      expect(dates.has(d)).toBeTruthy();
    }
  });

  test("TC-SEED-004: each day has roughly equal distribution (~15 per day)", async () => {
    const data = seedData as Array<{ date: string }>;
    const dateCounts: Record<string, number> = {};
    for (const r of data) {
      dateCounts[r.date] = (dateCounts[r.date] || 0) + 1;
    }

    for (const [date, count] of Object.entries(dateCounts)) {
      expect(count).toBeGreaterThanOrEqual(10);
      expect(count).toBeLessThanOrEqual(20);
    }
  });

  test("TC-SEED-005: reservations have varied preferences", async () => {
    const data = seedData as Array<{ preference: string | null }>;
    const prefs = new Set(data.map(r => r.preference).filter(Boolean));

    // Should have at least 5 different preference types
    expect(prefs.size).toBeGreaterThanOrEqual(5);

    // Expected preference types
    const expectedPrefs = ["Patio", "Window", "Booth", "Bar", "Private"];
    for (const p of expectedPrefs) {
      expect(prefs.has(p)).toBeTruthy();
    }
  });

  test("TC-SEED-006: reservations have times in lunch and dinner slots", async () => {
    const data = seedData as Array<{ time: string }>;
    const hours = data.map(r => parseInt(r.time.split(":")[0]));

    const lunchCount = hours.filter(h => h >= 12 && h <= 14).length;
    const dinnerCount = hours.filter(h => h >= 19 && h <= 23).length;

    expect(lunchCount).toBeGreaterThan(0);
    expect(dinnerCount).toBeGreaterThan(0);
    expect(lunchCount + dinnerCount).toBe(data.length);
  });

  test("TC-SEED-007: party sizes are varied and within range 1-12", async () => {
    const data = seedData as Array<{ party_size: number }>;
    const sizes = new Set(data.map(r => r.party_size));

    // Should have at least 4 different party sizes
    expect(sizes.size).toBeGreaterThanOrEqual(4);

    for (const r of data) {
      expect(r.party_size).toBeGreaterThanOrEqual(1);
      expect(r.party_size).toBeLessThanOrEqual(12);
    }
  });

  test("TC-SEED-008: some reservations have null preference (no preference)", async () => {
    const data = seedData as Array<{ preference: string | null }>;
    const noPrefs = data.filter(r => !r.preference);

    // About 20-40% should have no preference
    expect(noPrefs.length).toBeGreaterThan(20);
    expect(noPrefs.length).toBeLessThan(60);
  });

  test("TC-SEED-009: all reservations have required fields", async () => {
    const data = seedData as Array<Record<string, unknown>>;
    for (const r of data) {
      expect(r.guest_name).toBeTruthy();
      expect(r.guest_phone).toBeTruthy();
      expect(r.date).toBeTruthy();
      expect(r.time).toBeTruthy();
      expect(r.party_size).toBeDefined();
    }
  });

  test("TC-SEED-010: reservation names are diverse (at least 50 unique names)", async () => {
    const data = seedData as Array<{ guest_name: string }>;
    const names = new Set(data.map(r => r.guest_name));
    expect(names.size).toBeGreaterThanOrEqual(50);
  });
});
