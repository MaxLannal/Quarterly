import { useEffect, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import { ApiError, isNotAvailable } from "@/api/client";
import { useCourse } from "@/api/hooks";
import { inlineLinkClass, LoadingState, PageContainer, PageHeader, Section, standaloneLinkClass, tallTargetClass } from "@/components/layout/page";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { GraphIcon } from "@/components/ui/icons";
import { cn, isWebUrl } from "@/lib/utils";
import { Badge, CourseCode, NotAvailable } from "@/components/ui/misc";
import { AddToPlanButton } from "@/features/courses/AddToPlanButton";
import { AttributeCard, OfferingsTable, PrereqGraph } from "@/features/courses/CourseParts";
import { CourseOverview } from "@/features/courses/CourseOverview";

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

      <CourseOverview course={c} />

      <div className="flex flex-col gap-10">
        <Section
          id="prereq"
          title="Prerequisites"
          actions={
            <Button variant="ghost" size="sm" onClick={() => setGraphOpen(true)}>
              <GraphIcon size={16} />
              View prerequisite graph
            </Button>
          }
        >
          <div className="flex max-w-reading flex-col gap-2 text-body">
            <p className="text-ink">{c.prereq_human ?? c.prereq_text ?? "None listed."}</p>
            {c.prereq_text && c.prereq_human && (
              <p className="text-body-sm text-muted">
                Catalog text: <q>{c.prereq_text}</q>
              </p>
            )}
            {c.notes && <p className="text-body-sm">{c.notes}</p>}
          </div>
        </Section>
        <Dialog open={graphOpen} onClose={() => setGraphOpen(false)} title={`Prerequisite graph: ${c.code}`} className="max-w-4xl">
          <PrereqGraph course={c} />
        </Dialog>

        <div className="grid gap-10 lg:grid-cols-2 lg:gap-6">
          <Section id="offer" title="Offerings">
            <OfferingsTable course={c} />
          </Section>
          <AttributeCard course={c} />
        </div>

        <div className="grid gap-10 lg:grid-cols-2 lg:gap-6">
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
