const { test, expect } = require("@playwright/test");
const path = require("path");

const outputDirectory = process.env.BLOOM_SCREENSHOT_DIR || "test-results";
const targetUrl = process.env.BLOOM_TEST_URL || "https://bloom.surveycorps.cn";
const allowedHostname = new URL(targetUrl).hostname;

test.use({
  launchOptions: {
    args: ["--no-proxy-server"],
  },
});

for (const viewport of [
  { name: "desktop", width: 1440, height: 1000 },
  { name: "mobile", width: 390, height: 844 },
]) {
  test(`${viewport.name} production smoke`, async ({ page }) => {
    await page.setViewportSize({ width: viewport.width, height: viewport.height });

    const consoleErrors = [];
    const pageErrors = [];
    const externalRequests = [];
    page.on("console", message => {
      if (message.type() === "error") consoleErrors.push(message.text());
    });
    page.on("pageerror", error => pageErrors.push(error.message));
    page.on("request", request => {
      const requestUrl = new URL(request.url());
      if (requestUrl.hostname !== allowedHostname) externalRequests.push(request.url());
    });

    await page.goto(targetUrl, { waitUntil: "networkidle" });
    await expect(page).toHaveTitle(/Bloom/);
    await expect(page.locator(".hero h1")).toBeVisible();
    await expect(page.locator(".style-card").first()).toBeVisible();

    const canvas = page.locator("#three-bg canvas");
    await expect(canvas).toBeVisible();
    const canvasBox = await canvas.boundingBox();
    expect(canvasBox.width).toBeGreaterThan(100);
    expect(canvasBox.height).toBeGreaterThan(100);

    await page.screenshot({
      path: path.join(outputDirectory, `bloom-${viewport.name}.png`),
      fullPage: true,
    });
    await canvas.screenshot({
      path: path.join(outputDirectory, `bloom-${viewport.name}-canvas-a.png`),
    });
    await page.waitForTimeout(700);
    await canvas.screenshot({
      path: path.join(outputDirectory, `bloom-${viewport.name}-canvas-b.png`),
    });

    await page.locator('[data-view="community"]:visible').first().click();
    await expect(page.locator(".community-page")).toBeVisible();
    await expect(page.locator(".community-feed")).toBeVisible();

    expect(consoleErrors).toEqual([]);
    expect(pageErrors).toEqual([]);
    expect(externalRequests).toEqual([]);
  });
}
