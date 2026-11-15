import { Link } from "react-router-dom";
import { isNotAvailable } from "@/api/client";
import { usePrograms } from "@/api/hooks";
import { LoadingState, PageContainer, PageHeader, Section } from "@/components/layout/page";
import { Card } from "@/components/ui/card";
import { ErrorText, NotAvailable } from "@/components/ui/misc";
import { groupPrograms, StatusBadge, TYPE_LABELS } from "@/features/programs/ProgramPicker";

export default function ProgramsPage() {
  const q = usePrograms();
  return (
    <PageContainer>
      <PageHeader
        title="Program explorer"
        eyebrow="Programs"
      />
      {q.isLoading ? (
        <LoadingState label="Loading programs" />
      ) : q.error ? (
        isNotAvailable(q.error) ? (
          <NotAvailable feature="The program list" />
        ) : (
          <ErrorText>Could not load programs.</ErrorText>
        )
      ) : (
        <div className="flex flex-col gap-12">
          {groupPrograms(q.data ?? []).map(([type, programs]) => (
            <Section key={type} id={`type-${type}`} title={TYPE_LABELS[type]}>
              <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {programs.map((p) => (
                  <Card as="li" key={p.id} interactive className="relative flex flex-col gap-2">
                    <div className="flex items-start justify-between gap-3">
                      <Link to={`/programs/${p.id}`} className="rounded-xs text-title-md text-ink after:absolute after:inset-0 after:rounded-xl hover:underline">
                        {p.name}
                      </Link>
                      <StatusBadge status={p.status} />
                    </div>
                    <p className="text-caption text-muted">{[p.degree, p.department, `Catalog ${p.catalog_year}`].filter(Boolean).join(" · ")}</p>
                  </Card>
                ))}
              </ul>
            </Section>
          ))}
        </div>
      )}
    </PageContainer>
  );
}
