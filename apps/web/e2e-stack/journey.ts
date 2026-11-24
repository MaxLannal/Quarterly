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

/**
 * Sign-up through the real API: the code comes from the API log (console email backend),
 * matched on the pending id the browser received. Ends logged in, back on `next`.
 */
export async function signUp(page: Page, prefix: string, next = "/plan") {
  const who = freshIdentity(prefix);
  await page.goto(`/signup?next=${encodeURIComponent(next)}`);
  await expect(page.getByRole("heading", { level: 1, name: "Create an account" })).toBeVisible();
  await page.getByLabel("Email address").fill(who.email);
  const started = page.waitForResponse((r) => r.url().endsWith("/api/auth/email") && r.request().method() === "POST");
  await page.getByRole("button", { name: "Send code" }).click();
  const response = await started;
  expect(response.status()).toBe(202);
  const { pending_id: pendingId } = (await response.json()) as { pending_id: string };
  await expect(page.getByText("Step 2 of 3")).toBeVisible();
  await page.getByLabel("6-digit code").fill(await signupCode(pendingId));
  await page.getByRole("button", { name: "Verify code" }).click();
  await expect(page.getByText("Step 3 of 3")).toBeVisible();
  await page.getByLabel("Username").fill(who.username);
  await page.getByLabel("Password", { exact: true }).fill(who.password);
  await page.getByLabel("Repeat password").fill(who.password);
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page.getByRole("banner").first().getByRole("link", { name: new RegExp(who.username) })).toBeVisible();
  return who;
}

/**
 * Drags the card of `code` onto `to` until the plan check runs, and returns the time of the drop
 * (the mouse button's release) that started it. A pointer drag can miss on a busy machine
 * (OPEN_QUESTIONS E2E-1), so up to three drags. A missed drag changes nothing, so no plan check
 * starts. When 5 s pass without a check but the card did move, the check is slow: wait for it
 * and return the first drop's time, so the caller's timing still fails.
 */
export async function dragUntilChecked(page: Page, code: string, to: Locator): Promise<number> {
  const from = page.getByRole("button", { name: `Drag ${code}`, exact: true });
  // Both ends must be on screen at once (a pointer outside the window drops nowhere). Since the
  // full catalog import the cards are taller, so two quarters a year apart may not fit.
  const size = page.viewportSize();
  const a = await from.boundingBox();
  const b = await to.boundingBox();
  if (size && a && b) {
    const span = Math.abs(b.y - a.y) + Math.max(a.height, b.height) + 200;
    if (span > size.height) await page.setViewportSize({ width: size.width, height: Math.ceil(span) });
  }
  for (let attempt = 0; attempt < 3; attempt += 1) {
    const checked = page
      .waitForResponse((r) => r.url().endsWith("/api/verify") && r.request().method() === "POST", { timeout: 60_000 })
      .then(
        () => true,
        () => false,
      );
    const dropped = await drag(page, from, to);
    const quick = await Promise.race([checked, page.waitForTimeout(5_000).then(() => false)]);
    if (quick) return dropped;
    if ((await to.getByRole("button", { name: `Drag ${code}`, exact: true }).count()) > 0) {
      if (await checked) return dropped; // moved, but the check was slow
      throw new Error("drag: the card moved but no plan check ran");
    }
  }
  throw new Error("drag: the card did not move after three drags");
}

/** Drags with the mouse in small steps (dnd-kit's pointer sensor needs a few pixels to start). */
export async function drag(page: Page, from: Locator, to: Locator): Promise<number> {
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
  return Date.now();
}
