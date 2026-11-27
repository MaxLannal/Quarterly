import { expect, type Page } from "@playwright/test";

// Shared planner steps for the e2e specs (MSW mocks: catalog year 2099-00, TEST/FAKE courses).

export function card(page: Page, code: string) {
  return page.locator(`[data-testid="course-card"][data-course="${code}"]`);
}

/** Toolbar button for a drawer tab ("Requirements", "Goals", or "Check plan"). */
function panelButton(
  page: Page,
  name: "Requirements" | "Goals" | "Check plan",
) {
  return page.getByRole("button", {
    name: name === "Check plan" ? /^Check plan/ : name,
    exact: name !== "Check plan",
  });
}

/** Opens the right-hand drawer at a tab (no-op when that tab is already showing). */
export async function openPanel(
  page: Page,
  name: "Requirements" | "Goals" | "Check plan",
) {
  const drawer = page.getByTestId("plan-drawer");
  if (await drawer.isVisible()) {
    // Already open (on a phone it covers the toolbar): switch tabs inside it.
    await drawer
      .getByRole("tab", { name })
      .click();
  } else {
    await panelButton(page, name).click();
  }
  await expect(drawer).toBeVisible();
}

export async function closePanel(page: Page) {
  const drawer = page.getByTestId("plan-drawer");
  if (await drawer.isVisible()) {
    await drawer.getByRole("button", { name: "Close panel" }).click();
    await expect(drawer).toBeHidden();
  }
}

export async function addProgram(page: Page, name: string) {
  await page.getByRole("button", { name: "+ Program" }).click();
  const dialog = page.getByRole("dialog", { name: "Programs" });
  await dialog.getByRole("checkbox", { name }).check();
  await dialog.getByRole("button", { name: "Save programs" }).click();
  await expect(dialog).toBeHidden();
}

/** Keyboard path: requirement tree node -> course "Add" -> quarter picker. Leaves the drawer open. */
export async function addCourseViaTree(
  page: Page,
  node: RegExp,
  code: string,
  term: string,
) {
  await openPanel(page, "Requirements");
  const nodeButton = page
    .getByTestId("plan-drawer")
    .getByRole("button", { name: node });
  if ((await nodeButton.getAttribute("aria-expanded")) !== "true")
    await nodeButton.click();
  await page.getByRole("button", { name: `Add ${code} to a quarter` }).click();
  await page
    .getByRole("dialog", { name: `Add ${code} to…` })
    .getByRole("button", { name: term, exact: true })
    .click();
  await expect(card(page, code).first()).toBeAttached();
}

/** A planner with Fake Program and two courses in Autumn 2099 (TEST 10100 has a prerequisite issue). */
export async function plannerWithCourses(page: Page) {
  await page.goto("/plan");
  await addProgram(page, "Fake Program");
  for (const code of ["TEST 10000", "TEST 10100"])
    await addCourseViaTree(
      page,
      /^Fake introductory sequence/,
      code,
      "Autumn 2099",
    );
  await expect(card(page, "TEST 10100")).toContainText("Prerequisite not met.");
}

/** Opens the planner panel (issue #18): beside the grid on a wide screen, a sheet on a phone. */
export async function openAdvisor(page: Page) {
  await page.getByRole("button", { name: "Ask Quarterly" }).click();
  const panel = page.getByRole("complementary", { name: "Planner panel" }).or(page.getByRole("dialog", { name: "Ask Quarterly" }));
  await expect(panel).toBeVisible();
  return panel;
}

/** Generate plan, then answer the planner's question about interests (the mock asks it). */
export async function generatePlan(page: Page, interest = "machine learning") {
  await page.getByRole("button", { name: "Generate plan" }).click();
  const panel = page.getByRole("complementary", { name: "Planner panel" }).or(page.getByRole("dialog", { name: "Ask Quarterly" }));
  const question = panel.getByTestId("planner-question");
  await question.getByLabel("Your answer").fill(interest);
  await question.getByRole("button", { name: "Send" }).click();
  await expect(panel.getByTestId("walkthrough")).toBeVisible();
  return panel;
}

export async function logIn(page: Page, admin = false) {
  await page.goto("/guidelines");
  await expect(
    page.getByRole("heading", { level: 1, name: "Community guidelines" }),
  ).toBeVisible();
  await page.evaluate(async (asAdmin) => {
    if (asAdmin) sessionStorage.setItem("quarterly.mock.admin", "1");
    await fetch("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ login: "fake-user", password: "x" }),
    });
  }, admin);
}

/** Waits until every finite animation on the page has finished (axe and size checks read final styles). */
export async function settle(page: Page) {
  await page.evaluate(() =>
    Promise.all(
      document
        .getAnimations()
        .filter((a) =>
          Number.isFinite(Number(a.effect?.getComputedTiming().endTime)),
        )
        .map((a) => a.finished.catch(() => undefined)),
    ),
  );
}

/** The planner's graduation quarter (D8: shown as text; the pencil opens the list). */
export const graduation = (page: Page) => page.getByTestId("graduation");

export async function setGraduation(page: Page, term: string) {
  await page
    .getByRole("button", { name: /^Change graduation quarter/ })
    .click();
  await page.getByLabel("Graduating in").selectOption(term);
  await expect(graduation(page)).toHaveAttribute("data-term", term);
}
