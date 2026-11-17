import { expect, test } from "@playwright/test";

test("program explorer and program page", async ({ page }) => {
  await page.goto("/programs");
  await expect(page.getByRole("heading", { level: 1, name: "Program explorer" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Majors" })).toBeVisible();
  await expect(page.getByRole("listitem").filter({ hasText: "Fake Minor" })).toContainText("Not yet hand-checked");
  await page.getByRole("link", { name: "Fake Program" }).click();

  await expect(page.getByRole("heading", { level: 1, name: "Fake Program" })).toBeVisible();
  await expect(page.getByText("2 courses from TEST courses numbered 25000–29999")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Sample path" })).toBeVisible();
  await page.getByRole("button", { name: "Add to plan" }).click();
  await expect(page.getByText("Added Fake Program to your plan.")).toBeVisible();
  await page.getByRole("link", { name: "Open the planner" }).click();
  await expect(page.getByRole("list", { name: "Programs on this plan" })).toContainText("Fake Program");
});
