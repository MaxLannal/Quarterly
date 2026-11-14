import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

// Runs against MSW mocks (fake catalog year 2099-00, TEST/FAKE courses, "Fake Program").

async function addProgram(page: Page, name: string) {
  await page.getByRole("button", { name: "+ Program" }).click();
  const dialog = page.getByRole("dialog", { name: "Programs" });
  await dialog.getByRole("checkbox", { name: name }).check();
  await dialog.getByRole("button", { name: "Save programs" }).click();
  await expect(dialog).toBeHidden();
}

async function addCourseViaRail(page: Page, node: RegExp, code: string, term: string) {
  const nodeButton = page.getByRole("button", { name: node });
  if ((await nodeButton.getAttribute("aria-expanded")) !== "true") await nodeButton.click();
  await page.getByRole("button", { name: `Add ${code} to a quarter` }).click();
  await page.getByRole("dialog", { name: `Add ${code} to…` }).getByRole("button", { name: term, exact: true }).click();
}

function card(page: Page, code: string) {
  return page.locator(`[data-testid="course-card"][data-course="${code}"]`);
}

test("planner: build, verify, move, lock, highlight", async ({ page }) => {
  await page.goto("/plan");
  await expect(page.getByRole("heading", { level: 1, name: "Planner" })).toBeAttached();
  await expect(page.getByRole("heading", { name: "Year 1 (2099–00)" })).toBeVisible();
  await expect(page.getByTestId("verifier-badge")).toHaveText(/Valid/);

  await addProgram(page, "Fake Program");
  await expect(page.getByRole("heading", { name: "Fake Program", level: 3 })).toBeVisible();
  await expect(page.getByTestId("verifier-badge")).toHaveText(/3 errors/);

  // Keyboard path: requirement node -> eligible course -> "Add to…" quarter picker.
  await addCourseViaRail(page, /^Fake introductory sequence/, "TEST 10000", "Autumn 2099");
  await addCourseViaRail(page, /^Fake introductory sequence/, "TEST 10100", "Autumn 2099");
  await expect(card(page, "TEST 10000")).toContainText("Fake Introduction I");
  await expect(card(page, "TEST 10000")).toContainText("Fake Program · Fake introductory sequence");
  // TEST 10100 needs TEST 10000 earlier: the verifier flags the card.
  await expect(card(page, "TEST 10100")).toContainText("needs TEST 10000 in an earlier quarter");
  await expect(page.getByTestId("footer-2099-AU")).toContainText("200 units");

  // "Move to…" menu fixes it.
  await page.getByRole("button", { name: "Actions for TEST 10100" }).click();
  await page.getByRole("menuitem", { name: "Move to…" }).click();
  await page.getByRole("dialog", { name: "Move TEST 10100 to…" }).getByRole("button", { name: "Winter 2100" }).click();
  await expect(page.getByTestId("quarter-2100-WI")).toContainText("TEST 10100");
  await expect(card(page, "TEST 10100")).not.toContainText("earlier quarter");

  // Issues tab: clicking an issue highlights its cards.
  await page.getByRole("tab", { name: /Issues/ }).click();
  await addCourseViaRail(page, /^Fake core courses/, "TEST 20000", "Autumn 2099");
  const issue = page.getByRole("button", { name: /TEST 20000 needs TEST 10200/ });
  await issue.click();
  await expect(issue).toHaveAttribute("aria-pressed", "true");
  await expect(card(page, "TEST 20000")).toHaveAttribute("data-highlighted", "true");

  // Right-click opens the card menu: lock, then removing is disabled.
  await card(page, "TEST 20000").click({ button: "right" });
  await page.getByRole("menuitem", { name: "Lock" }).click();
  await expect(page.getByRole("button", { name: "TEST 20000 is locked" })).toBeVisible();
  await page.getByRole("button", { name: "Actions for TEST 20000" }).click();
  await expect(page.getByRole("menuitem", { name: "Remove" })).toBeDisabled();
  await page.getByRole("menuitem", { name: "Unlock" }).click();
  await page.getByRole("button", { name: "Actions for TEST 20000" }).click();
  await page.getByRole("menuitem", { name: "Remove" }).click();
  await expect(card(page, "TEST 20000")).toHaveCount(0);

  // Mark completed.
  await page.getByRole("button", { name: "Actions for TEST 10000" }).click();
  await page.getByRole("menuitem", { name: "Mark completed" }).click();
  await expect(card(page, "TEST 10000")).toContainText("Completed");

  // The plan survives a reload (localStorage).
  await page.reload();
  await expect(card(page, "TEST 10100")).toBeVisible();
  await expect(page.getByTestId("quarter-2100-WI")).toContainText("TEST 10100");
});

test("planner: drag and drop moves a card", async ({ page }) => {
  await page.goto("/plan");
  await addProgram(page, "Fake Program");
  await addCourseViaRail(page, /^Fake introductory sequence/, "TEST 10000", "Winter 2100");
  const handle = page.getByRole("button", { name: "Drag TEST 10000", exact: true });
  const target = page.getByTestId("quarter-2099-AU");
  const from = await handle.boundingBox();
  const to = await target.boundingBox();
  if (!from || !to) throw new Error("no boxes");
  await page.mouse.move(from.x + from.width / 2, from.y + from.height / 2);
  await page.mouse.down();
  await page.mouse.move(from.x + 20, from.y + 20, { steps: 5 });
  await page.mouse.move(to.x + to.width / 2, to.y + to.height / 2, { steps: 10 });
  await page.mouse.up();
  await expect(target).toContainText("TEST 10000");
});

test("planner: generate popup and advisor proposal", async ({ page }) => {
  await page.goto("/plan");
  await page.getByRole("button", { name: "Generate plan" }).click();
  const dialog = page.getByRole("dialog", { name: "Generate plan" });
  await dialog.getByRole("radio", { name: "Remaining quarters" }).check();
  await dialog.getByLabel("Interest tag").fill("ML");
  await dialog.getByRole("button", { name: "Add", exact: true }).click();
  await dialog.getByRole("button", { name: "Generate" }).click();
  const variant = dialog.getByRole("article", { name: "Variant Fake balanced" });
  await expect(variant).toBeVisible();
  await variant.getByRole("button", { name: "View diff" }).click();
  await expect(variant).toContainText("Add TEST 10000 to Autumn 2099");
  await variant.getByRole("button", { name: "Apply", exact: true }).click();
  await expect(dialog).toBeHidden();
  await expect(card(page, "TEST 10000")).toBeVisible();

  await page.getByRole("tab", { name: "Advisor" }).click();
  await page.getByLabel("Ask the advisor").fill("Please add a lighter elective");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByRole("link", { name: "TEST 25200", exact: true })).toBeVisible();
  const proposal = page.getByRole("article", { name: "Proposed change" });
  await expect(proposal).toContainText("Add TEST 25200");
  await proposal.getByRole("button", { name: "Apply" }).click();
  await expect(proposal).toContainText("Applied.");
  await expect(card(page, "TEST 25200")).toBeVisible();
});

test("planner: no axe violations", async ({ page }) => {
  await page.goto("/plan");
  await addProgram(page, "Fake Program");
  await addCourseViaRail(page, /^Fake introductory sequence/, "TEST 10100", "Autumn 2099");
  await expect(card(page, "TEST 10100")).toContainText("earlier quarter");
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
  expect(results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`)).toEqual([]);
});
