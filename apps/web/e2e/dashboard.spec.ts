import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { logIn, settle } from "./helpers";

async function expectNoAxeViolations(page: Page) {
  await settle(page);
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
  expect(results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`)).toEqual([]);
}

// Issue #16 on mock data: the registration form (sign-up step 4), the dashboard agent's
// conversation, and the dashboard's General Information, changed in place and exported.

async function signUpToStep4(page: Page) {
  await page.goto("/signup");
  await page.getByLabel("Email address").fill("fake-student@uchicago.edu");
  await page.getByRole("button", { name: "Send code" }).click();
  await page.getByLabel("6-digit code").fill("123456");
  await page.getByRole("button", { name: "Verify code" }).click();
  await page.getByLabel("Username").fill("fake-student");
  await page.getByLabel("Password", { exact: true }).fill("correct horse battery");
  await page.getByLabel("Repeat password").fill("correct horse battery");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page.getByText("Step 4 of 4")).toBeVisible();
  await expect(page.getByRole("heading", { level: 2, name: "About you" })).toBeVisible();
}

test("registration: a transfer student enters credits and taken courses, then answers the guide", async ({ page }) => {
  await signUpToStep4(page);
  await page.getByLabel("What is your class year?").selectOption({ label: "Class of 2030" });
  await expect(page.getByLabel("When do you expect to graduate?")).toHaveValue("2030-SP");
  await page.getByRole("checkbox", { name: "Fake Program" }).check();

  // The transfer questions wait behind the checkbox.
  await expect(page.getByLabel("Which quarter did you start at UChicago?")).toHaveCount(0);
  await page.getByRole("checkbox", { name: "I transferred, or I am not in my first year." }).check();
  await page.getByLabel("Which quarter did you start at UChicago?").selectOption("2027-AU");
  await page.getByLabel("Which year did you start in?").selectOption({ label: "Second year" });

  await page.getByLabel("Kind").selectOption("transfer");
  await page.getByLabel("Description").fill("Fake transfer credit");
  await page.getByRole("button", { name: "Add credit" }).click();
  await expect(page.getByText("Transfer credit: Fake transfer credit (not matched to a course yet) · 100 units")).toBeVisible();

  await page.getByLabel("Course", { exact: true }).fill("Fake Arts");
  await page.getByRole("option", { name: /^FAKE 13000/ }).click();
  await page.getByLabel("Quarter", { exact: true }).selectOption("2027-AU");
  await page.getByLabel("Grade (optional)").fill("A");
  await page.getByRole("button", { name: "Add course" }).click();
  await expect(page.getByRole("table", { name: "Taken courses" })).toContainText("FAKE 13000");

  await page.getByRole("button", { name: "Save and continue" }).click();
  await expect(page.getByRole("heading", { level: 2, name: "A few more questions?" })).toBeVisible();
  await page.getByRole("button", { name: "Answer a few more questions" }).click();

  // The guide opens on the first step-2 question, with its options as buttons.
  await expect(page).toHaveURL(/\/me$/);
  const guide = page.getByRole("dialog", { name: "Your guide" });
  await expect(guide.locator("p.sr-only[aria-live]")).toContainText("What do you plan to do after you graduate?");
  await guide.getByRole("group", { name: "Quick answers" }).getByRole("button", { name: "Graduate school" }).click();
  await guide.getByRole("button", { name: "Accept After graduation: Graduate school" }).click();
  await expect(guide.getByRole("complementary", { name: "Your answers" })).toContainText("Graduate school");

  // "Skip" moves on without a proposal.
  await expect(guide.locator("p.sr-only[aria-live]")).toContainText("How fast do you want to graduate?");
  await guide.getByRole("button", { name: "Skip", exact: true }).click();

  // An answer that does not map is asked again.
  await expect(guide.locator("p.sr-only[aria-live]")).toContainText("Are you interested in doing research?");
  await guide.getByRole("textbox", { name: "Your answer" }).fill("banana");
  await guide.getByRole("button", { name: "Send your answer" }).click();
  await expect(guide.getByText("I could not match that to an answer.").first()).toBeVisible();
  await guide.getByRole("group", { name: "Quick answers" }).getByRole("button", { name: "No" }).click();
  await guide.getByRole("button", { name: "Accept Interested in research: No" }).click();

  await guide.getByRole("group", { name: "Quick answers" }).getByRole("button", { name: "4 courses" }).click();
  await guide.getByRole("button", { name: "Accept Courses per quarter: 4 courses" }).click();
  await guide.getByRole("group", { name: "Quick answers" }).getByRole("button", { name: "None" }).click();
  await guide.getByRole("button", { name: "Accept Quarters away: None" }).click();

  // A multi-choice question: chips picked, then sent together.
  const formats = guide.getByRole("group", { name: "Choose all that apply, then send" });
  await formats.getByRole("button", { name: "Seminar" }).click();
  await formats.getByRole("button", { name: "Lab" }).click();
  await expect(formats.getByRole("button", { name: "Lab" })).toHaveAttribute("aria-pressed", "true");
  await formats.getByRole("button", { name: /^Send/ }).click();
  await expect(guide.getByRole("list", { name: "Answers to accept" })).toContainText("Seminar, Lab");
  await expectNoAxeViolations(page);
  // Change: the question's own control, saved instead of the proposal.
  await guide.getByRole("button", { name: "Change Class formats" }).click();
  await guide.getByRole("button", { name: "Online" }).click();
  await guide.getByRole("button", { name: "Save this answer" }).click();

  await guide.getByRole("group", { name: "Quick answers" }).getByRole("button", { name: "7", exact: true }).click();
  await guide.getByRole("button", { name: /^Accept Theory or application/ }).click();
  await expect(guide.getByText("Your guide has no more questions.", { exact: false })).toBeVisible();
  await expect(guide.getByRole("link", { name: "Open the planner" })).toHaveAttribute("href", "/plan");
  await guide.getByRole("button", { name: "Close the guide and go back to your dashboard" }).click();

  // The dashboard shows every accepted answer at once.
  const background = page.getByRole("region", { name: "Academic background" });
  await expect(background).toContainText("Class of 2030");
  await expect(background).toContainText("Second year");
  await expect(background).toContainText("1 credit");
  await expect(background).toContainText("1 course");
  await expect(page.getByRole("region", { name: "Goals" })).toContainText("Graduate school");
  await expect(page.getByRole("region", { name: "Goals" })).toContainText("Not answered");
  await expect(page.getByRole("region", { name: "Scheduling" })).toContainText("4 courses");
  await expect(page.getByRole("region", { name: "Learning preferences" })).toContainText("Seminar, Lab, Online");
  await expect(page.getByRole("region", { name: "Learning preferences" })).toContainText("7 of 10");
});

test("the dashboard: profile card, answers changed in place, the plan summary and the export", async ({ page }) => {
  await logIn(page);
  await page.goto("/me");
  await expect(page.getByRole("heading", { level: 1, name: /fake-user/ })).toBeVisible();
  await expect(page.getByText("fake-user@example.invalid")).toBeVisible();
  await expect(page.getByRole("button", { name: /Complete your profile/ })).toBeVisible();
  for (const group of ["Academic background", "Goals", "Scheduling", "Learning preferences"]) {
    await expect(page.getByRole("region", { name: group })).toBeVisible();
  }
  await expectNoAxeViolations(page);
  // The guide card asks the next open question from the question file.
  await expect(page.getByRole("region", { name: "Your guide" })).toContainText("What do you plan to do after you graduate?");

  // Change in place: a select saves at once.
  const scheduling = page.getByRole("region", { name: "Scheduling" });
  await scheduling.getByRole("button", { name: "Answer Courses per quarter" }).click();
  await scheduling.getByLabel("Courses per quarter", { exact: true }).selectOption({ label: "5 courses" });
  await expect(scheduling.getByText("Saved")).toBeVisible();
  await scheduling.getByRole("button", { name: "Done with Courses per quarter" }).click();
  await expect(scheduling).toContainText("5 courses");

  // A scale.
  const learning = page.getByRole("region", { name: "Learning preferences" });
  await learning.getByRole("button", { name: "Answer Theory or application" }).click();
  await learning.getByRole("button", { name: "3", exact: true }).click();
  await expect(learning).toContainText("3 of 10 (1 = Theory, 10 = Application)");

  // Research areas appear once the student wants research, as a list.
  const goals = page.getByRole("region", { name: "Goals" });
  await expect(goals.getByText("Research areas")).toHaveCount(0);
  await goals.getByRole("button", { name: "Answer Interested in research" }).click();
  await goals.getByLabel("Interested in research", { exact: true }).selectOption({ label: "Yes" });
  await goals.getByRole("button", { name: "Answer Research areas" }).click();
  await goals.getByLabel("Add to Research areas").fill("Fake topology");
  await goals.getByLabel("Add to Research areas").press("Enter");
  await expect(goals).toContainText("Fake topology");

  // No plan yet on this device.
  await expect(page.getByRole("region", { name: "No plan yet" }).getByRole("link", { name: "Set up your plan" })).toHaveAttribute("href", "/plan");

  // The export downloads student.md.
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export my information (.md)" }).click();
  expect((await download).suggestedFilename()).toBe("student.md");
});
