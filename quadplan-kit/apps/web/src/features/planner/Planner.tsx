import {
  DndContext,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type Announcements,
  type DragEndEvent,
} from "@dnd-kit/core";
import { useEffect, useId, useMemo, useReducer, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/api/client";
import { useCourseMap, usePlanPrograms, usePrograms } from "@/api/hooks";
import type { ChangeOp, Issue, PlanItem } from "@/api/types";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Notice } from "@/components/ui/misc";
import { AdvisorPanel } from "@/features/advisor/AdvisorPanel";
import { GenerateDialog } from "@/features/generate/GenerateDialog";
import { ProgramPickerBody, StatusBadge } from "@/features/programs/ProgramPicker";
import { useSession } from "@/lib/session";
import { applyOps, ChangeOpError } from "./changes";
import { highlightFor, PlannerContext, type PlannerContextValue, type RequirementTag } from "./context";
import { GoalsTab } from "./GoalsTab";
import { IssuesTab } from "./IssuesTab";
import { upsertPlan, type LocalPlan } from "./localPlans";
import { addCourseOps, editorReducer, initEditor, itemLabel, moveItemOps, type EditResult } from "./planModel";
import { PlanGrid } from "./PlanGrid";
import { RequirementRail } from "./RequirementRail";
import { Tabs } from "./RightRail";
import { TermPickerDialog } from "./TermPickerDialog";
import { termLabel } from "./terms";
import { useVerify } from "./useVerify";
import { VerifierBadge } from "./VerifierBadge";

type DragData = { kind: "item"; itemId: string } | { kind: "course"; code: string };

/** Turn a drop into an edit: an existing card moves, a rail course is added. */
export function dropResult(data: DragData | undefined, toTerm: string | undefined, items: PlanItem[]): EditResult | null {
  if (!data || !toTerm) return null;
  if (data.kind === "course") return addCourseOps(data.code, toTerm);
  const item = items.find((i) => i.id === data.itemId);
  return item ? moveItemOps(item, toTerm) : null;
}

/** Requirement tag per course: the deepest progress node that counts it. */
function requirementTags(progress: { node_id: string; program_id: string; label?: string | null; courses?: string[] }[], programIds: string[], names: Map<string, string>): Map<string, RequirementTag> {
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
        color: Math.max(0, programIds.indexOf(p.program_id)),
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
  const [state, dispatch] = useReducer(editorReducer, initial, (p) => initEditor(p.state, p.name, p.years));
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
  const nameId = useId();
  const { data: session } = useSession();

  const plan = state.plan;
  const items = useMemo(() => plan.items ?? [], [plan.items]);
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
  const tags = requirementTags(report?.progress ?? [], programIds, names);
  const issues = report?.issues ?? [];
  const highlight = useMemo(() => highlightFor(selectedIssue, items), [selectedIssue, items]);

  // Autosave every edit to this device (localStorage, never throws).
  useEffect(() => {
    setStored(upsertPlan({ ...initial, remoteId, name: state.name, state: plan, years: state.years }));
  }, [initial, remoteId, plan, state.name, state.years]);

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

  function onDragEnd(e: DragEndEvent) {
    const result = dropResult(e.active.data.current as DragData | undefined, e.over ? String(e.over.id) : undefined, items);
    if (result) dispatch({ type: "edit", result });
  }

  async function save() {
    const ok = upsertPlan({ ...initial, remoteId, name: state.name, state: plan, years: state.years });
    if (!session) {
      setSaveMsg(ok ? "Saved on this device. Log in to save it to your account." : "Could not save: this browser is blocking storage.");
      return;
    }
    try {
      const res = remoteId
        ? await api.PATCH("/plans/{plan_id}", { params: { path: { plan_id: remoteId } }, body: { name: state.name, state: plan } })
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

  return (
    <PlannerContext.Provider value={ctx}>
      <div className="mx-auto max-w-[1600px] space-y-3 p-3">
        <div className="flex flex-wrap items-center gap-2 border-b border-border pb-3">
          <h1 className="sr-only">Planner</h1>
          <div className="flex min-w-0 flex-col">
            <label htmlFor={nameId} className="text-xs text-muted-foreground">
              Plan name
            </label>
            <input
              id={nameId}
              value={state.name}
              onChange={(e) => dispatch({ type: "rename", name: e.target.value })}
              className="min-h-11 w-48 rounded-md border border-border bg-background px-2 font-semibold"
            />
          </div>
          <span className="text-sm text-muted-foreground">Catalog {plan.catalog_year}</span>
          <ul className="flex flex-wrap items-center gap-1" aria-label="Programs on this plan">
            {(plan.programs ?? []).map((p) => {
              const summary = allPrograms.find((x) => x.id === p.program_id);
              return (
                <li key={p.program_id} className="flex items-center gap-1 rounded-full border border-border bg-muted pl-3 text-sm">
                  {names.get(p.program_id) ?? p.program_id}
                  {summary && <StatusBadge status={summary.status} />}
                  <button
                    type="button"
                    aria-label={`Remove program ${names.get(p.program_id) ?? p.program_id}`}
                    onClick={() => dispatch({ type: "programs", programs: (plan.programs ?? []).filter((x) => x.program_id !== p.program_id) })}
                    className="flex min-h-11 min-w-11 items-center justify-center rounded-full hover:bg-zinc-200"
                  >
                    <span aria-hidden="true">✕</span>
                  </button>
                </li>
              );
            })}
            <li>
              <Button variant="outline" onClick={() => setPickPrograms(true)}>
                + Program
              </Button>
            </li>
          </ul>
          <div className="ml-auto flex flex-wrap items-center gap-2">
            <VerifierBadge verify={verify} />
            <Button onClick={() => setGenerateOpen(true)}>Generate plan</Button>
            <Button variant="outline" onClick={() => void save()}>
              Save
            </Button>
          </div>
        </div>
        {saveMsg && (
          <Notice role="status" tone="blue">
            {saveMsg}
          </Notice>
        )}
        {!stored && (
          <Notice tone="amber" role="alert">
            This browser is not storing data for this site, so your plan will be lost when you leave. Log in to save it.
          </Notice>
        )}
        {state.error && (
          <Notice tone="red" role="alert" className="flex items-center justify-between gap-2">
            <span>{state.error}</span>
            <Button variant="ghost" onClick={() => dispatch({ type: "dismissError" })}>
              Dismiss
            </Button>
          </Notice>
        )}
        {items.length === 0 && programIds.length === 0 && (
          <Notice tone="blue">
            New here? <Link to="/onboarding" className="font-medium underline">Set up your plan</Link> with your entry term, programs and goals, or drag courses in from the requirement list.
          </Notice>
        )}
        <DndContext sensors={sensors} onDragEnd={onDragEnd} accessibility={{ announcements }}>
          <div className="grid gap-4 lg:grid-cols-[280px_minmax(0,1fr)] xl:grid-cols-[260px_minmax(0,1fr)_320px]">
            <section aria-label="Requirements" className="min-w-0">
              <RequirementRail details={programQueries.map((q, i) => ({ ...q, id: programIds[i] ?? "" }))} progress={report?.progress} onAddProgram={() => setPickPrograms(true)} />
            </section>
            <section aria-label="Plan grid" className="min-w-0">
              <PlanGrid years={state.years} showSummer={showSummer} onToggleSummer={() => setShowSummer(!showSummer)} onYears={(n) => dispatch({ type: "years", years: n })} />
            </section>
            <section aria-label="Issues, goals and advisor" className="min-w-0 lg:col-span-2 xl:col-span-1">
              <Tabs
                label="Plan details"
                tabs={[
                  {
                    key: "issues",
                    label: `Issues${issues.length ? ` (${issues.length})` : ""}`,
                    content: <IssuesTab verify={verify} selected={selectedIssue} onSelect={setSelectedIssue} />,
                  },
                  {
                    key: "goals",
                    label: "Goals",
                    content: (
                      <GoalsTab
                        goals={plan.goals ?? []}
                        entryTerm={plan.entry_term}
                        years={state.years}
                        issues={issues}
                        programs={allPrograms}
                        onChange={(goals) => dispatch({ type: "goals", goals })}
                      />
                    ),
                  },
                  { key: "advisor", label: "Advisor", content: <AdvisorPanel plan={plan} onApply={tryOps} /> },
                ]}
              />
            </section>
          </div>
        </DndContext>
      </div>

      <TermPickerDialog
        open={moveTarget !== null}
        title={moveTarget ? `Move ${itemLabel(moveTarget)} to…` : "Move to…"}
        entryTerm={plan.entry_term}
        years={state.years}
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
        entryTerm={plan.entry_term}
        years={state.years}
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
        years={state.years}
        planId={remoteId && savedSnapshot === JSON.stringify(plan) ? remoteId : null}
        onApply={tryOps}
      />
    </PlannerContext.Provider>
  );
}

