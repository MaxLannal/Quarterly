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
    if (path === "/plan") {
      // Measure a planner with a course card on it (drag handle, actions menu).
      await page.getByRole("button", { name: "+ Program" }).click();
      const dialog = page.getByRole("dialog", { name: "Programs" });
      await dialog.getByRole("checkbox", { name: "Fake Program" }).check();
      await dialog.getByRole("button", { name: "Save programs" }).click();
      const node = page.getByRole("button", { name: /^Fake introductory sequence/ });
      if ((await node.getAttribute("aria-expanded")) !== "true") await node.click();
      await page.getByRole("button", { name: "Add TEST 10000 to a quarter" }).click();
      await page.getByRole("dialog", { name: "Add TEST 10000 to…" }).getByRole("button", { name: "Autumn 2099", exact: true }).click();
      await expect(page.locator('[data-testid="course-card"][data-course="TEST 10000"]')).toBeVisible();
    }
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

// ------------------------------------------------------------------------------------------
// Design review (step 5): axe on the planner (with the Generate dialog and an answered Advisor
// tab) and on the forum page and thread, at desktop (1440x900) and phone (390x844) width. No
// serious or critical WCAG 2.1 A/AA violations.
// ------------------------------------------------------------------------------------------

const FORUM = "/courses/TEST%2010000/i/fake-instructor-a";

async function expectNoSeriousAxeViolations(page: Page, include?: string) {
  let builder = new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]);
  if (include) builder = builder.include(include);
  const results = await builder.analyze();
  const serious = results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
  expect(serious.map((v) => `${v.impact} ${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`)).toEqual([]);
}

async function logIn(page: Page) {
  await page.goto("/guidelines");
  await expect(page.getByRole("heading", { level: 1, name: "Community guidelines" })).toBeVisible();
  await page.evaluate(() => fetch("/api/auth/login", { method: "POST", body: JSON.stringify({ login: "fake-user", password: "x" }) }));
}

async function plannerWithCourses(page: Page) {
  await page.goto("/plan");
  await page.getByRole("button", { name: "+ Program" }).click();
  const dialog = page.getByRole("dialog", { name: "Programs" });
  await dialog.getByRole("checkbox", { name: "Fake Program" }).check();
  await dialog.getByRole("button", { name: "Save programs" }).click();
  for (const code of ["TEST 10000", "TEST 10100"]) {
    const node = page.getByRole("button", { name: /^Fake introductory sequence/ });
    if ((await node.getAttribute("aria-expanded")) !== "true") await node.click();
    await page.getByRole("button", { name: `Add ${code} to a quarter` }).click();
    await page.getByRole("dialog", { name: `Add ${code} to…` }).getByRole("button", { name: "Autumn 2099", exact: true }).click();
  }
  await expect(page.locator('[data-testid="course-card"][data-course="TEST 10100"]')).toContainText("earlier quarter");
}

for (const size of [
  { width: 1440, height: 900 },
  { width: 390, height: 844 },
]) {
  test.describe(`axe at ${size.width}px`, () => {
    test.use({ viewport: size });

    test(`planner, Generate dialog and Advisor @${size.width}: no serious axe violations`, async ({ page }) => {
      await logIn(page);
      await plannerWithCourses(page);
      await expectNoSeriousAxeViolations(page);

      await page.getByRole("button", { name: "Generate plan" }).click();
      const dialog = page.getByRole("dialog", { name: "Generate plan" });
      await expectNoSeriousAxeViolations(page, '[role="dialog"]');
      await dialog.getByRole("button", { name: "Generate" }).click();
      await expect(dialog.getByRole("article", { name: "Variant Fake balanced" })).toBeVisible();
      await expectNoSeriousAxeViolations(page, '[role="dialog"]');
      await page.keyboard.press("Escape");
      await expect(dialog).toBeHidden();

      await page.getByRole("tab", { name: "Advisor" }).click();
      await page.getByLabel("Ask the advisor").fill("Please add a lighter elective");
      await page.getByRole("button", { name: "Send" }).click();
      await expect(page.getByRole("article", { name: "Proposed change" })).toBeVisible();
      // Forum citations become links once the post and its page load (forum reads need a login).
      await expect(page.getByRole("link", { name: "Student post #3" })).toHaveAttribute("href", `${FORUM}/t/3`);
      await expect(page.getByRole("link", { name: "What students say" })).toHaveAttribute("href", FORUM);
      await expectNoSeriousAxeViolations(page);
    });

    test(`forum page and thread @${size.width}: no serious axe violations`, async ({ page }) => {
      await logIn(page);
      await page.goto(FORUM);
      await expect(page.getByRole("article", { name: "Review by Fake Heron" })).toBeVisible();
      await expectNoSeriousAxeViolations(page);
      await page.getByRole("button", { name: "Write a review" }).click();
      await expect(page.getByRole("form", { name: "Write a review" })).toBeVisible();
      await expectNoSeriousAxeViolations(page);

      await page.goto(`${FORUM}/t/3`);
      await expect(page.getByText("Fake reply at depth 5.")).toBeVisible();
      await expectNoSeriousAxeViolations(page);
      await page.getByRole("button", { name: "Report discussion by Fake Lark" }).click();
      await expect(page.getByRole("dialog", { name: "Report this post" })).toBeVisible();
      await expectNoSeriousAxeViolations(page, '[role="dialog"]');
    });
  });
}
