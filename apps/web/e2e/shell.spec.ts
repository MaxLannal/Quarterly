import { expect, test } from "@playwright/test";

test("home and app shell", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1, name: "The Best of UChicago, within your reach." })).toBeVisible();
  const nav = page.getByRole("navigation", { name: "Main" });
  // Four tabs (issue #15): Dashboard, Planner, Catalog, Forum.
  await expect(nav.getByRole("link")).toHaveText(["Dashboard", "Planner", "Catalog", "Forum"]);
  await expect(page.getByRole("link", { name: "Log in" })).toBeVisible();
  await page.getByRole("link", { name: "Start planning" }).click();
  // Logged out, "Start planning" opens sign-up (Issue #16).
  await expect(page.getByRole("heading", { level: 1, name: "Create an account" })).toBeVisible();
  await nav.getByRole("link", { name: "Planner" }).click();
  await expect(nav.getByRole("link", { name: "Planner", exact: true })).toHaveAttribute("aria-current", "page");
});

test("phone width: no horizontal scroll on main pages", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 800 });
  const paths = [
    ...["/", "/plan", "/plans", "/plans/compare", "/me", "/courses", "/courses/TEST%2020000", "/programs", "/programs/fake-major"],
    ...["/instructors", "/signup", "/login", "/account", "/guidelines", "/privacy", "/about", "/no-such-page"],
  ];
  for (const path of paths) {
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1 })).toBeAttached();
    // Every page has a search: the top bar's, or the course search page's own (D11 H-1). The
    // homepage's question bar went in issue #15, so the top bar's search shows there on phones too.
    const search = page.getByRole("search").or(page.getByRole("searchbox"));
    await expect(search.filter({ visible: true }).first()).toBeVisible();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow, path).toBeLessThanOrEqual(0);
  }
});
