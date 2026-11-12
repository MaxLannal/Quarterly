import { expect, test } from "@playwright/test";

test("onboarding: five steps create a plan and open the generator", async ({ page }) => {
  await page.goto("/onboarding");
  await expect(page.getByRole("heading", { level: 1, name: "Planner setup" })).toBeVisible();

  // 1. Entry term and status
  await expect(page.getByRole("heading", { name: "Step 1 of 5: Entry term" })).toBeVisible();
  await expect(page.getByLabel("Catalog year")).toHaveValue("2099-00");
  await page.getByLabel("First quarter at UChicago").selectOption("2099-AU");
  await page.getByRole("radio", { name: "First-year" }).check();
  await page.getByRole("button", { name: "Next" }).click();

  // 2. Credits
  await page.getByLabel("Kind").selectOption("AP");
  await page.getByLabel("Description").fill("Fake AP exam");
  await page.getByLabel("Counts as course (if known)").fill("TEST 10000");
  await page.getByRole("button", { name: "Add credit" }).click();
  await expect(page.getByText("AP: Fake AP exam → TEST 10000")).toBeVisible();
  await page.getByRole("button", { name: "Next" }).click();

  // 3. Programs
  await page.getByRole("checkbox", { name: "Fake Program" }).check();
  await page.getByRole("checkbox", { name: "Fake Core" }).check();
  await page.getByLabel(/Interests/).fill("ML");
  await page.getByRole("button", { name: "Add", exact: true }).click();
  await page.getByRole("button", { name: "Next" }).click();

  // 4. Goals: a career chip, then a quarter chip (keyboard "Place" and drag)
  await page.getByRole("button", { name: "Protect GPA" }).click();
  await expect(page.getByRole("button", { name: "Protect GPA" })).toHaveAttribute("aria-pressed", "true");
  await page.getByLabel("Quarter for Light quarter").selectOption("2100-WI");
  await page.getByRole("listitem").filter({ hasText: "Light quarter" }).getByRole("button", { name: "Place" }).click();
  await expect(page.getByTestId("timeline-2100-WI")).toContainText("Light quarter");
  const chip = page.getByRole("button", { name: "Drag “At most 4 courses” onto a quarter" });
  const target = page.getByTestId("timeline-2100-SP");
  const a = await chip.boundingBox();
  const b = await target.boundingBox();
  if (!a || !b) throw new Error("no boxes");
  await page.mouse.move(a.x + a.width / 2, a.y + a.height / 2);
  await page.mouse.down();
  await page.mouse.move(a.x + 20, a.y + 20, { steps: 5 });
  await page.mouse.move(b.x + b.width / 2, b.y + b.height / 2, { steps: 10 });
  await page.mouse.up();
  await expect(target).toContainText("At most 4 courses");
  // dnd-kit swallows a click that lands within a few milliseconds of a drop (a person cannot
  // click that fast; Playwright can), so press Next until the step changes.
  const review = page.getByRole("heading", { name: "Step 5 of 5: Review" });
  await expect(async () => {
    if (!(await review.isVisible())) await page.getByRole("button", { name: "Next" }).click({ timeout: 1000 });
    await expect(review).toBeVisible({ timeout: 1000 });
  }).toPass();

  // 5. Review
  await expect(page.getByText("Fake Program, Fake Core")).toBeVisible();
  await expect(page.getByRole("checkbox", { name: "Generate a starting plan" })).toBeChecked();
  await page.getByRole("button", { name: "Create plan" }).click();

  await expect(page).toHaveURL(/\/plan\?generate=1$/);
  await expect(page.getByRole("dialog", { name: "Generate plan" })).toBeVisible();
  await expect(page.getByRole("dialog").getByRole("checkbox", { name: "Protect GPA" })).toBeChecked();
  await expect(page.getByRole("dialog").getByRole("button", { name: "Remove interest ML" })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("list", { name: "Programs on this plan" })).toContainText("Fake Program");
  await expect(page.getByTestId("footer-2100-WI")).toContainText("Light quarter");
});
