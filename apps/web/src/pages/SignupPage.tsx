import { useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { keepNext, safeNext } from "@/features/auth/next";
import { inlineLinkClass } from "@/components/layout/page";
import { Button } from "@/components/ui/button";
import { ArrowIcon } from "@/components/ui/icons";
import { api, attempt } from "@/features/auth/api";
import { signedIn } from "@/features/auth/session";
import { AboutYouForm, type AboutSaved } from "@/features/profile/AboutYouForm";
import { useQuestions } from "@/features/profile/questions";
import {
  AuthPage,
  OrDivider,
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
  | { name: "account"; ticket: string }
  | { name: "about" }
  | { name: "next" };

const STEP_NUMBER = { email: 1, code: 2, account: 3, about: 4, next: 4 } as const;
const UCHICAGO = /^[^@\s]+@uchicago\.edu$/i;
const USERNAME = /^[A-Za-z0-9_-]{3,32}$/;

/** SPEC "Accounts and anonymity", protocol steps 1-3, then "About you" (Issue #16 step 1). */
export default function SignupPage() {
  const [params] = useSearchParams();
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
  // What step 4 saved, so that "Back" on the next screen shows it again.
  const [about, setAbout] = useState<AboutSaved | undefined>(undefined);

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
    // Step 4: the registration form (Issue #16), then the choice to answer more questions.
    setStep({ name: "about" });
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    if (step.name === "email") void sendCode(false);
    else if (step.name === "code") void submitCode(step.pendingId);
    else if (step.name === "account") void register(step.ticket);
  }

  // "Back" from step 2 or 3 opens step 1 with the email kept: a code works once, so step 3 has
  // no way back to step 2 (Richard, 2026-11-25).
  function startOver() {
    clearMessages();
    setCode("");
    setStep({ name: "email" });
  }

  return (
    <AuthPage
      title="Create an account"
      eyebrow={`Step ${STEP_NUMBER[step.name]} of 4`}
      wide={step.name === "about"}
      subline={
        STEP_NUMBER[step.name] === 4
          ? "Your account is ready. A few answers let the planner set up your plan."
          : "Use your @uchicago.edu email. It stays private: the forum only ever shows a random handle."
      }
    >
      {step.name === "email" || step.name === "code" || step.name === "account" ? (
      <form onSubmit={onSubmit} noValidate className="flex flex-col gap-5">
        {step.name === "email" ? (
          <>
            <StepHeading>Your UChicago email</StepHeading>
            <TextField
              label="Email address"
              icon="mail"
              type="email"
              name="email"
              autoComplete="email"
              inputMode="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              error={fieldError}
              hint="Only @uchicago.edu addresses. We email you a 6-digit code."
              placeholder="cnetid@uchicago.edu"
            />
            {/* D11 AU-1: one line before the button; the details are on the privacy page. */}
            <p className="text-body-sm text-muted">
              Other students never see your email; the forum shows a pseudonym.{" "}
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
            <BackButton disabled={busy} onClick={startOver} />
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
            <Button type="button" variant="outline" disabled={busy} onClick={() => void sendCode(true)}>
              Send a new code
            </Button>
          </>
        ) : null}

        {step.name === "account" ? (
          <>
            <BackButton disabled={busy} onClick={startOver} />
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
          </>
        ) : null}
      </form>
      ) : step.name === "about" ? (
        <AboutYouForm
          initial={about}
          onSaved={(saved) => {
            setAbout(saved);
            setStep({ name: "next" });
          }}
        />
      ) : (
        <MoreQuestions next={safeNext(params.get("next"))} onBack={() => setStep({ name: "about" })} />
      )}
      {step.name === "email" || step.name === "code" || step.name === "account" ? (
        <>
          <OrDivider />
          <p className="text-center text-body-sm text-body">
            Already have an account?{" "}
            <Link to={keepNext("/login", params.get("next"))} className={linkClass}>
              Log in
            </Link>
          </p>
        </>
      ) : null}
    </AuthPage>
  );
}

/** After "About you": the dashboard agent's questions now, or later (step 2 is optional). */
function MoreQuestions({ next, onBack }: { next: string; onBack: () => void }) {
  const navigate = useNavigate();
  const questions = useQuestions();
  const count = (questions.data?.questions ?? []).filter((q) => q.step === 2).length;
  return (
    <div className="flex flex-col gap-5">
      <BackButton onClick={onBack} />
      <StepHeading>A few more questions?</StepHeading>
      <p className="text-body-sm text-body">
        Your guide can ask {count ? `${count} short questions` : "a few short questions"} about your goals, your schedule and how you like to learn. The
        planner uses them too. Skip them if you like: you can answer them later on your dashboard.
      </p>
      <Button type="button" onClick={() => navigate("/me?guide=1")}>
        Answer a few more questions
      </Button>
      <Button type="button" variant="outline" onClick={() => navigate(next)}>
        Skip for now
      </Button>
    </div>
  );
}

/** "Back" to the step before, after a misclick (Richard, 2026-11-25). Not on step 1, and not on
 * step 4: step 3 made the account. */
function BackButton({ onClick, disabled }: { onClick: () => void; disabled?: boolean }) {
  return (
    <Button type="button" variant="ghost" size="sm" className="-ml-3 self-start" disabled={disabled} onClick={onClick}>
      <ArrowIcon className="rotate-180" />
      Back
    </Button>
  );
}
