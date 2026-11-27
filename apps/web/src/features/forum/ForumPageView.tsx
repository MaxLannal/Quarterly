import { useId, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError } from "@/api/client";
import { EmptyState, inlineLinkClass, LoadingState, PageContainer, PageHeader, standaloneLinkClass, tallTargetClass } from "@/components/layout/page";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { CourseCode, ErrorText } from "@/components/ui/misc";
import { Tabs } from "@/components/ui/tabs";
import { termLabel } from "@/features/planner/terms";
import { usePosts, useForumPage, type ForumPage, type PostKind, type Sort } from "./api";
import { Composer } from "./Composer";
import { plural, relativeDay, threadPath } from "./format";
import { ChevronIcon } from "@/components/ui/icons";
import { RatingBars, RatingStats } from "./parts";
import { PostCard } from "./PostCard";
import { FactChip, FactChips, Kicker } from "@/features/courses/Glass";

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
    <div className="flex flex-col gap-7 pt-2">
      {composing && (
        // The composer floats: a raised pane of frosted glass with a lit edge.
        <div className="glass-raised qg-rise relative rounded-[28px] p-5 sm:p-8">
          <span aria-hidden="true" className="pointer-events-none absolute inset-x-10 -top-px h-px bg-[linear-gradient(90deg,transparent,rgb(255_120_140/0.8),transparent)]" />
          <p className="qg-kicker mb-2">{kind === "review" ? "New review" : "New discussion"} <span className="text-muted-soft">//</span> under a pseudonym</p>
          <h3 className="mb-6 font-display text-display-sm text-ink">{kind === "review" ? "Write a review" : "Start a discussion"}</h3>
          <Composer page={page} kind={kind} onCancel={() => setComposing(false)} onDone={(p) => p.status === "visible" && setComposing(false)} />
        </div>
      )}

      <div className="flex flex-wrap items-center gap-3">
        {!composing && <Button onClick={() => setComposing(true)}>{kind === "review" ? "Write a review" : "Start a discussion"}</Button>}
        <div className="ml-auto flex flex-wrap items-center gap-2.5">
          <div className="qg-filter w-44">
            <label htmlFor={`${id}-sort`}>Sort by</label>
            <select id={`${id}-sort`} value={sort} onChange={(e) => setSort(e.target.value as Sort)}>
              {SORTS[kind].map((s) => (
                <option key={s.value} value={s.value}>
                  {s.label}
                </option>
              ))}
            </select>
          </div>
          {kind === "review" && terms.length > 0 && (
            <div className="qg-filter w-48" data-set={term ? true : undefined}>
              <label htmlFor={`${id}-term`}>Term taken</label>
              <select id={`${id}-term`} value={term} onChange={(e) => setTerm(e.target.value)}>
                <option value="">All terms</option>
                {terms.map((t) => (
                  <option key={t} value={t}>
                    {termLabel(t)}
                  </option>
                ))}
              </select>
            </div>
          )}
          <p role="status" className="px-2 font-mono text-[11.5px] uppercase tracking-[0.16em] text-muted">
            {posts.isLoading ? "" : plural(total, noun)}
          </p>
        </div>
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
    <section id="summary" aria-labelledby="summary-heading" className="min-w-0 scroll-mt-24">
      <Kicker className="mb-2">
        AI summary <span className="text-muted-soft">//</span> from the reviews
      </Kicker>
      <h2 id="summary-heading" className="mb-5 font-display text-display-sm text-ink sm:text-display-md">
        What students say
      </h2>
      {s ? (
        <div className="qg-tile qg-edge flex flex-col gap-4 p-6 sm:p-8">
          <p className="font-serif text-[22px] font-light italic leading-[1.5] text-ink">{s.text}</p>
          <p className="border-t border-hairline pt-4 text-caption text-muted">
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
    </section>
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
      {/* The same cover as the course page: a mono code chip, the title in the display serif with
          the instructor in its lit italic, and the facts as two-line glass chips. */}
      <header className="qg-hero pb-12 pt-4 sm:pt-10">
        <Kicker className="mb-5">
          <Link to="/forum" className={cn("hover:text-ink", tallTargetClass)}>
            Forum
          </Link>{" "}
          <span className="text-muted-soft">//</span> Course × instructor
        </Kicker>
        <h1 className="max-w-[22ch] font-display text-display-lg text-ink [text-shadow:0_0_60px_rgb(255_92_112/0.22)] sm:text-display-xl">
          <span className="mb-5 flex">
            <CourseCode className="inline-flex min-h-9 items-center rounded-pill border border-[rgb(255_120_140/0.35)] bg-[linear-gradient(90deg,rgb(255_92_112/0.2),rgb(255_92_112/0.05))] px-4 text-[13px] tracking-[0.16em] text-ink shadow-[inset_0_1px_0_rgb(255_255_255/0.12)] [text-shadow:none]">
              {page.course_code}
            </CourseCode>
          </span>{" "}
          <span className="sr-only">·</span> {page.course_title}{" "}
          <span className="mt-1 block text-display-sm text-body sm:text-display-md">
            with <em>{page.instructor.display_name}</em>
          </span>
        </h1>
        <FactChips label="About this page" className="mt-8">
          <FactChip label="Instructor">
            <Link to={`/instructors/${encodeURIComponent(page.instructor.slug)}`} className={tallTargetClass}>
              {page.instructor.display_name}
            </Link>
          </FactChip>
          {page.instructor.department && <FactChip label="Department">{page.instructor.department}</FactChip>}
          <FactChip label="When">{terms.length ? `Taught ${terms.map(termLabel).join(", ")}` : "Terms taught not recorded yet"}</FactChip>
          {(page.also_listed_as ?? []).length > 0 && <FactChip label="Also listed as">{(page.also_listed_as ?? []).join(", ")}</FactChip>}
          <FactChip label="Catalog">
            <Link to={`/courses/${encodeURIComponent(page.course_code)}`} className={tallTargetClass}>
              Course page
            </Link>
          </FactChip>
        </FactChips>
      </header>

      <div className="grid gap-12 lg:grid-cols-[minmax(0,1fr)_minmax(340px,400px)] lg:gap-14">
        {/* The ratings card: first on a phone, a sticky pane on the right on wider screens (it
            scrolls inside itself if the breakdown makes it taller than the window). */}
        <aside aria-label="Ratings at a glance" className="min-w-0 lg:sticky lg:top-24 lg:order-2 lg:max-h-[calc(100vh-7rem)] lg:self-start lg:overflow-y-auto lg:[scrollbar-width:thin]">
          <section id="ratings" aria-labelledby="ratings-heading" className="qg-tile qg-edge overflow-hidden p-6 sm:p-7">
            <span aria-hidden="true" className="pointer-events-none absolute -right-24 -top-24 size-64 rounded-pill bg-[radial-gradient(closest-side,rgb(220_30_60/0.28),transparent)]" />
            <div className="relative mb-5 flex items-baseline justify-between gap-3">
              <h2 id="ratings-heading" className="font-display text-display-sm text-ink">
                Ratings
              </h2>
              <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-muted">{page.n_reviews ? `From ${plural(page.n_reviews ?? 0, "review")}` : "No reviews yet"}</p>
            </div>
            <div className="relative flex flex-col gap-5">
              <RatingStats ratings={page.ratings ?? { n_reviews: 0 }} />
              {/* D11 FO-2: the per-score breakdown folds away, so reviews start near the top on a phone. */}
              <details className="group border-t border-hairline pt-2">
                <summary className="inline-flex min-h-11 cursor-pointer list-none items-center gap-1.5 rounded-xs text-body-sm font-medium text-ink hover:text-primary-hover [&::-webkit-details-marker]:hidden">
                  <ChevronIcon className="size-4 text-muted transition-transform duration-300 group-open:rotate-90 motion-reduce:transition-none" />
                  Rating breakdown
                </summary>
                <div className="mt-3">
                  <RatingBars distribution={page.rating_distribution ?? {}} />
                </div>
              </details>
            </div>
          </section>
        </aside>
        <div className="flex min-w-0 flex-col gap-16 lg:order-1">
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
      </div>
    </PageContainer>
  );
}
