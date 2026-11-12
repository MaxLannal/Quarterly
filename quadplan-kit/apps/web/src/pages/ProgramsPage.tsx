import { Link } from "react-router-dom";
import { isNotAvailable } from "@/api/client";
import { usePrograms } from "@/api/hooks";
import { NotAvailable, Spinner } from "@/components/ui/misc";
import { groupPrograms, StatusBadge, TYPE_LABELS } from "@/features/programs/ProgramPicker";

export default function ProgramsPage() {
  const q = usePrograms();
  return (
    <div className="mx-auto max-w-5xl space-y-4 p-4">
      <h1 className="text-2xl font-semibold">Program explorer</h1>
      {q.isLoading ? (
        <Spinner label="Loading programs" />
      ) : q.error ? (
        isNotAvailable(q.error) ? (
          <NotAvailable feature="The program list" />
        ) : (
          <p className="text-red-800">Could not load programs.</p>
        )
      ) : (
        groupPrograms(q.data ?? []).map(([type, programs]) => (
          <section key={type} aria-labelledby={`type-${type}`}>
            <h2 id={`type-${type}`} className="text-lg font-semibold">
              {TYPE_LABELS[type]}
            </h2>
            <ul className="mt-1 grid gap-2 sm:grid-cols-2">
              {programs.map((p) => (
                <li key={p.id} className="rounded-md border border-border p-3">
                  <Link to={`/programs/${p.id}`} className="font-medium text-primary hover:underline">
                    {p.name}
                  </Link>{" "}
                  <StatusBadge status={p.status} />
                  <div className="text-sm text-muted-foreground">
                    {[p.degree, p.department, `Catalog ${p.catalog_year}`].filter(Boolean).join(" · ")}
                  </div>
                </li>
              ))}
            </ul>
          </section>
        ))
      )}
    </div>
  );
}
