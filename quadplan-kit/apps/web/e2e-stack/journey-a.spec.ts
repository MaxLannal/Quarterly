import { expect, test } from "@playwright/test";
import { accountPlans, drag, expectVariants, gap, generate, gridByTerm, signUp, verifierSettled } from "./journey";

// SPEC "Core user journeys" A: incoming first-year with no plan (real stack, fake LLM).
test("journey A: first-year onboards, generates, drags a course and saves to a new account", async ({ page }) => {
  // A1. Home -> Start planning, no login.
  await page.goto("/");
  await page.getByRole("link", { name: "Start planning" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Planner setup" })).toBeVisible();

  // A2. Onboarding: entry quarter, a placement result, an interest, career-goal chips.
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

  // A3. The planner opens on the new plan, with the Generate popup.
  await expect(page).toHaveURL(/\/plan\?generate=1$/);
  await expect(page.getByRole("list", { name: "Programs on this plan" })).toContainText("Computer Science (BS)");
  gap("A3: the Core is not pre-placed as requirement slots; the grid starts empty.");

  // A4. Generate: 2-3 verified variants, a rationale line per quarter (from the fake LLM).
  const { dialog, variants } = await generate(page);
  await expectVariants(variants);
  gap('A4: variants are named "Option A/B/C", not "Exploratory CS" / "Econ-leaning" / "Balanced".');
  await variants.first().getByRole("button", { name: "Apply", exact: true }).click();
  await expect(dialog).toBeHidden();
  await verifierSettled(page);

  // A5. Swap a course by drag-and-drop; the verifier re-runs in under a second.
  const before = await gridByTerm(page);
  const moved = before["2027-SP"]?.[0];
  if (!moved) throw new Error("no course in Spring 2027 after applying the variant");
  const target = page.getByTestId("quarter-2028-SP");
  const verified = page.waitForResponse((r) => r.url().endsWith("/api/verify") && r.request().method() === "POST");
  const dropped = Date.now();
  await drag(page, page.getByRole("button", { name: `Drag ${moved}`, exact: true }), target);
  await verified;
  await verifierSettled(page);
  const elapsed = Date.now() - dropped;
  expect((await gridByTerm(page))["2028-SP"]).toContain(moved);
  expect(elapsed, `drop to verified badge took ${elapsed} ms`).toBeLessThan(1000);

  // A6. Create an account to save it: the local plan is imported, and Save updates that plan.
  const plan = await gridByTerm(page);
  await signUp(page, "a", "/plan");
  await expect.poll(() => accountPlans(page).then((p) => p.length)).toBe(1);
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await expect(page.getByText("Saved to your account.")).toBeVisible();
  const saved = await accountPlans(page);
  expect(saved, "exactly one account plan after sign-up and Save").toHaveLength(1);
  expect(await gridByTerm(page)).toEqual(plan);
});
