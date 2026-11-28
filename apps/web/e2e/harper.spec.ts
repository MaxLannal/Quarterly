import { expect, test } from "@playwright/test";

// The homepage (docs/DESIGN.md "Simple light"): the title, Harper Memorial Library's reading room
// drawn in code (features/home/HarperHall.tsx) in a white card, then the three parts of Quarterly.

const TITLE = "The Best of UChicago, within your reach.";

test("the homepage shows Harper's reading room and asks nothing of another origin", async ({ page, baseURL }) => {
  const foreign: string[] = [];
  page.on("request", (r) => {
    const url = new URL(r.url());
    if (url.protocol.startsWith("http") && url.origin !== new URL(baseURL ?? "http://127.0.0.1").origin) foreign.push(r.url());
  });
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1, name: TITLE })).toBeVisible();
  await expect(page.getByRole("img", { name: /reading room of Harper Memorial Library/ })).toBeVisible();
  await expect(page.getByText("Harper Memorial Library, the reading room")).toBeVisible();
  await page.waitForLoadState("networkidle");
  expect(foreign).toEqual([]);
});

test("day is sunlight through the windows; night is lamplight", async ({ page }) => {
  await page.goto("/");
  const picture = page.getByRole("img", { name: /reading room of Harper Memorial Library/ });
  await expect(picture).toHaveAccessibleName(/in sunlight/);
  await page.getByRole("radio", { name: "Night" }).click();
  await expect(picture).toHaveAccessibleName(/at night, lit by its lamps/);
  await expect(page.locator(".harper")).toHaveAttribute("data-scene", "night");
});

test("the three cards open the planner, the catalog and the forum", async ({ page }) => {
  await page.goto("/");
  const folders = page.getByRole("list", { name: "What's inside" });
  for (const [name, path] of [
    ["Planner", /\/plan$/],
    ["Catalog", /\/courses$/],
    ["Forum", /\/forum$/],
  ] as const) {
    await folders.getByRole("link", { name, exact: true }).click();
    await expect(page).toHaveURL(path);
    await page.goBack();
  }
});

test("with reduced motion the light holds still and no dust drifts", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1, name: TITLE })).toBeVisible();
  await expect(page.locator(".harper-dust")).toBeHidden();
  await expect(page.locator(".harper-shafts").first()).toHaveCSS("animation-name", "none");
});
