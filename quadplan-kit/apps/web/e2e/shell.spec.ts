import { expect, test } from "@playwright/test";

test("home and app shell", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1, name: "Quarterly" })).toBeVisible();
  const nav = page.getByRole("navigation", { name: "Main" });
  for (const name of ["Plan", "Courses", "Programs", "Forum"]) await expect(nav.getByRole("link", { name })).toBeVisible();
  await expect(page.getByRole("link", { name: "Log in" })).toBeVisible();
  await page.getByRole("link", { name: "Start planning" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Planner setup" })).toBeVisible();
  await nav.getByRole("link", { name: "Plan" }).click();
  await expect(nav.getByRole("link", { name: "Plan", exact: true })).toHaveAttribute("aria-current", "page");
});

test("phone width: no horizontal scroll on main pages", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 800 });
  for (const path of ["/", "/plan", "/courses", "/courses/TEST%2020000", "/onboarding", "/programs/fake-major"]) {
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1 })).toBeAttached();
    await expect(page.getByRole("searchbox", { name: "Search courses", exact: true })).toBeVisible();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow, path).toBeLessThanOrEqual(0);
  }
});
