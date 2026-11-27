import { Link } from "react-router-dom";
import { cn } from "@/lib/utils";
import type { ThreadSummary } from "./api";
import { ArchGlyph, Body, CourseChip, Day, Handle, TagChip, VoteControl } from "./parts";
import { plural, threadPath } from "./text";

function Badge({ tone, children }: { tone: "answered" | "accepted" | "ai" | "open"; children: React.ReactNode }) {
  return (
    <span
      className={cn(
        "inline-flex min-h-6 items-center gap-1.5 rounded-pill px-2.5 font-mono text-[10.5px] font-medium uppercase tracking-[0.14em]",
        tone === "accepted" && "bg-success text-on-primary",
        tone === "answered" && "bg-success-wash text-success shadow-[inset_0_0_0_1px_rgb(185_214_144/0.25)]",
        tone === "ai" && "bg-primary-wash text-primary shadow-[inset_0_0_0_1px_rgb(255_120_140/0.3)]",
        tone === "open" && "border border-dashed border-hairline-strong text-muted",
      )}
    >
      {children}
    </span>
  );
}

/**
 * The AI's short answer under a question in the `/forum` list (issue #20, at most 60 words),
 * always labelled as written by an AI.
 */
function AiAnswer({ html, questionTitle }: { html: string; questionTitle: string }) {
  return (
    <section aria-label={`Quarterly AI's answer to “${questionTitle}”`} className="relative overflow-hidden rounded-[18px] bg-[linear-gradient(100deg,rgb(255_92_112/0.12),rgb(255_255_255/0.025)_55%)] py-3 pl-5 pr-4 shadow-[inset_0_0_0_1px_rgb(255_120_140/0.18)]"><span aria-hidden="true" className="absolute inset-y-3 left-0 w-px bg-primary shadow-[0_0_10px_rgb(255_92_112/0.8)]" />
      <p className="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-caption">
        <span className="inline-flex items-center gap-1 font-semibold text-ink">
          <ArchGlyph size={14} className="text-primary" />
          Quarterly AI
        </span>
        <span className="rounded-pill border border-primary/30 px-1.5 text-[11px] font-semibold uppercase tracking-[0.08em] text-primary">AI</span>
        <span className="text-muted">Written by an AI and can be wrong.</span>
      </p>
      <Body html={html} className="mt-1 text-body-sm" />
    </section>
  );
}

/** A question in the Commons list: votes, title, excerpt, course, tags, status and who asked. */
export function ThreadCard({
  thread,
  loggedIn,
  tagHref,
  aiAnswerHtml,
}: {
  thread: ThreadSummary;
  loggedIn: boolean;
  tagHref: (tag: string) => string;
  /** The AI's short answer, shown under the question (the `/forum` list). */
  aiAnswerHtml?: string | null;
}) {
  const titleId = `thread-${thread.id}-title`;
  return (
    <article
      aria-labelledby={titleId}
      data-spotlight="" className="qg-tile qg-tile-link group flex gap-2 py-5 pl-1 pr-5 sm:gap-5 sm:py-7 sm:pl-3 sm:pr-8"
    >
      <div className="shrink-0">
        <VoteControl
          targetType="thread"
          targetId={thread.id}
          score={thread.score}
          myVote={thread.my_vote}
          mine={thread.is_mine}
          loggedIn={loggedIn}
          label={`the question “${thread.title}”`}
        />
      </div>
      <div className="flex min-w-0 flex-1 flex-col gap-2 pt-1">
        <div className="flex flex-wrap items-center gap-2">
          {thread.accepted ? (
            <Badge tone="accepted">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" aria-hidden="true">
                <path d="M5 12.5l4.5 4.5L19 7.5" />
              </svg>
              Accepted answer
            </Badge>
          ) : thread.answered ? (
            <Badge tone="answered">Answered</Badge>
          ) : (
            <Badge tone="open">Waiting for a student</Badge>
          )}
          {thread.has_bot_answer && (
            <Badge tone="ai">
              <ArchGlyph size={13} />
              AI answered
            </Badge>
          )}
        </div>
        <h3 id={titleId} className="font-display text-[26px] leading-[1.15] tracking-[-0.2px] text-ink sm:text-[30px]">
          <Link to={threadPath(thread.id)} className="rounded-xs transition-colors duration-300 hover:text-primary-hover focus-visible:text-primary-hover">
            {thread.title}
          </Link>
        </h3>
        {thread.excerpt && <p className="line-clamp-2 text-body-sm text-body">{thread.excerpt}</p>}
        {aiAnswerHtml && <AiAnswer html={aiAnswerHtml} questionTitle={thread.title} />}
        <div className="flex flex-wrap items-center gap-x-2 gap-y-2 pt-1">
          {thread.course && <CourseChip course={thread.course} />}
          {thread.tags.map((t) => (
            <TagChip key={t} tag={t} to={tagHref(t)} />
          ))}
        </div>
        <p className="flex flex-wrap items-center gap-x-2 gap-y-1 border-t border-hairline pt-3 text-caption text-muted">
          <Link to={threadPath(thread.id)} className="inline-flex min-h-8 items-center gap-1.5 rounded-xs font-medium text-ink hover:text-primary">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" aria-hidden="true">
              <path d="M4 5h16v11H9l-5 4z" />
            </svg>
            {plural(thread.answer_count, "answer")}
            {thread.reply_count > thread.answer_count ? <span className="font-normal text-muted">· {plural(thread.reply_count - thread.answer_count, "comment")}</span> : null}
          </Link>
          <span aria-hidden="true">·</span>
          <span>
            asked by <Handle handle={thread.handle} mine={thread.is_mine} />
          </span>
          <span aria-hidden="true">·</span>
          <Day day={thread.created_day} edited={thread.edited_day} />
        </p>
      </div>
    </article>
  );
}

export function ThreadCardSkeleton() {
  return (
    <div aria-hidden="true" className="qg-tile flex gap-4 px-7 py-6">
      <div className="skeleton h-24 w-10" />
      <div className="flex flex-1 flex-col gap-3">
        <div className="skeleton h-5 w-28" />
        <div className="skeleton h-6 w-4/5" />
        <div className="skeleton h-4 w-full" />
        <div className="skeleton h-4 w-2/3" />
      </div>
    </div>
  );
}
