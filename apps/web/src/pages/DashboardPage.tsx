import { useQuery } from "@tanstack/react-query";
import { useCallback, useEffect, useId, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useCatalogYears } from "@/api/hooks";
import type { NodeProgress, PlanState } from "@/api/types";
import { LoadingState, PageContainer, inlineLinkClass } from "@/components/layout/page";
import { Button, buttonVariants } from "@/components/ui/button";
import { Avatar } from "@/components/ui/card";
import { Notice } from "@/components/ui/misc";
import { useAuthLinks } from "@/features/auth/next";
import { downloadStudentMd, errorText, useProfile, type Profile, type TurnEvent } from "@/features/dashboard/api";
import "@/features/dashboard/dashboard.css";
import { GuideCard } from "@/features/dashboard/GuideCard";
import { GuideOverlay } from "@/features/dashboard/GuideOverlay";
import { memberSince, planSummary, programHref, programProgress, questionTurn } from "@/features/dashboard/logic";
import { CompletenessRing, DashCard, GuideMark, SaveStatus, useSaver } from "@/features/dashboard/parts";
import { useGuide } from "@/features/dashboard/useGuide";
import { loadPlans, type LocalPlan } from "@/features/planner/localPlans";
import { defaultCatalogYear, termLabel } from "@/features/planner/terms";
import { verifyPlan } from "@/features/planner/useVerify";
import { AnswerControl } from "@/features/profile/AnswerControls";
import { answerText, applies, questionsIn, remainingQuestions, useQuestions, valueOf, type Question, type QuestionSet } from "@/features/profile/questions";
import { useSession } from "@/lib/session";
import { cn } from "@/lib/utils";

/** The dashboard's frame: the full width of the page sheet, panels packed close together. */
const GRID = "mx-auto grid w-full max-w-[1760px] grid-cols-1 gap-3 p-3 sm:p-4 md:grid-cols-6 xl:grid-cols-12";

/** Where each General Information group sits in the grid. */
const GROUP_SPAN: Record<string, string> = {
  academic_background: "md:col-span-6 xl:col-span-7",
  goals: "md:col-span-6 xl:col-span-5",
  scheduling: "md:col-span-3 xl:col-span-6",
  learning_preferences: "md:col-span-3 xl:col-span-6",
};

/**
 * The personal dashboard (`/me`, Issue #16): who the student is and how far their programs are
 * on the plan, the General Information the planner uses for a first plan (answered in place or
 * through the dashboard agent), a read-only summary of the primary plan, and the export of
 * everything as `student.md`.
 */
export default function DashboardPage() {
  const session = useSession();
  if (session.isLoading) {
    return (
      <PageContainer>
        <LoadingState label="Opening your Quarterly" />
      </PageContainer>
    );
  }
  return session.data ? <Dashboard /> : <LoggedOut />;
}

function LoggedOut() {
  const links = useAuthLinks();
  return (
    <div className={GRID}>
      <section className="flex flex-col justify-center gap-4 rounded-[22px] border border-hairline bg-surface-card p-5 sm:p-7 md:col-span-6 xl:col-span-8">
        <p className="text-[12px] font-bold uppercase tracking-[0.08em] text-primary">Your Quarterly</p>
        <h1 className="font-display text-[40px] font-extrabold leading-[1.02] tracking-[-1.4px] text-ink sm:text-[52px]">
          Tell Quarterly <em>about you</em>.
        </h1>
        <p className="max-w-[40rem] text-body-md text-body">
          Your class year, programs and credits, and a few questions about your goals and your schedule. The planner uses your answers for a first plan; you can change or export them at any time.
        </p>
        <div className="flex flex-wrap gap-2">
          <Link to={links.signup} className={buttonVariants()}>
            Sign up
          </Link>
          <Link to={links.login} className={buttonVariants({ variant: "outline" })}>
            Log in
          </Link>
        </div>
      </section>
      <section aria-label="Your guide, for example" className="rounded-[22px] bg-surface-dark p-5 text-on-dark md:col-span-6 xl:col-span-4">
        <p className="flex items-center gap-2 text-[12px] font-bold uppercase tracking-[0.08em] text-on-dark-soft">
          <GuideMark size={14} className="text-primary" /> Your guide
        </p>
        <p className="mt-3 font-serif text-[20px] font-light leading-[1.35]">“How many courses do you want to take each quarter?”</p>
        <p className="mt-3 text-caption text-on-dark-soft">One question at a time, with the answers as buttons. Nothing is saved until you accept it.</p>
      </section>
      {[
        ["General Information", "Academic background, goals, scheduling and learning preferences: short answers the planner can use."],
        ["A guide that asks", "Answer a few questions now, or skip them and come back later. Change any answer in place."],
        ["Your plan, at a glance", "Your primary plan year by year, and how far each program is. Export everything as one Markdown file."],
      ].map(([title, text]) => (
        <section key={title} className="rounded-[22px] border border-hairline bg-surface-card p-4 sm:p-5 md:col-span-2 xl:col-span-4">
          <h2 className="font-display text-[21px] font-bold tracking-[-0.02em] text-ink">{title}</h2>
          <p className="mt-1.5 text-body-sm text-body">{text}</p>
        </section>
      ))}
      <div className="md:col-span-6 xl:col-span-12">
        <Preview />
      </div>
    </div>
  );
}

/** An illustration of a filled dashboard, blurred: what logging in opens. */
function Preview() {
  const rows: [string, string][] = [
    ["Class year", "Class of 2030"],
    ["Intended programs", "Computer Science, Mathematics"],
    ["Graduation pace", "On time"],
    ["Course load", "Normal"],
  ];
  return (
    <div aria-hidden="true" className="relative overflow-hidden rounded-[22px] border border-hairline bg-canvas-soft p-4 sm:p-6">
      <div className="dash-preview grid gap-3 md:grid-cols-[1.3fr_1fr]">
        <div className="rounded-xxl border border-hairline bg-surface-card p-6">
          <p className="font-display text-display-sm text-ink">General Information</p>
          <dl className="mt-4 grid gap-2">
            {rows.map(([k, v]) => (
              <div key={k} className="flex justify-between gap-3 rounded-lg bg-canvas-soft px-3 py-2 text-body-sm">
                <dt className="text-muted">{k}</dt>
                <dd className="text-ink">{v}</dd>
              </div>
            ))}
          </dl>
        </div>
        <div className="rounded-xxl bg-surface-dark p-6 text-on-dark">
          <p className="text-caption-uppercase uppercase text-on-dark-soft">Your guide</p>
          <p className="mt-3 font-serif text-[24px] font-light leading-snug">Which class formats do you like?</p>
          <div className="mt-4 flex flex-wrap gap-2">
            {["Seminar", "Lecture", "Lab", "Online"].map((w) => (
              <span key={w} className="rounded-pill border border-on-dark/25 px-3 py-1 text-body-sm">
                {w}
              </span>
            ))}
          </div>
        </div>
      </div>
      <div className="absolute inset-0 flex items-center justify-center bg-[radial-gradient(ellipse_at_center,color-mix(in_srgb,var(--color-canvas)_80%,transparent)_0%,transparent_70%)]">
        <p className="rounded-pill bg-surface-card px-5 py-2.5 text-body-sm text-ink shadow-overlay">Log in to open yours</p>
      </div>
    </div>
  );
}

function Dashboard() {
  const profile = useProfile(true);
  const questions = useQuestions();
  if (profile.isLoading) {
    return (
      <PageContainer>
        <LoadingState label="Opening your Quarterly" lines={4} />
      </PageContainer>
    );
  }
  if (profile.error || !profile.data) {
    return (
      <PageContainer>
        <Notice tone="error" role="alert">
          {errorText(profile.error)}{" "}
          <button type="button" className="underline underline-offset-2" onClick={() => void profile.refetch()}>
            Try again
          </button>
        </Notice>
      </PageContainer>
    );
  }
  return <DashboardBody profile={profile.data} questions={questions.data} questionsError={!!questions.error} />;
}

/** The primary plan on this device (the planner keeps logged-in plans here too). */
function primaryPlan(): LocalPlan | null {
  const doc = loadPlans();
  return doc.plans.find((p) => p.isPrimary) ?? doc.plans.find((p) => p.localId === doc.activeId) ?? doc.plans[0] ?? null;
}

/** The verifier's report for the primary plan (POST /verify, the call the planner makes on each
 * edit; no solver run), for the programs' progress. */
function usePlanReport(plan: PlanState | null) {
  const key = plan ? JSON.stringify(plan) : "";
  return useQuery({
    queryKey: ["dashboard", "verify", key],
    queryFn: ({ signal }) => verifyPlan(plan as PlanState, signal),
    enabled: !!plan && ((plan.programs?.length ?? 0) > 0 || (plan.items?.length ?? 0) > 0),
    staleTime: 60_000,
    retry: false,
  });
}

function DashboardBody({ profile, questions, questionsError }: { profile: Profile; questions: QuestionSet | undefined; questionsError: boolean }) {
  const guide = useGuide();
  const [open, setOpen] = useState(false);
  const [params, setParams] = useSearchParams();
  const years = useCatalogYears();
  const catalogYear = defaultCatalogYear(years.data?.map((y) => y.id));
  const [plan] = useState(primaryPlan);
  const report = usePlanReport(plan?.state ?? null);
  const left = remainingQuestions(questions, profile);

  const openGuide = useCallback(
    (options?: { seed?: TurnEvent | null; message?: string }) => {
      setOpen(true);
      guide.begin(options);
    },
    [guide],
  );
  const total = (questions?.questions ?? []).filter((q) => q.step === 2).length;
  const completeProfile = useCallback(() => {
    const next = left[0];
    openGuide(next ? { seed: questionTurn(next, total ? (total - left.length) / total : 0) } : undefined);
  }, [left, openGuide, total]);

  // `/me?guide=1` (after the registration form): open the guide once the questions are here.
  const wantsGuide = params.get("guide") === "1";
  useEffect(() => {
    if (!wantsGuide || !questions) return;
    setParams(
      (p) => {
        p.delete("guide");
        return p;
      },
      { replace: true },
    );
    completeProfile();
  }, [wantsGuide, questions, setParams, completeProfile]);

  const askAbout = (q: Question) => openGuide({ seed: questionTurn(q) });

  return (
    <>
      <div className={GRID}>
        <ProfileCard profile={profile} report={report.data?.progress} planPrograms={(plan?.state.programs ?? []).map((p) => p.program_id)} remaining={left.length} onComplete={completeProfile} />
        <div className="md:col-span-6 xl:col-span-4">
          <GuideCard profile={profile} questions={questions} onOpen={openGuide} />
        </div>

        <section aria-labelledby="general-info" className="flex flex-wrap items-center justify-between gap-3 rounded-[22px] border border-hairline bg-canvas-soft px-4 py-3 sm:px-5 md:col-span-6 xl:col-span-12">
          <div className="min-w-0">
            <h2 id="general-info" className="font-display text-[24px] font-bold tracking-[-0.02em] text-ink">
              General Information
            </h2>
            <p className="text-body-sm text-body">The planner uses these answers for your first plan. Change any of them here.</p>
          </div>
          <ExportButton />
        </section>

        {questionsError && (
          <div className="md:col-span-6 xl:col-span-12">
            <Notice tone="error" role="alert">
              The questions could not be loaded. Reload the page to try again.
            </Notice>
          </div>
        )}
        {(questions?.groups ?? []).map((group) => (
          <div key={group.id} className={GROUP_SPAN[group.id] ?? "md:col-span-6 xl:col-span-6"}>
            <DashCard title={group.title} level={3}>
              <ul className="flex flex-col divide-y divide-hairline">
                {questionsIn(questions, group.id)
                  .filter((q) => applies(q, profile))
                  .map((q) => (
                    <AnswerRow key={q.id} question={q} profile={profile} set={questions} catalogYear={catalogYear} onAsk={askAbout} />
                  ))}
              </ul>
            </DashCard>
          </div>
        ))}

        <div className="md:col-span-6 xl:col-span-12">
          <PlanCard plan={plan} report={report.data} verifying={report.isFetching} />
        </div>
      </div>

      <GuideOverlay
        open={open}
        onClose={() => {
          setOpen(false);
          guide.stop();
        }}
        guide={guide}
        profile={profile}
        questions={questions}
        catalogYear={catalogYear}
      />
    </>
  );
}

/** Top left: the student, their class year and email, their programs and how far each is on the
 * primary plan, and how much of the General Information is answered. */
function ProfileCard({ profile, report, planPrograms, remaining, onComplete }: { profile: Profile; report: NodeProgress[] | undefined; planPrograms: string[]; remaining: number; onComplete: () => void }) {
  const year = profile.class_year;
  return (
    <section aria-labelledby="dash-name" className="flex flex-col gap-4 rounded-[22px] border border-hairline bg-surface-card p-4 sm:p-5 md:col-span-6 xl:col-span-8">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex min-w-0 items-center gap-3">
          <Avatar name={profile.username} className="size-14 shrink-0 bg-primary-wash text-title-md text-primary" />
          <div className="min-w-0">
            <p className="text-[12px] font-bold uppercase tracking-[0.08em] text-primary">Profile</p>
            <h1 id="dash-name" className="font-display text-[30px] font-extrabold leading-[1.05] tracking-[-0.9px] text-ink sm:text-[38px]">
              {profile.username}, <em>{year ? `Class of ${year}` : "welcome"}</em>.
            </h1>
            <p className="truncate text-body-sm text-body">
              {profile.email} · {capitalize(memberSince(profile.member_since))}
            </p>
          </div>
        </div>
        <CompletenessRing value={profile.completeness} size={56} />
      </div>
      <div>
        <h2 className="text-[12px] font-bold uppercase tracking-[0.08em] text-muted">Intended programs and progress on your plan</h2>
        {profile.programs.length === 0 ? (
          <p className="mt-1 text-body-sm text-muted">None yet. Choose them under Academic background.</p>
        ) : (
          <ul className="mt-2 grid gap-2 sm:grid-cols-2">
            {profile.programs.map((p) => {
              const progress = programProgress(report, p.id);
              const onPlan = planPrograms.includes(p.id);
              const pct = progress && progress.need > 0 ? Math.min(100, Math.round((progress.have / progress.need) * 100)) : 0;
              return (
                <li key={p.id} className="flex flex-col gap-1 rounded-[14px] bg-canvas-soft px-3 py-2">
                  <Link to={programHref(p.id)} className={cn(inlineLinkClass, "inline-flex min-h-11 items-center text-body-sm")}>
                    {p.name}
                  </Link>
                  {progress ? (
                    <>
                      <div className="h-1.5 overflow-hidden rounded-pill bg-hairline" aria-hidden="true">
                        <div className="h-full rounded-pill bg-primary" style={{ width: `${pct}%` }} />
                      </div>
                      <p className="text-caption text-body">
                        {progress.satisfied ? "All requirements met on your plan" : `${progress.have} of ${progress.need} ${progress.unit === "units" ? "units" : "requirements"} on your plan`}
                      </p>
                    </>
                  ) : (
                    <p className="text-caption text-muted">{onPlan ? "Checking your plan…" : "Not on your plan yet"}</p>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </div>
      <div className="mt-auto flex flex-wrap items-center gap-2">
        {remaining > 0 ? (
          <Button onClick={onComplete}>
            <GuideMark size={14} /> Complete your profile
          </Button>
        ) : (
          <p className="text-body-sm text-body">Every question is answered.</p>
        )}
        <Link to="/plan" className={buttonVariants({ variant: "outline" })}>
          Open the planner
        </Link>
        {remaining > 0 && <span className="text-caption text-muted">{remaining} question{remaining === 1 ? "" : "s"} left</span>}
      </div>
    </section>
  );
}

function capitalize(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

/** One General Information answer: its label and value, changed in place with the control that
 * fits its type, or through the guide while the question is still open. */
function AnswerRow({ question, profile, set, catalogYear, onAsk }: { question: Question; profile: Profile; set: QuestionSet | undefined; catalogYear: string; onAsk: (q: Question) => void }) {
  const saver = useSaver();
  const [editing, setEditing] = useState(false);
  const editorId = useId();
  const text = answerText(question, profile, set);
  // The guide asks only the questions it has not covered yet (the server ignores the others).
  const askable = question.step === 2 && text === null && !profile.interview.covered.includes(question.id);
  return (
    <li className="flex flex-col gap-2 py-2.5 first:pt-0 last:pb-0">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <div className="min-w-0 flex-1 basis-[12rem]">
          <p className="text-[12px] font-bold uppercase tracking-[0.08em] text-muted">{question.label}</p>
          <p className={cn("text-body-sm", text === null ? "text-muted" : "text-ink")}>{text ?? "Not answered"}</p>
        </div>
        <SaveStatus state={saver.state} />
        <div className="flex flex-wrap items-center gap-1">
          <Button variant="outline" size="sm" aria-expanded={editing} aria-controls={editorId} onClick={() => setEditing(!editing)} aria-label={`${editing ? "Done with" : text === null ? "Answer" : "Change"} ${question.label}`}>
            {editing ? "Done" : text === null ? "Answer" : "Change"}
          </Button>
          {askable && (
            <Button variant="ghost" size="sm" className="text-primary" onClick={() => onAsk(question)} aria-label={`Ask the guide about ${question.label}`}>
              <GuideMark size={12} /> Ask the guide
            </Button>
          )}
        </div>
      </div>
      {editing && (
        <div id={editorId} className="rounded-[16px] border border-hairline bg-canvas-soft p-3">
          <AnswerControl
            question={question}
            set={set}
            value={valueOf(profile, question)}
            onChange={(value) => saver.save({ [question.field]: value })}
            classYear={profile.class_year}
            catalogYear={catalogYear}
            programNames={new Map(profile.programs.map((p) => [p.id, p.name]))}
            layout="panel"
          />
        </div>
      )}
    </li>
  );
}

/** "Export my information (.md)": GET /me/profile/export.md as a download. */
function ExportButton() {
  const [state, setState] = useState<{ kind: "idle" | "busy" } | { kind: "error"; message: string }>({ kind: "idle" });
  return (
    <div className="flex flex-wrap items-center gap-2">
      {state.kind === "error" && (
        <p role="alert" className="text-caption text-error">
          {state.message}
        </p>
      )}
      <Button
        variant="outline"
        disabled={state.kind === "busy"}
        onClick={() => {
          setState({ kind: "busy" });
          downloadStudentMd().then(
            () => setState({ kind: "idle" }),
            (e: unknown) => setState({ kind: "error", message: errorText(e) }),
          );
        }}
      >
        {state.kind === "busy" ? "Preparing…" : "Export my information (.md)"}
      </Button>
    </div>
  );
}

/** The primary plan, read-only (D3: the plan changes only on the planner). */
function PlanCard({ plan, report, verifying }: { plan: LocalPlan | null; report: { status: string; issues?: { level: string }[] } | undefined; verifying: boolean }) {
  if (!plan) {
    return (
      <DashCard kicker="Your plan" title="No plan yet" actions={<Link to="/plan" className={buttonVariants({ variant: "outline", size: "sm" })}>Set up your plan</Link>}>
        <p className="text-body-sm text-body">The planner sets up a first plan from your General Information.</p>
      </DashCard>
    );
  }
  const summary = planSummary(plan.state);
  const errors = report?.issues?.filter((i) => i.level === "error").length ?? 0;
  const warnings = report?.issues?.filter((i) => i.level === "warning").length ?? 0;
  const verdict = !report ? (verifying ? "Checking…" : null) : report.status === "valid" ? "Valid" : errors ? `${errors} error${errors === 1 ? "" : "s"}` : `${warnings} warning${warnings === 1 ? "" : "s"}`;
  return (
    <DashCard
      kicker="Your plan"
      title={plan.name}
      status={verdict && <span className="rounded-pill bg-surface-strong px-3 py-1 text-caption text-ink">{verdict}</span>}
      actions={
        <Link to="/plan" className={buttonVariants({ variant: "outline", size: "sm" })}>
          Open the planner
        </Link>
      }
    >
      <p className="mb-3 text-body-sm text-body">
        {termLabel(summary.entry)} to {termLabel(summary.graduation)} · {summary.courses} course{summary.courses === 1 ? "" : "s"}. Read only: change it on the planner.
      </p>
      {summary.courses === 0 ? (
        <p className="text-body-sm text-muted">No courses on it yet.</p>
      ) : (
        <ol className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4" aria-label="Your plan by year">
          {summary.years.map((y) => (
            <li key={y.year} className="rounded-[14px] bg-canvas-soft p-3">
              <h3 className="text-[12px] font-bold uppercase tracking-[0.08em] text-muted">Year {y.year}</h3>
              <dl className="mt-1 flex flex-col gap-1.5">
                {y.terms.map((t) => (
                  <div key={t.term}>
                    <dt className="text-caption text-muted">{termLabel(t.term)}</dt>
                    <dd className="text-body-sm tabular-nums text-ink">{t.courses.length ? t.courses.join(", ") : "—"}</dd>
                  </div>
                ))}
              </dl>
            </li>
          ))}
        </ol>
      )}
    </DashCard>
  );
}
