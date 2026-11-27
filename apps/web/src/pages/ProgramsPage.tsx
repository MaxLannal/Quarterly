import { Link } from "react-router-dom";
import { isNotAvailable } from "@/api/client";
import { usePrograms } from "@/api/hooks";
import { LoadingState, PageContainer } from "@/components/layout/page";
import { ArrowIcon } from "@/components/ui/icons";
import { ErrorText, NotAvailable } from "@/components/ui/misc";
import { CatalogToggle } from "@/features/courses/CatalogToggle";
import { Kicker } from "@/features/courses/Glass";
import { groupPrograms, StatusBadge, TYPE_LABELS } from "@/features/programs/ProgramPicker";

/**
 * The program explorer. Dark glass: the Catalog's centred cover (the glass switch, a mono kicker,
 * the display serif), then each kind of program as a numbered department of glass tiles.
 */
export default function ProgramsPage() {
  const q = usePrograms();
  return (
    <PageContainer>
      <div className="qg-hero mx-auto flex w-full max-w-[880px] flex-col items-center gap-6 pb-6 pt-6 text-center sm:pt-14">
        <CatalogToggle current="programs" />
        <div className="flex flex-col items-center gap-3">
          <Kicker>Majors, minors and the Core</Kicker>
          <h1 className="font-display text-display-lg text-ink [text-shadow:0_0_60px_rgb(255_92_112/0.25)] sm:text-display-mega">Program explorer</h1>
          <p className="max-w-[34rem] text-body-md text-body">What each program asks of you, part by part, with every course a click away.</p>
        </div>
      </div>
      <div className="mx-auto mt-12 w-full max-w-[1240px]">
        {q.isLoading ? (
          <LoadingState label="Loading programs" />
        ) : q.error ? (
          isNotAvailable(q.error) ? (
            <NotAvailable feature="The program list" />
          ) : (
            <ErrorText>Could not load programs.</ErrorText>
          )
        ) : (
          <div className="flex flex-col gap-16">
            {groupPrograms(q.data ?? []).map(([type, programs], n) => (
              <section key={type} id={`type-${type}`} aria-labelledby={`type-${type}-heading`} className="scroll-mt-24">
                <div className="mb-6 flex flex-wrap items-end justify-between gap-3 border-b border-hairline pb-4">
                  <div className="flex flex-col gap-2">
                    <Kicker>
                      {String(n + 1).padStart(2, "0")} <span aria-hidden="true" className="text-muted-soft">//</span> {programs.length} {programs.length === 1 ? "program" : "programs"}
                    </Kicker>
                    <h2 id={`type-${type}-heading`} className="font-display text-display-sm text-ink sm:text-display-md">
                      {TYPE_LABELS[type]}
                    </h2>
                  </div>
                </div>
                <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                  {programs.map((p, i) => (
                    <li key={p.id} data-spotlight="" className="qg-tile qg-tile-link qg-rise group flex min-h-[180px] flex-col gap-3 p-6 sm:p-7" style={{ ["--i" as string]: i }}>
                      <div className="flex items-start justify-between gap-3">
                        <span className="font-mono text-[10.5px] font-medium uppercase tracking-[0.18em] text-muted">{[p.degree, `Catalog ${p.catalog_year}`].filter(Boolean).join(" // ")}</span>
                        <StatusBadge status={p.status} />
                      </div>
                      <Link
                        to={`/programs/${p.id}`}
                        className="rounded-xs font-display text-[30px] leading-[1.1] text-ink transition-colors duration-300 after:absolute after:inset-0 after:rounded-[24px] group-hover:text-primary-hover"
                      >
                        {p.name}
                      </Link>
                      <div className="mt-auto flex items-center justify-between gap-3 pt-2">
                        <p className="text-caption text-muted">{p.department}</p>
                        <span aria-hidden="true" className="inline-flex size-9 shrink-0 items-center justify-center rounded-pill border border-hairline text-muted transition-[translate,color,border-color] duration-300 group-hover:translate-x-0.5 group-hover:border-primary/50 group-hover:text-primary">
                          <ArrowIcon size={14} />
                        </span>
                      </div>
                    </li>
                  ))}
                </ul>
              </section>
            ))}
          </div>
        )}
      </div>
    </PageContainer>
  );
}
