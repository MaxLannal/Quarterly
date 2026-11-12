import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, isNotAvailable, unwrap } from "@/api/client";
import { Button } from "@/components/ui/button";
import { NotAvailable, Notice, Spinner } from "@/components/ui/misc";
import { deletePlan, loadPlans, newLocalId, setActive, upsertPlan, type LocalPlan } from "@/features/planner/localPlans";
import { useSession } from "@/lib/session";

function AccountPlans() {
  const q = useQuery({ queryKey: ["plans"], queryFn: async () => unwrap(await api.GET("/plans")), retry: false });
  if (q.isLoading) return <Spinner label="Loading saved plans" />;
  if (q.error) return isNotAvailable(q.error) ? <NotAvailable feature="Saving plans to your account">Your plans are kept on this device for now.</NotAvailable> : <p className="text-red-800">Could not load saved plans.</p>;
  if (!q.data?.length) return <p className="text-sm text-muted-foreground">No plans saved to your account yet.</p>;
  return (
    <ul className="space-y-1">
      {q.data.map((p) => (
        <li key={p.id} className="rounded-md border border-border p-2 text-sm">
          {p.name} {p.is_primary && "(primary)"} · catalog {p.catalog_year} · updated {p.updated_day}
        </li>
      ))}
    </ul>
  );
}

export default function PlansPage() {
  const navigate = useNavigate();
  const { data: session, isLoading } = useSession();
  const [doc, setDoc] = useState(() => loadPlans());
  const refresh = () => setDoc(loadPlans());

  function open(p: LocalPlan) {
    setActive(p.localId);
    navigate("/plan");
  }
  function duplicate(p: LocalPlan) {
    upsertPlan({ ...p, localId: newLocalId(), name: `${p.name} (copy)`, isPrimary: false, remoteId: undefined, importedFor: [] }, false);
    refresh();
  }
  function rename(p: LocalPlan, name: string) {
    upsertPlan({ ...p, name }, false);
    refresh();
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-4">
      <h1 className="text-2xl font-semibold">My plans</h1>
      <section aria-labelledby="device-plans" className="space-y-2">
        <h2 id="device-plans" className="text-lg font-semibold">
          On this device
        </h2>
        {doc.plans.length === 0 ? (
          <p className="text-sm">
            No plans yet.{" "}
            <Link to="/onboarding" className="text-primary underline">
              Start planning
            </Link>
          </p>
        ) : (
          <ul className="space-y-2">
            {doc.plans.map((p) => (
              <li key={p.localId} className="flex flex-wrap items-center gap-2 rounded-md border border-border p-2">
                <label className="sr-only" htmlFor={`name-${p.localId}`}>
                  Name of plan
                </label>
                <input
                  id={`name-${p.localId}`}
                  defaultValue={p.name}
                  onBlur={(e) => e.target.value.trim() && e.target.value !== p.name && rename(p, e.target.value.trim())}
                  className="min-h-11 flex-1 rounded-md border border-border bg-background px-2"
                />
                <span className="text-sm text-muted-foreground">
                  {p.isPrimary ? "Primary · " : ""}
                  {(p.state.items ?? []).length} items · updated {p.updatedDay}
                </span>
                <Button variant="outline" onClick={() => open(p)}>
                  Open
                </Button>
                <Button variant="outline" onClick={() => duplicate(p)}>
                  Duplicate
                </Button>
                {!p.isPrimary && (
                  <Button
                    variant="outline"
                    onClick={() => {
                      upsertPlan({ ...p, isPrimary: true }, false);
                      refresh();
                    }}
                  >
                    Set primary
                  </Button>
                )}
                <Button
                  variant="ghost"
                  onClick={() => {
                    deletePlan(p.localId);
                    refresh();
                  }}
                  aria-label={`Delete ${p.name}`}
                >
                  Delete
                </Button>
              </li>
            ))}
          </ul>
        )}
        {doc.plans.length >= 2 && (
          <Link to="/plans/compare" className="inline-flex min-h-11 items-center text-primary underline">
            Compare two plans
          </Link>
        )}
      </section>
      <section aria-labelledby="account-plans" className="space-y-2">
        <h2 id="account-plans" className="text-lg font-semibold">
          In your account
        </h2>
        {isLoading ? (
          <Spinner />
        ) : session ? (
          <AccountPlans />
        ) : (
          <Notice tone="blue">
            <Link to="/login" className="font-medium underline">
              Log in
            </Link>{" "}
            to save plans to your account; plans on this device are imported when you log in.
          </Notice>
        )}
      </section>
    </div>
  );
}
