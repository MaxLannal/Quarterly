import { useId, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { PageContainer, PageHeader } from "@/components/layout/page";
import { Button } from "@/components/ui/button";
import { Avatar } from "@/components/ui/card";
import { api, attempt, type AccountOut } from "@/features/auth/api";
import { signedOut, useSession } from "@/features/auth/session";
import { FormError, linkClass, Notice, PASSWORD_HINT, passwordProblem, TextField } from "@/features/auth/ui";

function ChangePassword() {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    setError(null);
    setNotice(null);
    const problem = current.length === 0 ? "Enter your current password." : passwordProblem(next, confirm);
    if (problem) {
      setError(problem);
      return;
    }
    setBusy(true);
    const result = await attempt(() =>
      api.POST("/account/password", { body: { current_password: current, new_password: next } }),
    );
    setBusy(false);
    if (!result.ok) {
      setError(result.message);
      return;
    }
    setCurrent("");
    setNext("");
    setConfirm("");
    setNotice("Password changed. Your other sessions were logged out.");
  }

  return (
    <form onSubmit={(e) => void onSubmit(e)} noValidate className="flex flex-col gap-5 rounded-xl border border-hairline bg-surface-card p-6 sm:p-8" aria-labelledby="change-password">
      <h2 id="change-password" className="font-display text-display-sm">
        Change password
      </h2>
      <TextField
        label="Current password"
        type="password"
        name="current-password"
        autoComplete="current-password"
        required
        value={current}
        onChange={(e) => setCurrent(e.target.value)}
      />
      <TextField
        label="New password"
        type="password"
        name="new-password"
        autoComplete="new-password"
        required
        value={next}
        onChange={(e) => setNext(e.target.value)}
        hint={PASSWORD_HINT}
      />
      <TextField
        label="Repeat new password"
        type="password"
        name="confirm-password"
        autoComplete="new-password"
        required
        value={confirm}
        onChange={(e) => setConfirm(e.target.value)}
      />
      <FormError message={error} />
      <Notice message={notice} />
      <Button type="submit" disabled={busy} className="self-start">
        {busy ? "Saving…" : "Change password"}
      </Button>
    </form>
  );
}

function ExportData({ account }: { account: AccountOut }) {
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function download() {
    setError(null);
    setNotice(null);
    setBusy(true);
    const result = await attempt(() => api.GET("/account/export"));
    setBusy(false);
    if (!result.ok) {
      setError(result.message);
      return;
    }
    const blob = new Blob([JSON.stringify(result.data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `quarterly-${account.username}.json`;
    document.body.append(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
    const count = result.data.plans?.length ?? 0;
    setNotice(`Downloaded your account and ${count} ${count === 1 ? "plan" : "plans"} as JSON.`);
  }

  return (
    <section aria-labelledby="export-data" className="flex flex-col gap-5 rounded-xl border border-hairline bg-surface-card p-6 sm:p-8">
      <h2 id="export-data" className="font-display text-display-sm">
        Export your data
      </h2>
      <p className="text-body-sm text-muted">Your account details and every plan, as one JSON file.</p>
      <FormError message={error} />
      <Notice message={notice} />
      <Button type="button" variant="outline" disabled={busy} onClick={() => void download()} className="self-start">
        {busy ? "Preparing…" : "Download my data (JSON)"}
      </Button>
    </section>
  );
}

function DeleteAccount() {
  const navigate = useNavigate();
  const groupId = useId();
  const [posts, setPosts] = useState<"keep" | "delete" | null>(null);
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    setError(null);
    if (posts === null) {
      setError("Choose what happens to your forum posts.");
      return;
    }
    if (password.length === 0) {
      setError("Enter your password to confirm.");
      return;
    }
    setBusy(true);
    const result = await attempt(() => api.POST("/account/delete", { body: { password, posts } }));
    setBusy(false);
    if (!result.ok) {
      setError(result.message);
      return;
    }
    signedOut();
    navigate("/");
  }

  const options = [
    {
      value: "keep" as const,
      label: "Keep my posts, shown as “[deleted account]”",
      detail: "Reviews and comments stay for other students, with no pseudonym and no link to you.",
    },
    {
      value: "delete" as const,
      label: "Delete my posts",
      detail:
        "Your reviews and threads are removed with the comments under them. A comment of yours that someone replied to is blanked instead.",
    },
  ];

  return (
    <form onSubmit={(e) => void onSubmit(e)} noValidate className="flex flex-col gap-5 rounded-xl border border-hairline bg-surface-card p-6 sm:p-8" aria-labelledby="delete-account">
      <h2 id="delete-account" className="font-display text-display-sm">
        Delete account
      </h2>
      <p className="text-body-sm text-body">
        This permanently removes your account, your email address, your plans and your sessions. It
        cannot be undone.
      </p>
      <fieldset className="flex flex-col gap-2">
        <legend className="text-body-sm font-medium">Your forum posts</legend>
        {options.map((option) => (
          <div key={option.value} className="flex items-start gap-3 rounded-lg border border-hairline px-4 py-2 has-[:checked]:border-primary has-[:checked]:bg-primary-wash">
            <input
              id={`${groupId}-${option.value}`}
              type="radio"
              name="posts"
              value={option.value}
              checked={posts === option.value}
              onChange={() => setPosts(option.value)}
              aria-describedby={`${groupId}-${option.value}-detail`}
              className="mt-3 size-5 shrink-0 cursor-pointer"
            />
            <div>
              <label
                htmlFor={`${groupId}-${option.value}`}
                className="flex min-h-11 cursor-pointer items-center text-body-sm font-medium text-ink"
              >
                {option.label}
              </label>
              <p id={`${groupId}-${option.value}-detail`} className="text-body-sm text-muted">
                {option.detail}
              </p>
            </div>
          </div>
        ))}
      </fieldset>
      <TextField
        label="Password, to confirm"
        type="password"
        name="delete-password"
        autoComplete="current-password"
        required
        value={password}
        onChange={(e) => setPassword(e.target.value)}
      />
      <FormError message={error} />
      <Button type="submit" variant="destructive" disabled={busy} className="self-start">
        {busy ? "Deleting…" : "Delete my account permanently"}
      </Button>
    </form>
  );
}

/** SPEC sitemap `/account`: change password, export, delete. */
export default function AccountPage() {
  const session = useSession();
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);

  async function logOut() {
    setBusy(true);
    await attempt(() => api.POST("/auth/logout"));
    setBusy(false);
    signedOut();
    navigate("/login");
  }

  return (
    <PageContainer width="reading" as="section" className="flex flex-col gap-6">
      <PageHeader title="Account" size="md" className="mb-4" />
      {session.status === "loading" ? (
        <p role="status" className="text-muted">
          Loading your account…
        </p>
      ) : null}
      {session.status === "anonymous" ? (
        <p>
          <Link to="/login" className={linkClass}>
            Log in
          </Link>{" "}
          to change your password, export your data or delete your account.
        </p>
      ) : null}
      {session.status === "authenticated" ? (
        <>
          <div className="flex flex-wrap items-center justify-between gap-4 rounded-xl border border-hairline bg-surface-card p-6 sm:px-8">
            <div className="flex items-center gap-3">
              <Avatar name={session.account.username} />
              <p>
                Logged in as <span className="font-medium">{session.account.username}</span>{" "}
                <span className="text-muted">(account created {dayInWords(session.account.created_day)})</span>
              </p>
            </div>
            <Button type="button" variant="outline" disabled={busy} onClick={() => void logOut()}>
              Log out
            </Button>
          </div>
          <ChangePassword />
          <ExportData account={session.account} />
          <DeleteAccount />
          <p className="text-body-sm">
            <Link to="/privacy" className={linkClass}>
              What Quarterly stores about you
            </Link>
          </p>
        </>
      ) : null}
    </PageContainer>
  );
}

/** "2026-11-16" as "Nov 16, 2026" (D11 polish); day-level dates only. */
function dayInWords(day: string): string {
  const [y, m, d] = day.split("-").map(Number);
  if (!y || !m || !d) return day;
  return new Date(Date.UTC(y, m - 1, d)).toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric", timeZone: "UTC" });
}
