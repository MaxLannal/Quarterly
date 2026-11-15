import { useState } from "react";
import { Link } from "react-router-dom";
import { EmptyState, inlineLinkClass, LoadingState, PageContainer, PageHeader, tallTargetClass } from "@/components/layout/page";
import { Button } from "@/components/ui/button";
import { Label, Select } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { Badge, CourseCode, ErrorText, Notice } from "@/components/ui/misc";
import { useSession } from "@/features/auth/session";
import { useEndSuspension, useModerationDecision, useModerationQueue, useSuspensions, type ModerationItem } from "@/features/forum/api";
import { plural, relativeDay, threadPath } from "@/features/forum/format";
import { LoginRequired, PostBody } from "@/features/forum/parts";

const TITLE = "Moderation queue";

const LABELS: Record<string, string> = {
  classifier_unavailable: "Automatic check unavailable",
  identifying_info: "May identify someone",
  misconduct_claim: "Claim of misconduct",
  personal_attack: "Personal attack",
  harassment: "Harassment",
  sexual: "Sexual content",
  spam: "Spam",
  off_topic: "Off topic",
};

/** Suspension lengths an admin can pick when removing (P08-3: suspensions are always manual). */
const SUSPENSIONS = [7, 30, 90] as const;

function QueueItem({ item, onDone }: { item: ModerationItem; onDone: (message: string) => void }) {
  const decide = useModerationDecision();
  const reports = item.reports ?? [];
  const where = `${item.course_code} with ${item.instructor_name}`;
  const [suspendDays, setSuspendDays] = useState<string>("");
  const selectId = `suspend-${item.target_type}-${item.target_id}`;
  const name = item.title ?? `${item.kind} ${item.target_id}`;

  function act(decision: "approve" | "remove") {
    const days = decision === "remove" && suspendDays ? Number(suspendDays) : undefined;
    decide.mutate(
      { item, decision, suspendDays: days },
      {
        onSuccess: (r) =>
          onDone(
            decision === "approve"
              ? `Kept: ${name}. Reports dismissed.`
              : r.author_suspended
                ? `Removed: ${name}. The author is suspended for ${days} days.`
                : days
                  ? `Removed: ${name}. The author has deleted their account, so there was no one to suspend.`
                  : `Removed: ${name}. Reports upheld.`,
          ),
      },
    );
  }

  return (
    <Card as="article" aria-label={`${item.kind} on ${where}`} className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <Badge>{item.kind}</Badge>
        <Badge tone={item.status === "held" ? "warning" : item.status === "removed" ? "error" : "neutral"} casing="normal">
          {item.status === "held" ? "Held" : item.status === "removed" ? "Not published" : "Published"}
        </Badge>
        {item.model_label && (
          <Badge tone="info" casing="normal">
            {LABELS[item.model_label] ?? item.model_label}
          </Badge>
        )}
        {reports.length > 0 && (
          <Badge tone="warning" casing="normal">
            {plural(reports.length, "report")}
          </Badge>
        )}
      </div>
      <p className="text-caption text-muted">
        <CourseCode>{item.course_code}</CourseCode> with {item.instructor_name} · {item.pseudonym} · {relativeDay(item.created_day)}
      </p>
      {item.title && <h2 className="text-title-sm text-ink">{item.title}</h2>}
      <PostBody html={item.body_html} className="rounded-md bg-canvas-soft p-4" />
      {reports.length > 0 && (
        <ul className="flex flex-col gap-1 text-body-sm text-body">
          {reports.map((r) => (
            <li key={r.id}>
              <span className="text-muted">{r.from_author ? "Author asks for review: " : "Report: "}</span>
              {r.reason}
            </li>
          ))}
        </ul>
      )}
      <div className="flex flex-col gap-1.5 sm:max-w-xs">
        <Label htmlFor={selectId}>When removing, also suspend the author</Label>
        <Select id={selectId} value={suspendDays} onChange={(e) => setSuspendDays(e.target.value)}>
          <option value="">No suspension</option>
          {SUSPENSIONS.map((d) => (
            <option key={d} value={String(d)}>
              For {d} days
            </option>
          ))}
        </Select>
      </div>
      <div className="flex flex-wrap gap-2">
        <Button variant="outline" disabled={decide.isPending} onClick={() => act("approve")}>
          Approve
        </Button>
        <Button variant="destructive" disabled={decide.isPending} onClick={() => act("remove")}>
          Remove
        </Button>
        {(item.status === "visible" || item.target_type === "comment") && (
          <Link
            to={threadPath(item.course_code, item.instructor_slug, item.post_id)}
            className={`${inlineLinkClass} inline-flex min-h-11 items-center px-2`}
          >
            Open thread
          </Link>
        )}
      </div>
    {decide.error && <ErrorText>{decide.error.message}</ErrorText>}
    </Card>
  );
}

/** Curator console: the forum moderation queue (SPEC "Curator console"). Admins only. */
export default function AdminModerationPage() {
  const session = useSession();
  const isAdmin = session.status === "authenticated" && session.account.role === "admin";
  const queue = useModerationQueue(isAdmin);
  const [done, setDone] = useState<string | null>(null);

  if (session.status === "loading") {
    return (
      <PageContainer as="section" width="reading">
        <PageHeader title={TITLE} size="md" />
        <LoadingState label="Checking your login" />
      </PageContainer>
    );
  }
  if (session.status === "anonymous") return <LoginRequired title={TITLE} eyebrow="Curator console" />;
  if (!isAdmin) {
    return (
      <PageContainer as="section" width="reading">
        <PageHeader eyebrow="Curator console" title={TITLE} size="md" />
        <Notice tone="info">Only admins can moderate the forum.</Notice>
      </PageContainer>
    );
  }

  const items = queue.data?.items ?? [];
  return (
    <PageContainer as="section" width="reading">
      <PageHeader
        eyebrow="Curator console"
        title={TITLE}
        description="Reported posts and comments, oldest first. Approve keeps it and dismisses the reports; Remove takes it down and upholds them. You may also suspend the author when removing: suspensions are never automatic, and you never see who the author is."
        meta={
          <Link to="/guidelines" className={cn(inlineLinkClass, tallTargetClass)}>
            Community guidelines
          </Link>
        }
      />
      <div role="status" className="mb-4">
        {done && <Notice tone="success">{done}</Notice>}
      </div>
      {queue.isLoading ? (
        <LoadingState label="Loading the queue" />
      ) : queue.error ? (
        <ErrorText>{queue.error.message}</ErrorText>
      ) : items.length === 0 ? (
        <EmptyState title="Nothing to review">The queue is empty.</EmptyState>
      ) : (
        <div className="flex flex-col gap-4">
          <p className="text-caption text-muted">
            {plural(queue.data?.total ?? items.length, "item")} waiting
          </p>
          {items.map((item) => (
            <QueueItem key={`${item.target_type}-${item.target_id}`} item={item} onDone={setDone} />
          ))}
        </div>
      )}
      <Suspensions onDone={setDone} />
    </PageContainer>
  );
}

/** Active suspensions, each listed by the removal that started it: the author is never shown. */
function Suspensions({ onDone }: { onDone: (message: string) => void }) {
  const list = useSuspensions(true);
  const end = useEndSuspension();
  const rows = list.data ?? [];
  if (!rows.length) return null;
  return (
    <section aria-labelledby="suspensions" className="mt-10 flex flex-col gap-3">
      <h2 id="suspensions" className="font-display text-display-sm">
        Suspensions
      </h2>
      {rows.map((s) => (
        <Card key={`${s.target_type}-${s.target_id}`} as="article" aria-label={`Suspension from ${s.target_type} ${s.target_id}`} className="flex flex-wrap items-center justify-between gap-3">
          <div className="min-w-0">
            <p className="text-body-sm text-ink">{s.title ?? s.excerpt}</p>
            <p className="text-caption text-muted">
              <CourseCode>{s.course_code}</CourseCode> with {s.instructor_name} · suspended until {s.until}
            </p>
          </div>
          <Button
            variant="outline"
            disabled={end.isPending}
            onClick={() =>
              end.mutate(
                { targetType: s.target_type, targetId: s.target_id },
                { onSuccess: () => onDone(`Suspension ended: ${s.title ?? `${s.target_type} ${s.target_id}`}.`) },
              )
            }
          >
            End suspension
          </Button>
        </Card>
      ))}
    </section>
  );
}
