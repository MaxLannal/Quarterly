import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

// Design foundation (docs/DESIGN.md, docs/DESIGN-IMPLEMENTATION.md): self-hosted fonts and assets,
// accessible pages, 44px targets.

const MAIN_PAGES = [
  "/",
  "/onboarding",
  "/plan",
  "/plans",
  "/courses",
  "/courses/TEST%2020000",
  "/programs",
  "/programs/fake-major",
  "/signup",
  "/login",
  "/account",
  "/privacy",
  "/instructors",
];

async function expectNoAxeViolations(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
  expect(results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`)).toEqual([]);
}

test("no request leaves the app's own origin (fonts, icons and images are bundled)", async ({ page, baseURL }) => {
  const own = new URL(baseURL ?? "http://127.0.0.1").origin;
  const foreign: string[] = [];
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (url.protocol === "data:" || url.protocol === "blob:") return;
    const local = url.hostname === "127.0.0.1" || url.hostname === "localhost";
    if (url.origin !== own && !local) foreign.push(`${request.resourceType()} ${request.url()}`);
  });
  for (const path of MAIN_PAGES) {
    await page.goto(path, { waitUntil: "networkidle" });
    await expect(page.getByRole("heading", { level: 1 })).toBeAttached();
  }
  expect(foreign).toEqual([]);
});

test("the DESIGN.md fonts load from the bundle", async ({ page }) => {
  const fontRequests: string[] = [];
  page.on("request", (r) => {
    if (r.resourceType() === "font") fontRequests.push(new URL(r.url()).pathname);
  });
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1, name: "Quarterly" })).toBeVisible();
  const loaded = await page.evaluate(async () => {
    await document.fonts.ready;
    return {
      display: document.fonts.check('300 64px "Newsreader"'),
      body: document.fonts.check('400 16px "Inter Variable"'),
      h1: getComputedStyle(document.querySelector("h1") as Element).fontFamily,
    };
  });
  expect(loaded.display).toBe(true);
  expect(loaded.body).toBe(true);
  expect(loaded.h1).toContain("Newsreader");
  expect(fontRequests.length).toBeGreaterThan(0);
  expect(fontRequests.every((p) => p.startsWith("/assets/"))).toBe(true);
});

test("home page: no axe violations", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1, name: "Quarterly" })).toBeVisible();
  await expectNoAxeViolations(page);
});

test("course page: no axe violations", async ({ page }) => {
  await page.goto("/courses/TEST%2020000");
  await expect(page.getByRole("heading", { level: 1, name: "TEST 20000 · Fake Theory" })).toBeVisible();
  await expect(page.getByRole("table", { name: "Predicted quarters" })).toBeVisible();
  await expectNoAxeViolations(page);
});

test("buttons keep a 44px target although pills are drawn 40px tall", async ({ page }) => {
  for (const path of ["/", "/plan", "/courses", "/courses/TEST%2020000"]) {
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1 })).toBeAttached();
    const small = await page.evaluate(() =>
      [...document.querySelectorAll<HTMLElement>("button, a[role='button'], [role='tab'], [role='menuitem']")]
        .filter((el) => el.offsetParent !== null && !el.classList.contains("sr-only"))
        .map((el) => ({ name: el.getAttribute("aria-label") ?? el.textContent?.trim() ?? "", box: el.getBoundingClientRect() }))
        .filter(({ box }) => box.height < 44 || box.width < 44)
        .map(({ name, box }) => `${name} (${Math.round(box.width)}x${Math.round(box.height)})`),
    );
    expect(small, path).toEqual([]);
  }
  // The primary pill is drawn 40px tall inside its 44px box.
  await page.goto("/");
  const pill = page.getByRole("link", { name: "Start planning" });
  const box = await pill.boundingBox();
  expect(box?.height).toBeGreaterThanOrEqual(44);
  const drawn = await pill.evaluate((el) => el.clientHeight); // the padding box, inside the transparent border
  expect(drawn).toBe(40);
});
