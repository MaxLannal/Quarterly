import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page, type Route } from "@playwright/test";

// Each test answers `/api/*` itself to check the exact calls the pages make. The e2e build
// ships the MSW service worker (VITE_MOCK_API=1), and a request answered by a service worker
// never reaches `page.route`, so service workers are blocked for this file.
test.use({ serviceWorkers: "block" });

const SESSION = {
  account: { id: "00000000-0000-0000-0000-000000000001", username: "quiet-heron", role: "user", created_day: "2026-11-12" },
  csrf_token: "csrf-token-1",
};
const PASSWORD = "correct horse battery";

type Reply = { status: number; body?: unknown };
interface Call {
  key: string;
  body: unknown;
  csrf: string | null;
}

async function mockApi(page: Page, replies: Record<string, Reply>): Promise<Call[]> {
  const calls: Call[] = [];
  await page.route("**/api/**", async (route: Route) => {
    const request = route.request();
    const key = `${request.method()} ${new URL(request.url()).pathname.replace(/^\/api/, "")}`;
    calls.push({ key, body: request.postDataJSON() as unknown, csrf: await request.headerValue("x-csrf-token") });
    const reply = replies[key] ?? { status: 401, body: { detail: "Log in to continue." } };
    await route.fulfill({
      status: reply.status,
      contentType: "application/json",
      body: reply.body === undefined ? "" : JSON.stringify(reply.body),
    });
  });
  return calls;
}

/** The auth writes among the calls: the app shell and the planner make other calls of their own
 *  (GET /auth/session, GET /catalog-years, POST /verify, ...). */
function authPosts(calls: Call[]): Call[] {
  return calls.filter((c) => c.key.startsWith("POST /auth/"));
}

async function expectAccessible(page: Page) {
  const results = await new AxeBuilder({ page }).include("main").analyze();
  expect(results.violations.map((v) => `${v.id}: ${v.help}`)).toEqual([]);
}

test("sign-up: email, code, then username and password", async ({ page }) => {
  const calls = await mockApi(page, {
    "POST /auth/email": { status: 202, body: { pending_id: "pend-1" } },
    "POST /auth/verify-code": { status: 200, body: { ticket: "ticket-1" } },
    "POST /auth/register": { status: 201, body: SESSION },
  });
  await page.goto("/signup");
  await expect(page.getByRole("heading", { level: 1, name: "Create an account" })).toBeVisible();
  await expectAccessible(page);

  // Only @uchicago.edu.
  await page.getByLabel("Email address").fill("student@gmail.com");
  await page.getByRole("button", { name: "Send code" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "Use your @uchicago.edu email address." })).toBeVisible();
  expect(authPosts(calls)).toHaveLength(0);

  await page.getByLabel("Email address").fill("student@uchicago.edu");
  await page.getByRole("button", { name: "Send code" }).click();
  await expect(page.getByText("Step 2 of 3")).toBeVisible();
  await page.getByLabel("6-digit code").fill("123456");
  await page.getByRole("button", { name: "Verify code" }).click();

  await expect(page.getByText("Step 3 of 3")).toBeVisible();
  await expectAccessible(page);
  await page.getByLabel("Username").fill("quiet-heron");
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByLabel("Repeat password").fill(PASSWORD);
  const box = await page.getByRole("button", { name: "Create account" }).boundingBox();
  expect(box?.height).toBeGreaterThanOrEqual(44);
  await page.getByRole("button", { name: "Create account" }).click();

  await expect(page).toHaveURL(/\/plan$/);
  const posts = authPosts(calls);
  expect(posts.map((c) => c.key)).toEqual(["POST /auth/email", "POST /auth/verify-code", "POST /auth/register"]);
  expect(posts[2]?.body).toEqual({ ticket: "ticket-1", username: "quiet-heron", password: PASSWORD });
});

test("log in, and reset a forgotten password", async ({ page }) => {
  const calls = await mockApi(page, {
    "POST /auth/login": { status: 200, body: SESSION },
    "POST /auth/password-reset/start": { status: 202, body: { pending_id: "pend-9" } },
    "POST /auth/password-reset/finish": { status: 204 },
  });
  await page.goto("/login");
  await expect(page.getByRole("heading", { level: 1, name: "Log in" })).toBeVisible();
  await expectAccessible(page);

  await page.getByRole("button", { name: "Forgot password?" }).click();
  await page.getByLabel("Email address").fill("student@uchicago.edu");
  await page.getByRole("button", { name: "Send reset code" }).click();
  await expect(page.getByText("If an account uses that address")).toBeVisible();
  await expectAccessible(page);
  await page.getByLabel("6-digit code").fill("654321");
  await page.getByLabel("New password", { exact: true }).fill("a brand new password");
  await page.getByLabel("Repeat new password").fill("a brand new password");
  await page.getByRole("button", { name: "Set new password" }).click();
  await expect(page.getByRole("status")).toContainText("Your password is changed");

  await page.getByLabel("Username or email").fill("quiet-heron");
  await page.getByLabel("Password").fill("a brand new password");
  await page.getByRole("button", { name: "Log in" }).click();
  await expect(page).toHaveURL(/\/plan$/);
  expect(authPosts(calls).at(-1)).toMatchObject({
    key: "POST /auth/login",
    body: { login: "quiet-heron", password: "a brand new password" },
  });
});

test("account: change password, export, delete with the posts choice", async ({ page }) => {
  const calls = await mockApi(page, {
    "GET /auth/session": { status: 200, body: SESSION },
    "POST /account/password": { status: 204 },
    "GET /account/export": { status: 200, body: { account: SESSION.account, plans: [] } },
    "POST /account/delete": { status: 204 },
  });
  await page.goto("/account");
  await expect(page.getByRole("heading", { level: 1, name: "Account" })).toBeVisible();
  await expect(page.getByText("Logged in as quiet-heron")).toBeVisible();
  await expectAccessible(page);

  const change = page.getByRole("form", { name: "Change password" });
  await change.getByLabel("Current password").fill(PASSWORD);
  await change.getByLabel("New password", { exact: true }).fill("a brand new password");
  await change.getByLabel("Repeat new password").fill("a brand new password");
  await change.getByRole("button", { name: "Change password" }).click();
  await expect(change.getByRole("status")).toContainText("Password changed");

  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download my data (JSON)" }).click();
  expect((await download).suggestedFilename()).toBe("quarterly-quiet-heron.json");

  const remove = page.getByRole("form", { name: "Delete account" });
  await remove.getByRole("button", { name: "Delete my account permanently" }).click();
  await expect(remove.getByRole("alert")).toContainText("Choose what happens to your forum posts.");
  await remove.getByRole("radio", { name: /Keep my posts/ }).check();
  await remove.getByLabel("Password, to confirm").fill(PASSWORD);
  await remove.getByRole("button", { name: "Delete my account permanently" }).click();
  await expect(page).toHaveURL(/\/$/);

  const writes = calls.filter((c) => c.key.startsWith("POST"));
  expect(writes.map((c) => c.key)).toEqual(["POST /account/password", "POST /account/delete"]);
  expect(writes.every((c) => c.csrf === "csrf-token-1")).toBe(true);
  expect(writes[1]?.body).toEqual({ password: PASSWORD, posts: "keep" });
});

test("account: a logged-out visitor is sent to log in", async ({ page }) => {
  await mockApi(page, {});
  await page.goto("/account");
  await page.getByRole("main").getByRole("link", { name: "Log in" }).click();
  await expect(page).toHaveURL(/\/login$/);
});

test("privacy: says what is stored and the limits", async ({ page }) => {
  await page.goto("/privacy");
  await expect(page.getByRole("heading", { level: 1, name: "Privacy" })).toBeVisible();
  const table = page.getByRole("table");
  await expect(table.getByRole("rowheader", { name: "Email address" })).toBeVisible();
  await expect(table.getByRole("rowheader", { name: "IP addresses" })).toBeVisible();
  await expect(page.getByText("has both the database and the server key can link a post to")).toBeVisible();
  await expectAccessible(page);
});
