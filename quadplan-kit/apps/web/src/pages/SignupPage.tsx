import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { inlineLinkClass } from "@/components/layout/page";
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

type Step =
  | { name: "email" }
  | { name: "code"; pendingId: string }
  | { name: "account"; ticket: string };

const STEP_NUMBER = { email: 1, code: 2, account: 3 } as const;
const UCHICAGO = /^[^@\s]+@uchicago\.edu$/i;
const USERNAME = /^[A-Za-z0-9_-]{3,32}$/;

/** SPEC "Accounts and anonymity", protocol steps 1-3. */
export default function SignupPage() {
  const navigate = useNavigate();
  const [step, setStep] = useState<Step>({ name: "email" });
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [fieldError, setFieldError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function clearMessages() {
    setFieldError(null);
    setFormError(null);
    setNotice(null);
  }

  async function sendCode(resend: boolean) {
    clearMessages();
    if (!UCHICAGO.test(email.trim())) {
      setFieldError("Use your @uchicago.edu email address.");
      return;
    }
    setBusy(true);
    const result = await attempt(() => api.POST("/auth/email", { body: { email: email.trim() } }));
    setBusy(false);
    if (!result.ok) {
      setFormError(result.message);
      return;
    }
    setCode("");
    setStep({ name: "code", pendingId: result.data.pending_id });
    if (resend) setNotice("We sent a new code. Earlier codes still work until they expire.");
  }

  async function submitCode(pendingId: string) {
    clearMessages();
    if (!CODE_PATTERN.test(code.trim())) {
      setFieldError("Enter the 6 digits from the email.");
      return;
    }
    setBusy(true);
    const result = await attempt(() =>
      api.POST("/auth/verify-code", { body: { pending_id: pendingId, code: code.trim() } }),
    );
    setBusy(false);
    if (!result.ok) {
      setFormError(result.message);
      return;
    }
    setStep({ name: "account", ticket: result.data.ticket });
  }

  async function register(ticket: string) {
    clearMessages();
    if (!USERNAME.test(username)) {
      setFieldError("Use 3 to 32 letters, digits, hyphens or underscores.");
      return;
    }
    const problem = passwordProblem(password, confirm);
    if (problem) {
      setFormError(problem);
      return;
    }
    setBusy(true);
    const result = await attempt(() =>
      api.POST("/auth/register", { body: { ticket, username, password } }),
    );
    setBusy(false);
    if (!result.ok) {
      if (result.status === 409 && result.message.toLowerCase().includes("username")) {
        setFieldError(result.message);
      } else {
        setFormError(result.message);
      }
      return;
    }
    signedIn(result.data);
    navigate("/plan");
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    if (step.name === "email") void sendCode(false);
    else if (step.name === "code") void submitCode(step.pendingId);
    else void register(step.ticket);
  }

  function startOver() {
    clearMessages();
    setCode("");
    setStep({ name: "email" });
  }

  return (
    <AuthPage title="Create an account" eyebrow={`Step ${STEP_NUMBER[step.name]} of 3`}>
      <form onSubmit={onSubmit} noValidate className="flex flex-col gap-5">
        {step.name === "email" ? (
          <>
            <StepHeading>Your UChicago email</StepHeading>
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
              hint="Only @uchicago.edu addresses. We email you a 6-digit code."
            />
            <p className="text-body-sm text-muted">
              We store this address so you can reset your password. Other students never see it;
              forum posts use a separate pseudonym on each page.{" "}
              <Link to="/privacy" className={inlineLinkClass}>
                What we store
              </Link>
            </p>
            <FormError message={formError} />
            <Button type="submit" disabled={busy}>
              {busy ? "Sending…" : "Send code"}
            </Button>
          </>
        ) : null}

        {step.name === "code" ? (
          <>
            <StepHeading>Enter the code</StepHeading>
            <p className="text-body-sm">
              If <span className="font-medium text-ink">{email.trim()}</span> can be used for a new account,
              a 6-digit code is on its way. It expires in 10 minutes.
            </p>
            <Notice message={notice} />
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
            <FormError message={formError} />
            <Button type="submit" disabled={busy}>
              {busy ? "Checking…" : "Verify code"}
            </Button>
            <div className="flex flex-wrap gap-2">
              <Button type="button" variant="outline" disabled={busy} onClick={() => void sendCode(true)}>
                Send a new code
              </Button>
              <Button type="button" variant="ghost" disabled={busy} onClick={startOver}>
                Use a different email
              </Button>
            </div>
          </>
        ) : null}

        {step.name === "account" ? (
          <>
            <StepHeading>Choose a username and password</StepHeading>
            <TextField
              label="Username"
              name="username"
              autoComplete="username"
              autoCapitalize="none"
              spellCheck={false}
              required
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              error={fieldError}
              hint="For logging in. 3 to 32 letters, digits, hyphens or underscores. Forum posts do not show it."
            />
            <TextField
              label="Password"
              type="password"
              name="new-password"
              autoComplete="new-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              hint={PASSWORD_HINT}
            />
            <TextField
              label="Repeat password"
              type="password"
              name="confirm-password"
              autoComplete="new-password"
              required
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
            />
            <FormError message={formError} />
            <Button type="submit" disabled={busy}>
              {busy ? "Creating…" : "Create account"}
            </Button>
            <Button type="button" variant="ghost" disabled={busy} onClick={startOver}>
              Start again
            </Button>
          </>
        ) : null}
      </form>
      <p className="border-t border-hairline pt-4 text-body-sm text-body">
        Already have an account?{" "}
        <Link to="/login" className={linkClass}>
          Log in
        </Link>
      </p>
    </AuthPage>
  );
}
