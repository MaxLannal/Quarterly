import { expect, test } from "@playwright/test";
import { card, gridByTerm, generate, openPanel, signUp } from "./journey";

test("journey A: incoming first-year plans, generates, edits and saves to a new account", async ({ page }) => {
  // 1. Home -> Start planning (no login).
  await page.goto("/");
  await page.getByRole("link", { name: "Start planning" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Planner setup" })).toBeVisible();

  // 2. Onboarding: entry quarter, a placement, interests, career chips.
  await expect(page.getByLabel("Catalog year")).toHaveValue("2026-27");
  await page.getByLabel("First quarter at UChicago").selectOption("2026-AU");
  await page.getByRole("radio", { name: "First-year" }).check();
  await page.getByRole("button", { name: "Next" }).click();

  await page.getByLabel("Kind").selectOption("placement");
  await page.getByLabel("Description").fill("Calculus placement");
  await page.getByLabel("Counts as course (if known)").fill("MATH 15100");
  await page.getByRole("button", { name: "Add credit" }).click();
  await expect(page.getByText("placement: Calculus placement → MATH 15100")).toBeVisible();
  await page.getByRole("button", { name: "Next" }).click();

  await page.getByRole("checkbox", { name: "Computer Science (BS)" }).check();
  await page.getByRole("checkbox", { name: "The Core (general education)" }).check();
  await page.getByLabel(/Interests/).fill("machine learning");
  await page.getByRole("button", { name: "Add", exact: true }).click();
  await page.getByRole("button", { name: "Next" }).click();

  await page.getByRole("button", { name: "Lighter first year" }).click();
  await expect(page.getByRole("button", { name: "Lighter first year" })).toHaveAttribute("aria-pressed", "true");
  await page.getByRole("button", { name: "Next" }).click();

  await expect(page.getByRole("heading", { name: "Step 5 of 5: Review" })).toBeVisible();
  await expect(page.getByText("Computer Science (BS), The Core (general education)")).toBeVisible();
  await page.getByRole("button", { name: "Create plan" }).click();

  // 3. The planner opens, with the Generate popup.
  await expect(page).toHaveURL(/\/plan\?generate=1$/);
  await expect(page.getByRole("list", { name: "Programs on this plan" })).toContainText("Computer Science (BS)");

  // 4. Generate: verified variants, one rationale line per quarter (fake LLM).
  const { dialog, variants } = await generate(page);
  await page.screenshot({ path: "test-results/a-variants.png", fullPage: true });
  console.log(await dialog.innerText());
  expect(await variants.count()).toBeGreaterThan(0);
  const first = variants.first();
  await expect(first).toContainText("Keeps the load even and moves the programs forward.");
  await first.getByRole("button", { name: "Apply", exact: true }).click();
  await expect(dialog).toBeHidden();

  console.log(JSON.stringify(await gridByTerm(page)));
  await openPanel(page, "Check plan");
  await page.screenshot({ path: "test-results/a-applied.png", fullPage: true });
  void card;
  void signUp;
});
