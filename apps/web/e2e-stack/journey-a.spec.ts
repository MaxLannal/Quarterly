import { expect, test } from "@playwright/test";
import { accountPlans, addCreditOnDashboard, closePanel, drag, expectVariants, gap, generate, gridByTerm, openPanel, setUpPlanFromRecord, signUp, verifierSettled } from "./journey";

// SPEC "Core user journeys" A: incoming first-year with no plan (real stack, fake LLM). Since
// Issue #16 a new student signs up first: the registration form replaced the onboarding wizard.
test("journey A: first-year signs up, sets up a plan from their information, generates, drags a course and saves", async ({ page }) => {
  // A1. Home -> Start planning opens sign-up for a logged-out visitor.
  await page.goto("/");
  await page.getByRole("link", { name: "Start planning" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Create an account" })).toBeVisible();

  // A2. Sign-up with "About you": a first-year of the class of 2030 (first quarter Autumn 2026),
  // CS and the Core. A first-year's form has no credits, so the placement result goes on the
  // dashboard's Academic background.
  await signUp(page, "a", "/plan", { classYear: "Class of 2030", programs: ["Computer Science (BS)", "The Core (general education)"] });
  await expect(page).toHaveURL(/\/plan$/);
  await addCreditOnDashboard(page, { kind: "placement", label: "Calculus placement", code: "MATH 15100", text: "Placement: Calculus placement → MATH 15100" });

  // A3. The planner sets the plan up from the student record; then the career-goal chip.
  await setUpPlanFromRecord(page, ["Computer Science (BS), The Core (general education)", "Autumn 2026", "Calculus placement"]);
  await expect(page.getByText("Catalog 2026-27")).toBeVisible();
  await expect(page.getByRole("list", { name: "Programs on this plan" })).toContainText("Computer Science (BS)");
  const goals = await openPanel(page, "Goals");
  await goals.getByRole("button", { name: "+ Lighter first year" }).click();
  await expect(goals).toContainText("Light quarter");
  await closePanel(page);
  gap("A3: the Core is not pre-placed as requirement slots; the grid starts empty.");

  // A4. Generate (the interest goes in the popup): 2-3 verified variants, a rationale line per
  // quarter (from the fake LLM).
  await page.getByRole("button", { name: "Generate plan" }).click();
  const { dialog, variants } = await generate(page, async (d) => {
    await d.getByLabel("Interest tag").fill("machine learning");
    await d.getByRole("button", { name: "Add", exact: true }).click();
    await expect(d.getByRole("button", { name: "Remove interest machine learning" })).toBeVisible();
  });
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

  // A6. Save to the account: exactly one plan there, the one on the grid.
  const plan = await gridByTerm(page);
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await expect(page.getByText("Saved to your account.")).toBeVisible();
  const saved = await accountPlans(page);
  expect(saved, "exactly one account plan after sign-up and Save").toHaveLength(1);
  expect(await gridByTerm(page)).toEqual(plan);
});
