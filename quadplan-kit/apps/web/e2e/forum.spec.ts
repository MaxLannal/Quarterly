import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Locator, type Page } from "@playwright/test";
import { settle } from "./helpers";

// Forum (prompt 08) against the MSW mocks in src/mocks/forum.ts.

const FORUM = "/courses/TEST%2010000/i/fake-instructor-a";
const THREAD = `${FORUM}/t/3`;

async function logIn(page: Page, admin = false) {
  await page.goto("/guidelines");
  // The mock API (service worker) is running once the app has rendered.
  await expect(page.getByRole("heading", { level: 1, name: "Community guidelines" })).toBeVisible();
  await page.evaluate(async (asAdmin) => {
    if (asAdmin) sessionStorage.setItem("quarterly.mock.admin", "1");
    await fetch("/api/auth/login", { method: "POST", body: JSON.stringify({ login: "fake-user", password: "x" }) });
  }, admin);
}

/** Click the pill (label) of a 1-5 rating radio. */
async function pick(form: Locator, name: string) {
  await form.locator("label", { has: form.page().getByRole("radio", { name, exact: true }) }).click();
}

/** No serious or critical axe violations (WCAG 2.1 A/AA). */
async function expectNoSeriousAxeViolations(page: Page) {
  await settle(page);
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
  const serious = results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
  expect(serious.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`)).toEqual([]);
  return results.violations;
}

async function expect44pxTargets(page: Page) {
  const small = await page.evaluate(() =>
    [...document.querySelectorAll<HTMLElement>("main button, main a[role='button'], main [role='tab'], main label:has(input[type='radio'])")]
      .filter((el) => el.offsetParent !== null && !el.classList.contains("sr-only"))
      .map((el) => ({ name: el.getAttribute("aria-label") ?? el.textContent?.trim() ?? "", box: el.getBoundingClientRect() }))
      .filter(({ box }) => box.height < 44 || box.width < 44)
      .map(({ name, box }) => `${name} (${Math.round(box.width)}x${Math.round(box.height)})`),
  );
  expect(small).toEqual([]);
}

test("forum pages need a login", async ({ page }) => {
  await page.goto(FORUM);
  await expect(page.getByRole("heading", { level: 1, name: "Course × instructor forum" })).toBeVisible();
  await expect(page.getByText("Reviews and discussion are for logged-in students.")).toBeVisible();
});

test("forum page: header, ratings, tabs, sorting, axe and 44px targets", async ({ page }) => {
  await logIn(page);
  await page.goto(FORUM);
  await expect(page.getByRole("heading", { level: 1, name: /Fake Introduction I with Fake Instructor A/ })).toBeVisible();
  await expect(page.getByText("Taught Autumn 2099, Winter 2100")).toBeVisible();
  await expect(page.getByRole("heading", { name: "What students say" })).toBeVisible();
  await expect(page.getByText("No summary yet")).toBeVisible();
  await expect(page.getByRole("tab", { name: "Reviews (2)" })).toHaveAttribute("aria-selected", "true");
  const heron = page.getByRole("article", { name: "Review by Fake Heron" });
  await expect(heron).toBeVisible();
  await expect(page.getByLabel("Sort by").first()).toHaveValue("best");
  await page.getByLabel("Term taken").selectOption("2100-WI");
  await expect(page.getByText("No reviews yet")).toBeVisible();
  await page.getByLabel("Term taken").selectOption("");
  await expect(heron).toBeVisible();

  await expectNoSeriousAxeViolations(page);
  await expect44pxTargets(page);

  await page.getByRole("tab", { name: "Discussion" }).click();
  const discussion = page.getByRole("tabpanel", { name: "Discussion" });
  await expect(discussion.getByLabel("Sort by")).toHaveValue("hot");
  await expect(discussion.getByRole("link", { name: "Fake question: is the midterm curved?" })).toBeVisible();
});

test("write a review and a discussion post; vote", async ({ page }) => {
  await logIn(page);
  await page.goto(FORUM);
  await page.getByRole("button", { name: "Write a review" }).click();
  const form = page.getByRole("form", { name: "Write a review" });
  await expect(page.getByRole("complementary", { name: "Community rules" })).toContainText("No claims of misconduct");
  for (const name of ["Overall 4 of 5", "Difficulty 2 of 5", "Intellectual intensity 3 of 5"]) await pick(form, name);
  await pick(form, "How fast it moved 4 of 5"); // optional; grading is left blank
  await form.getByLabel("Workload: hours per week outside class").fill("8");
  await form.getByRole("radio", { name: "Yes" }).check();
  await form.getByLabel("Term you took it").selectOption("2099-AU");
  await form.getByLabel("Your review").fill("Fake e2e review: <script>alert(1)</script> fine.");
  await form.getByRole("button", { name: "Post review" }).click();
  const mine = page.getByRole("article", { name: "Review by Fake Wren" });
  await expect(mine).toBeVisible();
  await expect(mine).toContainText("<script>alert(1)</script>"); // shown as text, never run
  await expect(mine.getByText("Pace", { exact: true })).toBeVisible();
  await expect(mine.getByText("Grading", { exact: true })).toHaveCount(0);

  // A second review on the same page is refused.
  await page.getByRole("button", { name: "Write a review" }).click();
  for (const name of ["Overall 1 of 5", "Difficulty 1 of 5", "Intellectual intensity 1 of 5"]) await pick(form, name);
  await form.getByLabel("Workload: hours per week outside class").fill("1");
  await form.getByRole("radio", { name: "No" }).check();
  await form.getByLabel("Term you took it").selectOption("2099-AU");
  await form.getByLabel("Your review").fill("again");
  await form.getByRole("button", { name: "Post review" }).click();
  await expect(form.getByText(/already reviewed/)).toBeVisible();
  await form.getByRole("button", { name: "Cancel" }).click();

  // Votes: up, then up again withdraws.
  const heron = page.getByRole("article", { name: "Review by Fake Heron" });
  const up = heron.getByRole("button", { name: "Upvote" });
  await up.click();
  await expect(up).toHaveAttribute("aria-pressed", "true");
  await expect(heron.locator("[aria-live=polite]")).toHaveText(/5/);
  await up.click();
  await expect(up).toHaveAttribute("aria-pressed", "false");

  // A discussion post appears at once: nothing checks it before it is published (P08-1).
  await page.getByRole("tab", { name: "Discussion" }).click();
  const panel = page.getByRole("tabpanel", { name: "Discussion" });
  await panel.getByRole("button", { name: "Start a discussion" }).click();
  await panel.getByLabel("Title").fill("Fake question about the midterm");
  await panel.getByLabel("Your post").fill("Fake: how long was the midterm?");
  await panel.getByRole("button", { name: "Post", exact: true }).click();
  const posted = panel.getByRole("article", { name: "Fake question about the midterm" });
  await expect(posted).toContainText("how long was the midterm");
  await expect(posted).not.toContainText("Not published");
  await expect(posted).not.toContainText("Held");
});

test("thread view: nested comments fold below depth 6, reply, report, axe", async ({ page }) => {
  await logIn(page);
  await page.goto(THREAD);
  await expect(page.getByRole("heading", { level: 1, name: "Fake question: is the midterm curved?" })).toBeVisible();
  await expect(page.getByText("Fake reply at depth 5.")).toBeVisible();
  await expect(page.getByText("Fake reply at depth 6.")).toHaveCount(0);

  await expectNoSeriousAxeViolations(page);
  await expect44pxTargets(page);

  await page.getByRole("button", { name: "Continue this thread (3 more replies)" }).click();
  await expect(page.getByText("Fake reply at depth 8.")).toBeVisible();

  await page.getByRole("textbox", { name: "Add a comment" }).fill("Fake e2e comment.");
  await page.getByRole("button", { name: "Comment", exact: true }).click();
  await expect(page.getByText("Fake e2e comment.")).toBeVisible();

  await page.getByRole("button", { name: "Reply to comment by Fake Otter" }).first().click();
  await page.getByRole("textbox", { name: "Reply to Fake Otter" }).fill("Fake nested reply.");
  await page.getByRole("form", { name: "Reply to Fake Otter" }).getByRole("button", { name: "Comment" }).click();
  await expect(page.getByText("Fake nested reply.")).toBeVisible();

  await page.getByRole("button", { name: "Report discussion by Fake Lark" }).click();
  const dialog = page.getByRole("dialog", { name: "Report this post" });
  await dialog.getByRole("radio", { name: "Names or identifies a student" }).check();
  await dialog.getByLabel("Details (optional)").fill("Fake details.");
  await dialog.getByRole("button", { name: "Send report" }).click();
  await expect(dialog.getByText("Thanks. A moderator will look at it.")).toBeVisible();
  await dialog.getByRole("button", { name: "Close", exact: true }).first().click();
  await expect(dialog).toHaveCount(0);
});

test("instructors: public names; course page ratings need login", async ({ page }) => {
  await page.goto("/instructors");
  await expect(page.getByRole("heading", { level: 1, name: "Forum" })).toBeVisible();
  await page.getByRole("link", { name: /Fake Instructor A/ }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Fake Instructor A" })).toBeVisible();
  await expect(page.getByText("to see ratings and read reviews.")).toBeVisible();

  // FEEDBACK 2026-11-16: ratings and instructors are a compact overview under the title.
  await page.goto("/courses/TEST%2010000");
  const overview = page.getByRole("region", { name: "Overview" });
  await expect(overview.getByText("Student ratings")).toBeVisible();
  await expect(overview.getByText("to see ratings.")).toBeVisible();
  await logIn(page);
  await page.goto("/courses/TEST%2010000");
  await expect(overview.getByText("2 reviews")).toBeVisible();
  await overview.getByRole("link", { name: "Fake Instructor A" }).click();
  await expect(page.getByRole("heading", { level: 1, name: /with Fake Instructor A/ })).toBeVisible();
});

test("guidelines page lists the community rules", async ({ page }) => {
  await page.goto("/guidelines");
  await expect(page.getByRole("heading", { level: 1, name: "Community guidelines" })).toBeVisible();
  await expect(page.getByText("No names of other students.")).toBeVisible();
});

test("logging in from a forum page comes back to it", async ({ page }) => {
  await page.goto(FORUM);
  await page.getByRole("main").getByRole("link", { name: "Log in" }).click();
  await expect(page).toHaveURL(/\/login\?next=/);
  await page.getByLabel("Username or email").fill("fake-user");
  await page.getByLabel("Password").fill("fake password 123");
  await page.getByRole("button", { name: "Log in" }).click();
  await expect(page).toHaveURL(new RegExp(`${FORUM.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}$`));
  await expect(page.getByRole("heading", { level: 1, name: /with Fake Instructor A/ })).toBeVisible();
});

test("admin moderation queue: remove and choose to suspend the author", async ({ page }) => {
  // The mock seeds one held post by another (fake) author; state lives in the page, so the
  // queue is opened directly rather than after posting from another page load.
  await logIn(page, true);
  await page.goto("/admin/moderation");
  await expect(page.getByRole("heading", { level: 1, name: "Moderation queue" })).toBeVisible();
  const item = page.getByRole("article", { name: /discussion on TEST 10000/ });
  await expect(item).toContainText("Fake held post");
  await expect(item).toContainText("May identify someone");
  await expectNoSeriousAxeViolations(page);
  // Suspensions are never automatic (P08-3): the admin picks one while removing.
  await item.getByLabel("When removing, also suspend the author").selectOption("30");
  await item.getByRole("button", { name: "Remove" }).click();
  await expect(page.getByRole("status").filter({ hasText: "Removed: Fake held post. The author is suspended for 30 days." })).toBeVisible();
  // The suspension can be ended early (FEEDBACK "End suspension"); the author is never shown.
  const suspension = page.getByRole("region", { name: "Suspensions" }).or(page.getByRole("article", { name: /^Suspension from post/ }));
  await expect(page.getByRole("article", { name: /^Suspension from post/ })).toContainText("Fake held post");
  await page.getByRole("button", { name: "End suspension" }).click();
  await expect(page.getByRole("status").filter({ hasText: "Suspension ended: Fake held post." })).toBeVisible();
  await expect(suspension).toHaveCount(0);
  await expect(page.getByText("Nothing to review")).toBeVisible();
});

test("the moderation queue is for admins only", async ({ page }) => {
  await logIn(page);
  await page.goto("/admin/moderation");
  await expect(page.getByText("Only admins can moderate the forum.")).toBeVisible();
});
