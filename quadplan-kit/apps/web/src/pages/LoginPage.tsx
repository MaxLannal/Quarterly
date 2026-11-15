import { useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { keepNext, safeNext } from "@/features/auth/next";
import { Button } from "@/components/ui/button";
import { api, attempt } from "@/features/auth/api";
import { signedIn } from "@/features/auth/session";
import {
  AuthPage,
  CODE_PATTERN,
  FormError,
  linkClass,
  Notice,
  PASSWORD_HINT,
  passwordProblem,
  StepHeading,
  TextField,
} from "@/features/auth/ui";

type View = { name: "login" } | { name: "reset-email" } | { name: "reset-code"; pendingId: string };

/** SPEC "Accounts and anonymity", steps 4 (login) and 5 (password reset). */
export default function LoginPage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [view, setView] = useState<View>({ name: "login" });
  const [login, setLogin] = useState("");
  const [password, setPassword] = useState("");
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [fieldError, setFieldError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function show(next: View, message: string | null = null) {
    setFieldError(null);
    setFormError(null);
    setNotice(message);
    setView(next);
  }

  async function submitLogin() {
    setFormError(null);
    setNotice(null);
    if (login.trim().length < 3 || password.length === 0) {
      setFormError("Enter your username or email, and your password.");
      return;
    }
    setBusy(true);
    const result = await attempt(() =>
      api.POST("/auth/login", { body: { login: login.trim(), password } }),
    );
    setBusy(false);
    if (!result.ok) {
      setFormError(result.message);
      return;
    }
    signedIn(result.data);
    navigate(safeNext(params.get("next")));
  }

  async function startReset() {
    setFieldError(null);
    setFormError(null);
    if (!/^[^@\s]+@[^@\s]+$/.test(email.trim())) {
      setFieldError("Enter the email address of your account.");
      return;
    }
    setBusy(true);
    const result = await attempt(() =>
      api.POST("/auth/password-reset/start", { body: { email: email.trim() } }),
    );
    setBusy(false);
    if (!result.ok) {
      setFormError(result.message);
      return;
    }
    setCode("");
    show({ name: "reset-code", pendingId: result.data.pending_id });
  }

  async function finishReset(pendingId: string) {
    setFieldError(null);
    setFormError(null);
    if (!CODE_PATTERN.test(code.trim())) {
      setFieldError("Enter the 6 digits from the email.");
      return;
    }
    const problem = passwordProblem(newPassword, confirm);
    if (problem) {
      setFormError(problem);
      return;
    }
    setBusy(true);
    const result = await attempt(() =>
      api.POST("/auth/password-reset/finish", {
        body: { pending_id: pendingId, code: code.trim(), new_password: newPassword },
      }),
    );
    setBusy(false);
    if (!result.ok) {
      setFormError(result.message);
      return;
    }
    setPassword("");
    setNewPassword("");
    setConfirm("");
    show({ name: "login" }, "Your password is changed and other sessions are logged out. Log in with the new password.");
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    if (view.name === "login") void submitLogin();
    else if (view.name === "reset-email") void startReset();
    else void finishReset(view.pendingId);
  }

  return (
    <AuthPage title="Log in">
      <form onSubmit={onSubmit} noValidate className="flex flex-col gap-5">
        {view.name === "login" ? (
          <>
            <Notice message={notice} />
            <TextField
              label="Username or email"
              name="username"
              autoComplete="username"
              autoCapitalize="none"
              spellCheck={false}
              required
              value={login}
              onChange={(e) => setLogin(e.target.value)}
            />
            <TextField
              label="Password"
              type="password"
              name="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            <FormError message={formError} />
            <Button type="submit" disabled={busy}>
              {busy ? "Logging in…" : "Log in"}
            </Button>
            <Button type="button" variant="ghost" onClick={() => show({ name: "reset-email" })}>
              Forgot password?
            </Button>
          </>
        ) : null}

        {view.name === "reset-email" ? (
          <>
            <StepHeading>Reset your password</StepHeading>
            <TextField
              label="Email address"
              type="email"
              name="email"
              autoComplete="email"
              inputMode="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              error={fieldError}
              hint="The @uchicago.edu address you signed up with."
            />
            <FormError message={formError} />
            <Button type="submit" disabled={busy}>
              {busy ? "Sending…" : "Send reset code"}
            </Button>
            <Button type="button" variant="ghost" disabled={busy} onClick={() => show({ name: "login" })}>
              Back to log in
            </Button>
          </>
        ) : null}

        {view.name === "reset-code" ? (
          <>
            <StepHeading>Choose a new password</StepHeading>
            <p className="text-body-sm">
              If an account uses that address, we sent it a 6-digit code. It expires in 10 minutes.
            </p>
            <TextField
              label="6-digit code"
              name="code"
              inputMode="numeric"
              autoComplete="one-time-code"
              maxLength={6}
              required
              value={code}
              onChange={(e) => setCode(e.target.value)}
              error={fieldError}
            />
            <TextField
              label="New password"
              type="password"
              name="new-password"
              autoComplete="new-password"
              required
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
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
            <FormError message={formError} />
            <Button type="submit" disabled={busy}>
              {busy ? "Saving…" : "Set new password"}
            </Button>
            <Button type="button" variant="ghost" disabled={busy} onClick={() => show({ name: "reset-email" })}>
              Send a new code
            </Button>
          </>
        ) : null}
      </form>
      <p className="border-t border-hairline pt-4 text-body-sm text-body">
        New here?{" "}
        <Link to={keepNext("/signup", params.get("next"))} className={linkClass}>
          Create an account
        </Link>
      </p>
    </AuthPage>
  );
}
