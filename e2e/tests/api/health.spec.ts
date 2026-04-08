/**
 * Test Suite: Health Check API
 * Tag: @api @smoke
 */
import { test, expect } from "../../fixtures/base.fixture";

test.describe("Health Check @api @smoke", () => {

  test("TC-BE-001: GET /health retorna status ok con metadata", async ({ api }) => {
    const res = await api.health();
    expect(res.ok()).toBeTruthy();

    const body = await res.json();
    expect(body.status).toBe("ok");
    expect(body.app).toBe("ai-host-agent");
    expect(body).toHaveProperty("version");
    expect(body).toHaveProperty("env");
    expect(body).toHaveProperty("restaurant");
  });
});
