import { expect, test, type Page } from "@playwright/test";
import {
  addCourseViaTree,
  addProgram,
  card,
  closePanel,
  graduation,
  logIn,
  openAdvisor,
  openPanel,
  setGraduation,
  settle,
} from "./helpers";

// Richard's FEEDBACK items F2-F6 (docs/FEEDBACK.md, 2026-11-14), against the MSW mocks
// (catalog year 2099-00: a first-year enters in Autumn 2099).

const quarterIds = (page: Page, year: number) =>
  page
    .getByTestId(`year-${year}`)
    .locator('[data-testid^="quarter-"]')
    .evaluateAll((els) => els.map((e) => e.getAttribute("data-testid")));

/** A second-year transfer student's plan, set up from the student record (Issue #16 replaced
 * the onboarding wizard), no generated plan. */
async function transferPlan(page: Page) {
  await logIn(page);
  await page.evaluate(async () => {
    await fetch("/api/me/profile", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ entry_term: "2099-AU", entry_year_level: 2, intended_programs: ["fake-major"] }),
    });
  });
  await page.goto("/plan");
  const setup = page.getByRole("region", { name: "Set up a plan from your information" });
  await expect(setup.getByText("3, graduating in Spring 2102")).toBeVisible();
  await setup.getByRole("checkbox", { name: "Generate a starting plan" }).uncheck();
  await setup.getByRole("button", { name: "Set up my plan" }).click();
  await expect(page.getByRole("list", { name: "Programs on this plan" })).toContainText("Fake Program");
}

test.describe("F2: Summer opens the academic year", () => {
  test("each year shows Summer first; a summer course before the first autumn is in the first year; no summer after the last spring", async ({
    page,
  }) => {
    await page.goto("/plan");
    await page.getByRole("button", { name: "Show Summer" }).click();
    expect(await quarterIds(page, 1)).toEqual([
      "quarter-2099-SU",
      "quarter-2099-AU",
      "quarter-2100-WI",
      "quarter-2100-SP",
    ]);
    expect(await quarterIds(page, 4)).toEqual([
      "quarter-2102-SU",
      "quarter-2102-AU",
      "quarter-2103-WI",
      "quarter-2103-SP",
    ]);
    await expect(
      page.getByRole("heading", { name: "First year 2099–00" }),
    ).toBeVisible();
    // Nothing follows the last Spring.
    await expect(page.getByTestId("quarter-2103-SU")).toHaveCount(0);

    await addProgram(page, "Fake Program");
    await addCourseViaTree(
      page,
      /^Fake introductory sequence/,
      "TEST 10000",
      "Summer 2099",
    );
    await expect(
      page.getByTestId("year-1").getByTestId("quarter-2099-SU"),
    ).toContainText("TEST 10000");
    await expect(page.getByRole("region", { name: "Other terms" })).toHaveCount(
      0,
    );

    // Hidden Summer still says what it holds.
    await page.getByRole("button", { name: "Hide Summer" }).click();
    await expect(
      page.getByRole("heading", {
        name: /First year 2099–00 · Summer 2099: 1 course \(hidden\)/,
      }),
    ).toBeVisible();
  });
});

test.describe("F3: number of years and the graduation quarter", () => {
  test("a second-year transfer gets three years; add and remove a year", async ({
    page,
  }) => {
    await transferPlan(page);
    await expect(page.getByRole("heading", { name: "My Plan" })).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "Second year 2099–00" }),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "Fourth year 2101–02" }),
    ).toBeVisible();
    await expect(page.getByTestId("year-4")).toHaveCount(0);
    await expect(graduation(page)).toHaveAttribute("data-term", "2102-SP");

    await page.getByRole("button", { name: "Add a year" }).click();
    await expect(page.getByTestId("year-4")).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "Fifth year 2102–03" }),
    ).toBeVisible();
    await expect(graduation(page)).toHaveAttribute("data-term", "2103-SP");
    await page.getByRole("button", { name: "Remove last year" }).click();
    await expect(page.getByTestId("year-4")).toHaveCount(0);

    // A year with courses is not removed.
    await addProgram(page, "Fake Program");
    await addCourseViaTree(
      page,
      /^Fake introductory sequence/,
      "TEST 10000",
      "Autumn 2101",
    );
    await closePanel(page);
    await page.getByRole("button", { name: "Remove last year" }).click();
    await expect(
      page.getByText(
        "Your fourth year has courses. Move or remove them first.",
      ),
    ).toBeVisible();
    await expect(page.getByTestId("year-3")).toBeVisible();

    // The choice is kept with the plan.
    await page.reload();
    await expect(page.getByTestId("year-3")).toBeVisible();
    await expect(page.getByTestId("year-4")).toHaveCount(0);
  });

  test("graduating in Winter hides the last Spring; its courses move to Other terms", async ({
    page,
  }) => {
    await page.goto("/plan");
    await addProgram(page, "Fake Program");
    await addCourseViaTree(
      page,
      /^Fake introductory sequence/,
      "TEST 10000",
      "Spring 2103",
    );
    await closePanel(page);
    await setGraduation(page, "2103-WI");
    await expect(page.getByTestId("quarter-2103-SP")).toHaveCount(0);
    await expect(page.getByTestId("quarter-2103-WI")).toBeVisible();
    await expect(
      page.getByRole("region", { name: "Other terms" }),
    ).toContainText("TEST 10000");
    // The quarter pickers end at Winter too.
    await page.getByRole("button", { name: "Actions for TEST 10000" }).click();
    await page.getByRole("menuitem", { name: "Move to…" }).click();
    const picker = page.getByRole("dialog", { name: "Move TEST 10000 to…" });
    await expect(
      picker.getByRole("button", { name: "Winter 2103" }),
    ).toBeVisible();
    await expect(
      picker.getByRole("button", { name: "Spring 2103" }),
    ).toHaveCount(0);
  });

  test("a plan saved with the old five-year setting opens with five years", async ({
    page,
  }) => {
    await page.goto("/plans");
    await page.evaluate(() => {
      const state = {
        catalog_year: "2099-00",
        entry_term: "2099-AU",
        entry_year_level: 1,
        items: [],
        credits: [],
        programs: [],
        goals: [],
        placements: [],
        overload_reasons: {},
      };
      localStorage.setItem(
        "quarterly.plans.v1",
        JSON.stringify({
          version: 1,
          activeId: "old",
          plans: [
            {
              localId: "old",
              name: "Old plan",
              isPrimary: true,
              state,
              updatedDay: "2099-01-01",
              years: 5,
            },
          ],
        }),
      );
    });
    await page.goto("/plan");
    await expect(page.getByTestId("year-5")).toBeVisible();
    await expect(graduation(page)).toHaveAttribute("data-term", "2104-SP");
  });
});

test.describe("F4: planner layout", () => {
  test("the drawer holds the requirement tree: bold code, small name; courses drag from it onto the grid", async ({
    page,
  }) => {
    await page.goto("/plan");
    await addProgram(page, "Fake Program");
    await openPanel(page, "Requirements");
    const drawer = page.getByRole("region", { name: "Plan panel" });
    await expect(
      drawer.getByRole("tab", { name: "Requirements", selected: true }),
    ).toBeVisible();
    // Program -> node -> courses.
    await expect(
      drawer.getByRole("heading", { name: /Fake Program/, level: 3 }),
    ).toBeVisible();
    await drawer
      .getByRole("button", { name: /^Fake introductory sequence/ })
      .click();
    const course = drawer.getByTestId("tree-course").first();
    await expect(course).toContainText("TEST 10000");
    const [code, name] = await course.evaluate((li) => {
      const [c, n] = li.querySelectorAll<HTMLElement>(".min-w-0 > div");
      return [c, n].map((el) =>
        el
          ? {
              text: el.textContent,
              weight: Number(getComputedStyle(el).fontWeight),
              size: getComputedStyle(el).fontSize,
            }
          : null,
      );
    });
    expect(code?.text).toBe("TEST 10000");
    expect(code?.weight).toBeGreaterThanOrEqual(600);
    expect(name?.text).toBe("Fake Introduction I");
    expect(name?.size).toBe("15px"); // the caption size of the redesign's bigger type
    await expect(
      drawer.getByRole("button", { name: /^Fake introductory sequence/ }),
    ).toContainText("0 of 3");

    // The grid stays usable beside the open drawer: drag a course from the tree to a quarter.
    const handle = drawer.getByRole("button", {
      name: "Drag TEST 10000 onto the plan",
    });
    const target = page.getByTestId("quarter-2100-WI");
    // A pointer drag can miss when the machine is busy (OPEN_QUESTIONS E2E-1): up to three
    // attempts, each measured after the drag starts; the course must land in the end.
    for (let attempt = 0; attempt < 3; attempt += 1) {
      const from = await handle.boundingBox();
      if (!from) throw new Error("no handle box");
      await page.mouse.move(from.x + from.width / 2, from.y + from.height / 2);
      await page.mouse.down();
      await page.mouse.move(from.x - 20, from.y + 10, { steps: 8 });
      await page.waitForTimeout(150); // let the drag overlay mount before aiming
      const to = await target.boundingBox();
      if (!to) throw new Error("no target box");
      await page.mouse.move(to.x + to.width / 2, to.y + to.height / 2, {
        steps: 16,
      });
      await page.mouse.move(to.x + to.width / 2 + 2, to.y + to.height / 2 + 2, {
        steps: 2,
      });
      await page.mouse.up();
      if (await target.getByTestId("course-card").count()) break;
    }
    await expect(target).toContainText("TEST 10000");
    await expect(drawer).toBeVisible();
  });

  test("errors stay subtle until Check plan opens the issues", async ({
    page,
  }) => {
    await page.goto("/plan");
    await addProgram(page, "Fake Program");
    await addCourseViaTree(
      page,
      /^Fake introductory sequence/,
      "TEST 10100",
      "Autumn 2099",
    );
    await closePanel(page);
    // No issue list or error banner on the page; only a small count on the button.
    await expect(
      page.getByRole("list", { name: "Verifier issues" }),
    ).toBeHidden();
    const check = page.getByRole("button", {
      name: /^Check plan \(\d+ errors?\)$/,
    });
    await expect(check).toBeVisible();
    await check.click();
    const issues = page.getByRole("list", { name: "Verifier issues" });
    await expect(issues).toBeVisible();
    await expect(issues).toContainText("Prerequisite of TEST 10100 not met.");
    await expect(page.getByTestId("verifier-badge")).toContainText("error");
  });

  test("Ask Quarterly opens from the top, says it is AI, and reads as a chat", async ({
    page,
  }) => {
    await page.goto("/plan");
    const sheet = await openAdvisor(page);
    await sheet.evaluate((el) =>
      Promise.all(el.getAnimations().map((a) => a.finished)),
    );
    const box = await sheet.boundingBox();
    expect(Math.round(box?.y ?? -1)).toBe(0);
    // FEEDBACK 2026-11-16: "Ask Quarterly", without the grey "Generative AI" badge.
    await expect(
      sheet.getByRole("heading", { name: "Ask Quarterly" }),
    ).toBeVisible();
    await expect(sheet.getByText("Generative AI", { exact: true })).toHaveCount(
      0,
    );
    await expect(
      sheet.getByText("Answers are written by an AI and can be wrong."),
    ).toBeVisible();
    await expect(sheet.getByLabel("Ask the advisor")).toBeFocused();
    await sheet.getByLabel("Ask the advisor").fill("Is TEST 20000 hard?");
    await sheet.getByLabel("Ask the advisor").press("Enter");
    await expect(sheet.getByTestId("chat-bubble-user")).toHaveText(
      "You: Is TEST 20000 hard?",
    );
    await expect(sheet.getByTestId("chat-bubble-ai").first()).toBeVisible();
    // The student's bubble sits on the right, the AI's on the left beside its avatar.
    await settle(page);
    const user = await sheet.getByTestId("chat-bubble-user").boundingBox();
    const ai = await sheet.getByTestId("chat-bubble-ai").first().boundingBox();
    expect(user && ai && user.x + user.width > ai.x + ai.width - 1).toBe(true);
    expect(ai?.x, JSON.stringify({ user, ai })).toBeLessThan(user?.x ?? 0);
    await sheet.getByRole("button", { name: "Close" }).click();
    await expect(sheet).toBeHidden();
    await expect(
      page.getByRole("button", { name: "Ask Quarterly" }),
    ).toBeFocused();
  });
});

test.describe("F5: text", () => {
  test("filler lines are gone; the legal lines stay", async ({ page }) => {
    await page.goto("/plan");
    await expect(
      page.getByText(
        "Not official advising. Confirm with your adviser and My Planner.",
      ),
    ).toBeVisible();
    await expect(page.getByRole("contentinfo")).toContainText(
      "Quarterly is a student project, not affiliated with the University of Chicago.",
    );
    await page.getByRole("button", { name: "Generate plan" }).click();
    await expect(
      page.getByRole("dialog", { name: "Generate plan" }),
    ).toBeVisible();
    await expect(page.getByText("A form, not a prompt")).toHaveCount(0);
    await page.keyboard.press("Escape");
    await page.getByRole("button", { name: "+ Program" }).click();
    await page
      .getByRole("dialog", { name: "Programs" })
      .getByRole("checkbox", { name: "Fake Program" })
      .check();
    await page
      .getByRole("dialog", { name: "Programs" })
      .getByRole("button", { name: "Save programs" })
      .click();
    await openPanel(page, "Requirements");
    await page
      .getByTestId("plan-drawer")
      .getByRole("button", { name: /^Fake introductory sequence/ })
      .click();
    await page
      .getByRole("button", { name: "Add TEST 10000 to a quarter" })
      .click();
    await expect(
      page.getByRole("dialog", { name: "Add TEST 10000 to…" }),
    ).not.toContainText("Choose a quarter.");
    await page.keyboard.press("Escape");

    await page.goto("/courses");
    await expect(
      page.getByRole("heading", { level: 1, name: "Catalog" }),
    ).toBeVisible();
    await expect(
      page.getByText("Filter by department, level, quarter"),
    ).toHaveCount(0);
    await page.goto("/programs");
    await expect(
      page.getByRole("heading", { level: 1, name: "Program explorer" }),
    ).toBeVisible();
    await expect(page.getByText("Every major, minor")).toHaveCount(0);
    await page.goto("/instructors");
    await expect(
      page.getByText("Find an instructor to see the courses they teach."),
    ).toHaveCount(0);
    await expect(page.getByText("Plan four years of courses")).toHaveCount(0);
  });
});

test.describe("F6: motion", () => {
  test("the drawer and the advisor animate in", async ({ page }) => {
    await page.emulateMedia({ reducedMotion: "no-preference" });
    await page.goto("/plan");
    await page
      .getByRole("button", { name: "Requirements", exact: true })
      .click();
    await expect(page.getByTestId("plan-drawer")).toHaveCSS(
      "animation-name",
      "drawer-in",
    );
    await page.getByRole("button", { name: "Ask Quarterly" }).click();
    await expect(page.getByTestId("top-sheet")).toHaveCSS(
      "animation-name",
      "sheet-in",
    );
  });

  test("with reduced motion, nothing animates", async ({ page }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto("/plan");
    await addProgram(page, "Fake Program");
    await addCourseViaTree(
      page,
      /^Fake introductory sequence/,
      "TEST 10000",
      "Autumn 2099",
    );
    await expect(page.getByTestId("plan-drawer")).toHaveCSS(
      "animation-name",
      "none",
    );
    await expect(card(page, "TEST 10000")).toHaveCSS("animation-name", "none");
    const sheet = await openAdvisor(page);
    await expect(page.getByTestId("top-sheet")).toHaveCSS(
      "animation-name",
      "none",
    );
    // No animation is running anywhere on the page.
    expect(await page.evaluate(() => document.getAnimations().length)).toBe(0);
    // Closing is immediate (no exit animation to wait for).
    await sheet.getByRole("button", { name: "Close" }).click();
    await expect(page.getByTestId("top-sheet")).toBeHidden({ timeout: 100 });
  });
});
