/**
 * Test Suite: Floor Plan Layout & Table Preferences
 * ==================================================
 * Verifica que el plano del restaurante tiene la estructura correcta:
 * - 18 mesas con 66 asientos distribuidos en secciones
 * - Elementos arquitectonicos (ventanas, puertas, banos)
 * - Zonas (interior, patio)
 * - Cada mesa tiene la seccion/preferencia correcta
 * Tag: @api @regression
 */
import { test, expect } from "../../fixtures/base.fixture";

test.describe("Floor Plan Layout Validation @api @regression", () => {

  test("TC-FP-001: floor plan has 18 tables with correct total seats", async ({ apiAsAdmin }) => {
    const res = await apiAsAdmin.getFloorPlan();
    expect(res.ok()).toBeTruthy();

    const body = await res.json();
    expect(body.tables).toHaveLength(18);

    const totalSeats = body.tables.reduce((sum: number, t: { seats: number }) => sum + t.seats, 0);
    expect(totalSeats).toBe(66);
  });

  test("TC-FP-002: each section has correct number of tables", async ({ apiAsAdmin }) => {
    const res = await apiAsAdmin.getFloorPlan();
    const body = await res.json();

    const sectionCounts: Record<string, number> = {};
    for (const t of body.tables) {
      sectionCounts[t.section] = (sectionCounts[t.section] || 0) + 1;
    }

    expect(sectionCounts["Window"]).toBe(4);
    expect(sectionCounts["Bar"]).toBe(2);
    expect(sectionCounts["Booth"]).toBe(2);
    expect(sectionCounts["Private"]).toBe(1);
    expect(sectionCounts["Near Bathroom"]).toBe(2);
    expect(sectionCounts["Quiet"]).toBe(2);
    expect(sectionCounts["Patio"]).toBe(5);
  });

  test("TC-FP-003: section seat capacity matches requirements", async ({ apiAsAdmin }) => {
    const res = await apiAsAdmin.getFloorPlan();
    const body = await res.json();

    const sectionSeats: Record<string, number> = {};
    for (const t of body.tables) {
      sectionSeats[t.section] = (sectionSeats[t.section] || 0) + t.seats;
    }

    expect(sectionSeats["Window"]).toBe(16);    // 4x4
    expect(sectionSeats["Bar"]).toBe(4);         // 2x2
    expect(sectionSeats["Booth"]).toBe(8);       // 2x4
    expect(sectionSeats["Private"]).toBe(6);     // 1x6
    expect(sectionSeats["Near Bathroom"]).toBe(4); // 2x2
    expect(sectionSeats["Quiet"]).toBe(8);       // 2x4
    expect(sectionSeats["Patio"]).toBe(20);      // 5x4
  });

  test("TC-FP-004: floor plan has elements (windows, doors, bathrooms)", async ({ apiAsAdmin }) => {
    const res = await apiAsAdmin.getFloorPlan();
    const body = await res.json();

    expect(body.elements).toBeDefined();
    expect(body.elements.length).toBe(10);

    const kinds = body.elements.map((e: { kind: string }) => e.kind);
    const windows = kinds.filter((k: string) => k === "window");
    const windowsV = kinds.filter((k: string) => k === "window_v");
    const doors = kinds.filter((k: string) => k === "door");
    const bathrooms = kinds.filter((k: string) => k === "bathroom");

    expect(windows.length).toBe(4);
    expect(windowsV.length).toBe(2);
    expect(doors.length).toBe(2);
    expect(bathrooms.length).toBe(2);
  });

  test("TC-FP-005: floor plan has indoor and patio zones", async ({ apiAsAdmin }) => {
    const res = await apiAsAdmin.getFloorPlan();
    const body = await res.json();

    expect(body.zones).toBeDefined();
    expect(body.zones).toHaveLength(2);

    const zoneKinds = body.zones.map((z: { kind: string }) => z.kind);
    expect(zoneKinds).toContain("zone_indoor");
    expect(zoneKinds).toContain("zone_outdoor");
  });

  test("TC-FP-006: window tables are positioned near window elements", async ({ apiAsAdmin }) => {
    const res = await apiAsAdmin.getFloorPlan();
    const body = await res.json();

    const windowTables = body.tables.filter((t: { section: string }) => t.section === "Window");
    const windowElements = body.elements.filter((e: { kind: string }) => e.kind === "window");

    // Window tables should be within 100px of at least one window element
    for (const table of windowTables) {
      const nearWindow = windowElements.some((w: { x: number; y: number; width: number; height: number }) => {
        const distY = Math.abs(table.y - (w.y + w.height));
        return distY < 100;
      });
      expect(nearWindow).toBeTruthy();
    }
  });

  test("TC-FP-007: patio tables are within patio zone", async ({ apiAsAdmin }) => {
    const res = await apiAsAdmin.getFloorPlan();
    const body = await res.json();

    const patioTables = body.tables.filter((t: { section: string }) => t.section === "Patio");
    const patioZone = body.zones.find((z: { kind: string }) => z.kind === "zone_outdoor");

    expect(patioZone).toBeDefined();

    for (const table of patioTables) {
      const W = table.shape === "round" ? 70 : 90;
      const H = table.shape === "round" ? 70 : 60;
      expect(table.x - W / 2).toBeGreaterThanOrEqual(patioZone.x - 10);
      expect(table.y - H / 2).toBeGreaterThanOrEqual(patioZone.y - 10);
      expect(table.x + W / 2).toBeLessThanOrEqual(patioZone.x + patioZone.width + 10);
      expect(table.y + H / 2).toBeLessThanOrEqual(patioZone.y + patioZone.height + 10);
    }
  });

  test("TC-FP-008: near-bathroom tables are close to bathroom elements", async ({ apiAsAdmin }) => {
    const res = await apiAsAdmin.getFloorPlan();
    const body = await res.json();

    const nearBathTables = body.tables.filter((t: { section: string }) => t.section === "Near Bathroom");
    const bathrooms = body.elements.filter((e: { kind: string }) => e.kind === "bathroom");

    for (const table of nearBathTables) {
      const nearBath = bathrooms.some((b: { x: number; y: number }) => {
        const dist = Math.sqrt(Math.pow(table.x - b.x, 2) + Math.pow(table.y - b.y, 2));
        return dist < 250;
      });
      expect(nearBath).toBeTruthy();
    }
  });

  test("TC-FP-009: all table IDs are unique", async ({ apiAsAdmin }) => {
    const res = await apiAsAdmin.getFloorPlan();
    const body = await res.json();

    const ids = body.tables.map((t: { id: string }) => t.id);
    const uniqueIds = new Set(ids);
    expect(uniqueIds.size).toBe(ids.length);
  });

  test("TC-FP-010: availability check returns tables filtered by section", async ({ apiAsAdmin }) => {
    const sections = ["Patio", "Window", "Bar", "Booth", "Private", "Quiet"];

    for (const section of sections) {
      const res = await apiAsAdmin.getAvailability("2026-04-15", "20:00", 2, section);
      expect(res.ok()).toBeTruthy();

      const body = await res.json();
      expect(body).toHaveProperty("matching_tables");
      expect(body).toHaveProperty("other_available");

      // All matching tables should be in the requested section
      for (const table of body.matching_tables) {
        expect(table.section).toBe(section);
      }
    }
  });

  test("TC-FP-011: availability filters tables by party size", async ({ apiAsAdmin }) => {
    // Party of 5 should not match 2-seat tables
    const res = await apiAsAdmin.getAvailability("2026-04-15", "20:00", 5);
    expect(res.ok()).toBeTruthy();

    const body = await res.json();
    const available = body.available_tables || body.matching_tables || [];
    for (const table of available) {
      expect(table.seats).toBeGreaterThanOrEqual(5);
    }
  });

  test("TC-FP-012: table assign and unassign round-trip", async ({ apiAsAdmin }) => {
    // Create a test reservation
    const createRes = await apiAsAdmin.createReservation({
      guest_name: `FP-Test-${Date.now().toString(36)}`,
      guest_phone: "+4915750441601",
      date: "2026-04-15",
      time: "20:00",
      party_size: 2,
    });
    const { reservation_id } = await createRes.json();

    // Assign to table t5 (Bar, 2 seats)
    const assignRes = await apiAsAdmin.assignTable({
      table_id: "t5",
      reservation_id,
      date: "2026-04-15",
      hour: "20:00",
    });
    expect(assignRes.ok()).toBeTruthy();

    // Verify assignment exists
    const getRes = await apiAsAdmin.getAssignments("2026-04-15", "20:00");
    const assignments = await getRes.json();
    const found = assignments.assignments.find(
      (a: { reservation_id: string }) => a.reservation_id === reservation_id
    );
    expect(found).toBeTruthy();
    expect(found.table_id).toBe("t5");

    // Unassign
    const unassignRes = await apiAsAdmin.unassignTable(reservation_id, "2026-04-15", "20:00");
    expect(unassignRes.ok()).toBeTruthy();

    // Verify unassigned
    const getRes2 = await apiAsAdmin.getAssignments("2026-04-15", "20:00");
    const assignments2 = await getRes2.json();
    const found2 = assignments2.assignments.find(
      (a: { reservation_id: string }) => a.reservation_id === reservation_id
    );
    expect(found2).toBeUndefined();
  });
});
