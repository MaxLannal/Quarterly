import { Link, useParams } from "react-router-dom";
import { ApiError, isNotAvailable } from "@/api/client";
import { useCourse } from "@/api/hooks";
import { inlineLinkClass, LoadingState, PageContainer, PageHeader, Section, standaloneLinkClass, tallTargetClass } from "@/components/layout/page";
import { Avatar } from "@/components/ui/card";
import { cn, isWebUrl } from "@/lib/utils";
import { Badge, CourseCode, NotAvailable } from "@/components/ui/misc";
import { AddToPlanButton } from "@/features/courses/AddToPlanButton";
import { AttributeCard, OfferingsTable, PrereqGraph } from "@/features/courses/CourseParts";
import { useSession } from "@/features/auth/session";
import { CourseForumSummary } from "@/features/forum/CourseForumSummary";
import { termLabel } from "@/features/planner/terms";

export default function CoursePage() {
  const { code = "" } = useParams();
  const q = useCourse(code);
  const loggedIn = useSession().status === "authenticated";

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
  return (
    <PageContainer as="article">
      <PageHeader
        size="xl"
        title={
          <>
            <CourseCode className="mb-4 block">{c.code}</CourseCode>
            {" "}<span className="sr-only">·</span>{" "}
            {c.title}
          </>
        }
        meta={
          <>
            <span>{c.units} units</span>
            {c.crosslists.length > 0 && <span>Cross-listed as {c.crosslists.join(", ")}</span>}
            <span>Catalog {c.catalog_year}</span>
            {c.core_tags.map((t) => (
              <Badge key={t}>Core: {t}</Badge>
            ))}
            {c.tags.map((t) => (
              <Badge key={t}>{t}</Badge>
            ))}
          </>
        }
        description={c.description ? <p>{c.description}</p> : undefined}
        actions={<AddToPlanButton code={c.code} catalogYear={c.catalog_year} />}
      />

      <div className="flex flex-col gap-12">
        <Section id="prereq" title="Prerequisites">
          <div className="flex max-w-reading flex-col gap-2 text-body">
            <p className="text-ink">{c.prereq_human ?? c.prereq_text ?? "None listed."}</p>
            {c.prereq_text && c.prereq_human && (
              <p className="text-body-sm text-muted">
                Catalog text: <q>{c.prereq_text}</q>
              </p>
            )}
            {c.notes && <p className="text-body-sm">{c.notes}</p>}
          </div>
          <div className="mt-5">
            <PrereqGraph course={c} />
          </div>
        </Section>

        <div className="grid gap-12 lg:grid-cols-2 lg:gap-6">
          <Section id="offer" title="Offerings">
            <OfferingsTable course={c} />
          </Section>
          <AttributeCard course={c} />
        </div>

        <div className="grid gap-12 lg:grid-cols-2 lg:gap-6">
          <Section id="instr" title="Instructors">
            {c.instructors.length === 0 ? (
              <p className="text-body-sm text-muted">No instructors recorded yet.</p>
            ) : (
              <ul className="divide-y divide-hairline border-y border-hairline">
                {c.instructors.map((i) => (
                  <li key={i.instructor.slug} className="flex items-center gap-3 py-3">
                    <Avatar name={i.instructor.display_name} />
                    <div className="min-w-0">
                      <Link to={`/courses/${encodeURIComponent(c.code)}/i/${i.instructor.slug}`} className={cn(inlineLinkClass, tallTargetClass, "text-title-sm")}>
                        {i.instructor.display_name}
                      </Link>
                      <p className="text-caption text-muted">
                        {i.n_terms} term{i.n_terms === 1 ? "" : "s"}
                        {i.first_term && i.last_term ? `, ${termLabel(i.first_term)}–${termLabel(i.last_term)}` : ""}
                        {loggedIn ? "" : " · reviews need login"}
                      </p>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </Section>

          <CourseForumSummary code={c.code} />
        </div>

        <div className="grid gap-12 lg:grid-cols-2 lg:gap-6">
          <Section id="counts" title="Counts toward">
            {c.counts_toward.length === 0 ? (
              <p className="text-body-sm text-muted">No program requirements list this course.</p>
            ) : (
              <ul className="divide-y divide-hairline border-y border-hairline">
                {c.counts_toward.map((ct) => (
                  <li key={`${ct.program_id}-${ct.node_id}`} className="py-3 text-body-sm text-body">
                    <Link to={`/programs/${ct.program_id}`} className={cn(inlineLinkClass, tallTargetClass, "text-body-strong")}>
                      {ct.program_name}
                    </Link>
                    {ct.label ? `: ${ct.label}` : ""}
                  </li>
                ))}
              </ul>
            )}
          </Section>
        </div>

        {isWebUrl(c.source?.url) && (
          <p className="text-caption text-muted">
            Source:{" "}
            <a href={c.source.url} className={inlineLinkClass} rel="noreferrer" target="_blank">
              catalog entry
            </a>
          </p>
        )}
      </div>
    </PageContainer>
  );
}
