import { Link, useParams } from "react-router-dom";
import { ApiError, isNotAvailable } from "@/api/client";
import { useCourse } from "@/api/hooks";
import { Badge, NotAvailable, Spinner } from "@/components/ui/misc";
import { AddToPlanButton } from "@/features/courses/AddToPlanButton";
import { AttributeCard, OfferingsTable, PrereqGraph } from "@/features/courses/CourseParts";
import { termLabel } from "@/features/planner/terms";

export default function CoursePage() {
  const { code = "" } = useParams();
  const q = useCourse(code);

  if (q.isLoading) {
    return (
      <section className="mx-auto max-w-5xl p-4">
        <h1 className="text-2xl font-semibold">{code}</h1>
        <Spinner label="Loading course" />
      </section>
    );
  }
  if (q.error || !q.data) {
    const missing = q.error instanceof ApiError && q.error.status === 404;
    return (
      <section className="mx-auto max-w-5xl space-y-3 p-4">
        <h1 className="text-2xl font-semibold">{missing ? "Course not found" : code}</h1>
        {isNotAvailable(q.error) ? (
          <NotAvailable feature="Course pages" />
        ) : (
          <p>{missing ? `There is no course ${code} in this catalog.` : "Could not load this course."}</p>
        )}
        <Link to="/courses" className="text-primary underline">
          Search courses
        </Link>
      </section>
    );
  }

  const c = q.data;
  return (
    <article className="mx-auto max-w-5xl space-y-5 p-4">
      <header className="space-y-2">
        <h1 className="text-2xl font-semibold">
          {c.code} · {c.title}
        </h1>
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <span>{c.units} units</span>
          {c.crosslists.length > 0 && <span>Cross-listed as {c.crosslists.join(", ")}</span>}
          {c.core_tags.map((t) => (
            <Badge key={t} tone="blue">
              Core: {t}
            </Badge>
          ))}
          {c.tags.map((t) => (
            <Badge key={t}>{t}</Badge>
          ))}
          <span className="text-muted-foreground">Catalog {c.catalog_year}</span>
        </div>
        <AddToPlanButton code={c.code} catalogYear={c.catalog_year} />
      </header>

      {c.description && <p className="max-w-prose">{c.description}</p>}

      <section aria-labelledby="prereq-heading" className="space-y-2">
        <h2 id="prereq-heading" className="text-lg font-semibold">
          Prerequisites
        </h2>
        <p>{c.prereq_human ?? c.prereq_text ?? "None listed."}</p>
        {c.prereq_text && c.prereq_human && (
          <p className="text-sm text-muted-foreground">
            Catalog text: <q>{c.prereq_text}</q>
          </p>
        )}
        {c.notes && <p className="text-sm">{c.notes}</p>}
        <PrereqGraph course={c} />
      </section>

      <div className="grid gap-5 lg:grid-cols-2">
        <section aria-labelledby="offer-heading">
          <h2 id="offer-heading" className="mb-2 text-lg font-semibold">
            Offerings
          </h2>
          <OfferingsTable course={c} />
        </section>
        <AttributeCard course={c} />
      </div>

      <section aria-labelledby="instr-heading">
        <h2 id="instr-heading" className="text-lg font-semibold">
          Instructors
        </h2>
        {c.instructors.length === 0 ? (
          <p className="text-sm text-muted-foreground">No instructors recorded yet.</p>
        ) : (
          <ul className="mt-1 space-y-1">
            {c.instructors.map((i) => (
              <li key={i.instructor.slug}>
                <Link to={`/courses/${encodeURIComponent(c.code)}/i/${i.instructor.slug}`} className="text-primary underline">
                  {i.instructor.display_name}
                </Link>{" "}
                <span className="text-sm text-muted-foreground">
                  {i.n_terms} term{i.n_terms === 1 ? "" : "s"}
                  {i.first_term && i.last_term ? `, ${termLabel(i.first_term)}–${termLabel(i.last_term)}` : ""} · reviews need login
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section aria-labelledby="counts-heading">
        <h2 id="counts-heading" className="text-lg font-semibold">
          Counts toward
        </h2>
        {c.counts_toward.length === 0 ? (
          <p className="text-sm text-muted-foreground">No program requirements list this course.</p>
        ) : (
          <ul className="mt-1 list-disc space-y-1 pl-5">
            {c.counts_toward.map((ct) => (
              <li key={`${ct.program_id}-${ct.node_id}`}>
                <Link to={`/programs/${ct.program_id}`} className="text-primary underline">
                  {ct.program_name}
                </Link>
                {ct.label ? `: ${ct.label}` : ""}
              </li>
            ))}
          </ul>
        )}
      </section>

      {c.source?.url && (
        <p className="text-sm text-muted-foreground">
          Source:{" "}
          <a href={c.source.url} className="underline" rel="noreferrer" target="_blank">
            catalog entry
          </a>
        </p>
      )}
    </article>
  );
}
