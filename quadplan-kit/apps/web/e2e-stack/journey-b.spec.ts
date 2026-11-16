import { expect, test, type Page } from "@playwright/test";
import { card, gap, verifierSettled } from "./journey";

// SPEC "Core user journeys" B: transfer student targeting CS BS + Math BS and the Bx/MS
// (real stack, fake LLM).

async function transferCredit(page: Page, label: string, code: string | null, units: string) {
  await page.getByLabel("Kind").selectOption("transfer");
  await page.getByLabel("Description").fill(label);
  if (code) {
    await page.getByLabel("Counts as course (if known)").fill(code);
    await page.getByRole("option", { name: new RegExp(`^${code}`) }).click();
  }
  await page.getByLabel("Units").fill(units);
  await page.getByRole("button", { name: "Add credit" }).click();
  // Each add looks the code up in the catalog first: wait for it before the next one.
  await expect(page.getByText(`transfer: ${label}${code ? ` → ${code}` : " (needs mapping)"} · ${units} units`)).toBeVisible();
}

test("journey B: transfer student with CS BS + Math BS + Bx/MS sees what cannot fit, then asks the advisor", async ({ page }) => {
  await page.goto("/onboarding");
  await page.getByLabel("First quarter at UChicago").selectOption("2026-AU");
  await page.getByRole("radio", { name: "Transfer student" }).check();
  await page.getByLabel("Class standing at entry").selectOption("2");
  await page.getByRole("button", { name: "Next" }).click();

  // B1. Transfer credits: a known equivalent is mapped, the others are flagged for manual mapping.
  await transferCredit(page, "Calculus I at a community college", "MATH 15100", "100");
  await transferCredit(page, "Intro to Programming at a community college", null, "100");
  await transferCredit(page, "First-year coursework at a previous college", null, "900");
  await page.getByRole("button", { name: "Next" }).click();

  // B2. Programs: CS BS, Math BS, CS Bx/MS (research option); the Core is required to graduate.
  await page.getByRole("checkbox", { name: "Computer Science (BS)" }).check();
  await page.getByRole("checkbox", { name: "Mathematics (BS)" }).check();
  await page.getByRole("checkbox", { name: "Computer Science Bx/MS, Option 1: Research-Oriented Computer Science Majors" }).check();
  await page.getByRole("checkbox", { name: "The Core (general education)" }).check();
  await page.getByRole("button", { name: "Next" }).click();

  // B3. Goals: at most one very hard course per quarter.
  await page.getByRole("button", { name: "At most one very hard course per quarter" }).click();
  await expect(page.getByRole("button", { name: "At most one very hard course per quarter" })).toHaveAttribute("aria-pressed", "true");
  gap('B3: there is no chip or control for the "Bx/MS application in Winter of 3rd year" goal (the goal type exists in the model only).');
  await page.getByRole("button", { name: "Next" }).click();
  await expect(page.getByText("Calculus I at a community college, Intro to Programming at a community college, First-year coursework at a previous college")).toBeVisible();
  await page.getByRole("button", { name: "Create plan" }).click();

  // B4. Generate: with three programs in nine quarters nothing fits, and the answer is a precise
  // list of the rules in conflict: shared-course (double-count) limits, the College unit limit
  // (overload), and whether the quarters left are enough to graduate.
  const dialog = page.getByRole("dialog", { name: "Generate plan" });
  await dialog.getByRole("checkbox", { name: "Allow a 500-unit quarter where the rules permit it" }).check();
  await dialog.getByRole("button", { name: "Generate", exact: true }).click();
  const results = dialog.getByRole("region", { name: "Generated variants" });
  await expect(results).toBeVisible({ timeout: 150_000 });
  const notice = results.getByRole("status").filter({ hasText: "No plan fits all of these settings." });
  await expect(notice).toBeVisible();
  for (const rule of [
    "The limits on courses shared between your programs",
    "Keeping every quarter full time and within the College's unit limit",
    "Reaching the units and number of quarters the College requires to graduate",
    "Placing courses only in quarters they are usually offered",
    "Completing cmsc-bs",
    "Completing math-bs",
    "Completing cmsc-bxms-1",
  ]) {
    await expect(notice).toContainText(rule);
  }
  await expect(results.getByRole("article")).toHaveCount(0);
  gap("B4: no variant is generated for this transfer case, so the verifier's per-plan overload and double-count issues are only shown as the generator's conflict list.");
  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
  await verifierSettled(page);

  // B5. Advisor chat: the answer cites the course, then drafts a change set; the student
  // confirms by typing the confirmation sentence, and the change is applied to the plan.
  await page.getByRole("button", { name: "Ask Quarterly" }).click();
  const sheet = page.getByRole("dialog", { name: "Ask Quarterly" });
  const input = sheet.getByLabel("Ask the advisor");
  await input.fill("Is Honors Analysis (MATH 20700) worth it if I want ML research?");
  await input.press("Enter");
  const proposal = sheet.getByRole("article", { name: "Proposed change" });
  await expect(proposal).toContainText(/Add MATH 20700 to (Autumn|Winter|Spring) \d{4}/, { timeout: 60_000 });
  await expect(sheet.getByText("MATH 20700 is a good fit for that goal.")).toBeVisible();
  const phrase = (await proposal.innerText()).match(/Or type “(I agree to [^”]+)”/)?.[1];
  expect(phrase, "the card shows the typed confirmation sentence").toBeTruthy();
  await input.fill(phrase!);
  await input.press("Enter");
  await expect(proposal).toContainText("Applied.");
  await expect(card(page, "MATH 20700")).toBeAttached();
  gap("B5: with the fake LLM the answer cites the course only; forum evidence in answers needs the real model (not run: API hold).");
});
