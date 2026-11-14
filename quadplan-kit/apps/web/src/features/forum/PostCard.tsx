import { useState } from "react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Avatar, Card } from "@/components/ui/card";
import { Badge, Dots, ErrorText, Notice } from "@/components/ui/misc";
import { termLabel } from "@/features/planner/terms";
import { useDeletePost, useReport, type ForumPage, type Post } from "./api";
import { Composer } from "./Composer";
import { relativeDay } from "./format";
import { PostBody, ReportDialog, VoteControl } from "./parts";

/** Pseudonym, day and badges: the post-card header. */
function Byline({ post }: { post: Post }) {
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
      <Avatar name={post.pseudonym} />
      <span className="text-body-strong text-ink">{post.pseudonym}</span>
      {post.mine && <Badge casing="normal">You</Badge>}
      <span className="text-caption text-muted">
        {relativeDay(post.created_day)}
        {post.edited_day ? " · edited" : ""}
      </span>
      {post.term_taken && <Badge casing="normal">Took it in {termLabel(post.term_taken)}</Badge>}
    </div>
  );
}

function ReviewFacts({ post }: { post: Post }) {
  const r = post.ratings;
  if (!r) return null;
  return (
    <dl className="flex flex-wrap gap-x-6 gap-y-2 text-caption text-muted">
      <div className="flex items-center gap-2">
        <dt>Overall</dt>
        <dd className="flex items-center gap-1.5 text-ink">
          <Dots value={r.overall} label="Overall" /> <span aria-hidden="true">{r.overall}</span>
        </dd>
      </div>
      <div className="flex items-center gap-2">
        <dt>Difficulty</dt>
        <dd className="flex items-center gap-1.5 text-ink">
          <Dots value={r.difficulty} label="Difficulty" /> <span aria-hidden="true">{r.difficulty}</span>
        </dd>
      </div>
      <div className="flex items-center gap-2">
        <dt>Intensity</dt>
        <dd className="flex items-center gap-1.5 text-ink">
          <Dots value={r.intellectual_intensity} label="Intellectual intensity" /> <span aria-hidden="true">{r.intellectual_intensity}</span>
        </dd>
      </div>
      <div className="flex items-center gap-2">
        <dt>Workload</dt>
        <dd className="text-ink tabular-nums">{r.workload_hours} h/wk</dd>
      </div>
      <div className="flex items-center gap-2">
        <dt className="sr-only">Recommendation</dt>
        <dd className="text-ink">{r.would_recommend ? "Would recommend" : "Would not recommend"}</dd>
      </div>
      {r.grade_bucket && r.grade_bucket !== "prefer not to say" && (
        <div className="flex items-center gap-2">
          <dt>Grade</dt>
          <dd className="text-ink">{r.grade_bucket}</dd>
        </div>
      )}
    </dl>
  );
}

/** In-place delete confirmation (DESIGN.md destructive button; DF-7). */
function DeleteButton({ postId, onDeleted }: { postId: number; onDeleted?: () => void }) {
  const [confirming, setConfirming] = useState(false);
  const del = useDeletePost();
  if (!confirming) {
    return (
      <Button variant="ghost" size="sm" onClick={() => setConfirming(true)}>
        Delete
      </Button>
    );
  }
  return (
    <span className="flex flex-wrap items-center gap-1" role="group" aria-label="Confirm delete">
      <span className="text-caption text-ink">Delete this post?</span>
      <Button variant="destructive" size="sm" disabled={del.isPending} onClick={() => del.mutate(postId, { onSuccess: onDeleted })}>
        Yes, delete
      </Button>
      <Button variant="ghost" size="sm" onClick={() => setConfirming(false)}>
        Cancel
      </Button>
      {del.error && <ErrorText>{del.error.message}</ErrorText>}
    </span>
  );
}

/**
 * post-card: one review or discussion post, with pseudonym, optional "took it in" badge, score,
 * Reply and Report. The author also gets Edit, Delete and, for a rejected post, "Ask for human
 * review". `threadHref` links the title and Reply to the thread view (absent on the thread).
 */
export function PostCard({
  post,
  page,
  threadHref,
  onReply,
  onDeleted,
  headingLevel = 3,
}: {
  post: Post;
  page: ForumPage;
  threadHref?: string;
  onReply?: () => void;
  onDeleted?: () => void;
  headingLevel?: 1 | 2 | 3;
}) {
  const [reporting, setReporting] = useState(false);
  const [editing, setEditing] = useState(false);
  const appeal = useReport();
  const Heading = (["h1", "h2", "h3"] as const)[headingLevel - 1] ?? "h3";
  const headingClass =
    headingLevel === 1 ? "font-display text-display-sm text-ink sm:text-display-md" : headingLevel === 2 ? "font-display text-display-sm text-ink" : "text-title-sm text-ink";
  const label = `${post.kind} by ${post.pseudonym}`;
  const title = post.title ?? (post.kind === "review" ? `Review by ${post.pseudonym}` : "Untitled post");
  const visible = post.status === "visible";

  if (editing) {
    return (
      <Card as="article" variant="post" aria-label={`Editing ${label}`} className="p-6 sm:p-8">
        <Composer page={page} kind={post.kind} editing={post} onDone={() => setEditing(false)} onCancel={() => setEditing(false)} />
      </Card>
    );
  }

  return (
    <Card as="article" variant="post" aria-labelledby={`post-${post.id}-title`} className="flex flex-col gap-4 p-6 sm:p-8">
      <Byline post={post} />
      <Heading id={`post-${post.id}-title`} className={headingClass}>
        {threadHref && visible ? (
          <Link to={threadHref} className="rounded-xs hover:text-primary hover:underline hover:underline-offset-4">
            {title}
          </Link>
        ) : (
          title
        )}
      </Heading>
      <ReviewFacts post={post} />
      {post.mine && post.moderation_note && (
        <Notice tone={post.status === "removed" ? "error" : "warning"}>
          <p>{post.moderation_note}</p>
        </Notice>
      )}
      <PostBody html={post.body_html ?? ""} />
      <div className="-mb-2 -ml-2 flex flex-wrap items-center gap-1">
        <VoteControl targetType="post" targetId={post.id} score={post.score} myVote={post.my_vote ?? 0} disabled={!visible} label={label} />
        {visible &&
          (threadHref ? (
            <Button variant="ghost" size="sm" asChild>
              <Link to={threadHref} aria-label={`Replies (${post.n_comments ?? 0}) to ${label}`}>
                Replies ({post.n_comments ?? 0})
              </Link>
            </Button>
          ) : (
            onReply && (
              <Button variant="ghost" size="sm" onClick={onReply}>
                Reply
              </Button>
            )
          ))}
        {!post.mine && visible && (
          <Button variant="ghost" size="sm" onClick={() => setReporting(true)} aria-label={`Report ${label}`}>
            Report
          </Button>
        )}
        {post.mine && post.status !== "removed" && (
          <Button variant="ghost" size="sm" onClick={() => setEditing(true)}>
            Edit
          </Button>
        )}
        {post.mine && post.status === "removed" && !post.moderation_note?.includes("asked for human review") && !post.moderation_note?.startsWith("Removed by a moderator") && (
          <Button
            variant="ghost"
            size="sm"
            disabled={appeal.isPending || appeal.isSuccess}
            onClick={() => appeal.mutate({ target_type: "post", target_id: post.id, reason: "The author asks for human review." })}
          >
            {appeal.isSuccess ? "Review requested" : "Ask for human review"}
          </Button>
        )}
        {post.mine && <DeleteButton postId={post.id} onDeleted={onDeleted} />}
      </div>
      {appeal.error && <ErrorText>{appeal.error.message}</ErrorText>}
      <ReportDialog open={reporting} onClose={() => setReporting(false)} targetType="post" targetId={post.id} />
    </Card>
  );
}
