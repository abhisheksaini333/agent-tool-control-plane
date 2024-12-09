import { test, expect } from "@playwright/test";
import { signIn } from "./helpers.ts";
test("administrator publishes an immutable contract, activates and disables it with audit evidence", async ({
  page,
}) => {
  await signIn(page, "clara");
  await page
    .getByRole("button", { name: "Tool registry", exact: true })
    .click();
  const sourceTitle = page.getByRole("heading", {
    name: "text.digest v1.0.0",
    exact: true,
  });
  const source = page.locator(".registry-tool").filter({ has: sourceTitle });
  await source.getByRole("button", { name: "New version from this" }).click();
  const name = `text.browser-${Date.now().toString(36)}`;
  await page.getByLabel("Tool name", { exact: true }).fill(name);
  await page.getByLabel("Version", { exact: true }).fill("1.0.0");
  await page
    .getByRole("button", { name: "Publish version", exact: true })
    .click();
  await expect(page.getByRole("status")).toContainText(`Published ${name}`);
  const createdTitle = page.getByRole("heading", {
    name: `${name} v1.0.0`,
    exact: true,
  });
  const created = page.locator(".registry-tool").filter({ has: createdTitle });
  await created
    .getByRole("button", { name: "Activate version", exact: true })
    .click();
  await expect(
    page.getByText("Existing requests for this tool will fail authorization", {
      exact: false,
    })
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Confirm activation", exact: true })
    .click();
  await expect(created.locator(".badge")).toHaveText("Active");
  await created
    .getByRole("button", { name: "Disable tool", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Confirm disable", exact: true })
    .click();
  await expect(created.locator(".badge")).toHaveText("Inactive");
  await page
    .getByRole("button", { name: "Workspace audit", exact: true })
    .click();
  await expect(
    page.getByText("Tool disabled", { exact: true }).first()
  ).toBeVisible();
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await signIn(page, "auditor");
  await page
    .getByRole("button", { name: "Tool registry", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Tool registry", exact: true })
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "New version from this" })
  ).toHaveCount(0);
});
