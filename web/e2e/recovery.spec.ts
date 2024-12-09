import { test, expect } from "@playwright/test";
import { signIn } from "./helpers.ts";

test("a lost submission response retries the same request and cancellation leaves no receipt", async ({
  page,
}) => {
  await signIn(page, "alice");
  await page.getByRole("button", { name: "New request" }).click();
  await page
    .getByLabel("Inventory item", { exact: true })
    .selectOption("KIT-AI");
  await page.getByLabel("Quantity", { exact: true }).fill("1");
  let originalId = "";
  let loseResponse = true;
  await page.route("**/api/requests", async (route) => {
    if (route.request().method() !== "POST" || !loseResponse)
      return route.continue();
    loseResponse = false;
    const response = await route.fetch();
    originalId = (await response.json()).id;
    await route.abort("failed");
  });
  await page
    .getByRole("button", { name: "Send for approval", exact: true })
    .click();
  await expect(page.getByRole("alert")).toContainText("could not be reached");
  expect(originalId).not.toBe("");
  const retried = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/requests") &&
      response.request().method() === "POST"
  );
  await page
    .getByRole("button", { name: "Send for approval", exact: true })
    .click();
  expect((await (await retried).json()).id).toBe(originalId);
  await page
    .getByRole("button", { name: "Cancel request", exact: true })
    .click();
  await expect(page.locator(".detail .badge")).toHaveText("Cancelled");
  await expect(
    page.getByRole("region", { name: "Execution receipt" })
  ).toHaveCount(0);
  await expect(
    page.getByText("Request cancelled", { exact: true })
  ).toBeVisible();
  await expect(
    page.locator(".request-item").filter({ hasText: originalId.slice(0, 8) })
  ).toHaveCount(1);
});

test("a delayed queue response cannot overwrite a newly selected request", async ({
  page,
}) => {
  await signIn(page, "alice");
  const rows = page.locator(".request-item");
  await expect(rows.first()).toBeVisible();
  expect(await rows.count()).toBeGreaterThan(1);
  await rows.first().click();
  const secondId = (await rows.nth(1).locator("code").textContent())!;
  let release: () => void = () => {};
  let held: () => void = () => {};
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  const arrived = new Promise<void>((resolve) => {
    held = resolve;
  });
  let intercept = true;
  await page.route("**/api/requests?limit=200", async (route) => {
    if (!intercept) return route.continue();
    intercept = false;
    const response = await route.fetch();
    const snapshot = await response.json();
    const second = snapshot.find((row: { id: string }) =>
      row.id.startsWith(secondId)
    );
    second.arguments = { marker: "STALE_RESPONSE_SHOULD_NOT_RENDER" };
    held();
    await gate;
    await route.fulfill({ response, body: JSON.stringify(snapshot) });
  });
  await arrived;
  await rows.nth(1).click();
  await expect(page.locator(".detail .eyebrow").first()).toContainText(
    secondId
  );
  release();
  await page.waitForTimeout(250);
  await expect(
    page.getByText("STALE_RESPONSE_SHOULD_NOT_RENDER", { exact: false })
  ).toHaveCount(0);
});

test("mobile workspace stays within the viewport and preserves usable request controls", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await signIn(page, "alice");
  await page.getByRole("button", { name: "New request" }).click();
  await expect(page.getByLabel("Tool", { exact: true })).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth
    )
  ).toBe(true);
  if (process.env.KEEL_EVIDENCE_DIR)
    await page.screenshot({
      path: `${process.env.KEEL_EVIDENCE_DIR}/workspace-mobile.png`,
      fullPage: true,
    });
});
