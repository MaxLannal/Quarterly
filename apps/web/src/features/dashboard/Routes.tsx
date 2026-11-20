import { forwardRef, useEffect, useId, useImperativeHandle, useRef, useState, type ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { CheckIcon, CloseIcon, MoreIcon } from "@/components/ui/icons";
import { Input, Textarea } from "@/components/ui/input";
import { Menu } from "@/components/ui/menu";
import { Badge, Notice } from "@/components/ui/misc";
import { newLocalId, today, upsertPlan } from "@/features/planner/localPlans";
import { termLabel } from "@/features/planner/terms";
import { cn } from "@/lib/utils";
import { errorText, streamRoutes, useRouteActions, useRoutes, type Profile, type ProgramRef, type Route, type RouteCourse, type RouteIn, type StepEvent } from "./api";
import { byYear, courseHref, KIND_LABELS, programHref, ROLE_LABELS, routePlanState } from "./logic";
import { GuideMark } from "./parts";

const ROLE_COLORS: Record<RouteCourse["role"], string> = {
  major: "var(--color-primary)",
  minor: "var(--color-data-4)",
  core: "var(--color-data-1)",
  humanities: "var(--color-data-5)",
  research: "var(--color-data-3)",
  elective: "var(--color-muted-soft)",
};
const QUARTER_NAMES = { AU: "Autumn", WI: "Winter", SP: "Spring", SU: "Summer" } as const;

interface Draft {
  key: string;
  route: RouteIn;
  programs: ProgramRef[];
  fallback: boolean;
}

export interface RoutesHandle {
  draft: () => void;
}

/**
 * "Your routes" (the bottom of the dashboard): the routes the student kept, at most one chosen
 * (or all open: "keeping your options open"), AI drafts to keep or discard, archived ones folded
 * away, a side-by-side comparison, and "Open in planner".
 */
export const RoutesSection = forwardRef<RoutesHandle, { profile: Profile }>(function RoutesSection({ profile }, ref) {
  const routes = useRoutes(true);
  const actions = useRouteActions();
  const [drafts, setDrafts] = useState<Draft[]>([]);
  const [steps, setSteps] = useState<StepEvent[]>([]);
  const [drafting, setDrafting] = useState(false);
  const [draftNote, setDraftNote] = useState<string | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [focus, setFocus] = useState("");
  const [compare, setCompare] = useState<string[]>([]);
  const [comparing, setComparing] = useState(false);
  const abort = useRef<AbortController | null>(null);
  const sectionRef = useRef<HTMLElement>(null);
  const focusId = useId();
  useEffect(() => () => abort.current?.abort(), []);

  const items = routes.data?.items ?? [];
  const active = items.filter((r) => r.status !== "archived").sort((a, b) => Number(b.status === "chosen") - Number(a.status === "chosen") || a.position - b.position);
  const archived = items.filter((r) => r.status === "archived");
  const chosen = items.find((r) => r.status === "chosen");

  async function draft() {
    sectionRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    abort.current?.abort();
    const controller = new AbortController();
    abort.current = controller;
    setDrafting(true);
    setSteps([]);
    setProblem(null);
    setDraftNote(null);
    const fresh: Draft[] = [];
    try {
      const body = {
        count: 3,
        focus: focus.trim() || null,
        keep_existing_titles: [...items.map((r) => r.title), ...drafts.map((d) => d.route.title)].slice(0, 12),
      };
      for await (const event of streamRoutes(body, controller.signal)) {
        if (event.type === "step") setSteps((s) => [...s, event]);
        else if (event.type === "route") {
          const d: Draft = { key: `${Date.now()}-${fresh.length}`, route: event.route, programs: event.programs, fallback: event.fallback };
          fresh.push(d);
          setDrafts((old) => [...old, d]);
        } else if (event.type === "done") setDraftNote(event.note ?? null);
        else if (event.type === "error") throw new Error(event.message);
      }
      if (!fresh.length) setProblem("No routes came back this time. Try again, or tell your guide a little more first.");
    } catch (e) {
      if (!controller.signal.aborted) setProblem(e instanceof Error && e.constructor === Error ? e.message : errorText(e));
    } finally {
      if (abort.current === controller) setDrafting(false);
    }
  }
  useImperativeHandle(ref, () => ({ draft: () => void draft() }));

  function keep(d: Draft) {
    setProblem(null);
    actions.create.mutate(d.route, {
      onSuccess: () => setDrafts((all) => all.filter((x) => x.key !== d.key)),
      onError: (e) => setProblem(errorText(e, "The route")),
    });
  }

  async function keepAll() {
    for (const d of drafts) {
      try {
        await actions.create.mutateAsync(d.route);
        setDrafts((all) => all.filter((x) => x.key !== d.key));
      } catch (e) {
        setProblem(errorText(e, "The route"));
        break;
      }
    }
  }

  const stateLine = chosen ? (
    <>
      You've chosen <strong className="font-medium text-ink">“{chosen.title}”</strong>. The others stay here, open, in case you change your mind.
    </>
  ) : (
    "Keeping your options open — nothing is committed."
  );

  return (
    <section ref={sectionRef} id="routes" aria-labelledby={`${focusId}-title`} className="scroll-mt-20">
      <div className="mb-6 flex flex-col gap-3 border-t border-hairline-strong pt-10 sm:pt-14">
        <p className="flex items-center gap-2 text-caption-uppercase uppercase text-primary">
          <span aria-hidden="true" className="inline-block h-px w-6 bg-primary" /> Four years, several ways
        </p>
        <h2 id={`${focusId}-title`} className="font-display text-[36px] leading-[1.05] tracking-[-0.6px] text-ink sm:text-[52px]">
          Your <em className="italic text-primary">routes</em>
        </h2>
        <p className="max-w-reading text-body-md text-body" role="status">
          {routes.isLoading ? "Loading your routes…" : stateLine}
        </p>
      </div>

      <div className="mb-8 flex flex-col gap-3 rounded-xxl border border-hairline bg-canvas-soft p-4 sm:flex-row sm:items-end sm:p-5">
        <div className="flex min-w-0 flex-1 flex-col gap-1.5">
          <label htmlFor={focusId} className="text-caption-uppercase uppercase text-muted">
            Anything in particular? (optional)
          </label>
          <Input id={focusId} value={focus} maxLength={200} onChange={(e) => setFocus(e.target.value)} placeholder="More humanities, a lighter load, a minor in economics…" />
        </div>
        <Button onClick={() => void draft()} disabled={drafting}>
          <GuideMark size={14} className={drafting ? "dash-thinking" : undefined} /> {drafting ? "Drafting…" : items.length || drafts.length ? "Draft new routes" : "Draft my routes"}
        </Button>
        {drafting && (
          <Button variant="ghost" onClick={() => abort.current?.abort()}>
            Stop
          </Button>
        )}
      </div>

      {drafting && <DraftTrace steps={steps} />}
      {problem && (
        <Notice tone="error" role="alert" className="mb-6">
          {problem}
        </Notice>
      )}

      {drafts.length > 0 && (
        <div className="mb-12 flex flex-col gap-4" aria-label="Drafts" role="region">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h3 className="font-display text-display-sm text-ink">Drafts</h3>
              <p className="text-caption text-muted">
                {draftNote ?? "Drafted by an AI from your portrait; it can be wrong. Every course was checked against the catalog."} Nothing is saved until you keep it.
              </p>
            </div>
            <div className="flex gap-2">
              <Button variant="outline" onClick={() => void keepAll()} disabled={actions.create.isPending}>
                Keep all
              </Button>
              <Button variant="ghost" onClick={() => setDrafts([])}>
                Discard all
              </Button>
            </div>
          </div>
          <ul className="grid gap-4 lg:grid-cols-3">
            {drafts.map((d) => (
              <li key={d.key} className="min-w-0">
                <RouteCard
                  route={d.route}
                  programs={d.programs}
                  compact
                  draftActions={
                    <>
                      <Button size="sm" onClick={() => keep(d)} disabled={actions.create.isPending}>
                        <CheckIcon size={14} /> Keep
                      </Button>
                      <Button size="sm" variant="ghost" onClick={() => setDrafts((all) => all.filter((x) => x.key !== d.key))}>
                        Discard
                      </Button>
                    </>
                  }
                />
              </li>
            ))}
          </ul>
        </div>
      )}

      {routes.error ? (
        <Notice tone="error">{errorText(routes.error)}</Notice>
      ) : routes.isLoading ? (
        <div aria-hidden="true" className="skeleton h-64" />
      ) : active.length === 0 && drafts.length === 0 && !drafting ? (
        <EmptyRoutes onDraft={() => void draft()} profile={profile} />
      ) : (
        <ul className="flex flex-col gap-6">
          {active.map((r) => (
            <li key={r.id}>
              <SavedRoute
                route={r}
                profile={profile}
                comparing={compare.includes(r.id)}
                onCompare={(on) => setCompare((c) => (on ? [...c.filter((x) => x !== r.id), r.id].slice(-2) : c.filter((x) => x !== r.id)))}
              />
            </li>
          ))}
        </ul>
      )}

      {compare.length === 2 && (
        <div className="sticky bottom-4 z-30 mx-auto mt-6 flex w-fit items-center gap-2 rounded-pill bg-ink p-1.5 pl-4 text-on-dark shadow-overlay">
          <span className="text-body-sm">2 routes selected</span>
          <Button size="sm" onClick={() => setComparing(true)}>
            Compare side by side
          </Button>
          <button type="button" aria-label="Clear the comparison" onClick={() => setCompare([])} className="inline-flex size-11 items-center justify-center rounded-pill hover:bg-on-dark/10">
            <CloseIcon size={14} />
          </button>
        </div>
      )}

      {archived.length > 0 && (
        <details className="group mt-10 rounded-xxl border border-hairline bg-canvas-soft p-4 sm:p-5">
          <summary className="flex min-h-11 cursor-pointer list-none items-center justify-between gap-2 text-title-sm text-ink">
            Archived routes ({archived.length})
            <span aria-hidden="true" className="text-muted transition-transform group-open:rotate-180">⌄</span>
          </summary>
          <ul className="mt-4 flex flex-col gap-4">
            {archived.map((r) => (
              <li key={r.id}>
                <SavedRoute route={r} profile={profile} comparing={false} onCompare={() => undefined} />
              </li>
            ))}
          </ul>
        </details>
      )}

      <CompareDialog open={comparing} onClose={() => setComparing(false)} routes={compare.map((id) => items.find((r) => r.id === id)).filter((r): r is Route => !!r)} />
    </section>
  );
});

function DraftTrace({ steps }: { steps: StepEvent[] }) {
  const latest = new Map<string, StepEvent>();
  for (const s of steps) latest.set(`${s.tool}:${s.label}`, s);
  return (
    <div role="status" aria-live="polite" className="mb-8 rounded-xxl bg-surface-dark p-5 text-on-dark">
      <p className="flex items-center gap-2 font-display text-title-md italic text-on-dark">
        <GuideMark size={16} className="dash-thinking text-primary" /> Your guide is drafting routes from your portrait…
      </p>
      {latest.size > 0 ? (
        <ul className="mt-3 grid gap-1.5 text-body-sm text-on-dark-soft sm:grid-cols-2">
          {[...latest.values()].slice(-10).map((s) => (
            <li key={`${s.tool}:${s.label}`} className="dash-rise flex items-center gap-2">
              <span aria-hidden="true" className="inline-flex size-4 items-center justify-center">
                {s.status === "done" ? <CheckIcon size={13} className="text-success" /> : s.status === "failed" ? <CloseIcon size={13} className="text-error" /> : <span className="inline-block size-1.5 animate-pulse rounded-pill bg-on-dark" />}
              </span>
              <span className="truncate">{s.label}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-2 text-body-sm text-on-dark-soft">Reading your portrait…</p>
      )}
    </div>
  );
}

function EmptyRoutes({ onDraft, profile }: { onDraft: () => void; profile: Profile }) {
  const thin = profile.completeness < 0.3;
  return (
    <div className="relative overflow-hidden rounded-xxl border border-dashed border-hairline-strong bg-canvas-soft p-6 sm:p-10">
      <p className="max-w-reading font-display text-display-sm text-ink">No routes yet. That's the most open your options will ever be.</p>
      <p className="mt-2 max-w-reading text-body-md text-body">
        {thin ? "Tell your guide a little about yourself first, then let it draft three different routes: one around a major, one that combines two things you love, and one that keeps every door open." : "Your guide can draft three different routes from your portrait: one around a major, one that combines two of your interests, and one that keeps every door open."}
      </p>
      <Button className="mt-5" onClick={onDraft}>
        Draft my routes
      </Button>
    </div>
  );
}

// ------------------------------------------------------------------------------ cards

function SavedRoute({ route, profile, comparing, onCompare }: { route: Route; profile: Profile; comparing: boolean; onCompare: (on: boolean) => void }) {
  const actions = useRouteActions();
  const navigate = useNavigate();
  const [menu, setMenu] = useState(false);
  const [renaming, setRenaming] = useState(false);
  const renameRef = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (renaming) renameRef.current?.focus();
  }, [renaming]);
  const [title, setTitle] = useState(route.title);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [planning, setPlanning] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const compareId = useId();
  const chosen = route.status === "chosen";
  const archived = route.status === "archived";

  const update = (patch: Parameters<typeof actions.update.mutate>[0]["patch"]) =>
    actions.update.mutate({ id: route.id, patch }, { onError: (e) => setProblem(errorText(e, "The route")) });

  const plan = routePlanState(route, profile.class_year);
  const placed = plan.state.items?.length ?? 0;
  function openInPlanner() {
    const ok = upsertPlan({ localId: newLocalId(), name: `Route: ${route.title}`.slice(0, 60), isPrimary: false, state: plan.state, updatedDay: today() });
    if (!ok) {
      setProblem("Your browser did not let Quarterly store the plan (storage is full or blocked).");
      return;
    }
    navigate("/plan");
  }

  return (
    <>
      <RouteCard
        route={route}
        programs={route.programs}
        chosen={chosen}
        archived={archived}
        title={
          renaming ? (
            <form
              className="flex flex-wrap items-center gap-2"
              onSubmit={(e) => {
                e.preventDefault();
                if (title.trim()) update({ title: title.trim() });
                setRenaming(false);
              }}
            >
              <label htmlFor={`${compareId}-title`} className="sr-only">
                Route name
              </label>
              <Input id={`${compareId}-title`} value={title} maxLength={80} ref={renameRef} onChange={(e) => setTitle(e.target.value)} onKeyDown={(e) => e.key === "Escape" && (e.stopPropagation(), setRenaming(false))} className="max-w-md" />
              <Button size="sm" type="submit">
                Save
              </Button>
              <Button size="sm" variant="ghost" type="button" onClick={() => setRenaming(false)}>
                Cancel
              </Button>
            </form>
          ) : undefined
        }
        menu={
          <Menu
            label={`More actions for ${route.title}`}
            open={menu}
            onOpenChange={setMenu}
            trigger={<MoreIcon size={18} />}
            items={[
              {
                label: "Rename",
                onSelect: () => {
                  setTitle(route.title);
                  setRenaming(true);
                },
              },
              archived ? { label: "Restore", onSelect: () => update({ status: "open" }) } : { label: "Archive", onSelect: () => update({ status: "archived" }) },
              { label: "Delete…", danger: true, onSelect: () => setConfirmDelete(true) },
            ]}
          />
        }
        footer={
          <>
            <NoteBox route={route} onSave={(note) => update({ note })} />
            {problem && <p className="text-caption text-error">{problem}</p>}
            <div className="flex flex-wrap items-center gap-2">
              {archived ? (
                <Button size="sm" variant="outline" onClick={() => update({ status: "open" })}>
                  Restore
                </Button>
              ) : chosen ? (
                <Button size="sm" variant="outline" onClick={() => update({ status: "open" })}>
                  Keep my options open
                </Button>
              ) : (
                <Button size="sm" onClick={() => update({ status: "chosen" })}>
                  Choose this route
                </Button>
              )}
              <Button size="sm" variant="outline" onClick={() => setPlanning(true)} disabled={route.courses.length === 0}>
                Open in planner
              </Button>
              {!archived && (
                <label className="ml-auto inline-flex min-h-11 cursor-pointer items-center gap-2 rounded-pill px-3 text-body-sm text-body hover:bg-surface-strong">
                  <input type="checkbox" checked={comparing} onChange={(e) => onCompare(e.target.checked)} />
                  Compare
                </label>
              )}
            </div>
          </>
        }
      />
      <Dialog open={confirmDelete} onClose={() => setConfirmDelete(false)} title={`Delete “${route.title}”?`} description="It goes for good; drafting again makes new routes, not this one.">
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={() => setConfirmDelete(false)}>
            Cancel
          </Button>
          <Button
            variant="destructive"
            onClick={() => {
              setConfirmDelete(false);
              actions.remove.mutate(route.id, { onError: (e) => setProblem(errorText(e)) });
            }}
          >
            Delete route
          </Button>
        </div>
      </Dialog>
      <Dialog open={planning} onClose={() => setPlanning(false)} title="Open this route in the planner" description="Quarterly makes a new plan from it in this browser; your other plans stay as they are.">
        <ul className="mb-4 flex list-disc flex-col gap-1.5 pl-5 text-body-sm text-body">
          <li>
            {placed} course{placed === 1 ? "" : "s"} placed by year and quarter, starting {termLabel(plan.state.entry_term)} (from your class year{profile.class_year ? "" : ", not set yet"}).
          </li>
          {route.courses.some((c) => !c.quarter) && <li>Courses without a set quarter go to the lightest quarter of their year in which they are usually offered.</li>}
          {route.program_ids.length > 0 && <li>Programs: {route.programs.map((p) => p.name).join(", ")}.</li>}
          {plan.skipped.length > 0 && <li>Not placed (a summer after the last year): {plan.skipped.join(", ")}.</li>}
          <li>Milestones, notes and fit scores stay here on your dashboard. The planner checks every rule and prerequisite.</li>
        </ul>
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={() => setPlanning(false)}>
            Cancel
          </Button>
          <Button onClick={openInPlanner}>Open in planner</Button>
        </div>
      </Dialog>
    </>
  );
}

function NoteBox({ route, onSave }: { route: Route; onSave: (note: string | null) => void }) {
  const id = useId();
  const [draft, setDraft] = useState(route.note ?? "");
  useEffect(() => setDraft(route.note ?? ""), [route.note]);
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-caption-uppercase uppercase text-muted">
        Your note
      </label>
      <Textarea
        id={id}
        rows={2}
        maxLength={1200}
        value={draft}
        placeholder="Why this one, what to ask an adviser, what would change your mind…"
        onChange={(e) => setDraft(e.target.value)}
        onBlur={() => {
          if (draft.trim() !== (route.note ?? "").trim()) onSave(draft.trim() || null);
        }}
      />
    </div>
  );
}

function RouteCard({
  route,
  programs,
  chosen = false,
  archived = false,
  compact = false,
  title,
  menu,
  footer,
  draftActions,
}: {
  route: RouteIn;
  programs: ProgramRef[];
  chosen?: boolean;
  archived?: boolean;
  compact?: boolean;
  title?: ReactNode;
  menu?: ReactNode;
  footer?: ReactNode;
  draftActions?: ReactNode;
}) {
  const ai = route.origin === "ai";
  return (
    <article
      className={cn(
        "flex h-full min-w-0 flex-col gap-4 rounded-xxl border bg-surface-card p-5 sm:p-6",
        chosen ? "border-primary shadow-[0_0_0_3px_var(--color-primary-wash)]" : "border-hairline",
        archived && "opacity-80",
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex flex-wrap items-center gap-1.5">
          {chosen && (
            <Badge tone="success" casing="normal">
              Your route
            </Badge>
          )}
          <Badge icon={false}>{KIND_LABELS[route.kind]}</Badge>
          <Badge icon={false} className={ai ? "bg-primary-wash text-primary" : ""}>
            {ai ? "Drafted" : "Yours"}
          </Badge>
          {archived && <Badge icon={false}>Archived</Badge>}
        </div>
        {menu}
      </div>
      <div className="flex flex-col gap-1.5">
        {title ?? <h3 className={cn("font-display text-ink", compact ? "text-title-md" : "text-display-sm")}>{route.title}</h3>}
        {route.tagline && <p className="text-body-sm text-body-strong">{route.tagline}</p>}
        {programs.length > 0 && (
          <p className="flex flex-wrap gap-x-3 text-body-sm">
            {programs.map((p) => (
              <Link key={p.id} to={programHref(p.id)} className="inline-flex min-h-11 items-center text-primary underline underline-offset-2 hover:text-primary-hover">
                {p.name}
              </Link>
            ))}
          </p>
        )}
        {route.summary && <p className={cn("text-body-sm text-body", compact && "line-clamp-4")}>{route.summary}</p>}
        {ai && !/without the AI/i.test(route.summary) && <p className="text-caption text-muted">Written by an AI and can be wrong; the courses are real and link to their pages.</p>}
      </div>
      <Timeline courses={route.courses} compact={compact} />
      {!compact && <RoleLegend courses={route.courses} />}
      <div className={cn("grid gap-5", !compact && "md:grid-cols-[minmax(0,1fr)_260px]")}>
        {route.milestones.length > 0 && (
          <div>
            <p className="mb-2 text-caption-uppercase uppercase text-muted">Milestones</p>
            <ol className="flex flex-col gap-2 border-l border-hairline-strong pl-4">
              {route.milestones.slice(0, compact ? 3 : 12).map((m, i) => (
                <li key={i} className="relative text-body-sm text-body">
                  <span aria-hidden="true" className="absolute -left-[21px] top-1.5 size-2.5 rounded-pill border-2 border-surface-card bg-primary" />
                  <span className="font-medium text-ink">{m.when}</span> · {m.text}
                </li>
              ))}
            </ol>
          </div>
        )}
        <FitBars fit={route.fit} />
      </div>
      {!compact && <WhyCourses courses={route.courses} />}
      {footer && <div className="mt-auto flex flex-col gap-3 border-t border-hairline pt-4">{footer}</div>}
      {draftActions && <div className="mt-auto flex flex-wrap gap-2 border-t border-hairline pt-3">{draftActions}</div>}
    </article>
  );
}

/** Four years of the route, quarter by quarter, each course a chip that opens its page. */
function Timeline({ courses, compact }: { courses: RouteCourse[]; compact: boolean }) {
  const years = byYear(courses);
  if (courses.length === 0) return <p className="text-body-sm text-muted">No courses in this route.</p>;
  return (
    <div className={cn("grid gap-3", compact ? "grid-cols-1" : "grid-cols-1 sm:grid-cols-2 xl:grid-cols-4")}>
      {[1, 2, 3, 4].map((y) => {
        const list = years.get(y) ?? [];
        return (
          <div key={y} className={cn("min-w-0 rounded-xl bg-canvas-soft p-3", compact && "flex items-start gap-3 p-2.5")}>
            <p className={cn("text-caption-uppercase uppercase text-muted", compact ? "w-14 shrink-0 pt-1.5" : "mb-2")}>Year {y}</p>
            {list.length === 0 ? (
              <p className="pt-1 text-caption text-muted-soft">Open</p>
            ) : (
              <ul className={cn("flex min-w-0 gap-1.5", compact ? "flex-wrap" : "flex-col")}>
                {list.map((c) => (
                  <li key={c.code} className="min-w-0">
                    <CourseChip course={c} compact={compact} />
                  </li>
                ))}
              </ul>
            )}
          </div>
        );
      })}
    </div>
  );
}

function CourseChip({ course, compact }: { course: RouteCourse; compact: boolean }) {
  const usual = (course.offered ?? []).map((q) => QUARTER_NAMES[q]);
  const quarter = course.quarter ? QUARTER_NAMES[course.quarter] : usual.length && usual.length < 3 ? `usually ${usual.join(", ")}` : "Any quarter";
  return (
    <Link
      to={courseHref(course.code)}
      title={course.note ? `${course.title}: ${course.note}` : course.title}
      className={cn("group flex min-h-11 min-w-0 items-center gap-2 rounded-lg border border-hairline bg-surface-card py-1.5 pl-2 pr-2.5 hover:border-hairline-strong hover:shadow-hover", compact && "min-h-9 py-1")}
      style={{ boxShadow: `inset 3px 0 0 ${ROLE_COLORS[course.role]}` }}
    >
      <span className="min-w-0 flex-1">
        <span className="block font-sans text-[11px] font-semibold uppercase tabular-nums tracking-wide text-muted">
          {course.code}
          {!compact && <span className="font-normal normal-case tracking-normal"> · {quarter}</span>}
        </span>
        {!compact && <span className="block truncate text-caption text-ink group-hover:text-primary">{course.title}</span>}
      </span>
      <span className="sr-only">
        , {ROLE_LABELS[course.role]}, {quarter}
        {compact ? `, ${course.title}` : ""}
      </span>
    </Link>
  );
}

function RoleLegend({ courses }: { courses: RouteCourse[] }) {
  const roles = [...new Set(courses.map((c) => c.role))];
  return (
    <ul className="flex flex-wrap gap-x-4 gap-y-1 text-caption text-muted" aria-label="Course roles">
      {roles.map((r) => (
        <li key={r} className="inline-flex items-center gap-1.5">
          <span aria-hidden="true" className="inline-block h-3 w-1 rounded-pill" style={{ background: ROLE_COLORS[r] }} />
          {ROLE_LABELS[r]}
        </li>
      ))}
    </ul>
  );
}

function WhyCourses({ courses }: { courses: RouteCourse[] }) {
  const noted = courses.filter((c) => c.note);
  if (noted.length === 0) return null;
  return (
    <details className="group rounded-xl border border-hairline px-4">
      <summary className="flex min-h-11 cursor-pointer list-none items-center justify-between text-body-sm font-medium text-ink">
        Why these courses
        <span aria-hidden="true" className="text-muted transition-transform group-open:rotate-180">⌄</span>
      </summary>
      <ul className="flex flex-col gap-2 pb-4">
        {noted.map((c) => (
          <li key={c.code} className="text-body-sm text-body">
            <Link to={courseHref(c.code)} className="font-medium text-primary underline underline-offset-2">
              {c.code}
            </Link>{" "}
            {c.title} · <span className="text-muted">{ROLE_LABELS[c.role]}</span>: {c.note}
          </li>
        ))}
      </ul>
    </details>
  );
}

function FitBars({ fit }: { fit: RouteIn["fit"] }) {
  const rows: [string, number][] = [
    ["Your interests", fit.interests],
    ["Your career plans", fit.career],
    ["Your humanities goal", fit.humanities],
  ];
  return (
    <div>
      <p className="mb-2 text-caption-uppercase uppercase text-muted">How it fits you</p>
      <dl className="flex flex-col gap-2">
        {rows.map(([label, value]) => {
          const pct = Math.round(Math.max(0, Math.min(1, value)) * 100);
          return (
            <div key={label} className="flex flex-col gap-1">
              <div className="flex justify-between text-caption">
                <dt className="text-body">{label}</dt>
                <dd className="tabular-nums text-muted">{pct}%</dd>
              </div>
              <div aria-hidden="true" className="h-1.5 overflow-hidden rounded-pill bg-surface-strong">
                <div className="h-full rounded-pill bg-primary" style={{ width: `${pct}%` }} />
              </div>
            </div>
          );
        })}
        {fit.workload && (
          <div className="flex justify-between text-caption">
            <dt className="text-body">Workload</dt>
            <dd className="capitalize text-muted">{fit.workload}</dd>
          </div>
        )}
      </dl>
      <p className="mt-2 text-caption text-muted-soft">An estimate, not a grade.</p>
    </div>
  );
}

function CompareDialog({ open, onClose, routes }: { open: boolean; onClose: () => void; routes: Route[] }) {
  if (routes.length !== 2) return null;
  const [a, b] = routes as [Route, Route];
  const shared = new Set(a.courses.map((c) => c.code).filter((c) => b.courses.some((x) => x.code === c)));
  return (
    <Dialog open={open} onClose={onClose} title="Two routes, side by side" description={shared.size ? `${shared.size} course${shared.size === 1 ? "" : "s"} in both (marked).` : "They share no course."} className="max-w-4xl">
      <div className="grid grid-cols-2 gap-4">
        {[a, b].map((r) => (
          <div key={r.id} className="min-w-0">
            <h3 className="mb-1 font-display text-title-md text-ink">{r.title}</h3>
            <p className="mb-3 text-caption text-muted">{KIND_LABELS[r.kind]}{r.programs.length ? ` · ${r.programs.map((p) => p.name).join(", ")}` : ""}</p>
            {[...byYear(r.courses).entries()].map(([y, list]) => (
              <div key={y} className="mb-3">
                <p className="text-caption-uppercase uppercase text-muted">Year {y}</p>
                {list.length === 0 ? (
                  <p className="text-caption text-muted-soft">Open</p>
                ) : (
                  <ul className="flex flex-col">
                    {list.map((c) => (
                      <li key={c.code} className="flex min-w-0 items-baseline gap-2 text-caption">
                        <Link to={courseHref(c.code)} onClick={onClose} className={cn("shrink-0 font-semibold tabular-nums underline-offset-2 hover:underline", shared.has(c.code) ? "text-primary" : "text-ink")}>
                          {c.code}
                        </Link>
                        <span className="truncate text-body">{c.title}</span>
                        {shared.has(c.code) && <span className="sr-only">(in both routes)</span>}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
          </div>
        ))}
      </div>
    </Dialog>
  );
}
