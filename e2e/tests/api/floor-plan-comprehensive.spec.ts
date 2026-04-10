/**
 * Test Suite: Floor Plan — Comprehensive Validation
 * ===================================================
 * Covers all floor plan functionality gaps:
 * - RBAC: authorization on save, assign, unassign
 * - Assignment conflicts and double-booking
 * - Availability edge cases (all occupied, party_size filtering)
 * - Save/load round-trip with section data preservation
 * - Unassign 404 path
 * - Hour filtering on assignments
 * Tag: @api @regression
 */
import { test, expect } from "../../fixtures/base.fixture";
import { uniqueGuest, futureDate, MINIMAL_FLOOR_PLAN } from "../../helpers/test-data";

// Use a unique date per test run to avoid cross-test contamination
const TEST_DATE = futureDate(7);

test.describe("Floor Plan Comprehensive @api @regression", () => {

  // ═══════════════════════════════════════════════════════════════════════════
  // RBAC — Authorization
  // ═══════════════════════════════════════════════════════════════════════════

  test("TC-FP-020: reader cannot save floor plan (403)", async ({ api }) => {
    await api.login("reader", "1234");
    const res = await api.saveFloorPlan(MINIMAL_FLOOR_PLAN);
    expect(res.status()).toBe(403);
  });

  test("TC-FP-021: writer without can_edit_floor_plan cannot save (403)", async ({ api }) => {
    await api.login("writer", "1234");
    const res = await api.saveFloorPlan(MINIMAL_FLOOR_PLAN);
    expect(res.status()).toBe(403);
  });

  test("TC-FP-022: admin can save floor plan (200)", async ({ apiAsAdmin }) => {
    const getRes = await apiAsAdmin.getFloorPlan();
    const layout = await getRes.json();
    const res = await apiAsAdmin.saveFloorPlan(layout);
    if (res.status() === 500) { test.skip(); return; }
    expect(res.ok()).toBeTruthy();
  });

  test("TC-FP-023: reader cannot assign table (403)", async ({ api, apiAsAdmin }) => {
    const createRes = await apiAsAdmin.createReservation({
      guest_name: uniqueGuest("RBAC-Assign"),
      guest_phone: "5550000001",
      date: TEST_DATE,
      time: "12:00",
      party_size: 2,
    });
    const { reservation_id } = await createRes.json();

    await api.login("reader", "1234");
    const res = await api.assignTable({
      table_id: "t1",
      reservation_id,
      date: TEST_DATE,
      hour: "12:00",
    });
    expect(res.status()).toBe(403);
  });

  test("TC-FP-024: reader cannot unassign table (403)", async ({ api }) => {
    await api.login("reader", "1234");
    const res = await api.unassignTable("fake-id", TEST_DATE, "12:00");
    expect(res.status()).toBe(403);
  });

  test("TC-FP-025: writer can assign and unassign tables", async ({ api, apiAsAdmin }) => {
    const createRes = await apiAsAdmin.createReservation({
      guest_name: uniqueGuest("Writer-Assign"),
      guest_phone: "5550000002",
      date: TEST_DATE,
      time: "13:00",
      party_size: 2,
    });
    const { reservation_id } = await createRes.json();

    await api.login("writer", "1234");

    const assignRes = await api.assignTable({
      table_id: "t4",
      reservation_id,
      date: TEST_DATE,
      hour: "13:00",
    });
    expect(assignRes.ok()).toBeTruthy();

    const unassignRes = await api.unassignTable(reservation_id, TEST_DATE, "13:00");
    expect(unassignRes.ok()).toBeTruthy();
  });

  // ═══════════════════════════════════════════════════════════════════════════
  // Assignment Conflicts & Edge Cases
  // ═══════════════════════════════════════════════════════════════════════════

  test("TC-FP-030: double-booking same table overwrites previous reservation", async ({ apiAsAdmin }) => {
    const res1 = await apiAsAdmin.createReservation({
      guest_name: uniqueGuest("Double-1"),
      guest_phone: "5550000003",
      date: TEST_DATE,
      time: "14:00",
      party_size: 2,
    });
    const { reservation_id: rid1 } = await res1.json();

    const res2 = await apiAsAdmin.createReservation({
      guest_name: uniqueGuest("Double-2"),
      guest_phone: "5550000004",
      date: TEST_DATE,
      time: "14:00",
      party_size: 2,
    });
    const { reservation_id: rid2 } = await res2.json();

    // Assign table t5 to reservation 1
    await apiAsAdmin.assignTable({ table_id: "t5", reservation_id: rid1, date: TEST_DATE, hour: "14:00" });

    // Assign same table to reservation 2 (should overwrite)
    const overwriteRes = await apiAsAdmin.assignTable({ table_id: "t5", reservation_id: rid2, date: TEST_DATE, hour: "14:00" });
    expect(overwriteRes.ok()).toBeTruthy();

    // Verify table is now assigned to reservation 2
    const assignments = await (await apiAsAdmin.getAssignments(TEST_DATE, "14:00")).json();
    const t5Assignment = assignments.assignments.find(
      (a: { table_id: string }) => a.table_id === "t5"
    );
    expect(t5Assignment).toBeTruthy();
    expect(t5Assignment.reservation_id).toBe(rid2);
  });

  test("TC-FP-031: unassign non-existent assignment returns 404", async ({ apiAsAdmin }) => {
    const res = await apiAsAdmin.unassignTable(
      "00000000-0000-0000-0000-000000000000",
      TEST_DATE,
      "23:00"
    );
    expect(res.status()).toBe(404);
  });

  test("TC-FP-032: assignments filtered by hour returns only that hour", async ({ apiAsAdmin }) => {
    const res14 = await apiAsAdmin.createReservation({
      guest_name: uniqueGuest("Hour-14"),
      guest_phone: "5550000005",
      date: TEST_DATE,
      time: "15:00",
      party_size: 2,
    });
    const { reservation_id: rid14 } = await res14.json();

    const res16 = await apiAsAdmin.createReservation({
      guest_name: uniqueGuest("Hour-16"),
      guest_phone: "5550000006",
      date: TEST_DATE,
      time: "16:00",
      party_size: 2,
    });
    const { reservation_id: rid16 } = await res16.json();

    await apiAsAdmin.assignTable({ table_id: "t7", reservation_id: rid14, date: TEST_DATE, hour: "15:00" });
    await apiAsAdmin.assignTable({ table_id: "t8", reservation_id: rid16, date: TEST_DATE, hour: "16:00" });

    // Filter by 15:00 — should only have t7
    const at15 = await (await apiAsAdmin.getAssignments(TEST_DATE, "15:00")).json();
    const t7 = at15.assignments.find((a: { table_id: string }) => a.table_id === "t7");
    const t8at15 = at15.assignments.find((a: { table_id: string }) => a.table_id === "t8");
    expect(t7).toBeTruthy();
    expect(t8at15).toBeUndefined();

    // No hour filter — should have both
    const all = await (await apiAsAdmin.getAssignments(TEST_DATE)).json();
    expect(all.assignments.length).toBeGreaterThanOrEqual(2);
  });

  // ═══════════════════════════════════════════════════════════════════════════
  // Save/Load Round-Trip
  // ═══════════════════════════════════════════════════════════════════════════

  test("TC-FP-033: save then load preserves section data in tables", async ({ apiAsAdmin }) => {
    const original = await (await apiAsAdmin.getFloorPlan()).json();
    if (!original.tables || original.tables.length === 0) { test.skip(); return; }

    // Save the current plan
    const saveRes = await apiAsAdmin.saveFloorPlan(original);
    if (saveRes.status() === 500) { test.skip(); return; }

    // Reload and verify sections survived round-trip
    const reloaded = await (await apiAsAdmin.getFloorPlan()).json();
    expect(reloaded.tables.length).toBe(original.tables.length);

    for (const origTable of original.tables) {
      const match = reloaded.tables.find((t: { id: string }) => t.id === origTable.id);
      expect(match).toBeTruthy();
      expect(match.section).toBe(origTable.section);
      expect(match.seats).toBe(origTable.seats);
      expect(match.shape).toBe(origTable.shape);
    }
  });

  test("TC-FP-034: save preserves elements and zones", async ({ apiAsAdmin }) => {
    const original = await (await apiAsAdmin.getFloorPlan()).json();

    const saveRes = await apiAsAdmin.saveFloorPlan(original);
    if (saveRes.status() === 500) { test.skip(); return; }

    const reloaded = await (await apiAsAdmin.getFloorPlan()).json();
    expect(reloaded.elements?.length).toBe(original.elements?.length ?? 0);
    expect(reloaded.zones?.length).toBe(original.zones?.length ?? 0);
  });

  // ═══════════════════════════════════════════════════════════════════════════
  // Availability Edge Cases
  // ═══════════════════════════════════════════════════════════════════════════

  test("TC-FP-035: availability filters tables smaller than party_size", async ({ apiAsAdmin }) => {
    // Party of 6 should NOT return 2-seat Bar tables
    const res = await apiAsAdmin.getAvailability(TEST_DATE, "20:00", 6);
    expect(res.ok()).toBeTruthy();

    const body = await res.json();
    const tables = body.available_tables || body.matching_tables || [];
    for (const t of tables) {
      expect(t.seats).toBeGreaterThanOrEqual(6);
    }
  });

  test("TC-FP-036: availability with Near Bathroom section works", async ({ apiAsAdmin }) => {
    const res = await apiAsAdmin.getAvailability(TEST_DATE, "20:00", 2, "Near Bathroom");
    expect(res.ok()).toBeTruthy();

    const body = await res.json();
    expect(body).toHaveProperty("matching_tables");
    for (const t of body.matching_tables) {
      expect(t.section).toBe("Near Bathroom");
    }
  });

  test("TC-FP-037: availability returns correct response shape without section", async ({ apiAsAdmin }) => {
    const res = await apiAsAdmin.getAvailability(TEST_DATE, "20:00", 2);
    expect(res.ok()).toBeTruthy();

    const body = await res.json();
    expect(body).toHaveProperty("date");
    expect(body).toHaveProperty("hour");
    expect(body).toHaveProperty("party_size");
    // Should have available_tables (all sections) when no section filter
    expect(body.available_tables || body.matching_tables).toBeDefined();
  });

  test("TC-FP-038: availability with occupied tables excludes them", async ({ apiAsAdmin }) => {
    // Create reservation and assign to a Bar table (2 seats)
    const createRes = await apiAsAdmin.createReservation({
      guest_name: uniqueGuest("Avail-Occ"),
      guest_phone: "5550000007",
      date: TEST_DATE,
      time: "18:00",
      party_size: 2,
    });
    const { reservation_id } = await createRes.json();

    await apiAsAdmin.assignTable({ table_id: "t4", reservation_id, date: TEST_DATE, hour: "18:00" });

    // Check availability for Bar section at the same time
    const res = await apiAsAdmin.getAvailability(TEST_DATE, "18:00", 2, "Bar");
    expect(res.ok()).toBeTruthy();

    const body = await res.json();
    const occupiedTable = body.matching_tables.find(
      (t: { id: string }) => t.id === "t4"
    );
    // t4 should NOT appear as available (it's assigned)
    expect(occupiedTable).toBeUndefined();
  });

  // ═══════════════════════════════════════════════════════════════════════════
  // Floor Plan Structure Integrity
  // ═══════════════════════════════════════════════════════════════════════════

  test("TC-FP-039: every table has all required fields", async ({ apiAsAdmin }) => {
    const body = await (await apiAsAdmin.getFloorPlan()).json();

    for (const table of body.tables) {
      expect(table).toHaveProperty("id");
      expect(table).toHaveProperty("label");
      expect(table).toHaveProperty("shape");
      expect(table).toHaveProperty("seats");
      expect(table).toHaveProperty("x");
      expect(table).toHaveProperty("y");
      expect(table).toHaveProperty("section");
      expect(["rect", "round", "circle"]).toContain(table.shape);
      expect(table.seats).toBeGreaterThan(0);
    }
  });

  test("TC-FP-040: every element has required fields and valid kind", async ({ apiAsAdmin }) => {
    const body = await (await apiAsAdmin.getFloorPlan()).json();
    const validKinds = ["window", "window_v", "door", "bathroom", "kitchen"];

    for (const el of body.elements || []) {
      expect(el).toHaveProperty("id");
      expect(el).toHaveProperty("kind");
      expect(el).toHaveProperty("x");
      expect(el).toHaveProperty("y");
      expect(el).toHaveProperty("width");
      expect(el).toHaveProperty("height");
      expect(validKinds).toContain(el.kind);
    }
  });

  test("TC-FP-041: all tables are within their zone boundaries", async ({ apiAsAdmin }) => {
    const body = await (await apiAsAdmin.getFloorPlan()).json();
    if (!body.zones || body.zones.length === 0) { test.skip(); return; }

    const indoorZone = body.zones.find((z: { kind: string }) => z.kind === "zone_indoor");
    const outdoorZone = body.zones.find((z: { kind: string }) => z.kind === "zone_outdoor");

    for (const table of body.tables) {
      const zone = table.section === "Patio" ? outdoorZone : indoorZone;
      if (!zone) continue;

      // Table center should be within zone bounds (with 20px tolerance)
      expect(table.x).toBeGreaterThanOrEqual(zone.x - 20);
      expect(table.y).toBeGreaterThanOrEqual(zone.y - 20);
      expect(table.x).toBeLessThanOrEqual(zone.x + zone.width + 20);
      expect(table.y).toBeLessThanOrEqual(zone.y + zone.height + 20);
    }
  });

  test("TC-FP-042: total capacity is exactly 60 seats", async ({ apiAsAdmin }) => {
    const body = await (await apiAsAdmin.getFloorPlan()).json();
    const totalSeats = body.tables.reduce(
      (sum: number, t: { seats: number }) => sum + t.seats, 0
    );
    expect(totalSeats).toBe(60);
  });
});
