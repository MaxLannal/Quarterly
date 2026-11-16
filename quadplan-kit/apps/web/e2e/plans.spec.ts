import { expect, test } from "@playwright/test";

test("my plans: duplicate, compare, import on login", async ({ page }) => {
  await page.goto("/courses/TEST%2010000");
  await page.getByRole("button", { name: "Add to plan" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Autumn 2099" }).click();
  await expect(page.getByText("Added TEST 10000")).toBeVisible();

  await page.goto("/plans");
  await expect(page.getByRole("heading", { level: 1, name: "My plans" })).toBeVisible();
  await page.getByRole("button", { name: "Duplicate" }).click();
  await expect(page.getByLabel("Name of plan")).toHaveCount(2);
  await page.getByRole("link", { name: "Compare two plans" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Compare plans" })).toBeVisible();
  await expect(page.getByText("1 courses are the same in both.")).toBeVisible();

  // Deleting asks first, in place (DF-7); Cancel keeps the plan.
  await page.goto("/plans");
  const copyDelete = page.getByRole("button", { name: /^Delete / }).last();
  await copyDelete.click();
  await page.getByRole("button", { name: "Cancel" }).click();
  await expect(page.getByLabel("Name of plan")).toHaveCount(2);
  await page.getByRole("button", { name: /^Delete / }).last().click();
  await page.getByRole("button", { name: "Yes, delete" }).click();
  await expect(page.getByLabel("Name of plan")).toHaveCount(1);

  // Log in (mock auth), then reload: the shell imports the device's plans.
  await page.goto("/plans");
  await expect(page.getByRole("link", { name: "Log in" }).first()).toBeVisible();
  await page.evaluate(() => fetch("/api/auth/login", { method: "POST", body: JSON.stringify({ login: "fake-user", password: "x" }) }));
  await page.reload();
  await expect(page.getByRole("link", { name: "fake-user" })).toBeVisible();
  await expect(page.getByText("Your plans from this device were added to your account.")).toBeVisible();
  await expect(page.getByRole("heading", { name: "In your account" })).toBeVisible();
  await expect(page.getByText(/My Plan \(primary\)/)).toBeVisible();
});
