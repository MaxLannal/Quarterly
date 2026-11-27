import { useEffect, useState, type ReactNode } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import { ApiError, isNotAvailable } from "@/api/client";
import { useCourse } from "@/api/hooks";
import { inlineLinkClass, LoadingState, PageContainer, PageHeader, standaloneLinkClass, tallTargetClass } from "@/components/layout/page";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { GraphIcon } from "@/components/ui/icons";
import { cn, isWebUrl } from "@/lib/utils";
import { NotAvailable } from "@/components/ui/misc";
import { AddToPlanButton } from "@/features/courses/AddToPlanButton";
import { AttributeCard, OfferingsTable, PrereqGraph } from "@/features/courses/CourseParts";
import { CourseOverview } from "@/features/courses/CourseOverview";
import { FactChip, FactChips, Kicker } from "@/features/courses/Glass";
import { quarterName } from "@/features/planner/terms";

/** A body section set like a magazine department: a mono index and kicker over the serif heading. */
function Part({ id, index, kicker, title, actions, children }: { id: string; index: number; kicker: string; title: string; actions?: ReactNode; children: ReactNode }) {
  return (
    <section id={id} aria-labelledby={`${id}-heading`} className="min-w-0 scroll-mt-24">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-3 border-b border-hairline pb-4">
        <div className="flex min-w-0 flex-col gap-2">
          <Kicker>
            {String(index).padStart(2, "0")} <span className="text-muted-soft">//</span> {kicker}
          </Kicker>
          <h2 id={`${id}-heading`} className="font-display text-display-sm text-ink sm:text-display-md">
            {title}
          </h2>
        </div>
        {actions}
      </div>
      {children}
    </section>
  );
}

export default function CoursePage() {
  const { code = "" } = useParams();
  const q = useCourse(code);
  const [graphOpen, setGraphOpen] = useState(false);
  const { hash } = useLocation();
  const loaded = !!q.data;
  // Links such as "View prerequisite" (planner issues) land on a section of this page.
  useEffect(() => {
    if (loaded && hash) document.getElementById(hash.slice(1))?.scrollIntoView({ block: "start" });
  }, [loaded, hash]);

  if (q.isLoading) {
    return (
      <PageContainer as="section">
        <PageHeader title={code} size="xl" />
        <LoadingState label="Loading course" />
      </PageContainer>
    );
  }
  if (q.error || !q.data) {
    const missing = q.error instanceof ApiError && q.error.status === 404;
    return (
      <PageContainer as="section" width="reading">
        <PageHeader title={missing ? "Course not found" : code} size="md" />
        <div className="flex flex-col gap-3">
          {isNotAvailable(q.error) ? (
            <NotAvailable feature="Course pages" />
          ) : (
            <p className="text-body">{missing ? `There is no course ${code} in this catalog.` : "Could not load this course."}</p>
          )}
          <Link to="/courses" className={standaloneLinkClass}>
            Search courses
          </Link>
        </div>
      </PageContainer>
    );
  }

  const c = q.data;
  const [, number = ""] = c.code.split(" ");
  const offered = [...c.offerings]
    .filter((o) => o.p_offered >= 0.3)
    .sort((a, b) => "AU WI SP SU".indexOf(a.quarter) - "AU WI SP SU".indexOf(b.quarter))
    .map((o) => quarterName(o.quarter));
  const names = c.instructors.map((i) => i.instructor.display_name);
  return (
    <PageContainer as="article">
      {/* The header: a magazine cover. The code is a mono chip, the title the display serif, the
          facts a row of two-line glass chips; the course number stands faintly behind in outline. */}
      <header className="qg-hero relative pb-12 pt-4 sm:pt-10">
        {number && (
          <span
            aria-hidden="true"
            className="pointer-events-none absolute -top-4 right-2 hidden select-none font-display text-[190px] leading-none tracking-[-0.04em] text-transparent [-webkit-text-stroke:1px_rgb(255_255_255/0.07)] lg:block"
          >
            {number}
          </span>
        )}
        <Kicker className="mb-5">
          <Link to="/courses" className={cn("hover:text-ink", tallTargetClass)}>
            Catalog
          </Link>{" "}
          <span className="text-muted-soft">//</span> {c.catalog_year}
        </Kicker>
        <h1 className="relative max-w-[18ch] font-display text-display-lg text-ink [text-shadow:0_0_60px_rgb(255_92_112/0.22)] sm:text-display-mega">
          <span className="mb-5 flex">
            <span className="inline-flex min-h-9 items-center rounded-pill border border-[rgb(255_120_140/0.35)] bg-[linear-gradient(90deg,rgb(255_92_112/0.2),rgb(255_92_112/0.05))] px-4 font-mono text-[13px] font-medium uppercase tracking-[0.16em] text-ink shadow-[inset_0_1px_0_rgb(255_255_255/0.12),0_0_24px_-6px_rgb(255_60_90/0.6)] [text-shadow:none]">
              {c.code}
            </span>
          </span>{" "}
          <span className="sr-only">·</span> {c.title}
        </h1>
        {c.description && <p className="relative mt-6 max-w-[62ch] text-[19px] leading-[1.6] text-body">{c.description}</p>}
        <FactChips label="Course facts" className="relative mt-8">
          <FactChip label="Units">{c.units}</FactChip>
          <FactChip label="Quarters offered">{offered.length ? offered.join(" · ") : "Not expected"}</FactChip>
          <FactChip label={names.length === 1 ? "Instructor" : "Instructors"}>
            {names.length === 0 ? "Not recorded" : names.length <= 2 ? names.join(", ") : `${names[0]} and ${names.length - 1} more`}
          </FactChip>
          <FactChip label="Prerequisites">{c.needs.length ? c.needs.join(", ") : "None"}</FactChip>
          {c.crosslists.length > 0 && <FactChip label="Cross-listed as">{c.crosslists.join(", ")}</FactChip>}
          {c.core_tags.length > 0 && <FactChip label="Core" tone="ember">{c.core_tags.join(", ")}</FactChip>}
          {c.tags.length > 0 && <FactChip label="Tags">{c.tags.join(", ")}</FactChip>}
        </FactChips>
      </header>

      <div className="grid gap-12 lg:grid-cols-[minmax(0,1fr)_minmax(340px,420px)] lg:gap-14">
        {/* The side card comes first on a phone (ratings and Add to plan near the top) and sits
            sticky on the right on wider screens. */}
        <aside aria-label="At a glance" className="min-w-0 lg:sticky lg:top-24 lg:order-2 lg:self-start">
          <CourseOverview course={c} action={<AddToPlanButton code={c.code} catalogYear={c.catalog_year} />} />
        </aside>

        <div className="flex min-w-0 flex-col gap-16 lg:order-1">
          <Part
            id="prereq"
            index={1}
            kicker="Before you take it"
            title="Prerequisites"
            actions={
              <Button variant="outline" size="sm" onClick={() => setGraphOpen(true)}>
                <GraphIcon size={16} />
                View prerequisite graph
              </Button>
            }
          >
            <div className="flex max-w-reading flex-col gap-3 text-body">
              <p className="text-[19px] leading-[1.55] text-ink">{c.prereq_human ?? c.prereq_text ?? "None listed."}</p>
              {c.prereq_text && c.prereq_human && (
                <p className="border-l border-primary/50 pl-4 font-serif text-body-sm italic text-muted">
                  Catalog text: <q>{c.prereq_text}</q>
                </p>
              )}
              {c.notes && <p className="text-body-sm">{c.notes}</p>}
            </div>
          </Part>
          <Dialog open={graphOpen} onClose={() => setGraphOpen(false)} title={`Prerequisite graph: ${c.code}`} className="max-w-4xl">
            <PrereqGraph course={c} />
          </Dialog>

          <Part id="offer" index={2} kicker="When it runs" title="Offerings">
            <OfferingsTable course={c} />
          </Part>

          <Part id="attr" index={3} kicker="What the planner uses" title="Course attributes">
            <AttributeCard course={c} />
          </Part>

          <Part id="counts" index={4} kicker="Where it counts" title="Counts toward">
            {c.counts_toward.length === 0 ? (
              <p className="text-body-sm text-muted">No program requirements list this course.</p>
            ) : (
              <ul className="grid gap-3 sm:grid-cols-2">
                {c.counts_toward.map((ct) => (
                  <li key={`${ct.program_id}-${ct.node_id}`} data-spotlight="" className="qg-tile qg-tile-link flex flex-col gap-1 px-5 py-4 text-body-sm text-body">
                    <span className="font-mono text-[10.5px] font-medium uppercase tracking-[0.18em] text-muted">Program</span>
                    <span>
                      <Link to={`/programs/${ct.program_id}`} className={cn(inlineLinkClass, tallTargetClass, "text-body-strong text-ink decoration-primary/50 after:absolute after:inset-0 after:rounded-[24px]")}>
                        {ct.program_name}
                      </Link>
                      {ct.label ? `: ${ct.label}` : ""}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </Part>

          {isWebUrl(c.source?.url) && (
            <p className="font-mono text-[11.5px] uppercase tracking-[0.16em] text-muted">
              Source:{" "}
              <a href={c.source.url} className={cn(inlineLinkClass, "normal-case tracking-normal")} rel="noreferrer" target="_blank">
                catalog entry
              </a>
            </p>
          )}
        </div>
      </div>
    </PageContainer>
  );
}
