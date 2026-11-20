/**
 * Quarterly AI's answer under a question: visually distinct (a maroon rule, the arch glyph,
 * "Written by an AI and can be wrong"). A pending question starts the bot when the card opens;
 * the live steps ("Reading CMSC 14100…") show while it works, then the answer fades in.
 */
import { useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { Button } from "@/components/ui/button";
import { ErrorText } from "@/components/ui/misc";
import { cn } from "@/lib/utils";
import type { Reply, ThreadDetail } from "./api";
import { botRunStarted, clearBotRun, runKey, startBotRun, useBotRun, type BotStep } from "./botRuns";
import { ArchGlyph, Body, CitationChips, Day, VoteControl } from "./parts";

function StepIcon({ status }: { status: BotStep["status"] }) {
  if (status === "done")
    return (
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" className="text-success" aria-hidden="true">
        <path d="M5 12.5l4.5 4.5L19 7.5" />
      </svg>
    );
  if (status === "failed")
    return (
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" className="text-error" aria-hidden="true">
        <path d="M6 6l12 12M18 6 6 18" />
      </svg>
    );
  return <span aria-hidden="true" className="inline-block size-2 animate-pulse rounded-pill bg-primary" />;
}

/** The live trace of a run: one line per tool call. */
export function BotSteps({ steps, busy }: { steps: BotStep[]; busy?: boolean }) {
  return (
    <div role="status" aria-live="polite" className="flex flex-col gap-2">
      <p className="flex items-center gap-2 text-body-sm text-ink">
        <span aria-hidden="true" className="inline-flex gap-[3px]">
          {[0, 1, 2].map((i) => (
            <span key={i} className="inline-block size-1.5 animate-typing rounded-pill bg-primary" style={{ animationDelay: `${i * 160}ms` }} />
          ))}
        </span>
        {busy ? "The AI is already answering this question…" : steps.length ? "Looking things up…" : "Reading the question…"}
      </p>
      {steps.length > 0 && (
        <ol className="flex flex-col gap-1.5 border-l border-hairline pl-4">
          {steps.map((s, i) => (
            <li key={`${s.tool}-${i}`} className="flex animate-rise items-center gap-2 text-caption text-body">
              <span className="inline-flex w-3.5 justify-center">
                <StepIcon status={s.status} />
              </span>
              <span className={cn(s.status === "started" && "text-ink")}>
                {s.label}
                {s.status === "started" ? "…" : ""}
              </span>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

function Header({ day, edited, compact }: { day?: string; edited?: string | null; compact?: boolean }) {
  return (
    <header className="flex flex-wrap items-center gap-x-3 gap-y-1">
      <span className={cn("inline-flex items-center justify-center rounded-pill bg-primary text-on-primary", compact ? "size-7" : "size-9")}>
        <ArchGlyph size={compact ? 16 : 20} />
      </span>
      <div className="flex min-w-0 flex-col">
        <span className="flex flex-wrap items-center gap-x-2 text-body-strong text-ink">
          Quarterly AI
          <span className="rounded-pill border border-primary/30 px-2 py-px text-[11px] font-semibold uppercase tracking-[0.08em] text-primary">AI</span>
        </span>
        <span className="text-caption text-muted">
          Written by an AI and can be wrong.
          {day ? (
            <>
              <span aria-hidden="true"> · </span>
              <Day day={day} edited={edited} />
            </>
          ) : null}
        </span>
      </div>
    </header>
  );
}

/** The bot's top answer card. */
export function BotAnswerCard({
  thread,
  loggedIn,
  isAsker,
  onAccept,
  accepting,
}: {
  thread: ThreadDetail;
  loggedIn: boolean;
  isAsker: boolean;
  onAccept: (reply: Reply) => void;
  accepting: boolean;
}) {
  const client = useQueryClient();
  const key = runKey(thread.id);
  const run = useBotRun(key);
  const stored = thread.replies.find((r) => r.kind === "bot" && r.depth === 0);
  const regenerating = run?.status === "running" && !!stored;

  // A question without an answer gets one as soon as anyone opens it.
  useEffect(() => {
    if (!stored && !botRunStarted(key) && thread.bot_state !== "off") startBotRun(client, thread.id);
  }, [client, key, stored, thread.bot_state, thread.id]);

  const reply = stored ?? (run?.status === "done" ? run.reply : undefined);
  const working = run && (run.status === "running" || run.status === "busy") && !reply;

  return (
    <section
      aria-labelledby={`bot-${thread.id}`}
      className="relative overflow-hidden rounded-xl border border-hairline bg-surface-card py-5 pl-6 pr-5 sm:py-6 sm:pl-8 sm:pr-7"
    >
      <span aria-hidden="true" className="absolute inset-y-0 left-0 w-1 bg-primary" />
      <span aria-hidden="true" className="pointer-events-none absolute -right-16 -top-20 size-56 rounded-pill bg-primary/5 blur-2xl" />
      <h2 id={`bot-${thread.id}`} className="sr-only">
        Quarterly AI's answer
      </h2>
      <div className="relative flex flex-col gap-4">
        <Header day={reply?.created_day} edited={reply?.edited_day} />
        {working && <BotSteps steps={run.steps} busy={run.status === "busy"} />}
        {run?.status === "error" && !reply && (
          <div className="flex flex-wrap items-center gap-3">
            <ErrorText>{run.error ?? "The AI could not answer right now."}</ErrorText>
            <Button
              variant="outline"
              onClick={() => {
                clearBotRun(key);
                startBotRun(client, thread.id);
              }}
            >
              Try again
            </Button>
          </div>
        )}
        {!run && !reply && <BotSteps steps={[]} />}
        {reply && (
          <div className={cn("flex flex-col gap-4", regenerating ? "opacity-50" : "animate-rise")}>
            {regenerating && run && <BotSteps steps={run.steps} />}
            <Body html={reply.body_html} />
            <CitationChips citations={reply.citations} />
            <div className="flex flex-wrap items-center gap-x-3 gap-y-2 border-t border-hairline pt-3">
              <VoteControl
                targetType="reply"
                targetId={reply.id}
                score={reply.score}
                myVote={reply.my_vote}
                mine={false}
                loggedIn={loggedIn}
                label="Quarterly AI's answer"
                layout="row"
              />
              {reply.accepted && <AcceptedMark />}
              {isAsker && (
                <Button variant="ghost" size="sm" disabled={accepting} onClick={() => onAccept(reply)} aria-pressed={reply.accepted}>
                  {reply.accepted ? "Unaccept" : "Accept this answer"}
                </Button>
              )}
              {isAsker && (
                <Button
                  variant="ghost"
                  size="sm"
                  disabled={run?.status === "running"}
                  onClick={() => {
                    clearBotRun(key);
                    startBotRun(client, thread.id, { regenerate: true });
                  }}
                >
                  {run?.status === "running" ? "Rewriting…" : "Regenerate"}
                </Button>
              )}
              <span className="text-caption text-muted">
                Follow up in a reply with <span className="font-medium text-primary">@quarterly</span>
              </span>
            </div>
            {run?.status === "error" && stored && <ErrorText>{run.error}</ErrorText>}
          </div>
        )}
      </div>
    </section>
  );
}

export function AcceptedMark() {
  return (
    <span className="inline-flex min-h-7 items-center gap-1 rounded-pill bg-success px-2.5 text-[12px] font-semibold text-on-dark">
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" aria-hidden="true">
        <path d="M5 12.5l4.5 4.5L19 7.5" />
      </svg>
      Accepted by the asker
    </span>
  );
}

/** A bot reply inside the tree (summoned with @quarterly), or its live run. */
export function BotReplyInline({ reply, steps, busy, error }: { reply?: Reply; steps?: BotStep[]; busy?: boolean; error?: string }) {
  return (
    <div className="relative overflow-hidden rounded-lg border border-hairline bg-canvas-soft py-3 pl-5 pr-4">
      <span aria-hidden="true" className="absolute inset-y-0 left-0 w-[3px] bg-primary" />
      <div className="flex flex-col gap-3">
        <Header compact day={reply?.created_day} edited={reply?.edited_day} />
        {reply ? (
          <div className="flex animate-rise flex-col gap-3">
            <Body html={reply.body_html} className="text-body-sm [&_p]:mb-2" />
            <CitationChips citations={reply.citations} />
          </div>
        ) : error ? (
          <ErrorText>{error}</ErrorText>
        ) : (
          <BotSteps steps={steps ?? []} busy={busy} />
        )}
      </div>
    </div>
  );
}
