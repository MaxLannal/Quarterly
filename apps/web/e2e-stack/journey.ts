import { expect, test, type Locator, type Page } from "@playwright/test";
import { freshIdentity, signupCode } from "./stack";

// Browser steps shared by the journeys (real stack: catalog 2026-27, seeded programs).

/** A SPEC step the app does not do yet: recorded on the test (and printed), never faked. */
export function gap(description: string) {
  test.info().annotations.push({ type: "gap", description });
  console.log(`GAP ${description}`);
}

/** The verifier badge has a result for the current plan (no "checking…"). */
export async function verifierSettled(page: Page) {
  const badge = page.getByTestId("verifier-badge");
  await expect(badge).toHaveText(/^(Valid|\d+ warnings?|\d+ errors?)$/);
  return (await badge.innerText()).trim();
}

/** The logged-in account's saved plans, from the real API. */
export async function accountPlans(page: Page): Promise<{ id: string; name: string }[]> {
  return page.evaluate(async () => {
    const r = await fetch("/api/plans", { credentials: "same-origin" });
    return r.ok ? ((await r.json()) as { id: string; name: string }[]) : [];
  });
}

/**
 * 2-3 variants, each checked by the verifier (a report badge) and each with a rationale line per
 * quarter it explains ("Autumn 2026: ...").
 */
export async function expectVariants(variants: Locator) {
  const n = await variants.count();
  expect(n).toBeGreaterThanOrEqual(2);
  expect(n).toBeLessThanOrEqual(3);
  for (let i = 0; i < n; i++) {
    const v = variants.nth(i);
    await expect(v.getByRole("heading", { level: 3 })).toHaveText(/^Option [A-C]$/);
    await expect(v.getByText(/^(Valid|\d+ warnings?|\d+ errors?)$/).first()).toBeVisible();
    const lines = await v.locator("ul li:has(strong)").allInnerTexts();
    expect(lines.length).toBeGreaterThan(0);
    for (const line of lines) expect(line).toMatch(/^(Autumn|Winter|Spring|Summer) \d{4}: \S/);
  }
}

export function card(page: Page, code: string): Locator {
  return page.locator(`[data-testid="course-card"][data-course="${code}"]`);
}

export function cards(page: Page): Locator {
  return page.locator('[data-testid="course-card"]');
}

/** The course codes on the grid, quarter by quarter: { "2026-AU": ["MATH 15200", ...] }. */
export async function gridByTerm(page: Page): Promise<Record<string, string[]>> {
  return page.locator('[data-testid="course-card"][data-course]').evaluateAll((els) => {
    const out: Record<string, string[]> = {};
    for (const el of els) {
      const term = el.getAttribute("data-term") ?? "";
      (out[term] ??= []).push(el.getAttribute("data-course") ?? "");
    }
    return out;
  });
}

/** Opens the drawer at a tab (the toolbar button, or the tab when the drawer is already open). */
export async function openPanel(page: Page, name: "Requirements" | "Goals" | "Check plan") {
  const drawer = page.getByTestId("plan-drawer");
  if (await drawer.isVisible()) {
    await drawer.getByRole("tab", { name }).click();
  } else {
    await page.getByRole("button", { name: name === "Check plan" ? /^Check plan/ : name, exact: name !== "Check plan" }).click();
  }
  await expect(drawer).toBeVisible();
  return drawer;
}

export async function closePanel(page: Page) {
  const drawer = page.getByTestId("plan-drawer");
  if (await drawer.isVisible()) {
    await drawer.getByRole("button", { name: "Close panel" }).click();
    await expect(drawer).toBeHidden();
  }
}

/** Runs the agent generator from the open Generate popup; returns the variant cards. */
export async function generate(page: Page, setup?: (dialog: Locator) => Promise<void>) {
  const dialog = page.getByRole("dialog", { name: "Generate plan" });
  await expect(dialog).toBeVisible();
  if (setup) await setup(dialog);
  await dialog.getByRole("button", { name: "Generate", exact: true }).click();
  // The run streams its steps, then the verified variants (the solver can take a while).
  await expect(dialog.getByRole("region", { name: "Generated variants" })).toBeVisible({ timeout: 150_000 });
  return { dialog, variants: dialog.getByRole("article", { name: /^Variant / }) };
}

/** What a journey enters in sign-up step 4, "About you" (Issue #16). */
export interface About {
  /** An option of the class-year question, e.g. "Class of 2030". */
  classYear: string;
  /** Program checkbox names, e.g. "Computer Science (BS)". */
  programs?: string[];
  /** "I transferred, or I am not in my first year.": first quarter, year started in, then any
   * credits or taken courses (`extra` fills them in the form). */
  transfer?: { entry: string; level: string; extra?: (page: Page) => Promise<void> };
}

/**
 * Sign-up through the real API: the code comes from the API log (console email backend),
 * matched on the pending id the browser received. Then step 4 ("About you") with `about`, and
 * "Skip for now" on the guide's questions. Ends logged in, back on `next`.
 */
export async function signUp(page: Page, prefix: string, next = "/plan", about: About = { classYear: "Class of 2030" }) {
  const who = freshIdentity(prefix);
  await page.goto(`/signup?next=${encodeURIComponent(next)}`);
  await expect(page.getByRole("heading", { level: 1, name: "Create an account" })).toBeVisible();
  await page.getByLabel("Email address").fill(who.email);
  const started = page.waitForResponse((r) => r.url().endsWith("/api/auth/email") && r.request().method() === "POST");
  await page.getByRole("button", { name: "Send code" }).click();
  const response = await started;
  expect(response.status()).toBe(202);
  const { pending_id: pendingId } = (await response.json()) as { pending_id: string };
  await expect(page.getByText("Step 2 of 4")).toBeVisible();
  await page.getByLabel("6-digit code").fill(await signupCode(pendingId));
  await page.getByRole("button", { name: "Verify code" }).click();
  await expect(page.getByText("Step 3 of 4")).toBeVisible();
  await page.getByLabel("Username").fill(who.username);
  await page.getByLabel("Password", { exact: true }).fill(who.password);
  await page.getByLabel("Repeat password").fill(who.password);
  await page.getByRole("button", { name: "Create account" }).click();
  await aboutYou(page, about);
  await expect(page.getByRole("banner").first().getByRole("link", { name: new RegExp(who.username) })).toBeVisible();
  return who;
}

/** Sign-up step 4: the registration form, then "Skip for now" (the guide's questions are optional). */
export async function aboutYou(page: Page, about: About) {
  await expect(page.getByText("Step 4 of 4")).toBeVisible();
  await expect(page.getByRole("heading", { level: 2, name: "About you" })).toBeVisible();
  await page.getByLabel("What is your class year?").selectOption({ label: about.classYear });
  for (const name of about.programs ?? []) await page.getByRole("checkbox", { name }).check();
  if (about.transfer) {
    await page.getByRole("checkbox", { name: "I transferred, or I am not in my first year." }).check();
    await page.getByLabel("Which quarter did you start at UChicago?").selectOption(about.transfer.entry);
    await page.getByLabel("Which year did you start in?").selectOption({ label: about.transfer.level });
    await about.transfer.extra?.(page);
  }
  await page.getByRole("button", { name: "Save and continue" }).click();
  await expect(page.getByRole("heading", { level: 2, name: "A few more questions?" })).toBeVisible();
  await page.getByRole("button", { name: "Skip for now" }).click();
}

/**
 * Adds a credit on the dashboard (Academic background), as a first-year whose registration form
 * has no credits question: the same credits editor, saved to the student record at once.
 */
export async function addCreditOnDashboard(page: Page, credit: { kind: string; label: string; code: string; text: string }) {
  await page.goto("/me");
  const background = page.getByRole("region", { name: "Academic background" });
  await background.getByRole("button", { name: "Answer Credits" }).click();
  await background.getByLabel("Kind").selectOption(credit.kind);
  await background.getByLabel("Description").fill(credit.label);
  await background.getByLabel("Counts as course (if known)").fill(credit.code);
  await page.getByRole("option", { name: new RegExp(`^${credit.code}`) }).click();
  await background.getByRole("button", { name: "Add credit" }).click();
  await expect(background.getByText(credit.text)).toBeVisible();
  await expect(background.getByText("Saved")).toBeVisible();
}

/**
 * The planner's "Set up a plan from your information" card (it replaced the onboarding wizard):
 * checks what it will set up, leaves "Generate a starting plan" off so the journey can add its
 * goals first, and sets the plan up.
 */
export async function setUpPlanFromRecord(page: Page, expectText: string[] = []) {
  await page.goto("/plan");
  const setup = page.getByRole("region", { name: "Set up a plan from your information" });
  await expect(setup).toBeVisible();
  for (const text of expectText) await expect(setup.getByText(text)).toBeVisible();
  await setup.getByRole("checkbox", { name: "Generate a starting plan" }).uncheck();
  await setup.getByRole("button", { name: "Set up my plan" }).click();
  await expect(setup).toBeHidden();
}

/** Drags with the mouse in small steps (dnd-kit's pointer sensor needs a few pixels to start). */
export async function drag(page: Page, from: Locator, to: Locator) {
  await to.scrollIntoViewIfNeeded();
  await from.scrollIntoViewIfNeeded();
  const a = await from.boundingBox();
  const b = await to.boundingBox();
  if (!a || !b) throw new Error("drag: no bounding boxes");
  await page.mouse.move(a.x + a.width / 2, a.y + a.height / 2);
  await page.mouse.down();
  await page.mouse.move(a.x + a.width / 2 + 12, a.y + a.height / 2 + 12, { steps: 5 });
  await page.mouse.move(b.x + b.width / 2, b.y + b.height / 2, { steps: 15 });
  await page.mouse.up();
}
