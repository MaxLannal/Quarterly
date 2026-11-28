import { useQuery } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuthLinks } from "@/features/auth/next";
import { api, isNotAvailable, unwrap } from "@/api/client";
import { EmptyState, PageContainer, PageHeader, standaloneLinkClass } from "@/components/layout/page";
import { Button } from "@/components/ui/button";
import { GlassFolder } from "@/components/ui/folder";
import { Input } from "@/components/ui/input";
import { ErrorText, NotAvailable, Notice, Spinner } from "@/components/ui/misc";
import { deletePlan, loadPlans, newLocalId, setActive, upsertPlan, type LocalPlan } from "@/features/planner/localPlans";
import { termLabel } from "@/features/planner/terms";
import { useSession } from "@/lib/session";

/** A band of the page: a mono label, a display-serif title and a hairline that runs to the edge. */
function Band({ id, label, title, children }: { id: string; label: string; title: string; children: ReactNode }) {
  return (
    <section id={id} aria-labelledby={`${id}-heading`} className="min-w-0 scroll-mt-24">
      <div className="mb-6 flex items-end gap-5">
        <div className="shrink-0">
          <p className="text-[12px] font-semibold text-muted">{label}</p>
          <h2 id={`${id}-heading`} className="font-display text-display-sm text-ink">
            {title}
          </h2>
        </div>
        <span aria-hidden="true" className="mb-4 h-px min-w-10 flex-1 bg-surface-strong" />
      </div>
      {children}
    </section>
  );
}

function AccountPlans() {
  const q = useQuery({ queryKey: ["plans"], queryFn: async () => unwrap(await api.GET("/plans")), retry: false });
  if (q.isLoading) return <Spinner label="Loading saved plans" />;
  if (q.error) return isNotAvailable(q.error) ? <NotAvailable feature="Saving plans to your account">Your plans are kept on this device for now.</NotAvailable> : <ErrorText>Could not load saved plans.</ErrorText>;
  if (!q.data?.length) return <EmptyState>No plans saved to your account yet.</EmptyState>;
  return (
    <ul className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
      {q.data.map((p) => (
        <li key={p.id} className="border border-hairline flex flex-col gap-1 rounded-[22px] bg-canvas-soft px-5 py-4 text-body-sm text-body">
          <span className="text-body-strong text-ink">
            {p.name} {p.is_primary && "(primary)"}
          </span>
          <span className="text-[12px] font-semibold text-muted">
            Catalog {p.catalog_year} · updated {p.updated_day}
          </span>
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
    <PageContainer className="max-w-7xl">
      <PageHeader title="My plans" />
      <div className="flex flex-col gap-16">
        <Band id="device-plans" label="Kept in this browser" title="On this device">
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
            // Each saved plan is a folder; its first courses are the files peeking out.
            <ul className="grid gap-x-6 gap-y-10 md:grid-cols-2 xl:grid-cols-3">
              {doc.plans.map((p, index) => {
                const items = p.state.items ?? [];
                const codes = items.flatMap((i) => (i.course ? [i.course] : []));
                const shown = codes.slice(0, 4);
                return (
                  <li key={p.localId} className="min-w-0">
                    <GlassFolder
                      tone={p.isPrimary ? "ember" : "smoke"}
                      tabRatio={0.55}
                      className="h-full hover:-translate-y-1"
                      tab={<span className="text-[12px] font-semibold truncate text-ink">{p.isPrimary ? "Primary plan" : `Plan ${String(index + 1).padStart(2, "0")}`}</span>}
                      aside={
                        <span className="text-[12px] font-semibold text-muted">
                          {items.length} course{items.length === 1 ? "" : "s"}
                        </span>
                      }
                      pocket={
                        <>
                          <span className="text-[12px] font-semibold min-w-0 flex-1 truncate text-muted">From {termLabel(p.state.entry_term)}</span>
                          <Button variant="outline" size="sm" onClick={() => open(p)}>
                            Open
                          </Button>
                        </>
                      }
                    >
                      <div className="flex flex-col gap-1 px-1">
                        <label className="sr-only" htmlFor={`name-${p.localId}`}>
                          Name of plan
                        </label>
                        <Input
                          id={`name-${p.localId}`}
                          defaultValue={p.name}
                          onBlur={(e) => e.target.value.trim() && e.target.value !== p.name && rename(p, e.target.value.trim())}
                          // D11 MP-1: the name reads as the plan's title; its field shows on hover and focus.
                          className="-ml-4 border-transparent bg-transparent font-display text-display-sm shadow-none hover:border-hairline-strong focus:bg-surface-card"
                        />
                        <span className="text-caption text-muted">
                          {p.isPrimary ? "Primary · " : ""}
                          {items.length} course{items.length === 1 ? "" : "s"} · updated {dayInWords(p.updatedDay)}
                        </span>
                      </div>
                      {shown.length > 0 && (
                        <ul className="mt-3 flex flex-wrap gap-2 px-1" aria-label={`First courses in ${p.name}`}>
                          {shown.map((code, n) => (
                            <li key={`${code}-${n}`} className="glass-file px-3 py-1.5 pr-5 font-mono text-[12px] font-medium text-ink">
                              {code}
                            </li>
                          ))}
                          {codes.length > shown.length && <li className="self-center px-1 text-caption text-muted">+{codes.length - shown.length} more</li>}
                        </ul>
                      )}
                      <div className="mt-4 flex flex-wrap items-center gap-x-1">
                        <Button variant="ghost" size="sm" onClick={() => duplicate(p)}>
                          Duplicate
                        </Button>
                        {!p.isPrimary && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => {
                              upsertPlan({ ...p, isPrimary: true }, false);
                              refresh();
                            }}
                          >
                            Set primary
                          </Button>
                        )}
                        {confirming === p.localId ? (
                          <span role="group" aria-label={`Delete ${p.name}?`} className="flex flex-wrap items-center gap-1 pl-3">
                            <span className="text-body-sm text-ink">Delete this plan?</span>
                            <Button
                              variant="destructive"
                              size="sm"
                              onClick={() => {
                                deletePlan(p.localId);
                                setConfirming(null);
                                refresh();
                              }}
                            >
                              Yes, delete
                            </Button>
                            <Button variant="ghost" size="sm" onClick={() => setConfirming(null)}>
                              Cancel
                            </Button>
                          </span>
                        ) : (
                          <Button variant="ghost" size="sm" className="text-error hover:bg-error-wash" onClick={() => setConfirming(p.localId)} aria-label={`Delete ${p.name}`}>
                            Delete
                          </Button>
                        )}
                      </div>
                    </GlassFolder>
                  </li>
                );
              })}
            </ul>
          )}
          {doc.plans.length >= 2 && (
            <Link to="/plans/compare" className={`${standaloneLinkClass} mt-8`}>
              Compare two plans
            </Link>
          )}
        </Band>
        <Band id="account-plans" label="Saved with your login" title="In your account">
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
        </Band>
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
