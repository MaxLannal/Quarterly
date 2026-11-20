import { expect, test } from "@playwright/test";
import { logIn } from "./helpers";

// The campus companion's pages on mock data (docs/BEST-OF-UCHICAGO-PLAN.md): Ask, the companion,
// the feed, the Commons and the dashboard, in the "Maroon and night" design (docs/DESIGN.md).

test("the homepage question bar asks the chatbot, which answers with course links", async ({ page }) => {
  await page.goto("/");
  await page
    .getByRole("combobox", { name: "Ask Quarterly a question about UChicago" })
    .fill("Which intro course should I take?");
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/ask/);
  await expect(page.getByText("Written by an AI and can be wrong.").first()).toBeVisible();
  await expect(page.getByRole("link", { name: /TEST 10000/ }).first()).toHaveAttribute(
    "href",
    "/courses/TEST%2010000",
  );
});

test("the Ask page has the split header with a course-title art panel", async ({ page }) => {
  await page.goto("/ask");
  await expect(page.getByRole("heading", { level: 1, name: "Ask anything about UChicago." })).toBeVisible();
  await expect(page.getByRole("img", { name: /Gothic window/ })).toBeVisible();
});

test("the companion opens from its orb and closes with Escape", async ({ page }) => {
  await page.goto("/courses");
  const orb = page.getByRole("button", { name: /Open Quarterly companion/ });
  await orb.click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(orb).toBeFocused();
});

test("the feed lists course spotlights that open their course", async ({ page }) => {
  await page.goto("/feed");
  await expect(page.getByRole("heading", { level: 1, name: /A river of ideas/ })).toBeVisible();
  const course = page.locator('main a[href^="/courses/TEST"]').first();
  await expect(course).toBeVisible();
});

test("a Commons question shows the AI's answer and the replies; a logged-in student can answer", async ({
  page,
}) => {
  await page.goto("/forum");
  await expect(page.getByRole("heading", { level: 1, name: /Ask the quad/ })).toBeVisible();
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
