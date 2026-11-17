import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { logIn, settle } from "./helpers";

// The curator console (prompt 09) against MSW mocks: a FAKE program version, prerequisite and course batch.

test("curator console: quotes beside rules, accept, then publish", async ({ page }) => {
  await logIn(page, true);
  await page.goto("/admin/review");
  await expect(page.getByRole("heading", { level: 1, name: "Curator console" })).toBeVisible();
  const card = page.getByRole("article", { name: "fake-science-bs 2099-00" });
  const tree = card.getByRole("region", { name: "Rule tree with source quotes" });
  await expect(tree.getByText("“FAKE: students take TEST 10000.”")).toBeVisible();
  await expect(tree.getByText("The second run disagrees here (different).")).toBeVisible();
  await card.getByRole("button", { name: "Accept" }).click();
  await expect(page.getByRole("status").getByText(/Accepted: fake-science-bs 2099-00\./)).toBeVisible();
  await page.getByLabel("Show").selectOption("accepted");
  await page.getByRole("article", { name: "fake-science-bs 2099-00" }).getByRole("button", { name: "Publish this version" }).click();
  await expect(page.getByText("Published fake-science-bs 2099-00. Students now see these rules.")).toBeVisible();
});

test("curator console has no accessibility violations", async ({ page }) => {
  await logIn(page, true);
  await page.goto("/admin/review");
  await expect(page.getByRole("article", { name: "fake-science-bs 2099-00" })).toBeVisible();
  await settle(page);
  const results = await new AxeBuilder({ page }).include("main").withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
  expect(results.violations).toEqual([]);
});

test("the curator console is for admins only", async ({ page }) => {
  await logIn(page);
  await page.goto("/admin/review");
  await expect(page.getByText("Only admins can review catalog changes.")).toBeVisible();
});
