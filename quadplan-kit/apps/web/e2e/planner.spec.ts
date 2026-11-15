import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { addCourseViaTree, addProgram, card, closePanel, openAdvisor, openPanel, settle } from "./helpers";

// Runs against MSW mocks (fake catalog year 2099-00, TEST/FAKE courses, "Fake Program").

test("planner: build, verify, move, lock, highlight", async ({ page }) => {
  await page.goto("/plan");
  await expect(page.getByRole("heading", { level: 1, name: "Planner" })).toBeAttached();
  await expect(page.getByRole("heading", { name: "First year 2099–00" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Check plan", exact: true })).toBeVisible();

  await addProgram(page, "Fake Program");
  await openPanel(page, "Requirements");
  await expect(page.getByRole("heading", { name: "Fake Program", level: 3 })).toBeVisible();
  // Errors stay subtle: a small count on the toolbar button, not a banner.
  await expect(page.getByRole("button", { name: "Check plan (3 errors)" })).toBeVisible();

  // Keyboard path: requirement node -> course -> "Add to…" quarter picker.
  await addCourseViaTree(page, /^Fake introductory sequence/, "TEST 10000", "Autumn 2099");
  await addCourseViaTree(page, /^Fake introductory sequence/, "TEST 10100", "Autumn 2099");
  await expect(card(page, "TEST 10000")).toContainText("Fake Introduction I");
  await expect(card(page, "TEST 10000")).toContainText("Fake Program · Fake introductory sequence");
  // TEST 10100 needs TEST 10000 earlier: the verifier notes it on the card.
  await expect(card(page, "TEST 10100")).toContainText("needs TEST 10000 in an earlier quarter");
  await expect(page.getByTestId("footer-2099-AU")).toContainText("200 units");

  // "Move to…" menu fixes it.
  await page.getByRole("button", { name: "Actions for TEST 10100" }).click();
  await page.getByRole("menuitem", { name: "Move to…" }).click();
  await page.getByRole("dialog", { name: "Move TEST 10100 to…" }).getByRole("button", { name: "Winter 2100" }).click();
  await expect(page.getByTestId("quarter-2100-WI")).toContainText("TEST 10100");
  await expect(card(page, "TEST 10100")).not.toContainText("earlier quarter");

  // Check plan: clicking an issue highlights its cards.
  await addCourseViaTree(page, /^Fake core courses/, "TEST 20000", "Autumn 2099");
  await openPanel(page, "Check plan");
  await expect(page.getByTestId("verifier-badge")).toContainText(/errors?/);
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
  await addCourseViaTree(page, /^Fake introductory sequence/, "TEST 10000", "Winter 2100");
  await closePanel(page);
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

  const sheet = await openAdvisor(page);
  await sheet.getByLabel("Ask the advisor").fill("Please add a lighter elective");
  await sheet.getByRole("button", { name: "Send" }).click();
  await expect(sheet.getByRole("link", { name: "TEST 25200", exact: true })).toBeVisible();
  const proposal = sheet.getByRole("article", { name: "Proposed change" });
  await expect(proposal).toContainText("Add TEST 25200");
  await proposal.getByRole("button", { name: "Apply" }).click();
  await expect(proposal).toContainText("Applied.");
  // The conversation survives closing and reopening the advisor.
  await page.keyboard.press("Escape");
  await expect(sheet).toBeHidden();
  await expect(card(page, "TEST 25200")).toBeVisible();
  await openAdvisor(page);
  await expect(proposal).toContainText("Applied.");
});

test("planner: no axe violations", async ({ page }) => {
  await page.goto("/plan");
  await addProgram(page, "Fake Program");
  await addCourseViaTree(page, /^Fake introductory sequence/, "TEST 10100", "Autumn 2099");
  await expect(card(page, "TEST 10100")).toContainText("earlier quarter");
  await settle(page);
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
  expect(results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`)).toEqual([]);
});

test("on a phone, the panel is full screen and closes back to the grid", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/plan");
  await page.getByRole("button", { name: "Requirements", exact: true }).click();
  const drawer = page.getByRole("dialog", { name: "Plan panel" });
  await expect(drawer).toBeVisible();
  const box = await drawer.boundingBox();
  expect(Math.round(box?.width ?? 0)).toBe(390);
  expect(Math.round(box?.height ?? 0)).toBe(844);
  await page.keyboard.press("Escape");
  await expect(drawer).toBeHidden();
  await expect(page.getByRole("button", { name: "Requirements", exact: true })).toBeFocused();
});
