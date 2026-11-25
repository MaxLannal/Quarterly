import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuthLinks } from "@/features/auth/next";
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
  const authLinks = useAuthLinks();
  const [doc, setDoc] = useState(() => loadPlans());
  const refresh = () => setDoc(loadPlans());
  // DESIGN.md: deleting asks "are you sure?" in place (DF-7).
  const [confirming, setConfirming] = useState<string | null>(null);

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
      <PageHeader title="My plans" />
      <div className="flex flex-col gap-8">
      <Section id="device-plans" title="On this device">
        {doc.plans.length === 0 ? (
          <EmptyState>
            No plans yet.{" "}
            {session ? (
              <Link to="/plan">Set up a plan from your information</Link>
            ) : (
              <>
                <Link to="/plan">Start planning</Link>, or <Link to="/signup">sign up to set up your plan</Link>
              </>
            )}
          </EmptyState>
        ) : (
          <ul className="flex flex-col gap-3">
            {doc.plans.map((p) => (
              <Card as="li" variant="compact" key={p.localId} className="flex flex-col gap-3 px-5 md:flex-row md:items-center">
                <div className="flex min-w-0 flex-1 flex-col gap-1">
                  <label className="sr-only" htmlFor={`name-${p.localId}`}>
                    Name of plan
                  </label>
                  <Input
                    id={`name-${p.localId}`}
                    defaultValue={p.name}
                    onBlur={(e) => e.target.value.trim() && e.target.value !== p.name && rename(p, e.target.value.trim())}
                    // D11 MP-1: the name reads as the plan's title; its field shows on hover and focus.
                    className="-ml-3 border-transparent bg-transparent text-title-sm hover:border-hairline-strong focus:bg-surface-card"
                  />
                  <span className="text-caption text-muted">
                    {p.isPrimary ? "Primary · " : ""}
                    {(p.state.items ?? []).length} course{(p.state.items ?? []).length === 1 ? "" : "s"} · updated {dayInWords(p.updatedDay)}
                  </span>
                </div>
                <div className="flex flex-wrap gap-x-2">
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
                  {confirming === p.localId ? (
                    <span role="group" aria-label={`Delete ${p.name}?`} className="flex flex-wrap items-center gap-2">
                      <span className="text-body-sm text-ink">Delete this plan?</span>
                      <Button
                        variant="destructive"
                        onClick={() => {
                          deletePlan(p.localId);
                          setConfirming(null);
                          refresh();
                        }}
                      >
                        Yes, delete
                      </Button>
                      <Button variant="ghost" onClick={() => setConfirming(null)}>
                        Cancel
                      </Button>
                    </span>
                  ) : (
                    <Button variant="destructive" onClick={() => setConfirming(p.localId)} aria-label={`Delete ${p.name}`}>
                      Delete
                    </Button>
                  )}
                </div>
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
            <Link to={authLinks.login} className="font-medium">
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

/** "2026-11-16" as "Nov 16, 2026" (D11 MP-1); day-level dates only. */
function dayInWords(day: string): string {
  const [y, m, d] = day.split("-").map(Number);
  if (!y || !m || !d) return day;
  return new Date(Date.UTC(y, m - 1, d)).toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric", timeZone: "UTC" });
}
