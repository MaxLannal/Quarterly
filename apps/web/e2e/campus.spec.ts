import { expect, test } from "@playwright/test";
import { logIn } from "./helpers";

// The campus companion's pages on mock data (docs/BEST-OF-UCHICAGO-PLAN.md): the Commons and the
// dashboard, in the "Maroon and night" design (docs/DESIGN.md). The Ask page, the homepage's
// question bar and the companion went in issue #15; the Feed moved into the Catalog in issue #19
// (e2e/courses.spec.ts).

test("the homepage has no question bar, and the old Ask page opens the planner (issue #15)", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1, name: "The Best of UChicago, within your reach." })).toBeVisible();
  await expect(page.getByRole("combobox", { name: /Ask Quarterly a question/ })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "CS BA or BS?" })).toHaveCount(0); // a "Try" question
  await expect(page.getByText("Try", { exact: true })).toHaveCount(0);
  await page.goto("/ask?q=Which%20intro%20course");
  await expect(page).toHaveURL(/\/plan$/);
});

test("no page has the companion orb (issue #15)", async ({ page }) => {
  for (const path of ["/", "/courses", "/me", "/forum"]) {
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1 }).first()).toBeVisible();
    await expect(page.getByRole("button", { name: /companion/i })).toHaveCount(0);
  }
});

test("a Commons question shows the AI's answer and the replies; a logged-in student can answer", async ({
  page,
}) => {
  await page.goto("/forum");
  await expect(page.getByRole("heading", { level: 1, name: /Ask the quad/ })).toBeVisible();
  // Issue #20: discussions start from a "New post" button, not a chatbot-like ask box.
  await expect(page.getByRole("link", { name: "New post" })).toHaveAttribute("href", "/forum/new");
  await expect(page.getByRole("textbox", { name: "Your question" })).toHaveCount(0);
  await page.getByRole("link", { name: "Fake question: is TEST 10000 fine without background?", exact: true }).click();
  await expect(page).toHaveURL(/\/forum\/t\/1$/);
  await page.goto("/forum/t/1");
  await expect(
    page.getByRole("heading", { level: 1, name: "Fake question: is TEST 10000 fine without background?" }),
  ).toBeVisible();
  await expect(page.getByText("Quarterly AI").first()).toBeVisible();
  await expect(page.getByText("Fake nested reply.")).toBeVisible();
  await logIn(page);
  await page.goto("/forum/t/1");
  // The answer box is a combobox: typing a course code offers matching courses to mention.
  const answer = page.getByRole("combobox", { name: "Your answer" });
  await answer.fill("Fake answer: try the course page first.");
  await expect(page.getByRole("button", { name: "Post answer" })).toBeEnabled();
});

test("the dashboard invites a logged-out visitor, and shows the identity card once logged in", async ({
  page,
}) => {
  await page.goto("/me");
  await expect(page.getByRole("link", { name: /Log in/ }).first()).toBeVisible();
  await logIn(page);
  await page.goto("/me");
  await expect(page.getByText("fake-user").first()).toBeVisible();
});

test("sign-in follows the reference card: big title, pill fields, a password that can be shown", async ({
  page,
}) => {
  await page.goto("/login");
  await expect(page.getByRole("heading", { level: 1, name: "Welcome back" })).toBeVisible();
  const password = page.getByLabel("Password", { exact: true });
  await password.fill("correct horse");
  await expect(password).toHaveAttribute("type", "password");
  await page.getByRole("button", { name: "Show characters" }).click();
  await expect(password).toHaveAttribute("type", "text");
  const radius = await password.evaluate((el) => getComputedStyle(el).borderTopLeftRadius);
  expect(radius).toBe("26px");
});

test("the homepage can be day or a snowy night, and remembers the choice", async ({ page }) => {
  await page.goto("/");
  const hero = page.locator("section[data-scene]");
  await expect(hero).toHaveAttribute("data-scene", "day");
  await page.getByRole("radio", { name: "Night" }).click();
  await expect(page.getByRole("radio", { name: "Night" })).toHaveAttribute("aria-checked", "true");
  await expect(hero).toHaveAttribute("data-scene", "night");
  await page.reload();
  await expect(page.locator("section[data-scene]")).toHaveAttribute("data-scene", "night");
  await page.getByRole("radio", { name: "Day" }).click();
  await expect(page.locator("section[data-scene]")).toHaveAttribute("data-scene", "day");
});
