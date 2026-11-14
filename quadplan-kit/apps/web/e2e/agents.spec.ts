import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

// The agent generator and the advisor's typed confirmation, against the MSW agent mocks
// (src/mocks/agents.ts; fake catalog year 2099-00).

test("agents: generated variants show their rationale and sources", async ({ page }) => {
  await page.goto("/plan");
  await page.getByRole("button", { name: "Generate plan" }).click();
  const dialog = page.getByRole("dialog", { name: "Generate plan" });
  await dialog.getByRole("button", { name: "Generate" }).click();
  const variant = dialog.getByRole("article", { name: "Variant Fake balanced" });
  await expect(variant).toContainText("Fake rationale: places TEST 10000 here.");
  await expect(variant.getByRole("list", { name: "Sources for Fake balanced" })).toBeVisible();
  const results = await new AxeBuilder({ page }).include('[role="dialog"]').withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
  expect(results.violations.map((v) => v.id)).toEqual([]);
});

test("agents: typing 'apply it' applies the latest proposal", async ({ page }) => {
  await page.goto("/plan");
  await page.getByRole("tab", { name: "Advisor" }).click();
  const input = page.getByLabel("Ask the advisor");
  await input.fill("Please add a lighter elective");
  await page.getByRole("button", { name: "Send" }).click();
  const proposal = page.getByRole("article", { name: "Proposed change" });
  await expect(proposal).toContainText("I agree to add TEST 25200 to Autumn 2099");
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
  expect(results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`)).toEqual([]);

  await input.fill("apply it");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(proposal).toContainText("Applied.");
  await expect(page.locator('[data-testid="course-card"][data-course="TEST 25200"]')).toBeVisible();

  await input.fill("Tell me a joke");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByText("I can only help with planning your courses.")).toBeVisible();
});
