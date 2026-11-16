import { expect, test, type Page } from "@playwright/test";
import { expectVariants, generate, gridByTerm, openPanel, verifierSettled } from "./journey";

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

async function placeGoal(page: Page, chip: string, term: string) {
  await page.getByLabel(`Quarter for ${chip}`).selectOption(term);
  await page.getByRole("listitem").filter({ hasText: chip }).getByRole("button", { name: "Place" }).click();
  await expect(page.getByTestId(`timeline-${term}`)).toContainText(chip);
}

test("journey C: Paris block in Autumn Y2 and at most 3 courses per quarter in Y4", async ({ page }) => {
  let report: VerifyReport | null = null;
  page.on("response", async (r) => {
    if (r.url().endsWith("/api/verify") && r.request().method() === "POST" && r.ok()) report = (await r.json()) as VerifyReport;
  });

  await page.goto("/onboarding");
  await page.getByLabel("First quarter at UChicago").selectOption("2026-AU");
  await page.getByRole("radio", { name: "First-year" }).check();
  await page.getByRole("button", { name: "Next" }).click();
  await page.getByLabel("Kind").selectOption("placement");
  await page.getByLabel("Description").fill("Calculus placement");
  await page.getByLabel("Counts as course (if known)").fill("MATH 15100");
  await page.getByRole("option", { name: /^MATH 15100/ }).click();
  await page.getByRole("button", { name: "Add credit" }).click();
  await expect(page.getByText("placement: Calculus placement → MATH 15100")).toBeVisible();
  await page.getByRole("button", { name: "Next" }).click();

  // C1. Pin the Paris civilization program as a block in Autumn of the second year. The
  // "Study abroad" chip uses the study-abroad program on the plan (Paris, not the first listed).
  await page.getByRole("checkbox", { name: "Computer Science (BS)" }).check();
  await page.getByRole("checkbox", { name: "The Core (general education)" }).check();
  await page.getByRole("checkbox", { name: "Paris: Migration, Decolonization, and Diaspora Civilization" }).check();
  await page.getByRole("button", { name: "Next" }).click();
  await placeGoal(page, "Study abroad", "2027-AU");

  // C2. Y4 at most 3 courses per quarter.
  for (const t of Y4) await placeGoal(page, "Light quarter", t);
  await page.getByRole("button", { name: "Next" }).click();
  await expect(page.getByText("Study abroad: civ-abroad-paris-mdd, Autumn 2027")).toBeVisible();
  await page.getByRole("button", { name: "Create plan" }).click();

  // C3. Generate and apply a verified variant.
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
  for (const c of civ!.courses) expect(PARIS).toContain(c);
  expect(r.progress.find((p) => p.program_id === "civ-abroad-paris-mdd" && p.node_id === "civ-abroad-paris-mdd")?.satisfied).toBe(true);

  // Y4 holds at most 3 courses a quarter; the major's courses sit mostly in Y2-Y3.
  for (const t of Y4) expect((grid[t] ?? []).length, `${t} courses`).toBeLessThanOrEqual(3);
  const cs = (terms: string[]) => terms.flatMap((t) => grid[t] ?? []).filter((c) => c.startsWith("CMSC ")).length;
  expect(cs(Y2_Y3)).toBeGreaterThan(cs(Y4));

  // Offering patterns were checked: no course is placed in a quarter it is not usually offered.
  expect(r.issues.filter((i) => i.code === "V04")).toEqual([]);
  const drawer = await openPanel(page, "Goals");
  await expect(drawer).toContainText("Study abroad: civ-abroad-paris-mdd, Autumn 2027");
});
