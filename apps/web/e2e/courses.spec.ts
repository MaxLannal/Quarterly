import { expect, test } from "@playwright/test";
import { logIn } from "./helpers";

test("the Catalog shows browse rows until a search; one centered field (issue #19)", async ({ page }) => {
  await page.goto("/courses");
  await expect(page.getByRole("heading", { level: 1, name: "Catalog" })).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Courses or programs" }).getByRole("link", { name: "Courses" })).toHaveAttribute("aria-current", "page");
  await expect(page.getByRole("region", { name: "Results" })).toHaveCount(0);
  // Before a search: new courses, spotlights from the old Feed, and what students say.
  const fresh = page.getByRole("region", { name: "Newly released courses" });
  await expect(fresh.getByRole("link", { name: /Fake Introduction II/ })).toHaveAttribute("href", "/courses/TEST%2010100");
  await fresh.getByText("Why it is new").click();
  await expect(fresh.getByText("Fake quote: TEST 10100 is new this year.")).toBeVisible();
  await expect(fresh.getByRole("link", { name: "Source" })).toHaveAttribute("href", "https://example.invalid/fake-new-courses");
  const spotlights = page.getByRole("region", { name: "Course spotlights" });
  await expect(spotlights.getByRole("link", { name: "Fake Introduction I", exact: true })).toHaveAttribute("href", "/courses/TEST%2010000");
  await expect(page.getByRole("region", { name: "What students say" }).getByText(/first course in Autumn/)).toBeVisible();
  await expect(page.getByText("to see student ratings.")).toBeVisible(); // logged out: no ratings
  await expect(page.getByLabel("Quarter offered")).toBeHidden(); // folded under "More filters"
  await page.getByLabel("Code or title").fill("Fake Elective");
  await page.getByRole("form", { name: "Course filters" }).getByRole("button", { name: "Search", exact: true }).click();
  await expect(page.getByRole("status").filter({ hasText: "3 courses" })).toBeVisible();
  // The switch goes to programs; the menu's one "Catalog" item stays current.
  await page.getByRole("navigation", { name: "Courses or programs" }).getByRole("link", { name: "Programs" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Program explorer" })).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Catalog" })).toHaveAttribute("aria-current", "page");
});

test("course search: header search, filters, results", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("searchbox", { name: "Search courses", exact: true }).fill("Fake Elective");
  await page.getByRole("button", { name: "Search", exact: true }).first().click();
  await expect(page).toHaveURL(/\/courses\?q=Fake%20Elective/);
  await expect(page.getByRole("heading", { level: 1, name: "Catalog" })).toBeVisible();
  await expect(page.getByRole("status").filter({ hasText: "3 courses" })).toBeVisible();

  // FEEDBACK 2026-11-16: the extra filters sit under "More filters".
  await page.getByText("More filters").click();
  await page.getByLabel("Quarter offered").selectOption("WI");
  await page.getByRole("button", { name: "Apply filters" }).click();
  await expect(page.getByRole("status").filter({ hasText: "1 course" })).toBeVisible();
  await page.getByRole("link", { name: "TEST 25100 · Fake Elective in Networks" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "TEST 25100 · Fake Elective in Networks" })).toBeVisible();
});

test("course page: prerequisites graph, offerings, attributes, add to plan", async ({ page }) => {
  await page.goto("/courses/TEST%2020000");
  await expect(page.getByRole("heading", { level: 1, name: "TEST 20000 · Fake Theory" })).toBeVisible();
  // FEEDBACK 2026-11-16: the graph opens in a window from "View prerequisite graph".
  await expect(page.getByRole("figure", { name: "Prerequisite graph" })).toHaveCount(0);
  await page.getByRole("button", { name: "View prerequisite graph" }).click();
  const graphDialog = page.getByRole("dialog", { name: "Prerequisite graph: TEST 20000" });
  const graph = graphDialog.getByRole("figure", { name: "Prerequisite graph" });
  await expect(graph.getByRole("link", { name: "TEST 10200" })).toBeVisible();
  await expect(graph.getByRole("link", { name: "TEST 25000" })).toBeVisible();
  await graphDialog.getByRole("button", { name: /Close/ }).first().click();
  await expect(graphDialog).toHaveCount(0);
  await expect(page.getByRole("table", { name: "Predicted quarters" })).toContainText("Likely (95%)");
  await expect(page.getByRole("table", { name: "Offerings by term" })).toContainText("Fake Instructor A");
  await expect(page.getByText("From 12 forum ratings").first()).toBeVisible();
  await expect(page.getByRole("link", { name: "Fake Program" })).toBeVisible();

  await page.getByRole("button", { name: "Add to plan" }).click();
  await page.getByRole("dialog", { name: "Add TEST 20000 to…" }).getByRole("button", { name: "Winter 2101" }).click();
  await expect(page.getByText("Added TEST 20000 to Winter 2101.")).toBeVisible();
  await page.getByRole("link", { name: "Open the planner" }).click();
  await expect(page.getByTestId("quarter-2101-WI")).toContainText("TEST 20000");

  await page.goto("/courses/TEST%2099999");
  await expect(page.getByRole("heading", { level: 1, name: "Course not found" })).toBeVisible();
});

test("a logged-in student sees ratings on the rows and the results (issue #19)", async ({ page }) => {
  await logIn(page);
  await page.goto("/courses");
  const spotlights = page.getByRole("region", { name: "Course spotlights" });
  await expect(spotlights.getByText("4.2 / 5", { exact: true }).first()).toBeVisible();
  await expect(page.getByRole("region", { name: "What students say" }).getByText(/hard but fair/)).toBeVisible();
  await page.getByLabel("Code or title").fill("Fake Introduction");
  await page.getByRole("form", { name: "Course filters" }).getByRole("button", { name: "Search", exact: true }).click();
  const results = page.getByRole("region", { name: "Results" });
  await expect(results.getByText("4.2 / 5", { exact: true }).first()).toBeVisible();
  await expect(page.getByRole("region", { name: "Course spotlights" })).toHaveCount(0);
});

test("the old Feed opens the Catalog, and the homepage button says so (issue #19)", async ({ page }) => {
  await page.goto("/feed");
  await expect(page).toHaveURL(/\/courses$/);
  await expect(page.getByRole("heading", { level: 1, name: "Catalog" })).toBeVisible();
  await page.goto("/");
  await page.getByRole("link", { name: "Explore the catalog" }).click();
  await expect(page).toHaveURL(/\/courses$/);
});
