import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import { Button } from "@/components/ui/button";
import { Avatar } from "@/components/ui/card";
import { Label, Textarea } from "@/components/ui/input";
import { Badge, ErrorText, Notice } from "@/components/ui/misc";
import { cn } from "@/lib/utils";
import "@/features/courses/glass.css";
import { useCreateComment, type Comment } from "./api";
import { COLLAPSE_DEPTH, plural, relativeDay } from "./format";
import { PostBody, ReportDialog, VoteControl } from "./parts";

export interface CommentNode {
  comment: Comment;
  children: CommentNode[];
}

/** The API sends comments depth-first; rebuild the tree (order of siblings is kept). */
export function buildTree(comments: Comment[]): CommentNode[] {
  const nodes = new Map<number, CommentNode>();
  const roots: CommentNode[] = [];
  for (const c of comments) nodes.set(c.id, { comment: c, children: [] });
  for (const c of comments) {
    const node = nodes.get(c.id) as CommentNode;
    const parent = c.parent_id != null ? nodes.get(c.parent_id) : undefined;
    if (parent) parent.children.push(node);
    else roots.push(node);
  }
  return roots;
}

function countAll(nodes: CommentNode[]): number {
  return nodes.reduce((n, node) => n + 1 + countAll(node.children), 0);
}

/** Reply box: a top-level comment on the post, or a reply to one comment. */
export function CommentForm({
  postId,
  parentId,
  label = "Add a comment",
  onDone,
  onCancel,
  focusOnOpen,
}: {
  postId: number;
  parentId?: number | null;
  label?: string;
  onDone?: () => void;
  onCancel?: () => void;
  /** Focus the box when it opens (it opens on the reader's own "Reply" click). */
  focusOnOpen?: boolean;
}) {
  const id = useId();
  const box = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    if (focusOnOpen) box.current?.focus();
  }, [focusOnOpen]);
  const [body, setBody] = useState("");
  const [tried, setTried] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const create = useCreateComment(postId);

  function submit(e: FormEvent) {
    e.preventDefault();
    setTried(true);
    setNote(null);
    if (!body.trim()) return;
    create.mutate(
      { body_md: body, parent_id: parentId ?? null },
      {
        onSuccess: (c) => {
          setBody("");
          setTried(false);
          if (c.status !== "visible") setNote(c.moderation_note ?? "Your comment is waiting for a moderator.");
          else onDone?.();
        },
      },
    );
  }

  return (
    <form onSubmit={submit} noValidate className="flex flex-col gap-2" aria-label={label}>
      <Label htmlFor={`${id}-body`}>{label}</Label>
      <Textarea
        id={`${id}-body`}
        rows={3}
        maxLength={10000}
        ref={box}
        value={body}
        onChange={(e) => setBody(e.target.value)}
        aria-invalid={tried && !body.trim() ? true : undefined}
      />
      {tried && !body.trim() && <ErrorText>Write something first.</ErrorText>}
      {create.error && <ErrorText>{create.error.message}</ErrorText>}
      {note && (
        <Notice tone="warning" role="status">
          {note}
        </Notice>
      )}
      <div className="flex flex-wrap gap-2">
        <Button type="submit" variant="outline" disabled={create.isPending}>
          {create.isPending ? "Sending…" : "Comment"}
        </Button>
        {onCancel && (
          <Button type="button" variant="ghost" onClick={onCancel}>
            Cancel
          </Button>
        )}
      </div>
    </form>
  );
}

function CommentItem({ node, postId, canReply, unfolded }: { node: CommentNode; postId: number; canReply: boolean; unfolded: boolean }) {
  const c = node.comment;
  const [replying, setReplying] = useState(false);
  const [reporting, setReporting] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const visible = c.status === "visible";
  const placeholder = !visible && !c.mine;
  const label = `comment by ${c.pseudonym}`;
  // Replies one level below the fold are hidden until asked for (SPEC: collapse below depth 6).
  // Once a reader opens a folded branch, everything under it stays open.
  const foldChildren = c.depth + 1 >= COLLAPSE_DEPTH && node.children.length > 0 && !expanded && !unfolded;

  return (
    <li className="min-w-0">
      <article aria-label={placeholder ? "Hidden comment" : `Comment by ${c.pseudonym}`} className="py-4">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          {!placeholder && <Avatar name={c.pseudonym} />}
          <span className={cn("text-body-strong", placeholder ? "text-muted" : "text-ink")}>{c.pseudonym}</span>
          {c.mine && <Badge casing="normal">You</Badge>}
          <span className="font-mono text-[11px] uppercase tracking-[0.16em] text-muted">{relativeDay(c.created_day)}</span>
        </div>
        {c.mine && c.moderation_note && (
          <Notice tone={c.status === "removed" ? "error" : "warning"} className="mt-2">
            <p>{c.moderation_note}</p>
          </Notice>
        )}
        <PostBody html={c.body_html ?? ""} className={cn("mt-2", placeholder && "italic text-muted")} />
        {!placeholder && (
          <div className="-ml-2 mt-1 flex flex-wrap items-center gap-1">
            <VoteControl targetType="comment" targetId={c.id} score={c.score} myVote={c.my_vote ?? 0} disabled={!visible} label={label} />
            {visible && canReply && (
              <Button variant="ghost" size="sm" aria-expanded={replying} onClick={() => setReplying((r) => !r)} aria-label={`Reply to ${label}`}>
                Reply
              </Button>
            )}
            {visible && !c.mine && (
              <Button variant="ghost" size="sm" onClick={() => setReporting(true)} aria-label={`Report ${label}`}>
                Report
              </Button>
            )}
          </div>
        )}
        {replying && (
          <div className="mt-2 max-w-reading">
            <CommentForm
              postId={postId}
              parentId={c.id}
              label={`Reply to ${c.pseudonym}`}
              focusOnOpen
              onDone={() => {
                setReplying(false);
                setExpanded(true);
              }}
              onCancel={() => setReplying(false)}
            />
          </div>
        )}
        <ReportDialog open={reporting} onClose={() => setReporting(false)} targetType="comment" targetId={c.id} />
      </article>
      {node.children.length > 0 &&
        (foldChildren ? (
          <div className="qg-thread pl-4 sm:pl-6">
            <Button variant="link" size="sm" onClick={() => setExpanded(true)}>
              Continue this thread ({plural(countAll(node.children), "more reply", "more replies")})
            </Button>
          </div>
        ) : (
          <CommentList nodes={node.children} postId={postId} canReply={canReply} nested unfolded={unfolded || expanded} />
        ))}
    </li>
  );
}

export function CommentList({
  nodes,
  postId,
  canReply,
  nested = false,
  unfolded = false,
}: {
  nodes: CommentNode[];
  postId: number;
  canReply: boolean;
  nested?: boolean;
  unfolded?: boolean;
}) {
  return (
    <ul className={cn("flex flex-col", nested ? "qg-thread pl-4 sm:pl-6" : "divide-y divide-hairline")}>
      {nodes.map((node) => (
        <CommentItem key={node.comment.id} node={node} postId={postId} canReply={canReply} unfolded={unfolded} />
      ))}
    </ul>
  );
}

/** Nested comments of a thread: unlimited depth in storage, folded below depth 6 here. */
export function CommentTree({ comments, postId, canReply }: { comments: Comment[]; postId: number; canReply: boolean }) {
  const roots = buildTree(comments);
  if (roots.length === 0) return <p className="text-body-sm text-muted">No comments yet.</p>;
  return <CommentList nodes={roots} postId={postId} canReply={canReply} />;
}
