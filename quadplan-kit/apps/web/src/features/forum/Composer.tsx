import { useId, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input, Label, Select, Textarea } from "@/components/ui/input";
import { ErrorText, Notice } from "@/components/ui/misc";
import { termLabel } from "@/features/planner/terms";
import { cn } from "@/lib/utils";
import { useCreatePost, useUpdatePost, type ForumPage, type Post, type PostKind, type ReviewRatings } from "./api";
import { COMMUNITY_RULES, GRADE_BUCKETS, RATING_FIELDS } from "./rules";

type Scale = 1 | 2 | 3 | 4 | 5;
type GradeBucket = NonNullable<ReviewRatings["grade_bucket"]>;

interface Draft {
  title: string;
  body: string;
  term: string;
  overall: Scale | null;
  difficulty: Scale | null;
  intellectual_intensity: Scale | null;
  workload: string;
  recommend: "yes" | "no" | "";
  grade: GradeBucket | "";
}

function draftFrom(post?: Post): Draft {
  const r = post?.ratings;
  return {
    title: post?.title ?? "",
    body: post?.body_md ?? "",
    term: post?.term_taken ?? "",
    overall: (r?.overall as Scale | undefined) ?? null,
    difficulty: (r?.difficulty as Scale | undefined) ?? null,
    intellectual_intensity: (r?.intellectual_intensity as Scale | undefined) ?? null,
    workload: r ? String(r.workload_hours) : "",
    recommend: r ? (r.would_recommend ? "yes" : "no") : "",
    grade: r?.grade_bucket ?? "",
  };
}

/** The community rules, shown beside every composer (SPEC "Moderation and community rules"). */
export function CommunityRules({ className }: { className?: string }) {
  return (
    <aside aria-label="Community rules" className={cn("rounded-xl border border-hairline bg-canvas-soft p-5", className)}>
      <p className="text-caption-uppercase uppercase text-muted">Community rules</p>
      <ul className="mt-2 flex list-disc flex-col gap-1 pl-5 text-body-sm text-body">
        {COMMUNITY_RULES.map((rule) => (
          <li key={rule}>{rule}</li>
        ))}
      </ul>
      <p className="mt-3 text-caption text-muted">
        Email addresses and phone numbers are removed automatically. Posts are checked before they appear.{" "}
        <Link to="/guidelines" className="text-primary underline underline-offset-2">
          Full guidelines
        </Link>
      </p>
    </aside>
  );
}

/** A 1–5 choice as a row of 44px pills (radio group). */
function ScaleField({
  name,
  label,
  low,
  high,
  value,
  onChange,
  invalid,
}: {
  name: string;
  label: string;
  low: string;
  high: string;
  value: Scale | null;
  onChange: (v: Scale) => void;
  invalid: boolean;
}) {
  return (
    <fieldset className="min-w-0">
      <legend className="mb-1.5 text-caption font-medium text-ink">
        {label} <span className="font-normal text-muted">(1 {low}, 5 {high})</span>
      </legend>
      <div className="flex flex-wrap gap-1">
        {([1, 2, 3, 4, 5] as const).map((n) => (
          <label
            key={n}
            className={cn(
              "flex min-h-11 min-w-11 cursor-pointer items-center justify-center rounded-pill border text-body-strong tabular-nums transition-colors",
              "has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-primary",
              value === n ? "border-primary bg-primary-wash text-primary" : "border-hairline-strong text-ink hover:bg-surface-strong",
              invalid && value === null && "border-error",
            )}
          >
            <input type="radio" name={name} value={n} checked={value === n} onChange={() => onChange(n)} className="sr-only" />
            <span aria-hidden="true">{n}</span>
            <span className="sr-only">{`${label} ${n} of 5`}</span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}

/**
 * Write a review (structured ratings and the term are required) or a discussion post, or edit
 * one's own post. Shows the community rules.
 */
export function Composer({
  page,
  kind,
  editing,
  onDone,
  onCancel,
}: {
  page: ForumPage;
  kind: PostKind;
  editing?: Post;
  onDone?: (post: Post) => void;
  onCancel?: () => void;
}) {
  const id = useId();
  const [draft, setDraft] = useState<Draft>(() => draftFrom(editing));
  const [tried, setTried] = useState(false);
  const [result, setResult] = useState<Post | null>(null);
  const create = useCreatePost(page.id);
  const update = useUpdatePost();
  const pending = create.isPending || update.isPending;
  const error = create.error ?? update.error;
  const review = kind === "review";
  const set = <K extends keyof Draft>(key: K, value: Draft[K]) => setDraft((d) => ({ ...d, [key]: value }));

  const workload = Number(draft.workload);
  const problems: string[] = [];
  if (review) {
    if (!draft.overall || !draft.difficulty || !draft.intellectual_intensity) problems.push("Give all three ratings.");
    if (draft.workload.trim() === "" || !Number.isFinite(workload) || workload < 0 || workload > 100)
      problems.push("Enter the hours per week outside class (0 to 100).");
    if (!draft.recommend) problems.push("Say whether you would recommend it.");
    if (!draft.term) problems.push("Pick the term you took it.");
  } else if (!draft.title.trim()) {
    problems.push("Give your post a title.");
  }
  if (!draft.body.trim()) problems.push(review ? "Write a few words about the course." : "Write your post.");

  function submit(e: FormEvent) {
    e.preventDefault();
    setTried(true);
    setResult(null);
    if (problems.length) return;
    const ratings: ReviewRatings | null = review
      ? {
          overall: draft.overall ?? 1,
          difficulty: draft.difficulty ?? 1,
          intellectual_intensity: draft.intellectual_intensity ?? 1,
          workload_hours: workload,
          would_recommend: draft.recommend === "yes",
          grade_bucket: draft.grade || null,
        }
      : null;
    const done = (post: Post) => {
      setTried(false);
      setResult(post);
      if (!editing) setDraft(draftFrom());
      onDone?.(post);
    };
    if (editing) {
      update.mutate(
        {
          id: editing.id,
          body: {
            title: review ? null : draft.title.trim(),
            body_md: draft.body,
            ...(review ? { ratings, term_taken: draft.term } : {}),
          },
        },
        { onSuccess: done },
      );
    } else {
      create.mutate(
        review
          ? { kind, body_md: draft.body, term_taken: draft.term, ratings, title: null }
          : { kind, body_md: draft.body, title: draft.title.trim() },
        { onSuccess: done },
      );
    }
  }

  const terms = page.terms_taught ?? [];
  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_280px]">
      <form onSubmit={submit} noValidate aria-label={editing ? "Edit your post" : review ? "Write a review" : "Start a discussion"} className="flex min-w-0 flex-col gap-5">
        {review ? (
          <>
            <div className="grid gap-5 sm:grid-cols-3">
              {RATING_FIELDS.map((f) => (
                <ScaleField
                  key={f.key}
                  name={`${id}-${f.key}`}
                  label={f.label}
                  low={f.low}
                  high={f.high}
                  value={draft[f.key]}
                  onChange={(v) => set(f.key, v)}
                  invalid={tried}
                />
              ))}
            </div>
            <div className="grid gap-5 sm:grid-cols-2">
              <div className="flex flex-col gap-1.5">
                <Label htmlFor={`${id}-workload`}>Workload: hours per week outside class</Label>
                <Input
                  id={`${id}-workload`}
                  type="number"
                  inputMode="decimal"
                  min={0}
                  max={100}
                  step={0.5}
                  value={draft.workload}
                  onChange={(e) => set("workload", e.target.value)}
                  aria-invalid={tried && (draft.workload.trim() === "" || workload < 0 || workload > 100) ? true : undefined}
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor={`${id}-term`}>Term you took it</Label>
                <Select id={`${id}-term`} value={draft.term} onChange={(e) => set("term", e.target.value)} aria-invalid={tried && !draft.term ? true : undefined}>
                  <option value="">Choose a term</option>
                  {terms.map((t) => (
                    <option key={t} value={t}>
                      {termLabel(t)}
                    </option>
                  ))}
                </Select>
              </div>
              <fieldset className="flex flex-col">
                <legend className="mb-1 text-caption font-medium text-ink">Would you recommend it?</legend>
                <div className="flex gap-4">
                  {(["yes", "no"] as const).map((v) => (
                    <label key={v} className="flex min-h-11 cursor-pointer items-center gap-2 text-body-sm text-ink">
                      <input
                        type="radio"
                        name={`${id}-recommend`}
                        value={v}
                        checked={draft.recommend === v}
                        onChange={() => set("recommend", v)}
                        className="size-5 cursor-pointer accent-primary"
                      />
                      {v === "yes" ? "Yes" : "No"}
                    </label>
                  ))}
                </div>
              </fieldset>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor={`${id}-grade`}>Grade received (optional)</Label>
                <Select id={`${id}-grade`} value={draft.grade} onChange={(e) => set("grade", e.target.value as GradeBucket | "")}>
                  <option value="">Not given</option>
                  {GRADE_BUCKETS.map((g) => (
                    <option key={g} value={g}>
                      {g === "prefer not to say" ? "Prefer not to say" : g}
                    </option>
                  ))}
                </Select>
              </div>
            </div>
          </>
        ) : (
          <div className="flex flex-col gap-1.5">
            <Label htmlFor={`${id}-title`}>Title</Label>
            <Input id={`${id}-title`} maxLength={200} value={draft.title} onChange={(e) => set("title", e.target.value)} aria-invalid={tried && !draft.title.trim() ? true : undefined} />
          </div>
        )}
        <div className="flex flex-col gap-1.5">
          <Label htmlFor={`${id}-body`}>{review ? "Your review" : "Your post"}</Label>
          <Textarea
            id={`${id}-body`}
            rows={6}
            maxLength={20000}
            value={draft.body}
            onChange={(e) => set("body", e.target.value)}
            aria-describedby={`${id}-body-hint`}
            aria-invalid={tried && !draft.body.trim() ? true : undefined}
          />
          <p id={`${id}-body-hint`} className="text-caption text-muted">
            Markdown works for **bold**, lists and links. No images.
          </p>
        </div>
        {tried && problems.length > 0 && (
          <div role="alert" className="flex flex-col gap-1">
            {problems.map((p) => (
              <ErrorText key={p}>{p}</ErrorText>
            ))}
          </div>
        )}
        {error && <ErrorText>{error.message}</ErrorText>}
        {result && result.status !== "visible" && (
          <Notice tone={result.status === "removed" ? "error" : "warning"} role="status">
            {result.moderation_note ?? "Your post is waiting for a moderator."}
          </Notice>
        )}
        {result && result.status === "visible" && !editing && (
          <Notice tone="success" role="status">
            Posted.
          </Notice>
        )}
        <div className="flex flex-wrap gap-3">
          <Button type="submit" disabled={pending}>
            {pending ? "Posting…" : editing ? "Save changes" : review ? "Post review" : "Post"}
          </Button>
          {onCancel && (
            <Button type="button" variant="outline" onClick={onCancel}>
              Cancel
            </Button>
          )}
        </div>
      </form>
      <CommunityRules className="self-start" />
    </div>
  );
}
