import { useId, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError } from "@/api/client";
import { EmptyState, inlineLinkClass, LoadingState, PageContainer, PageHeader, Section, standaloneLinkClass, tallTargetClass } from "@/components/layout/page";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Label, Select } from "@/components/ui/input";
import { CourseCode, ErrorText } from "@/components/ui/misc";
import { Tabs } from "@/components/ui/tabs";
import { termLabel } from "@/features/planner/terms";
import { usePosts, useForumPage, type ForumPage, type PostKind, type Sort } from "./api";
import { Composer } from "./Composer";
import { plural, relativeDay, threadPath } from "./format";
import { ChevronIcon } from "@/components/ui/icons";
import { RatingBars, RatingStats } from "./parts";
import { PostCard } from "./PostCard";

const SORTS: Record<PostKind, { value: Sort; label: string }[]> = {
  review: [
    { value: "best", label: "Best" },
    { value: "new", label: "New" },
    { value: "top", label: "Top" },
    { value: "controversial", label: "Controversial" },
  ],
  // Hot (score decayed with a 30-day half-life) is the discussion tab's default (SPEC).
  discussion: [
    { value: "hot", label: "Hot" },
    { value: "best", label: "Best" },
    { value: "new", label: "New" },
    { value: "top", label: "Top" },
    { value: "controversial", label: "Controversial" },
  ],
};

function PostList({ page, kind }: { page: ForumPage; kind: PostKind }) {
  const id = useId();
  const [sort, setSort] = useState<Sort>(kind === "review" ? "best" : "hot");
  const [term, setTerm] = useState("");
  const [composing, setComposing] = useState(false);
  const posts = usePosts(page.id, kind, sort, term);
  const items = posts.data?.pages.flatMap((p) => p.items) ?? [];
  const total = posts.data?.pages[0]?.total ?? 0;
  const noun = kind === "review" ? "review" : "post";
  const terms = page.terms_taught ?? [];

  return (
    <div className="flex flex-col gap-6">
      {composing ? (
        <Card variant="well" className="p-5 sm:p-6">
          <h3 className="mb-4 text-title-sm text-ink">{kind === "review" ? "Write a review" : "Start a discussion"}</h3>
          <Composer page={page} kind={kind} onCancel={() => setComposing(false)} onDone={(p) => p.status === "visible" && setComposing(false)} />
        </Card>
      ) : (
        <div>
          <Button onClick={() => setComposing(true)}>{kind === "review" ? "Write a review" : "Start a discussion"}</Button>
        </div>
      )}

      <div className="flex flex-wrap items-end gap-4">
        <div className="flex w-48 flex-col gap-1.5">
          <Label htmlFor={`${id}-sort`}>Sort by</Label>
          <Select id={`${id}-sort`} compact value={sort} onChange={(e) => setSort(e.target.value as Sort)}>
            {SORTS[kind].map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </Select>
        </div>
        {kind === "review" && terms.length > 0 && (
          <div className="flex w-48 flex-col gap-1.5">
            <Label htmlFor={`${id}-term`}>Term taken</Label>
            <Select id={`${id}-term`} compact value={term} onChange={(e) => setTerm(e.target.value)}>
              <option value="">All terms</option>
              {terms.map((t) => (
                <option key={t} value={t}>
                  {termLabel(t)}
                </option>
              ))}
            </Select>
          </div>
        )}
        <p role="status" className="pb-3 text-caption text-muted">
          {posts.isLoading ? "" : plural(total, noun)}
        </p>
      </div>

      {posts.isLoading ? (
        <LoadingState label={`Loading ${noun}s`} />
      ) : posts.error ? (
        <ErrorText>{posts.error.message}</ErrorText>
      ) : items.length === 0 ? (
        <EmptyState title={kind === "review" ? "No reviews yet" : "No discussion yet"} />
      ) : (
        <ul className="flex flex-col gap-4">
          {items.map((post) => (
            <li key={post.id}>
              <PostCard post={post} page={page} threadHref={threadPath(page.course_code, page.instructor.slug, post.id)} />
            </li>
          ))}
        </ul>
      )}
      {posts.hasNextPage && (
        <div>
          <Button variant="outline" disabled={posts.isFetchingNextPage} onClick={() => void posts.fetchNextPage()}>
            {posts.isFetchingNextPage ? "Loading…" : `Show more ${noun}s`}
          </Button>
        </div>
      )}
    </div>
  );
}

/** The AI "What students say" slot. Summaries come from agent A3 (prompt 11). */
function SummarySlot({ page }: { page: ForumPage }) {
  const s = page.summary;
  return (
    <Section id="summary" title="What students say">
      {s ? (
        <div className="flex max-w-reading flex-col gap-2">
          <p className="text-body-md text-body">{s.text}</p>
          <p className="text-caption text-muted">
            Written by AI from {plural(s.n_posts, "post")}, updated {relativeDay(s.computed_day)}.
            {(s.citations ?? []).length > 0 && (
              <>
                {" "}Sources:{" "}
                {(s.citations ?? []).map((pid, i) => (
                  <span key={pid}>
                    {i > 0 && ", "}
                    <Link to={threadPath(page.course_code, page.instructor.slug, pid)} className={inlineLinkClass}>
                      [{i + 1}]
                    </Link>
                  </span>
                ))}
              </>
            )}
          </p>
        </div>
      ) : (
        <EmptyState title="No summary yet">An AI summary appears once there are a few reviews.</EmptyState>
      )}
    </Section>
  );
}

/** Course x instructor forum page (SPEC "Course × instructor forum page"). */
export function ForumPageView({ code, slug }: { code: string; slug: string }) {
  const q = useForumPage(code, slug);
  if (q.isLoading) {
    return (
      <PageContainer as="section">
        <PageHeader title="Course × instructor forum" size="md" />
        <LoadingState label="Loading the forum" />
      </PageContainer>
    );
  }
  if (q.error || !q.data) {
    const missing = q.error instanceof ApiError && q.error.status === 404;
    return (
      <PageContainer as="section" width="reading">
        <PageHeader title={missing ? "Forum page not found" : "Course × instructor forum"} size="md" />
        <div className="flex flex-col gap-3">
          <p className="text-body">{missing ? "There is no forum page for this course and instructor yet." : (q.error?.message ?? "Could not load the forum.")}</p>
          <Link to={`/courses/${encodeURIComponent(code)}`} className={standaloneLinkClass}>
            Back to the course
          </Link>
        </div>
      </PageContainer>
    );
  }

  const page = q.data;
  const terms = page.terms_taught ?? [];
  return (
    <PageContainer as="article">
      <PageHeader
        size="lg"
        title={
          <>
            <CourseCode className="mb-4 block">{page.course_code}</CourseCode>
            <span className="sr-only"> · </span>
            {page.course_title}{" "}
            <span className="block text-display-sm text-muted">with {page.instructor.display_name}</span>
          </>
        }
        meta={
          <>
            <Link to={`/instructors/${encodeURIComponent(page.instructor.slug)}`} className={cn(inlineLinkClass, tallTargetClass)}>
              {page.instructor.display_name}
            </Link>
            {page.instructor.department && <span>{page.instructor.department}</span>}
            {(page.also_listed_as ?? []).length > 0 && <span>Also listed as {(page.also_listed_as ?? []).join(", ")}</span>}
            <span>{terms.length ? `Taught ${terms.map(termLabel).join(", ")}` : "Terms taught not recorded yet"}</span>
            <Link to={`/courses/${encodeURIComponent(page.course_code)}`} className={cn(inlineLinkClass, tallTargetClass)}>
              Course page
            </Link>
          </>
        }
      />
      <div className="flex flex-col gap-8">
        <Section id="ratings" title="Ratings" description={page.n_reviews ? `From ${plural(page.n_reviews ?? 0, "review")}` : "No reviews yet"}>
          <div className="flex flex-col gap-6">
            <RatingStats ratings={page.ratings ?? { n_reviews: 0 }} />
            {/* D11 FO-2: the per-score breakdown folds away, so reviews start near the top on a phone. */}
            <details className="group">
              <summary className="inline-flex min-h-11 cursor-pointer list-none items-center gap-1.5 rounded-xs text-body-sm font-medium text-ink hover:text-primary [&::-webkit-details-marker]:hidden">
                <ChevronIcon className="size-4 text-muted transition-transform duration-150 group-open:rotate-90 motion-reduce:transition-none" />
                Rating breakdown
              </summary>
              <div className="mt-3">
                <RatingBars distribution={page.rating_distribution ?? {}} />
              </div>
            </details>
          </div>
        </Section>
        <SummarySlot page={page} />
        <section aria-label="Posts">
          <Tabs
            label="Reviews and discussion"
            tabs={[
              { key: "reviews", label: `Reviews (${page.n_reviews ?? 0})`, content: <PostList page={page} kind="review" /> },
              { key: "discussion", label: "Discussion", content: <PostList page={page} kind="discussion" /> },
            ]}
          />
        </section>
      </div>
    </PageContainer>
  );
}
