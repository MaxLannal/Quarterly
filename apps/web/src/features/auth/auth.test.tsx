import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import AccountPage from "@/pages/AccountPage";
import LoginPage from "@/pages/LoginPage";
import PrivacyPage from "@/pages/PrivacyPage";
import SignupPage from "@/pages/SignupPage";
import type { SessionOut } from "./api";
import { forgetPersonalDevice, resetSession } from "./session";

interface Call {
  method: string;
  path: string;
  body: unknown;
  csrf: string | null;
  credentials: RequestCredentials;
}
type Reply = { status: number; body?: unknown };
type Routes = Record<string, Reply | ((body: unknown) => Reply)>;

const SESSION: SessionOut = {
  account: { id: "00000000-0000-0000-0000-000000000001", username: "quiet-heron", role: "user", created_day: "2026-11-12" },
  csrf_token: "csrf-token-1",
};
const PASSWORD = "correct horse battery";

/** Replaces `fetch` with a table of API replies and records every call. */
function mockApi(routes: Routes): Call[] {
  const calls: Call[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (request: Request) => {
      const path = new URL(request.url).pathname.replace(/^\/api/, "");
      const body: unknown = request.method === "GET" ? undefined : await request.json().catch(() => undefined);
      calls.push({
        method: request.method,
        path,
        body,
        csrf: request.headers.get("X-CSRF-Token"),
        credentials: request.credentials,
      });
      const route = routes[`${request.method} ${path}`];
      const reply = typeof route === "function" ? route(body) : (route ?? { status: 404, body: { detail: "Not found" } });
      return new Response(reply.body === undefined ? null : JSON.stringify(reply.body), {
        status: reply.status,
        headers: { "Content-Type": "application/json" },
      });
    }),
  );
  return calls;
}

function renderAt(path: string) {
  const router = createMemoryRouter(
    [
      { path: "/signup", element: <SignupPage /> },
      { path: "/login", element: <LoginPage /> },
      { path: "/account", element: <AccountPage /> },
      { path: "/privacy", element: <PrivacyPage /> },
      { path: "/plan", element: <h1>Planner</h1> },
      { path: "/", element: <h1>Home</h1> },
    ],
    { initialEntries: [path] },
  );
  render(<RouterProvider router={router} />);
  return router;
}

beforeEach(() => {
  resetSession();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("sign-up", () => {
  it("refuses an address outside uchicago.edu before calling the API", async () => {
    const calls = mockApi({});
    const user = userEvent.setup();
    renderAt("/signup");
    expect(screen.getByText("Step 1 of 3")).toBeInTheDocument();
    await user.type(screen.getByLabelText("Email address"), "student@gmail.com");
    await user.click(screen.getByRole("button", { name: "Send code" }));
    const input = screen.getByLabelText("Email address");
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(input).toHaveAccessibleDescription(/Use your @uchicago.edu email address/);
    expect(screen.getAllByRole("alert").some((el) => /uchicago\.edu/.test(el.textContent ?? ""))).toBe(true);
    expect(calls).toEqual([]);
  });

  it("walks email, code, then username and password", async () => {
    const calls = mockApi({
      "POST /auth/email": { status: 202, body: { pending_id: "pend-1" } },
      "POST /auth/verify-code": { status: 200, body: { ticket: "ticket-1" } },
      "POST /auth/register": { status: 201, body: SESSION },
    });
    const user = userEvent.setup();
    const router = renderAt("/signup");

    await user.type(screen.getByLabelText("Email address"), "Student@uchicago.edu");
    await user.click(screen.getByRole("button", { name: "Send code" }));

    const codeHeading = await screen.findByRole("heading", { level: 2, name: "Enter the code" });
    expect(codeHeading).toHaveFocus();
    expect(screen.getByText("Step 2 of 3")).toBeInTheDocument();
    await user.type(screen.getByLabelText("6-digit code"), "123456");
    await user.click(screen.getByRole("button", { name: "Verify code" }));

    await screen.findByRole("heading", { level: 2, name: "Choose a username and password" });
    expect(screen.getByText("Step 3 of 3")).toBeInTheDocument();
    await user.type(screen.getByLabelText("Username"), "quiet-heron");
    await user.type(screen.getByLabelText("Password"), PASSWORD);
    await user.type(screen.getByLabelText("Repeat password"), PASSWORD);
    await user.click(screen.getByRole("button", { name: "Create account" }));

    await waitFor(() => expect(router.state.location.pathname).toBe("/plan"));
    expect(calls.map((c) => [c.method, c.path, c.body])).toEqual([
      ["POST", "/auth/email", { email: "Student@uchicago.edu" }],
      ["POST", "/auth/verify-code", { pending_id: "pend-1", code: "123456" }],
      ["POST", "/auth/register", { ticket: "ticket-1", username: "quiet-heron", password: PASSWORD }],
    ]);
    expect(calls.every((c) => c.credentials === "same-origin")).toBe(true);
  });

  it("announces a wrong code and lets the student ask for a new one", async () => {
    const calls = mockApi({
      "POST /auth/email": { status: 202, body: { pending_id: "pend-1" } },
      "POST /auth/verify-code": { status: 400, body: { detail: "That code is wrong or has expired." } },
    });
    const user = userEvent.setup();
    renderAt("/signup");
    await user.type(screen.getByLabelText("Email address"), "student@uchicago.edu");
    await user.click(screen.getByRole("button", { name: "Send code" }));
    await user.type(await screen.findByLabelText("6-digit code"), "12");
    await user.click(screen.getByRole("button", { name: "Verify code" }));
    expect(screen.getByLabelText("6-digit code")).toHaveAccessibleDescription("Enter the 6 digits from the email.");
    expect(calls).toHaveLength(1);

    await user.type(screen.getByLabelText("6-digit code"), "3456");
    await user.click(screen.getByRole("button", { name: "Verify code" }));
    expect(await screen.findByText("That code is wrong or has expired.")).toBeInTheDocument();
    expect(screen.getByText("That code is wrong or has expired.").closest("[role=alert]")).not.toBeNull();

    await user.click(screen.getByRole("button", { name: "Send a new code" }));
    expect(await screen.findByRole("status")).toHaveTextContent("We sent a new code");
    expect(calls.filter((c) => c.path === "/auth/email")).toHaveLength(2);
  });

  it("checks the passwords match and shows a taken username on the field", async () => {
    const calls = mockApi({
      "POST /auth/email": { status: 202, body: { pending_id: "pend-1" } },
      "POST /auth/verify-code": { status: 200, body: { ticket: "ticket-1" } },
      "POST /auth/register": { status: 409, body: { detail: "That username is taken." } },
    });
    const user = userEvent.setup();
    renderAt("/signup");
    await user.type(screen.getByLabelText("Email address"), "student@uchicago.edu");
    await user.click(screen.getByRole("button", { name: "Send code" }));
    await user.type(await screen.findByLabelText("6-digit code"), "123456");
    await user.click(screen.getByRole("button", { name: "Verify code" }));
    await user.type(await screen.findByLabelText("Username"), "quiet-heron");
    await user.type(screen.getByLabelText("Password"), PASSWORD);
    await user.type(screen.getByLabelText("Repeat password"), "something else entirely");
    await user.click(screen.getByRole("button", { name: "Create account" }));
    expect(screen.getByText("The two passwords do not match.")).toBeInTheDocument();
    expect(calls.filter((c) => c.path === "/auth/register")).toHaveLength(0);

    await user.clear(screen.getByLabelText("Repeat password"));
    await user.type(screen.getByLabelText("Repeat password"), PASSWORD);
    await user.click(screen.getByRole("button", { name: "Create account" }));
    await waitFor(() =>
      expect(screen.getByLabelText("Username")).toHaveAccessibleDescription(/That username is taken\./),
    );
    expect(screen.getByLabelText("Username")).toHaveAttribute("aria-invalid", "true");
  });
});

describe("log in", () => {
  it("logs in with a username or email and a password", async () => {
    const calls = mockApi({ "POST /auth/login": { status: 200, body: SESSION } });
    const user = userEvent.setup();
    const router = renderAt("/login");
    await user.type(screen.getByLabelText("Username or email"), "quiet-heron");
    await user.type(screen.getByLabelText("Password"), PASSWORD);
    await user.click(screen.getByRole("button", { name: "Log in" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/plan"));
    expect(calls[0]?.body).toEqual({ login: "quiet-heron", password: PASSWORD });
  });

  it("announces a failed login", async () => {
    mockApi({ "POST /auth/login": { status: 401, body: { detail: "Wrong username, email or password." } } });
    const user = userEvent.setup();
    const router = renderAt("/login");
    await user.type(screen.getByLabelText("Username or email"), "quiet-heron");
    await user.type(screen.getByLabelText("Password"), "nope");
    await user.click(screen.getByRole("button", { name: "Log in" }));
    const message = await screen.findByText("Wrong username, email or password.");
    expect(message.closest("[role=alert]")).not.toBeNull();
    expect(router.state.location.pathname).toBe("/login");
  });

  it("resets a forgotten password with an emailed code", async () => {
    const calls = mockApi({
      "POST /auth/password-reset/start": { status: 202, body: { pending_id: "pend-9" } },
      "POST /auth/password-reset/finish": { status: 204 },
    });
    const user = userEvent.setup();
    renderAt("/login");
    await user.click(screen.getByRole("button", { name: "Forgot password?" }));
    expect(screen.getByRole("heading", { level: 2, name: "Reset your password" })).toHaveFocus();
    await user.type(screen.getByLabelText("Email address"), "student@uchicago.edu");
    await user.click(screen.getByRole("button", { name: "Send reset code" }));

    // The wording does not say whether the account exists.
    expect(await screen.findByText(/If an account uses that address/)).toBeInTheDocument();
    await user.type(screen.getByLabelText("6-digit code"), "654321");
    await user.type(screen.getByLabelText("New password"), "a brand new password");
    await user.type(screen.getByLabelText("Repeat new password"), "a brand new password");
    await user.click(screen.getByRole("button", { name: "Set new password" }));

    expect(await screen.findByRole("status")).toHaveTextContent("Your password is changed");
    expect(screen.getByRole("button", { name: "Log in" })).toBeInTheDocument();
    expect(calls.map((c) => [c.path, c.body])).toEqual([
      ["/auth/password-reset/start", { email: "student@uchicago.edu" }],
      ["/auth/password-reset/finish", { pending_id: "pend-9", code: "654321", new_password: "a brand new password" }],
    ]);
  });
});

describe("account", () => {
  it("asks a logged-out visitor to log in", async () => {
    mockApi({ "GET /auth/session": { status: 401, body: { detail: "Log in to continue." } } });
    renderAt("/account");
    expect(screen.getByRole("heading", { level: 1, name: "Account" })).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: "Log in" })).toHaveAttribute("href", "/login");
    expect(screen.queryByRole("button", { name: /Delete my account/ })).not.toBeInTheDocument();
  });

  it("changes the password, sending the CSRF token", async () => {
    const calls = mockApi({
      "GET /auth/session": { status: 200, body: SESSION },
      "POST /account/password": { status: 204 },
    });
    const user = userEvent.setup();
    renderAt("/account");
    const form = await screen.findByRole("form", { name: "Change password" });
    await user.type(within(form).getByLabelText("Current password"), PASSWORD);
    await user.type(within(form).getByLabelText("New password"), "a brand new password");
    await user.type(within(form).getByLabelText("Repeat new password"), "a brand new password");
    await user.click(within(form).getByRole("button", { name: "Change password" }));
    expect(await within(form).findByText(/Password changed/)).toBeInTheDocument();
    const call = calls.find((c) => c.path === "/account/password");
    expect(call?.body).toEqual({ current_password: PASSWORD, new_password: "a brand new password" });
    expect(call?.csrf).toBe("csrf-token-1");
    expect(calls.find((c) => c.method === "GET")?.csrf).toBeNull();
  });

  it("exports the account as a JSON download", async () => {
    mockApi({
      "GET /auth/session": { status: 200, body: SESSION },
      "GET /account/export": { status: 200, body: { account: SESSION.account, plans: [] } },
    });
    const createObjectURL = vi.fn((blob: Blob) => (expect(blob.type).toBe("application/json"), "blob:x"));
    vi.stubGlobal("URL", Object.assign(URL, { createObjectURL, revokeObjectURL: vi.fn() }));
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    const user = userEvent.setup();
    renderAt("/account");
    await user.click(await screen.findByRole("button", { name: "Download my data (JSON)" }));
    expect(await screen.findByText("Downloaded your account and 0 plans as JSON.")).toBeInTheDocument();
    expect(createObjectURL).toHaveBeenCalledOnce();
    expect(click).toHaveBeenCalledOnce();
    click.mockRestore();
  });

  it("deletes the account only after a posts choice and the password", async () => {
    const calls = mockApi({
      "GET /auth/session": { status: 200, body: SESSION },
      "POST /account/delete": (body) =>
        (body as { password: string }).password === PASSWORD
          ? { status: 204 }
          : { status: 403, body: { detail: "That password is wrong." } },
    });
    const user = userEvent.setup();
    const router = renderAt("/account");
    const form = await screen.findByRole("form", { name: "Delete account" });
    const submit = within(form).getByRole("button", { name: "Delete my account permanently" });

    await user.click(submit);
    expect(within(form).getByText("Choose what happens to your forum posts.")).toBeInTheDocument();
    expect(calls.filter((c) => c.path === "/account/delete")).toHaveLength(0);

    await user.click(within(form).getByRole("radio", { name: /Keep my posts, shown as “\[deleted account\]”/ }));
    await user.click(within(form).getByRole("radio", { name: "Delete my posts" }));
    await user.type(within(form).getByLabelText("Password, to confirm"), "wrong password");
    await user.click(submit);
    expect(await within(form).findByText("That password is wrong.")).toBeInTheDocument();

    await user.clear(within(form).getByLabelText("Password, to confirm"));
    await user.type(within(form).getByLabelText("Password, to confirm"), PASSWORD);
    await user.click(submit);
    await waitFor(() => expect(router.state.location.pathname).toBe("/"));
    const last = calls.filter((c) => c.path === "/account/delete").at(-1);
    expect(last?.body).toEqual({ password: PASSWORD, posts: "delete" });
    expect(last?.csrf).toBe("csrf-token-1");
  });

  it("logs out", async () => {
    const calls = mockApi({
      "GET /auth/session": { status: 200, body: SESSION },
      "POST /auth/logout": { status: 204 },
    });
    const user = userEvent.setup();
    const router = renderAt("/account");
    await user.click(await screen.findByRole("button", { name: "Log out" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/login"));
    expect(calls.find((c) => c.path === "/auth/logout")?.csrf).toBe("csrf-token-1");
  });
});

describe("privacy", () => {
  it("states plainly what is stored and the limits", () => {
    renderAt("/privacy");
    expect(screen.getByRole("heading", { level: 1, name: "Privacy" })).toBeInTheDocument();
    const table = screen.getByRole("table");
    for (const row of ["Email address", "Username, password hash (argon2id), plans", "Forum posts, comments, votes", "IP addresses", "Timestamps"]) {
      expect(within(table).getByRole("rowheader", { name: row })).toBeInTheDocument();
    }
    expect(within(table).getByText(/by anyone with access to the database/)).toBeInTheDocument();
    expect(screen.getByText(/has both the database and the server key can link a post to/)).toBeInTheDocument();
    expect(screen.getByText(/pseudonymous, not anonymous to the people who run Quarterly/)).toBeInTheDocument();
  });
});

describe("logging out on a shared computer", () => {
  it("forgets the companion's conversations, drafts and feed choices, but keeps plans", () => {
    localStorage.setItem("quarterly.ask.v1", "[]");
    localStorage.setItem("quarterly.companion.v1", "[]");
    localStorage.setItem("quarterly.commons.draft.reply-1", "half an answer");
    localStorage.setItem("quarterly.feed.saved", "[]");
    localStorage.setItem("quarterly.plans.v1", "{}");
    forgetPersonalDevice();
    expect(localStorage.getItem("quarterly.ask.v1")).toBeNull();
    expect(localStorage.getItem("quarterly.companion.v1")).toBeNull();
    expect(localStorage.getItem("quarterly.commons.draft.reply-1")).toBeNull();
    expect(localStorage.getItem("quarterly.feed.saved")).toBeNull();
    expect(localStorage.getItem("quarterly.plans.v1")).toBe("{}");
  });
});
