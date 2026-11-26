import { expect, test, type Page } from "@playwright/test";
import { signUp } from "./journey";

// The dashboard guide against the real API (Issue #16; Richard's report of 2026-11-25). Each
// accepted answer must stay in the student record with every earlier one, whether the student
// answers right after sign-up or later from the dashboard. The mock-data tests could not catch
// the bug: the mock sent only the answered field, the real server sent every field.

async function acceptAnswer(page: Page, question: string, reply: string, card: string) {
  const guide = page.getByRole("dialog", { name: "Your guide" });
  await expect(guide.locator("p.sr-only[aria-live]")).toContainText(question);
  await guide.getByRole("group", { name: "Quick answers" }).getByRole("button", { name: reply, exact: true }).click();
  await guide.getByRole("button", { name: `Accept ${card}` }).click();
  await expect(guide.getByRole("complementary", { name: "Your answers" })).toContainText(reply);
}

async function closeGuide(page: Page) {
  await page.getByRole("dialog", { name: "Your guide" }).getByRole("button", { name: "Close the guide and go back to your dashboard" }).click();
}

test("journey E: the guide's answers stay saved, at sign-up and later from the dashboard", async ({ page }) => {
  // E1. Sign up with "About you", then answer the guide at once.
  await signUp(page, "e", "/plan", { classYear: "Class of 2030", programs: ["Computer Science (BS)"], answerGuide: true });
  await acceptAnswer(page, "What do you plan to do after you graduate?", "Graduate school", "After graduation: Graduate school");
  await acceptAnswer(page, "How fast do you want to graduate?", "On time", "Graduation pace: On time");
  await closeGuide(page);

  // E2. After a reload, the sign-up answers and both accepted answers are in the record.
  await page.goto("/me");
  const background = page.getByRole("region", { name: "Academic background" });
  await expect(background).toContainText("Class of 2030");
  await expect(background).toContainText("Computer Science (BS)");
  const goals = page.getByRole("region", { name: "Goals" });
  await expect(goals).toContainText("Graduate school");
  await expect(goals).toContainText("On time");

  // E3. Later, from the dashboard: one more answer, and nothing earlier is lost.
  await page.getByRole("button", { name: /Complete your profile/ }).click();
  await acceptAnswer(page, "Are you interested in doing research?", "No", "Interested in research: No");
  await closeGuide(page);
  await page.goto("/me");
  await expect(background).toContainText("Class of 2030");
  await expect(background).toContainText("Computer Science (BS)");
  await expect(goals).toContainText("Graduate school");
  await expect(goals).toContainText("On time");
  // "Not answered" contains "No": check the row itself, which offers "Change" once answered.
  await expect(goals.getByRole("button", { name: "Change Interested in research" })).toBeVisible();
});
