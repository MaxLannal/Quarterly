/**
 * The replies under a question: a tree with thin thread lines, collapsible branches, inline reply
 * and edit composers, votes, accept (the asker), delete and report, and the AI's replies when a
 * reply summoned it with @quarterly (with its live steps while it works).
 */
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { cn } from "@/lib/utils";
import { useCreateReply, useDeleteReply, useUpdateReply, type Reply, type ThreadDetail } from "./api";
import { AcceptedMark, BotReplyInline } from "./BotAnswer";
import { runKey, startBotRun, useBotRun } from "./botRuns";
import { Composer } from "./Composer";
import { Body, ConfirmDialog, Day, Handle, ReportDialog, VoteControl } from "./parts";
import { plural } from "./text";

export type ReplySort = "top" | "new" | "old";

export interface TreeContext {
  thread: ThreadDetail;
  loggedIn: boolean;
  isAsker: boolean;
  highlight: number | null;
  onAccept: (reply: Reply) => void;
  accepting: boolean;
  onPosted: (replyId: number) => void;
  toast: (text: string) => void;
  onTyping: () => void;
}

const COLLAPSE_AT = 3;

function count(reply: Reply): number {
  return reply.children.reduce((n, c) => n + 1 + count(c), 0);
}

function contains(reply: Reply, id: number | null): boolean {
  if (id == null) return false;
  return reply.children.some((c) => c.id === id || contains(c, id));
}

export function sortReplies(replies: Reply[], sort: ReplySort): Reply[] {
  const out = [...replies];
  if (sort === "new") out.sort((a, b) => b.id - a.id);
  else if (sort === "old") out.sort((a, b) => a.id - b.id);
  else out.sort((a, b) => Number(b.accepted) - Number(a.accepted) || b.score - a.score || a.id - b.id);
  return out;
}

const AVATAR_TONES = ["bg-orb-lake/25 text-info", "bg-orb-goldenrod/30 text-warning", "bg-orb-ivy/35 text-success", "bg-orb-terracotta/30 text-warning", "bg-orb-rose/30 text-error", "bg-primary-wash text-primary"];

function Avatar({ handle }: { handle: string }) {
  const initials = handle
    .split(/\s+/)
    .filter((w) => /^[A-Za-z]/.test(w))
    .slice(0, 2)
    .map((w) => w[0])
    .join("");
  let h = 0;
  for (const ch of handle) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  return (
    <span aria-hidden="true" className={cn("inline-flex size-8 shrink-0 items-center justify-center rounded-pill text-[12px] font-semibold", AVATAR_TONES[h % AVATAR_TONES.length])}>
      {initials || "·"}
    </span>
  );
}

function SummonedRun({ threadId, replyId }: { threadId: number; replyId: number }) {
  const run = useBotRun(runKey(threadId, replyId));
  if (!run || (run.status === "done" && run.reply)) return null;
  if (run.status === "done") return null;
  return <BotReplyInline steps={run.steps} busy={run.status === "busy"} error={run.status === "error" ? run.error : undefined} />;
}

function ReplyItem({ reply, ctx }: { reply: Reply; ctx: TreeContext }) {
  const client = useQueryClient();
  const { thread } = ctx;
  const descendants = count(reply);
  const [collapsed, setCollapsed] = useState(() => reply.depth >= COLLAPSE_AT && descendants > 0 && !contains(reply, ctx.highlight));
  const [mode, setMode] = useState<"none" | "reply" | "edit">("none");
  const [confirming, setConfirming] = useState(false);
  const [reporting, setReporting] = useState(false);
  const create = useCreateReply(thread.id);
  const update = useUpdateReply(thread.id);
  const remove = useDeleteReply(thread.id);
  const visible = reply.status === "visible";
  const bot = reply.kind === "bot";
  const who = bot ? "Quarterly AI" : reply.handle;
  const childrenId = `reply-${reply.id}-children`;

  async function postReply(text: string) {
    const out = await create.mutateAsync({ body_md: text, parent_id: reply.id });
    setMode("none");
    ctx.onPosted(out.reply.id);
    ctx.toast(out.summon_bot ? "Reply posted. Quarterly AI is on its way." : "Reply posted");
    if (out.summon_bot) startBotRun(client, thread.id, { reply_to: out.reply.id });
  }

  return (
    <li id={`reply-${reply.id}`} className="relative scroll-mt-24">
      <div className={cn("flex gap-3 rounded-lg transition-colors duration-700", ctx.highlight === reply.id && "bg-primary-wash/70 ring-2 ring-primary/30")}>
        <div className="flex shrink-0 flex-col items-center pt-1">
          {bot ? (
            <span aria-hidden="true" className="inline-flex size-8 items-center justify-center rounded-pill bg-primary text-[11px] font-semibold text-on-primary">
              AI
            </span>
          ) : visible ? (
            <Avatar handle={reply.handle} />
          ) : (
            <span aria-hidden="true" className="inline-flex size-8 items-center justify-center rounded-pill border border-dashed border-hairline-strong" />
          )}
          {reply.children.length > 0 && !collapsed && (
            <button
              type="button"
              onClick={() => setCollapsed(true)}
              aria-label={`Collapse the ${plural(descendants, "reply", "replies")} under ${who}`}
              aria-expanded="true"
              aria-controls={childrenId}
              className="group mt-1 flex w-11 flex-1 justify-center"
            >
              <span className="w-px bg-hairline-strong transition-colors group-hover:w-0.5 group-hover:bg-primary" />
            </button>
          )}
        </div>
        <div className="min-w-0 flex-1 pb-2">
          {bot ? (
            <BotReplyInline reply={reply} />
          ) : (
            <>
              <p className="flex flex-wrap items-center gap-x-2 gap-y-1 pt-1.5 text-caption">
                {visible ? <Handle handle={reply.handle} op={reply.is_op} mine={reply.is_mine} /> : <span className="text-muted">[deleted]</span>}
                <span aria-hidden="true" className="text-muted">
                  ·
                </span>
                <Day day={reply.created_day} edited={visible ? reply.edited_day : null} />
                {reply.accepted && <AcceptedMark />}
              </p>
              {mode === "edit" ? (
                <Composer
                  className="mt-2"
                  label={`Edit your reply`}
                  labelHidden
                  initialValue={reply.body_md ?? ""}
                  draftKey={`edit-${reply.id}`}
                  focusOnMount
                  submitLabel="Save"
                  submittingLabel="Saving…"
                  onSubmit={async (text) => {
                    await update.mutateAsync({ id: reply.id, body_md: text });
                    setMode("none");
                    ctx.toast("Reply updated");
                  }}
                  onCancel={() => setMode("none")}
                />
              ) : (
                <Body html={reply.body_html} className={cn("mt-1 text-body-sm sm:text-body-md", !visible && "italic text-muted")} />
              )}
            </>
          )}
          {visible && mode !== "edit" && (
            <div className="-ml-2 mt-1 flex flex-wrap items-center gap-x-0.5">
              <VoteControl
                targetType="reply"
                targetId={reply.id}
                score={reply.score}
                myVote={reply.my_vote}
                mine={reply.is_mine}
                loggedIn={ctx.loggedIn}
                label={`${who}'s reply`}
                layout="row"
              />
              <Action onClick={() => setMode(mode === "reply" ? "none" : "reply")} pressed={mode === "reply"} disabled={!ctx.loggedIn} title={ctx.loggedIn ? undefined : "Log in to reply"}>
                Reply
              </Action>
              {ctx.isAsker && reply.depth === 0 && !reply.is_mine && (
                <Action onClick={() => ctx.onAccept(reply)} pressed={reply.accepted} disabled={ctx.accepting}>
                  {reply.accepted ? "Unaccept" : "Accept"}
                </Action>
              )}
              {reply.is_mine && !bot && (
                <>
                  <Action onClick={() => setMode("edit")}>Edit</Action>
                  <Action onClick={() => setConfirming(true)}>Delete</Action>
                </>
              )}
              {ctx.loggedIn && !reply.is_mine && <Action onClick={() => setReporting(true)}>Report</Action>}
            </div>
          )}
          {mode === "reply" && (
            <Composer
              className="mt-2"
              label={`Reply to ${who}`}
              labelHidden
              placeholder={`Reply to ${who}…`}
              draftKey={`reply-${reply.id}`}
              focusOnMount
              rows={3}
              summonHint
              submitLabel="Reply"
              onTyping={ctx.onTyping}
              onSubmit={postReply}
              onCancel={() => setMode("none")}
            />
          )}
          <div className="mt-2 empty:hidden">
            <SummonedRun threadId={thread.id} replyId={reply.id} />
          </div>
          {reply.children.length > 0 &&
            (collapsed ? (
              <button
                type="button"
                onClick={() => setCollapsed(false)}
                aria-expanded="false"
                aria-controls={childrenId}
                className="mt-1 inline-flex min-h-11 items-center gap-2 rounded-pill px-2 text-caption font-medium text-primary hover:bg-primary-wash"
              >
                <span aria-hidden="true" className="inline-flex size-5 items-center justify-center rounded-xs border border-primary/40 text-[13px] leading-none">
                  +
                </span>
                {plural(descendants, "more reply", "more replies")}
              </button>
            ) : (
              <ol id={childrenId} className="mt-1 flex flex-col gap-1">
                {sortReplies(reply.children, "old").map((child) => (
                  <ReplyItem key={child.id} reply={child} ctx={ctx} />
                ))}
              </ol>
            ))}
        </div>
      </div>
      <ConfirmDialog
        open={confirming}
        title="Delete this reply?"
        description="It shows as [deleted]; replies under it stay. This cannot be undone."
        confirmLabel="Delete reply"
        pending={remove.isPending}
        error={remove.error?.message}
        onClose={() => setConfirming(false)}
        onConfirm={() =>
          remove.mutate(reply.id, {
            onSuccess: () => {
              setConfirming(false);
              ctx.toast("Reply deleted");
            },
          })
        }
      />
      <ReportDialog open={reporting} onClose={() => setReporting(false)} targetType="reply" targetId={reply.id} />
    </li>
  );
}

function Action({ children, onClick, pressed, disabled, title }: { children: React.ReactNode; onClick: () => void; pressed?: boolean; disabled?: boolean; title?: string }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={pressed}
      disabled={disabled}
      title={title}
      className={cn(
        "inline-flex min-h-11 items-center rounded-pill px-2.5 text-caption font-medium text-muted transition-colors hover:bg-surface-strong hover:text-ink disabled:cursor-not-allowed disabled:opacity-50",
        pressed && "bg-surface-strong text-ink",
      )}
    >
      {children}
    </button>
  );
}

export function ReplyTree({ replies, sort, ctx }: { replies: Reply[]; sort: ReplySort; ctx: TreeContext }) {
  return (
    <ol className="flex flex-col gap-3">
      {sortReplies(replies, sort).map((r) => (
        <ReplyItem key={r.id} reply={r} ctx={ctx} />
      ))}
    </ol>
  );
}
