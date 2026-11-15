import { useState } from "react";
import { Link } from "react-router-dom";
import { EmptyState, inlineLinkClass, LoadingState, PageContainer, PageHeader, tallTargetClass } from "@/components/layout/page";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { FieldError, FieldHint, Label, Select, Textarea } from "@/components/ui/input";
import { Badge, ErrorText, Notice, type Tone } from "@/components/ui/misc";
import { LoginRequired } from "@/features/forum/parts";
import { plural } from "@/features/forum/format";
import { useSession } from "@/features/auth/session";
import { usePublishVersion, useReviewDecision, useReviewItems, type ReviewCheck, type ReviewItem, type ReviewNode, type ReviewStatus } from "@/features/review/api";
import { cn } from "@/lib/utils";

const TITLE = "Curator console";

const TYPE_LABELS: Record<string, string> = {
  program_version: "Program rules",
  requisite: "Prerequisite",
  course_batch: "Courses",
  ingest_run: "Ingestion run",
  catalog_change: "Catalog change",
};

const STATUSES: { value: ReviewStatus; label: string }[] = [
  { value: "open", label: "Waiting for a decision" },
  { value: "accepted", label: "Accepted" },
  { value: "rejected", label: "Rejected" },
];

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}
function asStrings(value: unknown): string[] {
  return Array.isArray(value) ? value.map((v) => (typeof v === "string" ? v : JSON.stringify(v))) : [];
}
function text(value: unknown): string | null {
  return typeof value === "string" && value ? value : null;
}

/** What "Edit" starts from, and the key the API expects it under (`edited.rules` / `edited.prereq`). */
function editable(item: ReviewItem): { key: "rules" | "prereq" | "content"; value: unknown } | null {
  const diff = asRecord(item.diff);
  if (item.target_type === "program_version") return item.program_version_id != null ? { key: "rules", value: diff.rules ?? {} } : null;
  if (item.target_type === "requisite") return { key: "prereq", value: diff.proposed ?? { any: [] } };
  if (item.target_type === "course_batch") return null;
  return { key: "content", value: {} };
}

function CheckList({ checks }: { checks: ReviewCheck[] }) {
  if (!checks.length) return null;
  return (
    <ul aria-label="Checks" className="flex flex-wrap gap-2">
      {checks.map((c) => {
        const tone: Tone = c.skipped ? "neutral" : c.ok ? "success" : "warning";
        return (
          <li key={c.id}>
            <Badge tone={tone} casing="normal" icon={!c.skipped}>
              ({c.id}) {c.name}: {c.skipped ? "not run" : c.ok ? "passed" : "look"}
            </Badge>
          </li>
        );
      })}
    </ul>
  );
}

function NodeRow({ node }: { node: ReviewNode }) {
  const flags = node.flags ?? [];
  return (
    <li className="grid gap-3 border-t border-hairline py-4 md:grid-cols-2 md:gap-6">
      <div className="min-w-0">
        <p className="break-words font-mono text-caption text-muted">{node.path}</p>
        <p className="text-body-sm text-ink">
          {node.label ? <span className="font-medium">{node.label}: </span> : null}
          {node.summary}
        </p>
        {flags.length > 0 && (
          <ul className="mt-2 flex flex-col gap-1">
            {flags.map((f) => (
              <li key={f}>
                <Badge tone="warning" casing="normal">
                  {f}
                </Badge>
              </li>
            ))}
          </ul>
        )}
      </div>
      <figure className="min-w-0">
        {node.quote ? (
          <blockquote className="border-l-2 border-hairline-strong pl-3 text-body-sm text-body">“{node.quote}”</blockquote>
        ) : (
          <p className="text-body-sm text-error">No source quote.</p>
        )}
        {node.url && /^https?:\/\//i.test(node.url) && (
          <figcaption className="mt-1 text-caption text-muted">
            <a href={node.url} className={inlineLinkClass} target="_blank" rel="noreferrer noopener">
              Source page
            </a>
            {node.snapshot_id ? ` · snapshot ${node.snapshot_id}` : ""}
          </figcaption>
        )}
      </figure>
    </li>
  );
}

/** The content of a non-program item: what the pipeline found, in plain words. */
function ItemDetail({ item }: { item: ReviewItem }) {
  const diff = asRecord(item.diff);
  if (item.target_type === "requisite") {
    const errors = asStrings(diff.errors);
    return (
      <div className="grid gap-3 md:grid-cols-2 md:gap-6">
        <div>
          <p className="text-caption text-muted">Proposed</p>
          <p className="text-body-sm text-ink">{text(diff.proposed_text) ?? "Nothing the checks could accept."}</p>
          {errors.length > 0 && (
            <ul className="mt-2 list-disc pl-5 text-body-sm text-body">
              {errors.map((e) => (
                <li key={e}>{e}</li>
              ))}
            </ul>
          )}
        </div>
        <blockquote className="border-l-2 border-hairline-strong pl-3 text-body-sm text-body">“{text(diff.raw_text) ?? ""}”</blockquote>
      </div>
    );
  }
  if (item.target_type === "course_batch") {
    const added = asStrings(diff.added);
    const removed = asStrings(diff.removed);
    const changed = Array.isArray(diff.changed) ? diff.changed.length : 0;
    return (
      <p className="text-body-sm text-body">
        {plural(added.length, "new course")}, {plural(changed, "changed course")}, {plural(removed.length, "removed course")}.
        {added.length > 0 && ` New: ${added.slice(0, 12).join(", ")}${added.length > 12 ? "…" : ""}.`}
        {removed.length > 0 && ` Removed: ${removed.slice(0, 12).join(", ")}.`}
      </p>
    );
  }
  const problems = asStrings(diff.problems);
  const changedPages = Array.isArray(diff.changed) ? diff.changed.map((c) => text(asRecord(c).url) ?? "") : [];
  const lines = [...problems, ...changedPages.filter(Boolean)];
  return lines.length ? (
    <ul className="list-disc pl-5 text-body-sm text-body">
      {lines.slice(0, 20).map((p) => (
        <li key={p} className="break-words">
          {p}
        </li>
      ))}
    </ul>
  ) : null;
}

function ReviewCard({ item, onDone }: { item: ReviewItem; onDone: (message: string) => void }) {
  const decide = useReviewDecision();
  const publish = usePublishVersion();
  const edit = editable(item);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const [parseError, setParseError] = useState<string | null>(null);
  const nodes = item.nodes ?? [];
  const id = `review-${item.id}`;
  const busy = decide.isPending || publish.isPending;
  const open = item.status === "open";
  const canPublish = item.program_version_id != null && item.program_version_status === "review" && item.status === "accepted";

  function act(decision: "accept" | "reject") {
    decide
      .mutateAsync({ id: item.id, body: { decision } })
      .then(() =>
        onDone(
          decision === "reject"
            ? `Rejected: ${item.title}.`
            : item.program_version_id != null
              ? `Accepted: ${item.title}. Choose "Accepted" under Show to publish it.`
              : `Accepted: ${item.title}.`,
        ),
      )
      .catch(() => undefined); // shown by decide.error
  }

  function saveEdit() {
    if (!edit) return;
    let parsed: unknown;
    try {
      parsed = JSON.parse(draft);
    } catch {
      setParseError("This is not valid JSON.");
      return;
    }
    setParseError(null);
    decide
      .mutateAsync({ id: item.id, body: { decision: "edit", edited: { [edit.key]: parsed } } })
      .then(() => onDone(`Saved your edit: ${item.title}.`))
      .catch(() => undefined);
  }

  function doPublish() {
    if (item.program_version_id == null) return;
    publish
      .mutateAsync(item.program_version_id)
      .then((v) => onDone(`Published ${v.program_id} ${v.catalog_year}. Students now see these rules.`))
      .catch(() => undefined);
  }

  return (
    <Card as="article" aria-labelledby={`${id}-title`} className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge>{TYPE_LABELS[item.target_type] ?? item.target_type}</Badge>
        {item.decision_hint === "carry_over" && (
          <Badge tone="success" casing="normal">
            Unchanged since last year
          </Badge>
        )}
        {item.program_version_status && (
          <Badge tone={item.program_version_status === "published" ? "success" : "neutral"} casing="normal" icon={item.program_version_status === "published"}>
            Version: {item.program_version_status}
          </Badge>
        )}
        {!open && (
          <Badge tone={item.status === "accepted" ? "success" : "error"} casing="normal">
            {item.status === "accepted" ? "Accepted" : "Rejected"}
            {item.decided_at ? ` ${item.decided_at}` : ""}
          </Badge>
        )}
      </div>
      <div>
        <h2 id={`${id}-title`} className="text-title-sm text-ink">
          {item.title || `${item.target_type} ${item.target_id}`}
        </h2>
        {item.reason && <p className="text-body-sm text-body">{item.reason}</p>}
      </div>
      <CheckList checks={item.checks ?? []} />
      {nodes.length > 0 ? (
        <section aria-label="Rule tree with source quotes">
          <div className="hidden grid-cols-2 gap-6 pb-2 text-caption-uppercase uppercase text-muted md:grid">
            <span>Rule</span>
            <span>Source quote</span>
          </div>
          <ul>
            {nodes.map((n) => (
              <NodeRow key={n.path} node={n} />
            ))}
          </ul>
        </section>
      ) : (
        <ItemDetail item={item} />
      )}
      {editing && edit && (
        <div className="flex flex-col gap-1.5">
          <Label htmlFor={`${id}-edit`}>{edit.key === "rules" ? "Rule tree (JSON)" : edit.key === "prereq" ? "Prerequisite (JSON)" : "Notes (JSON)"}</Label>
          <FieldHint id={`${id}-hint`}>Every node needs a `source` with a quote copied word for word from the page.</FieldHint>
          <Textarea
            id={`${id}-edit`}
            aria-describedby={`${id}-hint${parseError ? ` ${id}-error` : ""}`}
            aria-invalid={parseError ? true : undefined}
            rows={14}
            className="font-mono text-caption"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
          />
          {parseError && <FieldError id={`${id}-error`}>{parseError}</FieldError>}
        </div>
      )}
      <div className="flex flex-wrap gap-2">
        {open && !editing && (
          <>
            <Button disabled={busy} onClick={() => act("accept")}>
              Accept
            </Button>
            {edit && (
              <Button
                variant="outline"
                disabled={busy}
                onClick={() => {
                  setDraft(JSON.stringify(edit.value, null, 2));
                  setEditing(true);
                }}
              >
                Edit
              </Button>
            )}
            <Button variant="destructive" disabled={busy} onClick={() => act("reject")}>
              Reject
            </Button>
          </>
        )}
        {open && editing && (
          <>
            <Button disabled={busy} onClick={saveEdit}>
              Save edit
            </Button>
            <Button variant="outline" disabled={busy} onClick={() => setEditing(false)}>
              Cancel
            </Button>
          </>
        )}
        {canPublish && (
          <Button disabled={busy} onClick={doPublish}>
            Publish this version
          </Button>
        )}
      </div>
      {open && item.program_version_id != null && <p className="text-caption text-muted">Accept or edit first; then you can publish the version.</p>}
      {decide.error && <ErrorText>{decide.error.message}</ErrorText>}
      {publish.error && <ErrorText>{publish.error.message}</ErrorText>}
    </Card>
  );
}

/** Curator console: the review queue for the catalog pipeline (SPEC "Curator console"). Admins only. */
export default function AdminReviewPage() {
  const session = useSession();
  const isAdmin = session.status === "authenticated" && session.account.role === "admin";
  const [status, setStatus] = useState<ReviewStatus>("open");
  const queue = useReviewItems(status, isAdmin);
  const [done, setDone] = useState<string | null>(null);

  if (session.status === "loading") {
    return (
      <PageContainer as="section" width="reading">
        <PageHeader title={TITLE} size="md" />
        <LoadingState label="Checking your login" />
      </PageContainer>
    );
  }
  if (session.status === "anonymous") return <LoginRequired title={TITLE} />;
  if (!isAdmin) {
    return (
      <PageContainer as="section" width="reading">
        <PageHeader title={TITLE} size="md" />
        <Notice tone="info">Only admins can review catalog changes.</Notice>
      </PageContainer>
    );
  }

  const items = queue.data?.items ?? [];
  return (
    <PageContainer as="section">
      <PageHeader
        title={TITLE}
        size="md"
        description="What the catalog pipeline proposed, with the catalog's own words beside each rule. Accept, edit or reject each item. Program rules reach students only after you publish them."
        meta={
          <Link to="/admin/moderation" className={cn(inlineLinkClass, tallTargetClass)}>
            Moderation queue
          </Link>
        }
      />
      <div className="mb-6 flex flex-col gap-1.5 sm:max-w-xs">
        <Label htmlFor="review-status">Show</Label>
        <Select id="review-status" value={status} onChange={(e) => setStatus(e.target.value as ReviewStatus)}>
          {STATUSES.map((s) => (
            <option key={s.value} value={s.value}>
              {s.label}
            </option>
          ))}
        </Select>
      </div>
      <div role="status" className="mb-4">
        {done && <Notice tone="success">{done}</Notice>}
      </div>
      {queue.isLoading ? (
        <LoadingState label="Loading the review queue" />
      ) : queue.error ? (
        <ErrorText>{queue.error.message}</ErrorText>
      ) : items.length === 0 ? (
        <EmptyState title="Nothing here">{status === "open" ? "No item is waiting for a decision." : "No item has this status."}</EmptyState>
      ) : (
        <div className="flex flex-col gap-4">
          <p className="text-caption text-muted">{plural(queue.data?.total ?? items.length, "item")}</p>
          {items.map((item) => (
            <ReviewCard key={item.id} item={item} onDone={setDone} />
          ))}
        </div>
      )}
    </PageContainer>
  );
}
