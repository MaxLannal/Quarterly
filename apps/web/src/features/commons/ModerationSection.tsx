import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, unwrap } from "@/api/client";
import type { components } from "@/api/schema";
import { EmptyState, LoadingState } from "@/components/layout/page";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge, CourseCode, ErrorText } from "@/components/ui/misc";
import { plural, relativeDay } from "@/features/forum/format";

type Item = components["schemas"]["CommonsModerationItem"];
type Decision = components["schemas"]["CommonsModerationDecision"]["decision"];

const KEY = ["admin", "commons-reports"];

/**
 * The Commons part of the moderation queue (OPEN_QUESTIONS CC-7): reported questions and replies,
 * oldest report first. Remove shows the item as "[removed]" (replies under it stay); Keep leaves
 * it up. Either way its reports close. The author is a per-thread handle only.
 */
export function CommonsModerationSection({ onDone }: { onDone: (message: string) => void }) {
  const client = useQueryClient();
  const queue = useQuery({
    queryKey: KEY,
    queryFn: async () => unwrap(await api.GET("/admin/commons-reports")),
  });
  const decide = useMutation({
    mutationFn: async ({ item, decision }: { item: Item; decision: Decision }) =>
      unwrap(
        await api.POST("/admin/commons-reports/{target_type}/{target_id}/decision", {
          params: { path: { target_type: item.target_type, target_id: item.target_id } },
          body: { decision },
        }),
      ),
    onSuccess: (out, { item }) => {
      onDone(
        `${out.status === "removed" ? "Removed" : "Kept"}: ${item.title} (${plural(out.reports_closed, "report")} closed).`,
      );
      void client.invalidateQueries({ queryKey: KEY });
    },
  });
  const items = queue.data ?? [];
  return (
    <section aria-labelledby="commons-reports" className="mt-12 flex flex-col gap-4">
      <div className="flex flex-col gap-1">
        <h2 id="commons-reports" className="font-display text-display-sm">
          Commons <em>reports</em>
        </h2>
        <p className="text-body-sm text-body">
          Reported questions and replies in the Commons (/forum). Remove shows it as &ldquo;[removed]&rdquo;;
          replies under it stay.
        </p>
      </div>
      {queue.isLoading ? (
        <LoadingState label="Loading Commons reports" lines={2} />
      ) : queue.error ? (
        <ErrorText>{queue.error.message}</ErrorText>
      ) : items.length === 0 ? (
        <EmptyState title="No Commons reports">Nothing reported in the Commons.</EmptyState>
      ) : (
        items.map((item) => (
          <Card
            key={`${item.target_type}-${item.target_id}`}
            as="article"
            aria-label={`Reported ${item.target_type}: ${item.title}`}
            className="flex flex-col gap-3"
          >
            <div className="flex flex-wrap items-center gap-2 text-caption text-muted">
              <Badge icon={false}>{item.target_type === "thread" ? "Question" : "Reply"}</Badge>
              {item.by_ai && <Badge icon={false}>Quarterly AI</Badge>}
              {item.status !== "visible" && <Badge icon={false}>{item.status}</Badge>}
              {item.course_code && <CourseCode>{item.course_code}</CourseCode>}
              <span>{plural(item.reports.length, "report")}</span>
            </div>
            <h3 className="text-title-sm text-ink">{item.title}</h3>
            {item.excerpt && <p className="text-body-sm text-body">{item.excerpt}</p>}
            <ul className="flex flex-col gap-1 text-caption text-body-strong">
              {item.reports.map((r, i) => (
                <li key={i}>
                  &ldquo;{r.reason}&rdquo; <span className="text-muted">· {relativeDay(r.created_day)}</span>
                </li>
              ))}
            </ul>
            <div className="flex flex-wrap items-center gap-3">
              <Button
                variant="destructive"
                disabled={decide.isPending}
                onClick={() => decide.mutate({ item, decision: "remove" })}
              >
                Remove
              </Button>
              <Button
                variant="outline"
                disabled={decide.isPending}
                onClick={() => decide.mutate({ item, decision: "keep" })}
              >
                Keep
              </Button>
              <Link to={item.href} className="text-button text-primary underline underline-offset-4">
                Open in the Commons
              </Link>
            </div>
          </Card>
        ))
      )}
      {decide.error && <ErrorText>{decide.error.message}</ErrorText>}
    </section>
  );
}
