import { TestInfo, Page } from "@playwright/test";

/**
 * Capture a screenshot and attach it to the test report as evidence.
 * The screenshot is embedded in the HTML report with the given label.
 */
export async function evidence(page: Page, testInfo: TestInfo, label: string) {
  const screenshot = await page.screenshot({ fullPage: true });
  await testInfo.attach(label, { body: screenshot, contentType: "image/png" });
}
