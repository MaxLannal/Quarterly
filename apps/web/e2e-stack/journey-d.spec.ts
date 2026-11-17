import { expect, test, type Locator } from "@playwright/test";
import { signUp } from "./journey";

// SPEC "Core user journeys" D: forum reader and writer (real stack, fake LLM). The demo forum
// seed (`make seed-forum-demo`, fake data) puts no instructor on MATH 20700, so the journey uses
// CMSC 14100 with Demo Instructor A (3 fake reviews and a discussion). The AI summary comes from
// the attributes job that `make e2e-stack` runs with the fake LLM.

const COURSE = "CMSC 14100";

/** Click the pill (label) of a 1-5 rating radio. */
async function pick(form: Locator, name: string) {
  await form.locator("label", { has: form.page().getByRole("radio", { name, exact: true }) }).click();
}

test("journey D: search a course, read the instructor forum, post a review and upvote an answer", async ({ page }) => {
  // D1. Search, open the course page: aggregate attributes and the instructors who teach it.
  await page.goto("/");
  await page.getByRole("searchbox", { name: "Search courses", exact: true }).fill(COURSE);
  await page.getByRole("button", { name: "Search", exact: true }).first().click();
  await expect(page.getByRole("heading", { level: 1, name: "Course search" })).toBeVisible();
  await page.getByRole("link", { name: /^CMSC 14100 · / }).first().click();
  await expect(page.getByRole("heading", { level: 1, name: "CMSC 14100 · Introduction to Computer Science I" })).toBeVisible();
  const main = page.getByRole("main");
  await expect(main.getByText("Course attributes")).toBeVisible();
  for (const name of ["Difficulty", "Intellectual intensity", "Would recommend", "Workload"]) {
    await expect(main.getByText(name, { exact: true }).first()).toBeVisible();
  }
  await expect(main.getByText(/From \d+ forum ratings/).first()).toBeVisible();
  await expect(main.getByRole("link", { name: /Demo Instructor A/ }).first()).toBeVisible();
  await expect(main.getByRole("link", { name: /Demo Instructor B/ }).first()).toBeVisible();

  // D2 (logged out): the course x instructor page asks for a login.
  await main.getByRole("link", { name: /Demo Instructor A/ }).last().click();
  await expect(page.getByText("Reviews and discussion are for logged-in students.")).toBeVisible();
  const forumPath = new URL(page.url()).pathname;

  // D3. Log in (a new account) to read and post; sign-up comes back to the forum page.
  await signUp(page, "d", forumPath);
  await expect(page).toHaveURL(new RegExp(`${forumPath}$`));
  await expect(page.getByRole("heading", { level: 1, name: /CMSC 14100.*with Demo Instructor A/ })).toBeVisible();

  // D2. Rating summary, the AI summary with citations to posts, threads sorted by Best.
  await expect(page.getByText(/^From \d+ reviews?$/)).toBeVisible();
  const summary = page.getByRole("region", { name: "What students say" }).or(page.locator("#summary"));
  await expect(summary.getByText(/Written by AI from \d+ posts?/)).toBeVisible();
  const citations = summary.getByRole("link", { name: /^\[\d+\]$/ });
  expect(await citations.count()).toBeGreaterThan(0);
  await expect(page.getByRole("tab", { name: /^Reviews \(\d+\)$/ })).toHaveAttribute("aria-selected", "true");
  await expect(page.getByLabel("Sort by").first()).toHaveValue("best");

  // D3. Write a review: structured ratings + text, posted under a pseudonym ("Quiet Heron").
  const text = `Journey D review ${Date.now().toString(36)}: weekly problem sets, fair exams.`;
  await page.getByRole("button", { name: "Write a review" }).click();
  const form = page.getByRole("form", { name: "Write a review" });
  for (const name of ["Overall 4 of 5", "Difficulty 3 of 5", "Intellectual intensity 4 of 5"]) await pick(form, name);
  await form.getByLabel("Workload: hours per week outside class").fill("9");
  await form.getByRole("radio", { name: "Yes" }).check();
  await form.getByLabel("Term you took it").selectOption("2026-AU");
  await form.getByLabel("Your review").fill(text);
  await form.getByRole("button", { name: "Post review" }).click();
  await expect(page.getByRole("article", { name: /^Review by [A-Z][a-z]+ [A-Z][a-z]+$/ }).filter({ hasText: text })).toBeVisible();

  // Upvote a helpful answer in the discussion thread.
  await page.getByRole("tab", { name: "Discussion" }).click();
  await page.getByRole("tabpanel", { name: "Discussion" }).getByRole("link", { name: "Demo question (fake data): is the midterm curved?" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Demo question (fake data): is the midterm curved?" })).toBeVisible();
  const answer = page.getByRole("article", { name: /^Comment by / }).filter({ hasText: "it was last time, according to the syllabus" });
  const up = answer.getByRole("button", { name: "Upvote" });
  await expect(up).toHaveAttribute("aria-pressed", "false");
  await up.click();
  await expect(up).toHaveAttribute("aria-pressed", "true");
  await page.reload();
  await expect(answer.getByRole("button", { name: "Upvote" })).toHaveAttribute("aria-pressed", "true");
});
