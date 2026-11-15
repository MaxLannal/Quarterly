import { expect, type Locator, type Page } from "@playwright/test";
import { freshIdentity, signupCode } from "./stack";

// Browser steps shared by the journeys (real stack: catalog 2026-27, seeded programs).

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
    await drawer.getByRole("tab", { name: name === "Check plan" ? "Issues" : name }).click();
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
