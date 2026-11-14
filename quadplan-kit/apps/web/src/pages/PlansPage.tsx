import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, isNotAvailable, unwrap } from "@/api/client";
import { EmptyState, PageContainer, PageHeader, Section, standaloneLinkClass } from "@/components/layout/page";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ErrorText, NotAvailable, Notice, Spinner } from "@/components/ui/misc";
import { deletePlan, loadPlans, newLocalId, setActive, upsertPlan, type LocalPlan } from "@/features/planner/localPlans";
import { useSession } from "@/lib/session";

function AccountPlans() {
  const q = useQuery({ queryKey: ["plans"], queryFn: async () => unwrap(await api.GET("/plans")), retry: false });
  if (q.isLoading) return <Spinner label="Loading saved plans" />;
  if (q.error) return isNotAvailable(q.error) ? <NotAvailable feature="Saving plans to your account">Your plans are kept on this device for now.</NotAvailable> : <ErrorText>Could not load saved plans.</ErrorText>;
  if (!q.data?.length) return <EmptyState>No plans saved to your account yet.</EmptyState>;
  return (
    <ul className="divide-y divide-hairline rounded-xl border border-hairline bg-surface-card px-6">
      {q.data.map((p) => (
        <li key={p.id} className="py-4 text-body-sm text-body">
          <span className="text-body-strong text-ink">
            {p.name} {p.is_primary && "(primary)"}
          </span>{" "}
          · catalog {p.catalog_year} · updated {p.updated_day}
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
    <PageContainer className="max-w-4xl">
      <PageHeader title="My plans" eyebrow="Plans" />
      <div className="flex flex-col gap-12">
      <Section id="device-plans" title="On this device">
        {doc.plans.length === 0 ? (
          <EmptyState>
            No plans yet.{" "}
            <Link to="/onboarding">
              Start planning
            </Link>
          </EmptyState>
        ) : (
          <ul className="flex flex-col gap-3">
            {doc.plans.map((p) => (
              <Card as="li" variant="compact" key={p.localId} className="flex flex-wrap items-center gap-3 px-5">
                <label className="sr-only" htmlFor={`name-${p.localId}`}>
                  Name of plan
                </label>
                <Input
                  id={`name-${p.localId}`}
                  defaultValue={p.name}
                  onBlur={(e) => e.target.value.trim() && e.target.value !== p.name && rename(p, e.target.value.trim())}
                  className="min-w-48 flex-1 text-body-strong"
                />
                <span className="text-caption text-muted">
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
                  variant="destructive"
                  onClick={() => {
                    deletePlan(p.localId);
                    refresh();
                  }}
                  aria-label={`Delete ${p.name}`}
                >
                  Delete
                </Button>
              </Card>
            ))}
          </ul>
        )}
        {doc.plans.length >= 2 && (
          <Link to="/plans/compare" className={`${standaloneLinkClass} mt-3`}>
            Compare two plans
          </Link>
        )}
      </Section>
      <Section id="account-plans" title="In your account">
        {isLoading ? (
          <Spinner />
        ) : session ? (
          <AccountPlans />
        ) : (
          <Notice tone="info">
            <Link to="/login" className="font-medium">
              Log in
            </Link>{" "}
            to save plans to your account; plans on this device are imported when you log in.
          </Notice>
        )}
      </Section>
      </div>
    </PageContainer>
  );
}
