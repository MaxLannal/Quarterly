import { expect, test } from "@playwright/test";
import { logIn } from "./helpers";

// Issue #16 replaced the onboarding wizard: its entry, credits and programs steps are in the
// registration form, and the planner sets up a plan from the student record.

test("the old onboarding address opens the dashboard", async ({ page }) => {
  await page.goto("/onboarding");
  await expect(page).toHaveURL(/\/me$/);
  await expect(page.getByRole("heading", { level: 1, name: "Tell Quarterly about you." })).toBeVisible();
});

test("logged out, the planner offers sign-up to set up a plan", async ({ page }) => {
  await page.goto("/plan");
  await expect(page.getByRole("link", { name: "Sign up to set up your plan" })).toHaveAttribute("href", "/signup");
});

test("a plan set up from the student record opens the generator", async ({ page }) => {
  await logIn(page);
  await page.goto("/plan");
  // Without a first quarter or programs, the card sends the student to the dashboard first.
  const setup = page.getByRole("region", { name: "Set up a plan from your information" });
  await expect(setup.getByRole("link", { name: "Answer on your dashboard" })).toHaveAttribute("href", "/me");

  await page.evaluate(async () => {
    await fetch("/api/me/profile", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        entry_term: "2099-AU",
        entry_year_level: 1,
        expected_graduation_term: "2103-SP",
        intended_programs: ["fake-major"],
        credits: [{ kind: "AP", label: "Fake AP exam", maps_to: "TEST 10000", units: 100 }],
        taken_courses: [{ course: "FAKE 13000", term: "2099-AU", status: "completed", grade: "A" }],
      }),
    });
  });
  await page.reload();
  await expect(setup.getByText("Fake Program, Fake Core")).toBeVisible();
  await expect(setup.getByText("Fake AP exam")).toBeVisible();
  await expect(setup.getByRole("checkbox", { name: "Generate a starting plan" })).toBeChecked();
  await setup.getByRole("button", { name: "Set up my plan" }).click();

  await expect(page.getByRole("dialog", { name: "Generate plan" })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("list", { name: "Programs on this plan" })).toContainText("Fake Program");
  await expect(page.getByRole("list", { name: "Programs on this plan" })).toContainText("Fake Core");
  await expect(page.locator('[data-testid="course-card"][data-course="FAKE 13000"]')).toBeAttached();
});
