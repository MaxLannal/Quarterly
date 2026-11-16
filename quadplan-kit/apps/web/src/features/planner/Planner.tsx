import {
  DndContext,
  DragOverlay,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type Announcements,
  type DragEndEvent,
  pointerWithin,
  rectIntersection,
  type CollisionDetection,
  type DragStartEvent,
} from "@dnd-kit/core";
import { useEffect, useMemo, useReducer, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/api/client";
import { useCourseMap, usePlanPrograms, usePrograms } from "@/api/hooks";
import type { ChangeOp, Issue, PlanItem, ProgramSummary } from "@/api/types";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { CloseIcon, SparkIcon } from "@/components/ui/icons";
import { Notice } from "@/components/ui/misc";
import { AdvisorSheet } from "@/features/advisor/AdvisorPanel";
import { GenerateDialog } from "@/features/generate/GenerateDialog";
import { ProgramPickerBody, StatusBadge } from "@/features/programs/ProgramPicker";
import { useMediaQuery } from "@/lib/motion";
import { useSession } from "@/lib/session";
import { applyOps, ChangeOpError } from "./changes";
import { highlightFor, PlannerContext, stripKind, type PlannerContextValue, type RequirementTag } from "./context";
import { GoalsTab } from "./GoalsTab";
import { IssuesTab } from "./IssuesTab";
import { storedRemoteId, upsertPlan, type LocalPlan } from "./localPlans";
import { addCourseOps, editorReducer, initEditor, itemLabel, moveItemOps, type EditResult } from "./planModel";
import { CreditsEditor } from "@/features/credits/CreditsEditor";
import { DrawerButton, PlanDrawer, type DrawerTab } from "./PlanDrawer";
import { PlanGrid } from "./PlanGrid";
import { RequirementTree } from "./RequirementTree";
import { TermPickerDialog } from "./TermPickerDialog";
import { graduationTerm, planTerms, termLabel } from "./terms";
import { useVerify } from "./useVerify";
import { PlanVerdict } from "./VerifierBadge";

type DragData = { kind: "item"; itemId: string } | { kind: "course"; code: string };

/** Drop on the quarter under the pointer; keyboard drags (no pointer) use the overlap. */
const collision: CollisionDetection = (args) => {
  const hits = pointerWithin(args);
  return hits.length ? hits : rectIntersection(args);
};

/** Turn a drop into an edit: an existing card moves, a requirement-tree course is added. */
export function dropResult(data: DragData | undefined, toTerm: string | undefined, items: PlanItem[]): EditResult | null {
  if (!data || !toTerm) return null;
  if (data.kind === "course") return addCourseOps(data.code, toTerm);
  const item = items.find((i) => i.id === data.itemId);
  return item ? moveItemOps(item, toTerm) : null;
}

/** Requirement tag per course: the deepest progress node that counts it. */
function requirementTags(
  progress: { node_id: string; program_id: string; label?: string | null; courses?: string[] }[],
  programIds: string[],
  names: Map<string, string>,
  types: Map<string, ProgramSummary["type"]>,
): Map<string, RequirementTag> {
  const out = new Map<string, RequirementTag & { depth: number }>();
  for (const p of progress) {
    const depth = p.node_id.split("/").length;
    for (const code of p.courses ?? []) {
      const prev = out.get(code);
      if (prev && prev.depth >= depth) continue;
      const leaf = p.label ?? p.node_id.split("/").pop() ?? p.node_id;
      out.set(code, {
        programId: p.program_id,
        label: `${names.get(p.program_id) ?? p.program_id} · ${leaf}`,
        kind: stripKind(p.program_id, programIds, types),
        depth,
      });
    }
  }
  return out;
}

interface PlannerProps {
  initial: LocalPlan;
  autoGenerate?: boolean;
}

export function Planner({ initial, autoGenerate = false }: PlannerProps) {
  const [state, dispatch] = useReducer(editorReducer, initial, (p) => initEditor(p.state, p.name));
  const [remoteId, setRemoteId] = useState(initial.remoteId);
  // The plan as last saved to the account; generation uses the saved plan only while equal.
  const [savedSnapshot, setSavedSnapshot] = useState<string | null>(() => (initial.remoteId ? JSON.stringify(initial.state) : null));
  const [stored, setStored] = useState(true);
  const [saveMsg, setSaveMsg] = useState<string | null>(null);
  const [showSummer, setShowSummer] = useState(() => (initial.state.items ?? []).some((i) => i.term.endsWith("-SU")));
  const [selectedIssue, setSelectedIssue] = useState<Issue | null>(null);
  const [moveTarget, setMoveTarget] = useState<PlanItem | null>(null);
  const [addTarget, setAddTarget] = useState<string | null>(null);
  const [pickPrograms, setPickPrograms] = useState(false);
  const [generateOpen, setGenerateOpen] = useState(autoGenerate);
  const [drawer, setDrawer] = useState<{ open: boolean; tab: DrawerTab }>({ open: false, tab: "requirements" });
  const [advisorOpen, setAdvisorOpen] = useState(false);
  const [dragging, setDragging] = useState<string | null>(null);
  const desktop = useMediaQuery("(min-width: 1024px)");
  const { data: session } = useSession();

  const plan = state.plan;
  const items = useMemo(() => plan.items ?? [], [plan.items]);
  const terms = useMemo(() => planTerms(plan.entry_term, graduationTerm(plan)), [plan]);
  const programIds = (plan.programs ?? []).map((p) => p.program_id);
  const verify = useVerify(plan);
  const report = verify.report;
  const courses = useCourseMap(
    items.flatMap((i) => (i.course ? [i.course] : [])),
    plan.catalog_year,
  );
  const allPrograms = usePrograms(plan.catalog_year).data ?? [];
  const programQueries = usePlanPrograms(programIds, plan.catalog_year);
  const names = new Map(allPrograms.map((p) => [p.id, p.name]));
  programQueries.forEach((q) => q.data && names.set(q.data.id, q.data.name));
  const types = new Map(allPrograms.map((p) => [p.id, p.type]));
  programQueries.forEach((q) => q.data && types.set(q.data.id, q.data.type));
  const tags = requirementTags(report?.progress ?? [], programIds, names, types);
  const issues = report?.issues ?? [];
  const errorCount = issues.filter((i) => i.level === "error").length;
  const highlight = useMemo(() => highlightFor(selectedIssue, items), [selectedIssue, items]);
  const savedPlanId = remoteId && savedSnapshot === JSON.stringify(plan) ? remoteId : null;

  // Autosave every edit to this device (localStorage, never throws).
  useEffect(() => {
    setStored(upsertPlan({ ...initial, remoteId, name: state.name, state: plan, years: undefined }));
  }, [initial, remoteId, plan, state.name]);

  useEffect(() => {
    if (highlight.items.size || highlight.terms.size) {
      document.querySelector('[data-highlighted="true"]')?.scrollIntoView?.({ block: "nearest" });
    }
  }, [highlight]);

  function tryOps(ops: ChangeOp[]): boolean {
    try {
      applyOps(plan, ops);
    } catch (e) {
      if (e instanceof ChangeOpError) {
        dispatch({ type: "edit", result: { ok: false, error: `Could not apply the change: ${e.message}` } });
        return false;
      }
      throw e;
    }
    dispatch({ type: "ops", ops });
    return true;
  }

  /** Toolbar: open the drawer at `tab`, or close it when that tab is already showing. */
  function toggleDrawer(tab: DrawerTab) {
    setDrawer((d) => (d.open && d.tab === tab ? { ...d, open: false } : { open: true, tab }));
  }

  const ctx: PlannerContextValue = {
    plan,
    courses,
    programs: allPrograms,
    issues,
    highlight,
    tags,
    edit: (result) => dispatch({ type: "edit", result }),
    applyOps: (ops) => void tryOps(ops),
    openMoveTo: setMoveTarget,
    openAddTo: setAddTarget,
  };

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 4 } }), useSensor(KeyboardSensor));

  function nameOf(id: string | number): string {
    const s = String(id);
    if (s.startsWith("new:")) return s.slice(4);
    const item = items.find((i) => i.id === s);
    return item ? itemLabel(item) : s;
  }
  const where = (id: string | number | undefined) => (id ? termLabel(String(id)) : "nowhere");
  const announcements: Announcements = {
    onDragStart: ({ active }) => `Picked up ${nameOf(active.id)}.`,
    onDragOver: ({ active, over }) => `${nameOf(active.id)} is over ${where(over?.id)}.`,
    onDragEnd: ({ active, over }) => (over ? `${nameOf(active.id)} dropped on ${where(over.id)}.` : `${nameOf(active.id)} dropped.`),
    onDragCancel: ({ active }) => `Cancelled moving ${nameOf(active.id)}.`,
  };

  function onDragStart(e: DragStartEvent) {
    setDragging(nameOf(e.active.id));
  }

  function onDragEnd(e: DragEndEvent) {
    setDragging(null);
    const result = dropResult(e.active.data.current as DragData | undefined, e.over ? String(e.over.id) : undefined, items);
    if (result) dispatch({ type: "edit", result });
  }

  async function save() {
    const ok = upsertPlan({ ...initial, remoteId, name: state.name, state: plan, years: undefined });
    if (!session) {
      setSaveMsg(ok ? "Saved on this device. Log in to save it to your account." : "Could not save: this browser is blocking storage.");
      return;
    }
    // An import on login that ran while this plan was open stored the account plan's id.
    const accountPlanId = remoteId ?? storedRemoteId(initial.localId);
    try {
      const res = accountPlanId
        ? await api.PATCH("/plans/{plan_id}", { params: { path: { plan_id: accountPlanId } }, body: { name: state.name, state: plan } })
        : await api.POST("/plans", { body: { name: state.name, is_primary: initial.isPrimary, state: plan } });
      if (res.response.status === 501) {
        setSaveMsg("Saving to your account is not available yet. Your plan is saved on this device.");
      } else if (res.data) {
        setRemoteId(res.data.id);
        setSavedSnapshot(JSON.stringify(plan));
        setSaveMsg("Saved to your account.");
      } else {
        setSaveMsg("Could not save to your account. Your plan is saved on this device.");
      }
    } catch {
      setSaveMsg("Could not reach the server. Your plan is saved on this device.");
    }
  }

  const drawerTabs = [
    {
      key: "requirements" as const,
      label: "Requirements",
      content: <RequirementTree details={programQueries.map((q, i) => ({ ...q, id: programIds[i] ?? "" }))} progress={report?.progress} onAddProgram={() => setPickPrograms(true)} />,
    },
    {
      key: "goals" as const,
      label: "Goals",
      content: <GoalsTab goals={plan.goals ?? []} entryTerm={plan.entry_term} terms={terms} issues={issues} programs={allPrograms} planPrograms={programIds} onChange={(goals) => dispatch({ type: "goals", goals })} />,
    },
    {
      key: "credits" as const,
      label: "Credits",
      content: (
        <div className="space-y-3">
          <h3 className="text-title-sm">Test, placement and transfer credits</h3>
          <CreditsEditor credits={plan.credits ?? []} catalogYear={plan.catalog_year} onChange={(credits) => dispatch({ type: "credits", credits })} />
        </div>
      ),
    },
    {
      key: "issues" as const,
      label: "Issues",
      content: <IssuesTab verify={verify} selected={selectedIssue} onSelect={setSelectedIssue} />,
    },
  ];

  return (
    <PlannerContext.Provider value={ctx}>
      <div className="mx-auto flex w-full max-w-tool flex-col gap-3 px-4 pb-16 pt-4 sm:px-6 lg:px-8">
        <h1 className="sr-only">Planner</h1>
        <div className="flex flex-wrap items-start gap-x-8 gap-y-4">
          <div className="flex min-w-0 flex-col gap-1 self-end">
            <p className="text-caption text-muted">Not official advising. Confirm with your adviser and My Planner.</p>
          </div>
          <div className="flex min-w-0 flex-col gap-1">
            <span className="text-caption-uppercase uppercase text-muted">Catalog {plan.catalog_year}</span>
            <ul className="flex flex-wrap items-center gap-2" aria-label="Programs on this plan">
              {(plan.programs ?? []).map((p) => {
                const summary = allPrograms.find((x) => x.id === p.program_id);
                return (
                  <li key={p.program_id} className="flex min-h-11 animate-fade-in items-center gap-1 rounded-pill border border-hairline-strong bg-surface-card pl-4 text-body-sm text-ink">
                    {names.get(p.program_id) ?? p.program_id}
                    {summary && <StatusBadge status={summary.status} />}
                    <Button
                      variant="ghost"
                      size="icon"
                      aria-label={`Remove program ${names.get(p.program_id) ?? p.program_id}`}
                      onClick={() => dispatch({ type: "programs", programs: (plan.programs ?? []).filter((x) => x.program_id !== p.program_id) })}
                      className="-my-px text-muted hover:text-ink"
                    >
                      <CloseIcon size={14} />
                    </Button>
                  </li>
                );
              })}
              <li>
                <Button variant="outline" onClick={() => setPickPrograms(true)}>
                  + Program
                </Button>
              </li>
            </ul>
          </div>
        </div>

        {/* Toolbar: the panels open on demand, so the grid keeps the page (FEEDBACK F4). */}
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1 border-y border-hairline py-2">
          <DrawerButton active={drawer.tab === "requirements"} open={drawer.open} onClick={() => toggleDrawer("requirements")}>
            Requirements
          </DrawerButton>
          <DrawerButton active={drawer.tab === "goals"} open={drawer.open} onClick={() => toggleDrawer("goals")}>
            Goals
          </DrawerButton>
          <DrawerButton active={drawer.tab === "credits"} open={drawer.open} onClick={() => toggleDrawer("credits")}>
            Credits
            {(plan.credits ?? []).length > 0 && <span className="text-muted tabular-nums">{(plan.credits ?? []).length}</span>}
          </DrawerButton>
          <DrawerButton
            active={drawer.tab === "issues"}
            open={drawer.open}
            onClick={() => toggleDrawer("issues")}
          >
            Check plan{" "}
            {errorCount > 0 && <span className="sr-only">({errorCount} {errorCount === 1 ? "error" : "errors"})</span>}
            {errorCount > 0 && (
              <span aria-hidden="true" data-testid="issue-count" className="inline-flex min-w-5 animate-fade-in justify-center rounded-pill bg-error-wash px-1.5 text-caption tabular-nums text-error">
                {errorCount}
              </span>
            )}
          </DrawerButton>
          <Button variant="outline" aria-haspopup="dialog" onClick={() => setAdvisorOpen(true)}>
            <SparkIcon className="text-primary" />
            Ask Quarterly
          </Button>
          <div className="flex flex-wrap items-center gap-2 sm:ml-auto">
            <Button variant="outline" onClick={() => void save()}>
              Save
            </Button>
            <Button onClick={() => setGenerateOpen(true)}>Generate plan</Button>
          </div>
        </div>

        {saveMsg && (
          <Notice role="status" tone="info" className="animate-rise">
            {saveMsg}
          </Notice>
        )}
        {!stored && (
          <Notice tone="warning" role="alert">
            This browser is not storing data for this site, so your plan will be lost when you leave. Log in to save it.
          </Notice>
        )}
        {state.error && (
          <Notice tone="error" role="alert" className="animate-rise">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span>{state.error}</span>
              <Button variant="ghost" size="sm" onClick={() => dispatch({ type: "dismissError" })}>
                Dismiss
              </Button>
            </div>
          </Notice>
        )}
        {items.length === 0 && programIds.length === 0 && (
          <Notice tone="info">
            New here? <Link to="/onboarding" className="font-medium">Set up your plan</Link>, or open Requirements and drag courses onto the grid.
          </Notice>
        )}

        <DndContext sensors={sensors} collisionDetection={collision} onDragStart={onDragStart} onDragEnd={onDragEnd} onDragCancel={() => setDragging(null)} accessibility={{ announcements }}>
          <div className="mt-2 flex items-start gap-6">
            <section id="plan-grid" aria-label="Plan grid" className="min-w-0 flex-1">
              <PlanGrid
                name={state.name}
                verdict={<PlanVerdict verify={verify} onOpen={() => setDrawer({ open: true, tab: "issues" })} />}
                onRename={(name) => dispatch({ type: "rename", name })}
                showSummer={showSummer}
                onToggleSummer={() => setShowSummer(!showSummer)}
                onGraduation={(term) => dispatch({ type: "graduation", term })}
                onAddYear={() => dispatch({ type: "addYear" })}
              />
            </section>
            <PlanDrawer
              open={drawer.open}
              tab={drawer.tab}
              onTab={(tab) => setDrawer({ open: true, tab })}
              onClose={() => setDrawer((d) => ({ ...d, open: false }))}
              tabs={drawerTabs}
              fullScreen={!desktop}
            />
          </div>
          <DragOverlay dropAnimation={null}>
            {dragging ? (
              <div className="cursor-grabbing rounded-lg border border-hairline-strong bg-surface-card px-4 py-2.5 text-body-sm font-semibold tabular-nums text-ink shadow-overlay">{dragging}</div>
            ) : null}
          </DragOverlay>
        </DndContext>
      </div>

      <TermPickerDialog
        open={moveTarget !== null}
        title={moveTarget ? `Move ${itemLabel(moveTarget)} to…` : "Move to…"}
        plan={plan}
        current={moveTarget?.term}
        onClose={() => setMoveTarget(null)}
        onPick={(term) => {
          if (moveTarget) dispatch({ type: "edit", result: moveItemOps(moveTarget, term) });
          setMoveTarget(null);
        }}
      />
      <TermPickerDialog
        open={addTarget !== null}
        title={addTarget ? `Add ${addTarget} to…` : "Add to…"}
        plan={plan}
        onClose={() => setAddTarget(null)}
        onPick={(term) => {
          if (addTarget) dispatch({ type: "edit", result: addCourseOps(addTarget, term) });
          setAddTarget(null);
        }}
      />
      <Dialog open={pickPrograms} onClose={() => setPickPrograms(false)} title="Programs" description="Choose the programs this plan should satisfy.">
        <ProgramPickerBody
          catalogYear={plan.catalog_year}
          initial={programIds}
          onDone={(ids) => {
            const kept = (plan.programs ?? []).filter((p) => ids.includes(p.program_id));
            const added = ids.filter((id) => !programIds.includes(id)).map((program_id) => ({ program_id, options: {}, version_id: null }));
            dispatch({ type: "programs", programs: [...kept, ...added] });
            setPickPrograms(false);
          }}
        />
      </Dialog>
      <GenerateDialog
        open={generateOpen}
        onClose={() => setGenerateOpen(false)}
        plan={plan}
        planId={savedPlanId}
        onApply={(ops) => {
          // GE-2 (D11): confirm the change in the planner once the popup closes.
          const ok = tryOps(ops);
          if (ok) setSaveMsg("Applied the generated plan. The plan check beside your plan's name shows the result.");
          return ok;
        }}
      />
      <AdvisorSheet open={advisorOpen} onClose={() => setAdvisorOpen(false)} plan={plan} planId={savedPlanId} onApply={tryOps} currentReport={verify.report ?? null} />
    </PlannerContext.Provider>
  );
}
