import { expect, test, type Page } from "@playwright/test";
import { addCreditOnDashboard, closePanel, expectVariants, generate, gridByTerm, openPanel, setUpPlanFromRecord, signUp, verifierSettled } from "./journey";

// SPEC "Core user journeys" C: goal-constrained student (study abroad + lighter senior year),
// real stack, fake LLM. The SPEC example says "Paris, Spring Y2", but the seeded catalog offers
// the Paris program (SOSC 19076-19078) in Autumn only, so the journey pins it in Autumn of Y2.

const PARIS = ["SOSC 19076", "SOSC 19077", "SOSC 19078"];
const Y2_Y3 = ["2027-AU", "2028-WI", "2028-SP", "2028-AU", "2029-WI", "2029-SP"];
const Y4 = ["2029-AU", "2030-WI", "2030-SP"];

interface NodeProgress {
  program_id: string;
  node_id: string;
  satisfied: boolean;
  courses: string[];
}
interface VerifyReport {
  issues: { code: string; level: string; message: string }[];
  progress: NodeProgress[];
}

/** A quarter goal from the planner's Goals tab (the onboarding wizard's timeline is gone). */
async function placeGoal(page: Page, goal: string, term: string) {
  const drawer = await openPanel(page, "Goals");
  const before = await drawer.getByRole("button", { name: /^Remove goal:/ }).count();
  await drawer.getByLabel("Goal", { exact: true }).selectOption({ label: goal });
  await drawer.getByLabel("Quarter", { exact: true }).selectOption(term);
  await drawer.getByRole("button", { name: "Add quarter goal" }).click();
  await expect(drawer.getByRole("button", { name: /^Remove goal:/ })).toHaveCount(before + 1);
}

test("journey C: Paris block in Autumn Y2 and at most 3 courses per quarter in Y4", async ({ page }) => {
  let report: VerifyReport | null = null;
  page.on("response", async (r) => {
    if (r.url().endsWith("/api/verify") && r.request().method() === "POST" && r.ok()) report = (await r.json()) as VerifyReport;
  });

  // Sign-up with "About you" (Issue #16 replaced the onboarding wizard): a first-year of the
  // class of 2030 (first quarter Autumn 2026), CS, the Core and the Paris civilization program.
  // A first-year's form has no credits: the placement result goes on the dashboard.
  await signUp(page, "c", "/plan", {
    classYear: "Class of 2030",
    programs: ["Computer Science (BS)", "The Core (general education)", "Paris: Migration, Decolonization, and Diaspora Civilization"],
  });
  await addCreditOnDashboard(page, { kind: "placement", label: "Calculus placement", code: "MATH 15100", text: "Placement: Calculus placement → MATH 15100" });
  await setUpPlanFromRecord(page, ["Autumn 2026", "Calculus placement"]);

  // C1. Pin the Paris civilization program as a block in Autumn of the second year. The
  // "Study abroad" goal uses the study-abroad program on the plan (Paris, not the first listed).
  await placeGoal(page, "Study abroad", "2027-AU");

  // C2. Y4 at most 3 courses per quarter.
  for (const t of Y4) await placeGoal(page, "Light quarter", t);
  await expect(page.getByTestId("plan-drawer")).toContainText("Study abroad: civ-abroad-paris-mdd, Autumn 2027");
  await closePanel(page);

  // C3. Generate and apply a verified variant.
  await page.getByRole("button", { name: "Generate plan" }).click();
  const { dialog, variants } = await generate(page);
  await expectVariants(variants);
  await variants.first().getByRole("button", { name: "Apply", exact: true }).click();
  await expect(dialog).toBeHidden();
  await verifierSettled(page);
  const grid = await gridByTerm(page);

  // The block fills its quarter: the three Paris courses and nothing else.
  expect([...(grid["2027-AU"] ?? [])].sort()).toEqual(PARIS);
  // ... and counts as the Core's civilization sequence.
  await expect.poll(() => report !== null).toBe(true);
  const r = report as unknown as VerifyReport;
  const civ = r.progress.find((p) => p.program_id === "core" && /(^|[./:])civ$/.test(p.node_id));
  expect(civ, `the Core's civilization node; Core nodes: ${r.progress.filter((p) => p.program_id === "core").map((p) => p.node_id).join(", ")}`).toBeTruthy();
  expect(civ!.satisfied).toBe(true);
  expect(civ!.courses.length).toBeGreaterThan(0);
  // Which eligible courses the verifier credits is its choice (a plan may also hold another
  // civilization course): the Paris block is placed (above) and its own requirement is met
  // (below). OPEN_QUESTIONS E2E-2.
  expect(r.progress.find((p) => p.program_id === "civ-abroad-paris-mdd" && p.node_id === "civ-abroad-paris-mdd")?.satisfied).toBe(true);

  // Y4 holds at most 3 courses a quarter; the major's courses sit mostly in Y2-Y3.
  for (const t of Y4) expect((grid[t] ?? []).length, `${t} courses`).toBeLessThanOrEqual(3);
  const cs = (terms: string[]) => terms.flatMap((t) => grid[t] ?? []).filter((c) => c.startsWith("CMSC ")).length;
  // A preference, not a rule: the generator stops at a time limit, and the forum ratings in
  // the reused dev database shift its choices run to run (OPEN_QUESTIONS E2E-2).
  expect(cs(Y2_Y3)).toBeGreaterThanOrEqual(cs(Y4));

  // Offering patterns were checked: no course is placed in a quarter it is not usually offered.
  expect(r.issues.filter((i) => i.code === "V04")).toEqual([]);
  const drawer = await openPanel(page, "Goals");
  await expect(drawer).toContainText("Study abroad: civ-abroad-paris-mdd, Autumn 2027");
});
