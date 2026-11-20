import { expect, test } from "@playwright/test";

test("home and app shell", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1, name: "The Best of UChicago, within your reach." })).toBeVisible();
  const nav = page.getByRole("navigation", { name: "Main" });
  for (const name of ["Plan", "Catalog", "Forum"]) await expect(nav.getByRole("link", { name })).toBeVisible();
  await expect(page.getByRole("link", { name: "Log in" })).toBeVisible();
  await page.getByRole("link", { name: "Start planning" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Planner setup" })).toBeVisible();
  await nav.getByRole("link", { name: "Plan" }).click();
  await expect(nav.getByRole("link", { name: "Plan", exact: true })).toHaveAttribute("aria-current", "page");
});

test("phone width: no horizontal scroll on main pages", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 800 });
  const paths = [
    ...["/", "/plan", "/plans", "/plans/compare", "/onboarding", "/courses", "/courses/TEST%2020000", "/programs", "/programs/fake-major"],
    ...["/instructors", "/signup", "/login", "/account", "/guidelines", "/privacy", "/about", "/no-such-page"],
  ];
  for (const path of paths) {
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1 })).toBeAttached();
    // Every page has one course search box: the top bar's, or the page's own on home and course search (D11 H-1).
    await expect(page.getByRole("searchbox").first()).toBeVisible();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow, path).toBeLessThanOrEqual(0);
  }
});
