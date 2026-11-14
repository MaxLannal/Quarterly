import { mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { expect, test, type Page } from "@playwright/test";

// Design review screenshots (step 5): every page at 1440x900 and 390x844, full page, device
// scale factor 1, animations off, saved to docs/screenshots/<name>-<width>.png. Runs only with
// SCREENSHOTS=1 (`make screenshots`), so a normal `make e2e` writes no files.

const OUT = resolve(dirname(fileURLToPath(import.meta.url)), "../../../docs/screenshots");
const FORUM = "/courses/TEST%2010000/i/fake-instructor-a";
const THREAD = `${FORUM}/t/3`;
const WIDTHS = [
  { width: 1440, height: 900 },
  { width: 390, height: 844 },
] as const;

async function logIn(page: Page, admin = false) {
  await page.goto("/guidelines");
  await expect(page.getByRole("heading", { level: 1, name: "Community guidelines" })).toBeVisible();
  await page.evaluate(async (asAdmin) => {
    if (asAdmin) sessionStorage.setItem("quarterly.mock.admin", "1");
    await fetch("/api/auth/login", { method: "POST", body: JSON.stringify({ login: "fake-user", password: "x" }) });
  }, admin);
}

/** A planner with a program and two courses on it (one with a prerequisite warning). */
async function fillPlanner(page: Page) {
  await page.goto("/plan");
  await page.getByRole("button", { name: "+ Program" }).click();
  const dialog = page.getByRole("dialog", { name: "Programs" });
  await dialog.getByRole("checkbox", { name: "Fake Program" }).check();
  await dialog.getByRole("button", { name: "Save programs" }).click();
  await expect(dialog).toBeHidden();
  for (const [code, term] of [
    ["TEST 10000", "Autumn 2099"],
    ["TEST 10100", "Autumn 2099"],
  ] as const) {
    const node = page.getByRole("button", { name: /^Fake introductory sequence/ });
    if ((await node.getAttribute("aria-expanded")) !== "true") await node.click();
    await page.getByRole("button", { name: `Add ${code} to a quarter` }).click();
    await page.getByRole("dialog", { name: `Add ${code} to…` }).getByRole("button", { name: term, exact: true }).click();
    await expect(page.locator(`[data-testid="course-card"][data-course="${code}"]`)).toBeVisible();
  }
}

/**
 * Waits for the page to settle, parks the mouse in the left gutter (no hover states), then saves
 * a PNG: the full page, or only the viewport for an open dialog (it is fixed to the viewport).
 */
async function shoot(page: Page, name: string, size: { width: number; height: number }, fullPage: boolean) {
  await page.waitForLoadState("networkidle");
  await page.evaluate(() => document.fonts.ready);
  await expect(page.locator('[role="status"]:has-text("Loading")')).toHaveCount(0);
  await page.mouse.move(0, size.height - 1);
  await page.screenshot({ path: `${OUT}/${name}-${size.width}.png`, fullPage, animations: "disabled", caret: "hide" });
}

const h1 = (page: Page, name?: string | RegExp) => expect(page.getByRole("heading", { level: 1, ...(name ? { name } : {}) }).first()).toBeVisible();

/** `dialog`: shoot the viewport only. `phoneOnly`: a state that exists only at phone width. */
type Shot = { name: string; run: (page: Page) => Promise<void>; dialog?: boolean; phoneOnly?: boolean };

const SHOTS: Shot[] = [
  { name: "home", run: async (p) => (await p.goto("/"), h1(p, "Quarterly")) },
  {
    name: "nav-menu",
    dialog: true,
    phoneOnly: true,
    run: async (p) => {
      await p.goto("/courses");
      await h1(p, "Course search");
      await p.getByRole("button", { name: "Menu" }).click();
      await expect(p.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Courses" })).toBeVisible();
    },
  },
  { name: "onboarding", run: async (p) => (await p.goto("/onboarding"), h1(p, "Planner setup")) },
  {
    name: "plan",
    run: async (p) => {
      await fillPlanner(p);
      await expect(p.getByTestId("verifier-badge")).toBeVisible();
    },
  },
  {
    name: "plan-generate",
    dialog: true,
    run: async (p) => {
      await p.goto("/plan");
      await p.getByRole("button", { name: "Generate plan" }).click();
      const dialog = p.getByRole("dialog", { name: "Generate plan" });
      await dialog.getByRole("button", { name: "Generate" }).click();
      await expect(dialog.getByRole("article", { name: "Variant Fake balanced" })).toBeVisible();
    },
  },
  {
    name: "plan-advisor",
    run: async (p) => {
      await logIn(p);
      await fillPlanner(p);
      await p.getByRole("tab", { name: "Advisor" }).click();
      await p.getByLabel("Ask the advisor").fill("Please add a lighter elective");
      await p.getByRole("button", { name: "Send" }).click();
      await expect(p.getByRole("article", { name: "Proposed change" })).toBeVisible();
      await expect(p.getByRole("link", { name: "Student post #3" })).toBeVisible();
    },
  },
  {
    name: "plans",
    run: async (p) => {
      await fillPlanner(p);
      await p.goto("/plans");
      await h1(p, "My plans");
      await p.getByRole("button", { name: "Duplicate" }).first().click();
      await expect(p.getByLabel("Name of plan")).toHaveCount(2);
    },
  },
  {
    name: "plans-compare",
    run: async (p) => {
      await fillPlanner(p);
      await p.goto("/plans");
      await p.getByRole("button", { name: "Duplicate" }).first().click();
      await p.getByRole("link", { name: "Compare two plans" }).click();
      await h1(p, "Compare plans");
    },
  },
  { name: "courses", run: async (p) => (await p.goto("/courses"), h1(p, "Course search")) },
  {
    name: "course",
    run: async (p) => {
      await logIn(p);
      await p.goto("/courses/TEST%2010000");
      await h1(p, "TEST 10000 · Fake Introduction I");
      await expect(p.getByText("From 2 reviews")).toBeVisible();
    },
  },
  {
    name: "forum",
    run: async (p) => {
      await logIn(p);
      await p.goto(FORUM);
      await h1(p, /with Fake Instructor A/);
      await expect(p.getByRole("article", { name: "Review by Fake Heron" })).toBeVisible();
    },
  },
  {
    name: "thread",
    run: async (p) => {
      await logIn(p);
      await p.goto(THREAD);
      await h1(p, "Fake question: is the midterm curved?");
      await expect(p.getByText("Fake reply at depth 5.")).toBeVisible();
    },
  },
  { name: "instructors", run: async (p) => (await p.goto("/instructors"), h1(p, "Instructors")) },
  {
    name: "instructor",
    run: async (p) => {
      await logIn(p);
      await p.goto("/instructors/fake-instructor-a");
      await h1(p, "Fake Instructor A");
    },
  },
  { name: "programs", run: async (p) => (await p.goto("/programs"), h1(p, "Program explorer")) },
  { name: "program", run: async (p) => (await p.goto("/programs/fake-major"), h1(p, "Fake Program")) },
  { name: "signup", run: async (p) => (await p.goto("/signup"), h1(p, "Create an account")) },
  { name: "login", run: async (p) => (await p.goto("/login"), h1(p, "Log in")) },
  {
    name: "account",
    run: async (p) => {
      await logIn(p);
      await p.goto("/account");
      await h1(p, "Account");
      await expect(p.getByRole("link", { name: "fake-user" })).toBeVisible();
    },
  },
  { name: "guidelines", run: async (p) => (await p.goto("/guidelines"), h1(p, "Community guidelines")) },
  { name: "privacy", run: async (p) => (await p.goto("/privacy"), h1(p, "Privacy")) },
  { name: "about", run: async (p) => (await p.goto("/about"), h1(p, "About")) },
  {
    name: "admin-moderation",
    run: async (p) => {
      await logIn(p, true);
      await p.goto("/admin/moderation");
      await h1(p, "Moderation queue");
      await expect(p.getByRole("article", { name: /discussion on TEST 10000/ })).toBeVisible();
    },
  },
  {
    name: "admin",
    run: async (p) => {
      await logIn(p, true);
      await p.goto("/admin/review");
      await h1(p, "Curator console");
    },
  },
  { name: "not-found", run: async (p) => (await p.goto("/no-such-page"), h1(p, "Page not found")) },
];

for (const size of WIDTHS) {
  test.describe(`screenshots at ${size.width}px`, () => {
    test.skip(!process.env.SCREENSHOTS, "set SCREENSHOTS=1 (make screenshots) to write docs/screenshots");
    test.use({ viewport: size, deviceScaleFactor: 1, reducedMotion: "reduce" });
    test.beforeAll(() => mkdirSync(OUT, { recursive: true }));

    for (const shot of SHOTS.filter((s) => !s.phoneOnly || size.width < 768)) {
      test(`${shot.name} @${size.width}`, async ({ page }) => {
        await shot.run(page);
        await shoot(page, shot.name, size, !shot.dialog);
      });
    }
  });
}
