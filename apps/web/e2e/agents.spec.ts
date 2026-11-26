import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { generatePlan, openAdvisor, settle } from "./helpers";

// The planner agent (issues #17 and #18) against the MSW agent mocks (src/mocks/agents.ts; fake
// catalog year 2099-00): a first plan with its walkthrough, and the chat's typed confirmation.

test("agents: a generated plan is walked through with reasons for this student", async ({ page }) => {
  await page.goto("/plan");
  const panel = await generatePlan(page, "machine learning");
  const walk = panel.getByTestId("walkthrough");
  await expect(walk).toContainText("Step 1 of 3");
  const card = walk.getByRole("article", { name: "Walkthrough: Test introductory sequence" });
  await expect(card).toContainText("You said you are interested in machine learning.");
  await expect(card.getByRole("link", { name: "Your interests" })).toHaveAttribute("href", "/me#field-interests");
  // The group's blocks glow on the grid; the others do not.
  await expect(page.locator('[data-testid="proposal-block"][data-glow="true"]')).toHaveCount(3);
  await walk.getByRole("button", { name: "Next" }).click();
  await expect(walk).toContainText("Step 2 of 3");
  await expect(page.locator('[data-testid="proposal-block"][data-glow="true"]')).toHaveCount(2);
  await settle(page);
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
  expect(results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`)).toEqual([]);

  await panel.getByRole("button", { name: "Accept all" }).click();
  await expect(page.getByTestId("proposal-block")).toHaveCount(0);
  await expect(page.locator('[data-testid="course-card"][data-course="TEST 25100"]')).toBeAttached();
});

test("agents: typing 'apply it' applies the latest proposal", async ({ page }) => {
  await page.goto("/plan");
  const panel = await openAdvisor(page);
  const input = panel.getByLabel("Ask or tell the planner");
  await input.fill("Please add a lighter elective");
  await input.press("Enter");
  const proposal = panel.getByRole("article", { name: "Proposal: Add TEST 25200" });
  await expect(proposal).toContainText("Add TEST 25200 to Autumn 2099");
  await expect(page.getByRole("button", { name: /^TEST 25200.*proposed in Add TEST 25200$/ })).toBeVisible();

  await input.fill("apply it");
  await panel.getByRole("button", { name: "Send" }).click();
  await expect(page.locator('[data-testid="course-card"][data-course="TEST 25200"]')).toBeAttached();
  await expect(page.getByTestId("proposal-block")).toHaveCount(0);

  await input.fill("Tell me a joke");
  await panel.getByRole("button", { name: "Send" }).click();
  await expect(panel.getByText("I can only help with planning your courses.")).toBeVisible();
});

test("agents: the keyboard reaches Generate, the answer, Accept and Escape", async ({ page }) => {
  await page.goto("/plan");
  await page.getByRole("button", { name: "Generate plan" }).focus();
  await page.keyboard.press("Enter");
  const answer = page.getByLabel("Your answer");
  await answer.focus();
  await page.keyboard.type("testing");
  await page.keyboard.press("Enter");
  const accept = page.getByTestId("walkthrough").getByRole("button", { name: "Accept" });
  await accept.focus();
  await page.keyboard.press("Enter");
  await expect(page.getByTestId("walkthrough")).toContainText("Step 1 of 2");
  await page.getByLabel("Ask or tell the planner").focus();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("complementary", { name: "Planner panel" })).toBeHidden();
});
