import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { EmptyState } from "@/components/layout/page";
import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";
import { ErrorText } from "@/components/ui/misc";
import { useSession } from "@/lib/session";
import { cn } from "@/lib/utils";
import {
  commonsKeys,
  useAccept,
  useCreateReply,
  useDeleteThread,
  useFollow,
  usePresence,
  useThread,
  useThreadPage,
  useTypingPing,
  useUpdateThread,
  type CourseRef,
  type Reply,
  type ThreadDetail,
} from "@/features/commons/api";
import { BotAnswerCard } from "@/features/commons/BotAnswer";
import { startBotRun } from "@/features/commons/botRuns";
import { Composer } from "@/features/commons/Composer";
import { CourseSearch } from "@/features/commons/CourseSearch";
import { Body, ConfirmDialog, CourseChip, Day, Handle, LoginCard, ReportDialog, TagChip, TypingDots, useToast, VoteControl } from "@/features/commons/parts";
import { ReplyTree, type ReplySort } from "@/features/commons/ReplyTree";
import { TagInput } from "@/features/commons/TagInput";
import { coursePath, plural, threadPath } from "@/features/commons/text";

function newest(replies: Reply[]): number {
  return replies.reduce((max, r) => Math.max(max, r.id, newest(r.children)), 0);
}

function humanCount(replies: Reply[]): number {
  return replies.reduce((n, r) => n + (r.kind === "human" && r.status === "visible" ? 1 : 0) + humanCount(r.children), 0);
}

function EditQuestion({ thread, onDone }: { thread: ThreadDetail; onDone: () => void }) {
  const update = useUpdateThread(thread.id);
  const [title, setTitle] = useState(thread.title);
  const [course, setCourse] = useState<CourseRef | null>(thread.course ?? null);
  const [tags, setTags] = useState(thread.tags);
  const short = title.trim().length < 8;
  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-col gap-1.5">
        <Label htmlFor={`edit-title-${thread.id}`}>Question</Label>
        <Input id={`edit-title-${thread.id}`} value={title} maxLength={160} onChange={(e) => setTitle(e.target.value)} aria-invalid={short || undefined} className="font-display text-title-md" />
        {short && <ErrorText>Write a title of at least 8 characters.</ErrorText>}
      </div>
      <Composer
        label="Details"
        initialValue={thread.body_md ?? ""}
        draftKey={`edit-thread-${thread.id}`}
        optional
        rows={5}
        submitLabel="Save changes"
        submittingLabel="Saving…"
        onSubmit={async (text) => {
          if (short) throw new Error("Write a title of at least 8 characters.");
          await update.mutateAsync({ title: title.trim(), body_md: text, course_code: course?.code ?? null, tags });
          onDone();
        }}
        onCancel={onDone}
      />
      <CourseSearch label="Course (optional)" value={course} onChange={setCourse} card />
      <TagInput value={tags} onChange={setTags} />
    </div>
  );
}

function Related({ thread }: { thread: ThreadDetail }) {
  const code = thread.course?.code;
  const related = useThreadPage({ sort: "top", course: code }, 6, !!code);
  const items = (related.data?.items ?? []).filter((t) => t.id !== thread.id).slice(0, 5);
  if (!code) return null;
  return (
    <section className="rounded-xl border border-hairline bg-canvas-soft p-5">
      <h2 className="text-caption-uppercase uppercase text-muted">More about {code}</h2>
      {items.length ? (
        <ul className="mt-2 flex flex-col">
          {items.map((t) => (
            <li key={t.id}>
              <Link to={threadPath(t.id)} className="flex min-h-11 items-center justify-between gap-3 rounded-xs py-1 text-body-sm text-ink hover:text-primary">
                <span className="min-w-0">{t.title}</span>
                <span className="shrink-0 text-caption text-muted">{plural(t.answer_count, "answer")}</span>
              </Link>
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-2 text-body-sm text-muted">No other questions about it yet.</p>
      )}
      <Link to={`/forum/new?course=${encodeURIComponent(code)}`} className="mt-2 inline-flex min-h-11 items-center text-caption font-medium text-primary underline underline-offset-2">
        Ask about {code}
      </Link>
    </section>
  );
}

export default function CommonsThreadPage() {
  const { id: raw } = useParams();
  const id = Number(raw);
  const { data: session } = useSession();
  const loggedIn = !!session;
  const location = useLocation();
  const navigate = useNavigate();
  const client = useQueryClient();
  const toast = useToast();
  const thread = useThread(id);
  const detail = thread.data;
  const live = detail && detail.status === "visible";
  const presence = usePresence(id, !!live);
  const ping = useTypingPing(id, loggedIn);
  const follow = useFollow(id);
  const accept = useAccept(id);
  const remove = useDeleteThread(id);
  const answer = useCreateReply(id);
  const [editing, setEditing] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [reporting, setReporting] = useState(false);
  const [sort, setSort] = useState<ReplySort>("top");
  const [highlight, setHighlight] = useState<number | null>(null);
  const [known, setKnown] = useState(0);
  const scrolled = useRef(false);

  const isAsker = !!detail?.is_mine;
  const humans = useMemo(() => (detail ? detail.replies.filter((r) => !(r.kind === "bot" && r.depth === 0)) : []), [detail]);
  const latestLoaded = detail ? Math.max(detail.last_reply_id ?? 0, newest(detail.replies)) : 0;
  useEffect(() => setKnown((k) => Math.max(k, latestLoaded)), [latestLoaded]);

  // #reply-12 in the address: scroll there once and highlight it.
  useEffect(() => {
    if (!detail || scrolled.current) return;
    const match = /^#reply-(\d+)$/.exec(location.hash);
    if (!match) return;
    scrolled.current = true;
    const target = Number(match[1]);
    window.setTimeout(() => {
      document.getElementById(`reply-${target}`)?.scrollIntoView({ block: "center" });
      setHighlight(target);
      window.setTimeout(() => setHighlight(null), 2600);
    }, 60);
  }, [detail, location.hash]);

  useEffect(() => {
    if (detail) document.title = `${detail.title} · The Commons · Quarterly`;
  }, [detail]);

  const p = presence.data;
  const fresh = p && p.latest_reply_id && p.latest_reply_id > known ? p.latest_reply_id : null;
  const freshCount = p && detail ? Math.max(p.reply_count - humanCount(detail.replies), 1) : 0;

  async function showNew() {
    const target = fresh;
    await client.invalidateQueries({ queryKey: commonsKeys.thread(id) });
    if (target) {
      setKnown(target);
      window.setTimeout(() => {
        document.getElementById(`reply-${target}`)?.scrollIntoView({ block: "center", behavior: "smooth" });
        setHighlight(target);
        window.setTimeout(() => setHighlight(null), 2600);
      }, 120);
    }
  }

  function onAccept(reply: Reply) {
    accept.mutate(reply.accepted ? null : reply.id, {
      onSuccess: () => toast.show(reply.accepted ? "Acceptance taken back" : "Marked as the accepted answer"),
      onError: (e) => toast.show(e.message),
    });
  }

  async function share() {
    const url = `${window.location.origin}${threadPath(id)}`;
    try {
      await navigator.clipboard.writeText(url);
      toast.show("Link copied");
    } catch {
      toast.show(url);
    }
  }

  if (!Number.isFinite(id) || id <= 0 || thread.isError) {
    return (
      <div className="mx-auto w-full max-w-reading px-4 pb-24 pt-12 sm:px-6">
        <EmptyState title="This question is not here">
          It may have been deleted, or the link is wrong. <Link to="/forum">Back to the Commons</Link>
        </EmptyState>
      </div>
    );
  }

  if (!detail) {
    return (
      <div className="mx-auto w-full max-w-content px-4 pb-24 pt-10 sm:px-6 lg:px-8" aria-busy="true">
        <p role="status" className="sr-only">
          Loading the question…
        </p>
        <div className="flex max-w-reading flex-col gap-4">
          <div className="skeleton h-4 w-32" />
          <div className="skeleton h-12 w-4/5" />
          <div className="skeleton h-24 w-full" />
          <div className="skeleton h-48 w-full" />
        </div>
      </div>
    );
  }

  if (detail.status !== "visible") {
    return (
      <div className="mx-auto w-full max-w-reading px-4 pb-24 pt-12 sm:px-6">
        <EmptyState title="You deleted this question">
          Nobody else can see it. <Link to="/forum">Back to the Commons</Link>
        </EmptyState>
      </div>
    );
  }

  const mentions = detail.mentions.filter((m) => m.code !== detail.course?.code);
  const typing = p?.typing ?? 0;

  return (
    <div className="mx-auto w-full max-w-content px-4 pb-24 pt-6 sm:px-6 sm:pt-10 lg:px-8">
      <nav aria-label="Breadcrumb" className="mb-4 flex flex-wrap items-center gap-x-2 text-caption text-muted">
        <Link to="/forum" className="inline-flex min-h-11 items-center hover:text-primary">
          ← The Commons
        </Link>
        {detail.course && (
          <>
            <span aria-hidden="true">/</span>
            <Link to={`/forum?course=${encodeURIComponent(detail.course.code)}`} className="inline-flex min-h-11 items-center hover:text-primary">
              {detail.course.code}
            </Link>
          </>
        )}
      </nav>
      <div className="grid gap-10 lg:grid-cols-[minmax(0,1fr)_300px]">
        <div className="flex min-w-0 flex-col gap-6">
          {/* The question */}
          <article aria-labelledby="question-title" className="flex gap-2 sm:gap-4">
            <div className="shrink-0 pt-1">
              <VoteControl targetType="thread" targetId={detail.id} score={detail.score} myVote={detail.my_vote} mine={detail.is_mine} loggedIn={loggedIn} label="the question" />
            </div>
            <div className="flex min-w-0 flex-1 flex-col gap-4">
              {editing ? (
                <EditQuestion
                  thread={detail}
                  onDone={() => {
                    setEditing(false);
                    toast.show("Question updated");
                  }}
                />
              ) : (
                <>
                  <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-caption text-muted">
                    <span className="text-caption-uppercase uppercase text-primary">Question</span>
                    <span aria-hidden="true">·</span>
                    asked by <Handle handle={detail.handle} op mine={detail.is_mine} />
                    <span aria-hidden="true">·</span>
                    <Day day={detail.created_day} edited={detail.edited_day} />
                  </p>
                  <h1 id="question-title" className="font-display text-[32px] font-bold leading-[1.1] tracking-[-0.5px] text-ink text-balance sm:text-[44px] sm:tracking-[-1px]">
                    {detail.title}
                  </h1>
                  {detail.body_html && <Body html={detail.body_html} className="max-w-reading" />}
                  {(detail.course || mentions.length > 0 || detail.tags.length > 0) && (
                    <div className="flex flex-wrap items-center gap-2">
                      {detail.course && <CourseChip course={detail.course} />}
                      {mentions.map((m) => (
                        <CourseChip key={m.code} course={m} className="border-hairline-strong bg-surface-card" />
                      ))}
                      {detail.tags.map((t) => (
                        <TagChip key={t} tag={t} to={`/forum?tag=${encodeURIComponent(t)}`} />
                      ))}
                    </div>
                  )}
                  <div className="-ml-2 flex flex-wrap items-center gap-1">
                    {loggedIn && (
                      <Button
                        variant="ghost"
                        size="sm"
                        aria-pressed={detail.following}
                        disabled={follow.isPending}
                        onClick={() =>
                          follow.mutate(!detail.following, {
                            onSuccess: (o) => toast.show(o.following ? "Following" : "Unfollowed"),
                          })
                        }
                        className={cn(detail.following && "text-primary")}
                      >
                        {detail.following ? "✓ Following" : "Follow"}
                      </Button>
                    )}
                    <Button variant="ghost" size="sm" onClick={() => void share()}>
                      Share
                    </Button>
                    {detail.is_mine && (
                      <>
                        <Button variant="ghost" size="sm" onClick={() => setEditing(true)}>
                          Edit
                        </Button>
                        <Button variant="ghost" size="sm" onClick={() => setConfirming(true)}>
                          Delete
                        </Button>
                      </>
                    )}
                    {loggedIn && !detail.is_mine && (
                      <Button variant="ghost" size="sm" onClick={() => setReporting(true)}>
                        Report
                      </Button>
                    )}
                  </div>
                </>
              )}
            </div>
          </article>

          <BotAnswerCard thread={detail} loggedIn={loggedIn} isAsker={isAsker} onAccept={onAccept} accepting={accept.isPending} />

          {/* The answers */}
          <section aria-labelledby="answers-title" className="flex flex-col gap-4 pt-4">
            <div className="flex flex-wrap items-end justify-between gap-3 border-b border-hairline pb-3">
              <h2 id="answers-title" className="font-display text-display-sm text-ink">
                {humans.length === 0 ? "No answers yet" : plural(detail.answer_count, "answer")}
                {detail.reply_count > detail.answer_count && <span className="ml-2 font-sans text-caption text-muted">and {plural(detail.reply_count - detail.answer_count, "comment")}</span>}
              </h2>
              {humans.length > 1 && (
                <div role="tablist" aria-label="Sort answers" className="flex gap-0.5">
                  {(
                    [
                      ["top", "Top"],
                      ["new", "New"],
                      ["old", "Oldest"],
                    ] as const
                  ).map(([key, label]) => (
                    <button
                      key={key}
                      type="button"
                      role="tab"
                      aria-selected={sort === key}
                      onClick={() => setSort(key)}
                      className={cn("inline-flex min-h-11 items-center rounded-pill px-3 text-caption font-medium", sort === key ? "bg-ink text-canvas" : "text-body hover:bg-surface-strong")}
                    >
                      {label}
                    </button>
                  ))}
                </div>
              )}
            </div>

            {fresh && (
              <button
                type="button"
                onClick={() => void showNew()}
                className="sticky top-3 z-10 mx-auto inline-flex min-h-11 animate-rise items-center gap-2 rounded-pill bg-primary px-5 text-button text-on-primary shadow-overlay hover:bg-primary-hover"
              >
                <span aria-hidden="true">↓</span>
                {plural(freshCount, "new reply", "new replies")} · show
              </button>
            )}

            {humans.length > 0 ? (
              <ReplyTree
                replies={humans}
                sort={sort}
                ctx={{
                  thread: detail,
                  loggedIn,
                  isAsker,
                  highlight,
                  onAccept,
                  accepting: accept.isPending,
                  onPosted: (rid) => setKnown((k) => Math.max(k, rid)),
                  toast: toast.show,
                  onTyping: ping,
                }}
              />
            ) : (
              <p className="text-body-sm text-muted">Be the first student to answer. Even “I had the same question” helps the asker.</p>
            )}

            <p aria-live="polite" className="flex min-h-6 items-center gap-2 text-caption text-muted">
              {typing > 0 && (
                <>
                  <TypingDots />
                  {typing === 1 ? "Someone is typing…" : `${typing} people are typing…`}
                </>
              )}
            </p>

            {loggedIn ? (
              <div id="your-answer" className="scroll-mt-24">
                <Composer
                  label="Your answer"
                  placeholder={isAsker ? "Add something, or thank whoever helped…" : "Share what you know. Mention courses by code; add @quarterly to ask the AI."}
                  draftKey={`thread-${detail.id}`}
                  rows={4}
                  summonHint
                  submitLabel="Post answer"
                  onTyping={ping}
                  onSubmit={async (text) => {
                    const out = await answer.mutateAsync({ body_md: text, parent_id: null });
                    setKnown((k) => Math.max(k, out.reply.id));
                    toast.show(out.summon_bot ? "Answer posted. Quarterly AI is on its way." : "Answer posted");
                    if (out.summon_bot) startBotRun(client, detail.id, { reply_to: out.reply.id });
                    window.setTimeout(() => document.getElementById(`reply-${out.reply.id}`)?.scrollIntoView({ block: "center", behavior: "smooth" }), 300);
                  }}
                />
              </div>
            ) : (
              <LoginCard>Log in to answer. Your name never shows: you get a random handle on each question.</LoginCard>
            )}
          </section>
        </div>

        <aside aria-label="About this question" className="flex flex-col gap-5 lg:sticky lg:top-8 lg:self-start">
          {detail.course && (
            <section className="relative overflow-hidden rounded-xl border border-hairline bg-surface-card p-5">
              <span aria-hidden="true" className="absolute inset-x-0 top-0 h-1 bg-primary" />
              <p className="text-caption font-semibold tabular-nums text-primary">{detail.course.code}</p>
              <p className="mt-1 font-display text-title-md font-bold text-ink tracking-[-0.02em]">{detail.course.title}</p>
              <Link to={coursePath(detail.course.code)} className="mt-2 inline-flex min-h-11 items-center text-caption font-medium text-primary underline underline-offset-2">
                Course page, reviews and planner
              </Link>
            </section>
          )}
          <Related thread={detail} />
          <section className="rounded-xl border border-hairline bg-canvas-soft p-5 text-body-sm text-body">
            <h2 className="text-caption-uppercase uppercase text-muted">In this thread</h2>
            <p className="mt-2">Everyone has a random handle that only exists here. The asker is marked OP.</p>
            <p className="mt-2">
              Be kind and specific. <Link to="/guidelines" className="text-primary underline underline-offset-2">Guidelines</Link>
            </p>
          </section>
        </aside>
      </div>

      <ConfirmDialog
        open={confirming}
        title="Delete your question?"
        description="It disappears for everyone, with its answers. This cannot be undone."
        confirmLabel="Delete question"
        pending={remove.isPending}
        error={remove.error?.message}
        onClose={() => setConfirming(false)}
        onConfirm={() => remove.mutate(undefined, { onSuccess: () => navigate("/forum", { state: { toast: "Question deleted" } }) })}
      />
      <ReportDialog open={reporting} onClose={() => setReporting(false)} targetType="thread" targetId={detail.id} />
      {toast.node}
    </div>
  );
}
