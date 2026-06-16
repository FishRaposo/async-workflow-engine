import { test, expect } from "@playwright/test";

// These run against the demo-mode UI: with no backend, every data view falls
// back to bundled mock data and the "Demo mode" banner appears.

test("home page renders and links to runs", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveTitle(/Flowforge/i);
  await expect(
    page.getByRole("heading", { name: /orchestration console/i })
  ).toBeVisible();
  await page.getByRole("link", { name: /view runs/i }).click();
  await expect(page).toHaveURL(/\/runs/);
});

test("runs list shows demo data and the demo-mode banner", async ({ page }) => {
  await page.goto("/runs");
  await expect(page.getByTestId("demo-mode-banner")).toBeVisible();
  await expect(page.getByText("payment_reconcile").first()).toBeVisible();
});

test("a run detail page renders its DAG", async ({ page }) => {
  await page.goto("/runs/11111111-1111-1111-1111-111111111111");
  await expect(page.getByRole("img", { name: /workflow dag/i })).toBeVisible();
  await expect(page.getByTestId("dag-node-parse_input")).toBeVisible();
});

test("dead-letter queue lists failed steps", async ({ page }) => {
  await page.goto("/dead-letters");
  await expect(page.getByTestId("dead-letter-table")).toBeVisible();
  await expect(page.getByText("always_fail").first()).toBeVisible();
});

test("schedules page lists cron schedules", async ({ page }) => {
  await page.goto("/schedules");
  await expect(page.getByText("lead_intake_every_15m")).toBeVisible();
});

test("trigger page exposes the YAML form", async ({ page }) => {
  await page.goto("/trigger");
  await expect(page.getByRole("heading", { name: /trigger a workflow/i })).toBeVisible();
  await expect(page.getByLabel(/workflow yaml/i)).toBeVisible();
});
