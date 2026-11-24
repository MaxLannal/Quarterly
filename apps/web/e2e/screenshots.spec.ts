import { mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { expect, test, type Page } from "@playwright/test";
import {
  addCourseViaTree,
  closePanel,
  logIn,
  openAdvisor,
  openPanel,
  plannerWithCourses,
  setGraduation,
} from "./helpers";

// Design review screenshots (step 5): every page at 1440x900 and 390x844, full page, device
// scale factor 1, animations off, saved to docs/screenshots/<name>-<width>.png. Runs only with
// SCREENSHOTS=1 (`make screenshots`), so a normal `make e2e` writes no files.

// SCREENSHOTS_DIR (relative to docs/screenshots) keeps a set apart, e.g. "before".
const OUT = resolve(
  dirname(fileURLToPath(import.meta.url)),
  "../../../docs/screenshots",
  process.env.SCREENSHOTS_DIR ?? "",
);
const FORUM = "/courses/TEST%2010000/i/fake-instructor-a";
const THREAD = `${FORUM}/t/3`;
const WIDTHS = [
  { width: 1440, height: 900 },
  { width: 390, height: 844 },
] as const;

/** A planner with a program and two courses on it (one with a prerequisite issue), drawer closed. */
async function fillPlanner(page: Page) {
  await plannerWithCourses(page);
  await closePanel(page);
}

/** Logged in, with a partly answered student record (fake data). */
async function filledRecord(page: Page) {
  await logIn(page);
  await page.evaluate(async () => {
    await fetch("/api/me/profile", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        class_year: 2030,
        expected_graduation_term: "2030-SP",
        intended_programs: ["fake-major"],
        entry_term: "2099-AU",
        entry_year_level: 1,
        credits: [{ kind: "AP", label: "Fake AP exam", maps_to: "TEST 10000", units: 100 }],
        post_grad_plan: "grad_school",
        wants_research: true,
        research_areas: ["Fake topology"],
        courses_per_term: 4,
        terms_away: [],
      }),
    });
  });
}

/**
 * Waits for the page to settle, parks the mouse in the left gutter (no hover states), then saves
 * a PNG: the full page, or only the viewport for an open dialog (it is fixed to the viewport).
 */
async function shoot(
  page: Page,
  name: string,
  size: { width: number; height: number },
  fullPage: boolean,
) {
  await page.waitForLoadState("networkidle");
  await page.evaluate(() => document.fonts.ready);
  await expect(page.locator('[role="status"]:has-text("Loading")')).toHaveCount(
    0,
  );
  await page.mouse.move(0, size.height - 1);
  mkdirSync(OUT, { recursive: true });
  await page.screenshot({
    path: `${OUT}/${name}-${size.width}.png`,
    fullPage,
    animations: "disabled",
    caret: "hide",
  });
}

const h1 = (page: Page, name?: string | RegExp) =>
  expect(
    page.getByRole("heading", { level: 1, ...(name ? { name } : {}) }).first(),
  ).toBeVisible();

/** `dialog`: shoot the viewport only. `phoneOnly`: a state that exists only at phone width. */
type Shot = {
  name: string;
  run: (page: Page) => Promise<void>;
  dialog?: boolean;
  phoneOnly?: boolean;
};

const SHOTS: Shot[] = [
  { name: "home", run: async (p) => (await p.goto("/"), h1(p, /The Best of UChicago/)) },
  {
    name: "nav-menu",
    dialog: true,
    phoneOnly: true,
    run: async (p) => {
      await p.goto("/courses");
      await h1(p, "Course search");
      await p.getByRole("button", { name: "Menu" }).click();
      await expect(
        p
          .getByRole("navigation", { name: "Main" })
          .getByRole("link", { name: "Catalog" }),
      ).toBeVisible();
    },
  },
  {
    name: "signup-about",
    run: async (p) => {
      await p.goto("/signup");
      await p.getByLabel("Email address").fill("fake-student@uchicago.edu");
      await p.getByRole("button", { name: "Send code" }).click();
      await p.getByLabel("6-digit code").fill("123456");
      await p.getByRole("button", { name: "Verify code" }).click();
      await p.getByLabel("Username").fill("fake-student");
      await p.getByLabel("Password", { exact: true }).fill("correct horse battery");
      await p.getByLabel("Repeat password").fill("correct horse battery");
      await p.getByRole("button", { name: "Create account" }).click();
      await p.getByLabel("What is your class year?").selectOption({ label: "Class of 2030" });
      await p.getByRole("checkbox", { name: "Fake Program" }).check();
      await p.getByRole("checkbox", { name: "I transferred, or I am not in my first year." }).check();
      await expect(p.getByLabel("Which year did you start in?")).toBeVisible();
    },
  },
  {
    name: "dashboard",
    run: async (p) => {
      await filledRecord(p);
      await p.goto("/me");
      await h1(p, /fake-user/);
      await expect(p.getByRole("region", { name: "Goals" })).toContainText("Graduate school");
    },
  },
  {
    name: "dashboard-guide",
    dialog: true,
    run: async (p) => {
      await filledRecord(p);
      await p.goto("/me");
      await p.getByRole("button", { name: /Complete your profile/ }).click();
      const guide = p.getByRole("dialog", { name: "Your guide" });
      await guide.getByRole("group", { name: "Quick answers" }).getByRole("button", { name: "On time" }).click();
      await expect(guide.getByRole("button", { name: "Accept Graduation pace: On time" })).toBeVisible();
    },
  },
  {
    name: "plan-setup",
    run: async (p) => {
      await filledRecord(p);
      await p.goto("/plan");
      await expect(p.getByRole("region", { name: "Set up a plan from your information" })).toBeVisible();
    },
  },
  {
    name: "plan",
    run: async (p) => {
      await fillPlanner(p);
      await expect(
        p.getByRole("button", { name: /^Check plan/ }),
      ).toBeVisible();
    },
  },
  {
    // FEEDBACK F4: the right-hand drawer with the requirement tree (full screen on a phone).
    name: "plan-drawer",
    dialog: true,
    run: async (p) => {
      await plannerWithCourses(p);
      await p
        .getByTestId("plan-drawer")
        .getByRole("button", { name: /^Fake core courses/ })
        .click();
      await expect(
        p.getByRole("button", { name: "Add TEST 20000 to a quarter" }),
      ).toBeVisible();
      await p
        .getByTestId("plan-drawer")
        .evaluate((el) =>
          el.querySelector('[role="tabpanel"]:not([hidden])')?.scrollTo(0, 0),
        );
    },
  },
  {
    // FEEDBACK F4: "Check plan" opens the issues in the drawer.
    name: "plan-check",
    dialog: true,
    run: async (p) => {
      await plannerWithCourses(p);
      await openPanel(p, "Check plan");
      await expect(
        p.getByRole("list", { name: "Verifier issues" }),
      ).toBeVisible();
    },
  },
  {
    // FEEDBACK F2 and F3: Summer opens each year, the graduation quarter and the year controls.
    name: "plan-years",
    run: async (p) => {
      await p.goto("/plan");
      await p.getByRole("button", { name: "+ Program" }).click();
      const dialog = p.getByRole("dialog", { name: "Programs" });
      await dialog.getByRole("checkbox", { name: "Fake Program" }).check();
      await dialog.getByRole("button", { name: "Save programs" }).click();
      await p.getByRole("button", { name: "Show Summer" }).click();
      await addCourseViaTree(
        p,
        /^Fake introductory sequence/,
        "TEST 10000",
        "Summer 2099",
      );
      await addCourseViaTree(
        p,
        /^Fake introductory sequence/,
        "TEST 10100",
        "Autumn 2099",
      );
      await closePanel(p);
      await setGraduation(p, "2103-WI");
      await expect(p.getByTestId("quarter-2103-SP")).toHaveCount(0);
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
      await expect(
        dialog.getByRole("article", { name: "Variant Fake balanced" }),
      ).toBeVisible();
    },
  },
  {
    // FEEDBACK F4: the AI advisor slides down from the top, labelled as generative AI.
    name: "plan-advisor",
    dialog: true,
    run: async (p) => {
      await logIn(p);
      await fillPlanner(p);
      const sheet = await openAdvisor(p);
      await sheet
        .getByLabel("Ask the advisor")
        .fill("Please add a lighter elective");
      await sheet.getByRole("button", { name: "Send" }).click();
      await expect(
        sheet.getByRole("article", { name: "Proposed change" }),
      ).toBeVisible();
      await expect(
        sheet.getByRole("link", { name: "Student post #3" }),
      ).toBeVisible();
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
  {
    name: "courses",
    run: async (p) => (await p.goto("/courses"), h1(p, "Course search")),
  },
  {
    name: "course",
    run: async (p) => {
      await logIn(p);
      await p.goto("/courses/TEST%2010000");
      await h1(p, "TEST 10000 · Fake Introduction I");
      await expect(
        p
          .getByRole("region", { name: "Overview" })
          .getByText("Student ratings"),
      ).toBeVisible();
    },
  },
  {
    name: "forum",
    run: async (p) => {
      await logIn(p);
      await p.goto(FORUM);
      await h1(p, /with Fake Instructor A/);
      await expect(
        p.getByRole("article", { name: "Review by Fake Heron" }),
      ).toBeVisible();
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
  {
    name: "instructors",
    run: async (p) => (await p.goto("/instructors"), h1(p, "Forum")),
  },
  {
    name: "instructor",
    run: async (p) => {
      await logIn(p);
      await p.goto("/instructors/fake-instructor-a");
      await h1(p, "Fake Instructor A");
    },
  },
  {
    name: "programs",
    run: async (p) => (await p.goto("/programs"), h1(p, "Program explorer")),
  },
  {
    name: "program",
    run: async (p) => (
      await p.goto("/programs/fake-major"),
      h1(p, "Fake Program")
    ),
  },
  {
    name: "signup",
    run: async (p) => (await p.goto("/signup"), h1(p, "Create an account")),
  },
  {
    name: "login",
    run: async (p) => (await p.goto("/login"), h1(p, "Welcome back")),
  },
  {
    name: "account",
    run: async (p) => {
      await logIn(p);
      await p.goto("/account");
      await h1(p, "Account");
      await expect(p.getByRole("link", { name: "fake-user" })).toBeVisible();
    },
  },
  {
    name: "guidelines",
    run: async (p) => (
      await p.goto("/guidelines"),
      h1(p, "Community guidelines")
    ),
  },
  {
    name: "privacy",
    run: async (p) => (await p.goto("/privacy"), h1(p, "Privacy")),
  },
  { name: "about", run: async (p) => (await p.goto("/about"), h1(p, "About")) },
  {
    name: "admin-moderation",
    run: async (p) => {
      await logIn(p, true);
      await p.goto("/admin/moderation");
      await h1(p, "Moderation queue");
      await expect(
        p.getByRole("article", { name: /discussion on TEST 10000/ }),
      ).toBeVisible();
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
  {
    name: "not-found",
    run: async (p) => (await p.goto("/no-such-page"), h1(p, "Page not found")),
  },
];

for (const size of WIDTHS) {
  test.describe(`screenshots at ${size.width}px`, () => {
    test.skip(
      !process.env.SCREENSHOTS,
      "set SCREENSHOTS=1 (make screenshots) to write docs/screenshots",
    );
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
