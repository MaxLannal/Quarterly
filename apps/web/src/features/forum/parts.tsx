import { useId, useState, type FormEvent, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { useAuthLinks } from "@/features/auth/next";
import { PageContainer, PageHeader } from "@/components/layout/page";
import { Button } from "@/components/ui/button";
import { Meter, RatingRing } from "@/features/courses/Glass";
import { Dialog } from "@/components/ui/dialog";
import { ArrowIcon } from "@/components/ui/icons";
import { ChoiceRow, Label, Textarea } from "@/components/ui/input";
import { ErrorText, Notice } from "@/components/ui/misc";
import { cn } from "@/lib/utils";
import { useReport, useVote, type RatingSummary, type TargetType, type VoteValue } from "./api";
import { plural } from "./format";
import { OPTIONAL_RATING_FIELDS, RATING_FIELDS, REPORT_REASONS } from "./rules";

/** Every forum page needs a login (SPEC sitemap). Shown instead of the page when logged out. */
export function LoginRequired({ title, eyebrow }: { title: string; eyebrow?: ReactNode }) {
  const authLinks = useAuthLinks();
  return (
    <PageContainer width="reading" as="section" className="sm:pt-16">
      <PageHeader eyebrow={eyebrow} title={title} size="md" />
      <div className="qg-tile qg-edge flex flex-col gap-6 p-7 sm:p-9">
        <p className="qg-kicker">Members only <span className="text-muted-soft">//</span> anonymous inside</p>
        <p className="text-body-md text-body [&_a]:text-primary [&_a]:underline [&_a]:underline-offset-2">
          Reviews and discussion are for logged-in students. <Link to={authLinks.login}>Log in</Link> or{" "}
          <Link to={authLinks.signup}>create an account</Link> with your uchicago.edu address. Other readers only ever see a
          pseudonym that is different on every page.
        </p>
      </div>
    </PageContainer>
  );
}

const fmt = (v: number | null | undefined, digits = 1) => (v == null ? "–" : v.toFixed(digits));

/** One rating fact: a mono label over a value, with a thin lit meter for its share. */
function Stat({ label, value, share }: { label: string; value: string; share?: number | null }) {
  return (
    <div className="flex min-w-0 flex-col gap-1.5 rounded-[18px] border border-hairline bg-white/[0.03] px-4 py-3.5 shadow-[inset_0_1px_0_rgb(255_255_255/0.06)]">
      <dt className="font-mono text-[10.5px] font-medium uppercase tracking-[0.16em] text-muted">{label}</dt>
      <dd className="text-title-sm tabular-nums text-ink">{value}</dd>
      {share != null && (
        <dd aria-hidden="true">
          <Meter share={share} />
        </dd>
      )}
    </div>
  );
}

/**
 * Averages over the visible reviews. Dark glass: the overall rating is a ring of red light with
 * the number in the display serif; the others are small glass tiles with lit meters.
 */
export function RatingStats({ ratings }: { ratings: RatingSummary }) {
  const n = ratings.n_reviews ?? 0;
  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-5">
        <RatingRing value={n ? ratings.overall : null} size={104} stroke={6}>
          <span aria-hidden="true" className="qg-numeral text-[42px]">
            {n ? fmt(ratings.overall) : "–"}
          </span>
        </RatingRing>
        <p className="text-caption text-muted">
          <span className="block font-mono text-[10.5px] font-medium uppercase tracking-[0.16em]">Overall</span>
          <span className="mt-1 block text-title-sm text-ink">{n ? `${fmt(ratings.overall)} / 5` : "–"}</span>
        </p>
      </div>
      <dl className="grid grid-cols-2 gap-2.5">
        <Stat label="Difficulty" value={n ? `${fmt(ratings.difficulty)} / 5` : "–"} share={n && ratings.difficulty != null ? ratings.difficulty / 5 : null} />
        <Stat label="Workload" value={n ? `${fmt(ratings.workload_hours)} h/wk` : "–"} share={n && ratings.workload_hours != null ? ratings.workload_hours / 20 : null} />
        <Stat
          label="Would recommend"
          value={n && ratings.recommend_rate != null ? `${Math.round(ratings.recommend_rate * 100)}%` : "–"}
          share={n && ratings.recommend_rate != null ? ratings.recommend_rate : null}
        />
        {ratings.pace != null && <Stat label="Pace (5 fast)" value={`${fmt(ratings.pace)} / 5`} share={ratings.pace / 5} />}
        {ratings.grading_strictness != null && <Stat label="Grading (5 strict)" value={`${fmt(ratings.grading_strictness)} / 5`} share={ratings.grading_strictness / 5} />}
      </dl>
    </div>
  );
}

/** Rating distribution bars: single series in maroon (DESIGN.md data visualization). */
export function RatingBars({ distribution }: { distribution: Record<string, number[]> }) {
  return (
    <div className="grid gap-6">
      {[...RATING_FIELDS, ...OPTIONAL_RATING_FIELDS.filter((f) => (distribution[f.key] ?? []).some((c) => c > 0))].map((field) => {
        const counts = distribution[field.key] ?? [0, 0, 0, 0, 0];
        // Bars are shares of all ratings (D11 FO-3), so 1 of 2 ratings draws half a bar.
        const total = counts.reduce((a, b) => a + b, 0);
        return (
          <figure key={field.key} className="min-w-0">
            <figcaption className="mb-2.5 font-mono text-[11px] font-medium uppercase tracking-[0.16em] text-body-strong">
              {field.label} <span className="font-sans font-normal normal-case tracking-normal text-muted">({plural(total, "rating")})</span>
            </figcaption>
            <ul className="flex flex-col gap-1.5">
              {[5, 4, 3, 2, 1].map((score) => {
                const count = counts[score - 1] ?? 0;
                return (
                  <li key={score} className="flex items-center gap-2 text-caption tabular-nums text-muted">
                    <span className="sr-only">{`${field.label} ${score}: ${plural(count, "rating")}`}</span>
                    <span aria-hidden="true" className="w-3 text-right">
                      {score}
                    </span>
                    <span aria-hidden="true" className="qg-meter flex-1">
                      <span style={{ width: `${(count / (total || 1)) * 100}%` }} />
                    </span>
                    <span aria-hidden="true" className="w-6 text-right">
                      {count}
                    </span>
                  </li>
                );
              })}
            </ul>
          </figure>
        );
      })}
    </div>
  );
}

/** Server-rendered, server-sanitized markdown (nh3 allow-list; see api/forum/markdown.py). */
export function PostBody({ html, className }: { html: string; className?: string }) {
  return (
    <div
      className={cn(
        "max-w-reading text-body-md text-body [overflow-wrap:anywhere]",
        "[&_p]:mb-3 [&_p:last-child]:mb-0 [&_ul]:mb-3 [&_ul]:list-disc [&_ul]:pl-6 [&_ol]:mb-3 [&_ol]:list-decimal [&_ol]:pl-6",
        "[&_a]:rounded-xs [&_a]:text-primary [&_a]:underline [&_a]:underline-offset-2 [&_a:hover]:text-primary-hover",
        "[&_blockquote]:mb-3 [&_blockquote]:border-l-2 [&_blockquote]:border-hairline-strong [&_blockquote]:pl-4 [&_blockquote]:text-muted",
        "[&_code]:rounded-xs [&_code]:bg-surface-strong [&_code]:px-1 [&_code]:font-mono [&_code]:text-caption [&_code]:text-ink",
        "[&_pre]:mb-3 [&_pre]:overflow-x-auto [&_pre]:rounded-md [&_pre]:bg-surface-strong [&_pre]:p-3 [&_pre_code]:bg-transparent [&_pre_code]:p-0",
        className,
      )}
      // Sanitized on the server (tag allow-list, no raw HTML, http(s) links only).
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}

/** Up/down vote with the net score. One vote per reader; pressing the same arrow again withdraws it. */
export function VoteControl({
  targetType,
  targetId,
  score,
  myVote,
  disabled,
  label,
}: {
  targetType: TargetType;
  targetId: number;
  score: number;
  myVote: VoteValue;
  disabled?: boolean;
  /** What is being voted on, for screen readers ("post by Quiet Heron"). */
  label: string;
}) {
  const [state, setState] = useState({ score, myVote });
  const [error, setError] = useState<string | null>(null);
  const vote = useVote();

  function cast(direction: 1 | -1) {
    const next: VoteValue = state.myVote === direction ? 0 : direction;
    const previous = state;
    setState({ score: state.score - state.myVote + next, myVote: next });
    setError(null);
    vote.mutate(
      { target_type: targetType, target_id: targetId, value: next },
      {
        onSuccess: (out) => setState({ score: out.score, myVote: out.my_vote }),
        onError: (e) => {
          setState(previous);
          setError(e.message);
        },
      },
    );
  }

  return (
    <div className="flex flex-col">
      <div className="flex items-center" role="group" aria-label={`Votes on ${label}`}>
        <Button
          variant="ghost"
          size="icon"
          aria-label="Upvote"
          aria-pressed={state.myVote === 1}
          disabled={disabled || vote.isPending}
          onClick={() => cast(1)}
          className={cn(state.myVote === 1 && "bg-primary-wash text-primary")}
        >
          <ArrowIcon className="-rotate-90" />
        </Button>
        <span className="min-w-6 text-center text-body-strong tabular-nums text-ink" aria-live="polite">
          <span className="sr-only">Score </span>
          {state.score}
        </span>
        <Button
          variant="ghost"
          size="icon"
          aria-label="Downvote"
          aria-pressed={state.myVote === -1}
          disabled={disabled || vote.isPending}
          onClick={() => cast(-1)}
          className={cn(state.myVote === -1 && "bg-primary-wash text-primary")}
        >
          <ArrowIcon className="rotate-90" />
        </Button>
      </div>
      {error && <ErrorText>{error}</ErrorText>}
    </div>
  );
}

/** Report a post or comment to the moderators. */
export function ReportDialog({
  open,
  onClose,
  targetType,
  targetId,
}: {
  open: boolean;
  onClose: () => void;
  targetType: TargetType;
  targetId: number;
}) {
  const [reason, setReason] = useState<string>("");
  const [details, setDetails] = useState("");
  const [problem, setProblem] = useState<string | null>(null);
  const report = useReport();
  const id = useId();

  function close() {
    setReason("");
    setDetails("");
    setProblem(null);
    report.reset();
    onClose();
  }

  function submit(e: FormEvent) {
    e.preventDefault();
    if (!reason) {
      setProblem("Choose a reason.");
      return;
    }
    setProblem(null);
    const text = details.trim() ? `${reason}: ${details.trim()}` : reason;
    report.mutate({ target_type: targetType, target_id: targetId, reason: text.slice(0, 1000) });
  }

  return (
    <Dialog
      open={open}
      onClose={close}
      title={`Report this ${targetType}`}
      description="Moderators read every report. The author is not told who reported it."
    >
      {report.isSuccess ? (
        <div className="flex flex-col gap-4">
          <Notice tone="success" role="status">
            Thanks. A moderator will look at it.
          </Notice>
          <div>
            <Button variant="outline" onClick={close}>
              Close
            </Button>
          </div>
        </div>
      ) : (
        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <fieldset className="flex flex-col gap-1">
            <legend className="mb-1 text-caption font-medium text-ink">Reason</legend>
            {REPORT_REASONS.map((r) => (
              <ChoiceRow key={r} type="radio" name={`${id}-reason`} value={r} checked={reason === r} onChange={() => setReason(r)}>
                {r}
              </ChoiceRow>
            ))}
          </fieldset>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor={`${id}-details`}>Details (optional)</Label>
            <Textarea id={`${id}-details`} rows={3} maxLength={900} value={details} onChange={(e) => setDetails(e.target.value)} />
          </div>
          {(problem || report.error) && <ErrorText>{problem ?? report.error?.message}</ErrorText>}
          <div className="flex flex-wrap gap-3">
            <Button type="submit" disabled={report.isPending}>
              {report.isPending ? "Sending…" : "Send report"}
            </Button>
            <Button type="button" variant="outline" onClick={close}>
              Cancel
            </Button>
          </div>
        </form>
      )}
    </Dialog>
  );
}
