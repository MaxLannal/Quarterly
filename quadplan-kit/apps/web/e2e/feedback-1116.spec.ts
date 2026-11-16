import { mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { expect, test, type Page } from "@playwright/test";
import { addCourseViaTree, addProgram, card, closePanel, settle } from "./helpers";

// Richard's FEEDBACK of 2026-11-16. With SCREENSHOTS=1 the proof screenshots are written to
// docs/screenshots/fb1116-<name>.png (a normal `make e2e` writes no files).

const OUT = resolve(dirname(fileURLToPath(import.meta.url)), "../../../docs/screenshots");

async function shot(page: Page, name: string) {
  if (!process.env.SCREENSHOTS) return;
  mkdirSync(OUT, { recursive: true });
  await settle(page);
  await page.screenshot({ path: `${OUT}/fb1116-${name}.png`, fullPage: false });
}

test.use({ viewport: { width: 1440, height: 900 } });

test("minor issues: the heading is the plan's name, renamed with the pencil; Ask Quarterly", async ({ page }) => {
  await page.goto("/plan");
  await expect(page.getByRole("heading", { level: 2, name: "My Plan" })).toBeVisible();
  // The old plan-name field at the top is gone.
  await expect(page.getByLabel("Plan name")).toHaveCount(0);
  await page.getByRole("button", { name: "Rename plan" }).click();
  const field = page.getByLabel("Plan name");
  await expect(field).toBeFocused();
  await field.fill("Econ and CS");
  await field.press("Enter");
  await expect(page.getByRole("heading", { level: 2, name: "Econ and CS" })).toBeVisible();
  // Escape keeps the old name.
  await page.getByRole("button", { name: "Rename plan" }).click();
  await page.getByLabel("Plan name").fill("Discarded");
  await page.getByLabel("Plan name").press("Escape");
  await expect(page.getByRole("heading", { level: 2, name: "Econ and CS" })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("heading", { level: 2, name: "Econ and CS" })).toBeVisible();

  await expect(page.getByRole("button", { name: "AI advisor" })).toHaveCount(0);
  await page.getByRole("button", { name: "Ask Quarterly" }).click();
  const sheet = page.getByRole("dialog", { name: "Ask Quarterly" });
  await expect(sheet.getByText("Generative AI", { exact: true })).toHaveCount(0);
  await expect(sheet.getByText("Answers are written by an AI and can be wrong.")).toBeVisible();
  await shot(page, "ask-quarterly");
});

test("credits: see, edit, remove and add test, placement and transfer credits in the planner", async ({ page }) => {
  await page.goto("/plan");
  await page.getByRole("button", { name: "Credits", exact: true }).click();
  const drawer = page.getByTestId("plan-drawer");
  await expect(drawer.getByRole("heading", { name: "Test, placement and transfer credits" })).toBeVisible();
  await expect(drawer.getByText("No credits yet.")).toBeVisible();

  const add = drawer.getByRole("form", { name: "Add a credit" });
  await add.getByLabel("Kind").selectOption("AP");
  await add.getByLabel("Description").fill("AP Calculus BC, score 5");
  await add.getByLabel("Counts as course (if known)").fill("NOPE 10000");
  await add.getByRole("button", { name: "Add credit" }).click();
  await expect(add.getByRole("alert")).toHaveText("NOPE 10000 is not in the 2099-00 catalog. Leave this empty if you are not sure.");
  await add.getByLabel("Counts as course (if known)").fill("TEST 10000");
  await add.getByRole("button", { name: "Add credit" }).click();
  const list = drawer.getByRole("list", { name: "Your credits" });
  await expect(list).toContainText("AP: AP Calculus BC, score 5 → TEST 10000 · 100 units");
  // The toolbar button shows how many credits there are.
  await expect(page.getByRole("button", { name: "Credits 1" })).toBeVisible();

  await add.getByLabel("Kind").selectOption("transfer");
  await add.getByLabel("Description").fill("Community college statistics");
  await add.getByRole("button", { name: "Add credit" }).click();
  await expect(list).toContainText("transfer: Community college statistics (needs mapping) · 100 units");

  await list.getByRole("button", { name: "Edit credit Community college statistics" }).click();
  const edit = drawer.getByRole("form", { name: "Edit credit Community college statistics" });
  await edit.getByLabel("Units").fill("50");
  await edit.getByRole("button", { name: "Save credit" }).click();
  await expect(list).toContainText("transfer: Community college statistics (needs mapping) · 50 units");
  await shot(page, "credits");

  await list.getByRole("button", { name: "Remove credit Community college statistics" }).click();
  await expect(list).not.toContainText("Community college statistics");
  // Kept with the plan.
  await page.reload();
  await page.getByRole("button", { name: /^Credits/ }).click();
  await expect(page.getByTestId("plan-drawer").getByRole("list", { name: "Your credits" })).toContainText("AP Calculus BC, score 5");
});

test("short issues: a card says 'Prerequisite not met' and links to the prerequisites", async ({ page }) => {
  await page.goto("/plan");
  await addProgram(page, "Fake Program");
  await addCourseViaTree(page, /^Fake introductory sequence/, "TEST 10100", "Autumn 2099");
  await closePanel(page);
  const c = card(page, "TEST 10100");
  await expect(c).toContainText("Prerequisite not met.");
  await expect(c).not.toContainText("Requirement:");
  await shot(page, "planner-compact");
  await c.getByRole("link", { name: "View prerequisite" }).click();
  await expect(page).toHaveURL(/\/courses\/TEST%2010100#prereq$/);
  await expect(page.getByRole("heading", { level: 2, name: "Prerequisites" })).toBeInViewport();
});

test("course page: overview under the title; the prerequisite graph opens in a window", async ({ page }) => {
  await page.goto("/courses/TEST%2020000");
  const overview = page.getByRole("region", { name: "Overview" });
  await expect(overview.getByText("Student ratings")).toBeVisible();
  await expect(overview.getByRole("list", { name: "Instructors" })).toContainText("Fake Instructor A");
  // The overview sits between the title and the prerequisites.
  const overviewBox = await overview.boundingBox();
  const prereqBox = await page.getByRole("heading", { level: 2, name: "Prerequisites" }).boundingBox();
  expect((overviewBox?.y ?? 0) < (prereqBox?.y ?? 0)).toBe(true);
  await shot(page, "course-overview");
  await page.getByRole("button", { name: "View prerequisite graph" }).click();
  await expect(page.getByRole("dialog", { name: "Prerequisite graph: TEST 20000" }).getByRole("figure", { name: "Prerequisite graph" })).toBeVisible();
  await shot(page, "prereq-graph");
});
