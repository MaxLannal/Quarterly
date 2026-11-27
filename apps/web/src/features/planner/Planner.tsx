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
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useReducer, useState } from "react";
import { Link } from "react-router-dom";
import { api, unwrap } from "@/api/client";
import { useCourseMap, usePlanPrograms, usePrograms } from "@/api/hooks";
import type { ChangeOp, Issue, PlanItem, ProgramSummary } from "@/api/types";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { CloseIcon, SparkIcon } from "@/components/ui/icons";
import { Notice } from "@/components/ui/misc";
import { AdvisorSheet } from "@/features/advisor/AdvisorPanel";
import { PROFILE_KEY, useProfile } from "@/features/dashboard/api";
import { GenerateDialog } from "@/features/generate/GenerateDialog";
import { ProgramPickerBody, StatusBadge } from "@/features/programs/ProgramPicker";
import { useMediaQuery } from "@/lib/motion";
import { useSession } from "@/lib/session";
import { cn } from "@/lib/utils";
import { applyOps, ChangeOpError } from "./changes";
import { highlightFor, PlannerContext, STRIP_CLASSES, stripKind, type PlannerContextValue, type RequirementTag } from "./context";
import { GoalsTab } from "./GoalsTab";
import { IssuesTab } from "./IssuesTab";
import { storedRemoteId, upsertPlan, type LocalPlan } from "./localPlans";
import { quarterMetrics } from "./metrics";
import { addCourseOps, editorReducer, initEditor, itemLabel, moveItemOps, planYears, type EditResult } from "./planModel";
import { CreditsEditor } from "@/features/credits/CreditsEditor";
import { DrawerButton, PlanDrawer, type DrawerTab } from "./PlanDrawer";
import { PlanGrid } from "./PlanGrid";
import { graduationChoices, PlanHero } from "./PlanHero";
import { RequirementTree } from "./RequirementTree";
import { planToSave, recordKey, withRecord } from "./setup";
import { SetupCard } from "./SetupCard";
import { TermPickerDialog } from "./TermPickerDialog";
import { graduationTerm, planTerms, termLabel } from "./terms";
import { useVerify } from "./useVerify";
import { PlanVerdict } from "./VerifierBadge";

type DragData = { kind: "item"; itemId: string } | { kind: "course"; code: string; title?: string };

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
  /** Replaces this (empty) plan with one set up from the student record, then reopens it. */
  onSetUp?: (plan: LocalPlan, generate: boolean) => void;
}

export function Planner({ initial, autoGenerate = false, onSetUp }: PlannerProps) {
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
  const [dragging, setDragging] = useState<{ id: string; data?: DragData } | null>(null);
  const desktop = useMediaQuery("(min-width: 1024px)");
  const { data: session } = useSession();
  const queryClient = useQueryClient();
  const profile = useProfile(!!session);
  // Credits and taken courses belong to the student record (Issue #14): `recordBase` is them as
  // last read from (or saved to) the record, so Save can tell a planner edit from a stale copy.
  const [recordBase, setRecordBase] = useState<string | null>(null);

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
    setDragging({ id: String(e.active.id), data: e.active.data.current as DragData | undefined });
  }

  /** The file held up under the pointer while dragging: the card's code, title and strip. */
  function heldFile(d: { id: string; data?: DragData }) {
    const data = d.data;
    const item = data?.kind === "item" ? items.find((i) => i.id === data.itemId) : undefined;
    const code = data?.kind === "course" ? data.code : item?.course;
    const title = data?.kind === "course" ? data.title : item?.course ? courses.get(item.course)?.title : item?.slot_ref;
    const kind = code ? (tags.get(code)?.kind ?? "none") : "none";
    return (
      <div className={cn("glass-file planner-held flex cursor-grabbing flex-col gap-0.5 border-l-[3px] py-2.5 pl-4 pr-6", STRIP_CLASSES[kind])}>
        <span className="font-mono text-[13px] font-semibold tracking-[0.06em] tabular-nums text-ink">{code ?? nameOf(d.id)}</span>
        {title && <span className="max-w-64 truncate text-caption text-body">{title}</span>}
      </div>
    );
  }

  function onDragEnd(e: DragEndEvent) {
    setDragging(null);
    const result = dropResult(e.active.data.current as DragData | undefined, e.over ? String(e.over.id) : undefined, items);
    if (result) dispatch({ type: "edit", result });
  }

  // Logged in: show the record's credits and taken courses (edited on the dashboard) once loaded.
  // An empty plan is left alone: it shows the card that sets the whole plan up from the record.
  const totals = quarterMetrics(items, courses);
  const lastTerm = graduationTerm(plan);
  const years = planYears(plan);
  const choices = graduationChoices(plan.entry_term, years);
  if (!choices.includes(lastTerm)) choices.push(lastTerm);
  const blank = (plan.items ?? []).length === 0 && (plan.programs ?? []).length === 0;
  useEffect(() => {
    if (!session || !profile.data || recordBase !== null || blank) return;
    const next = withRecord(plan, profile.data);
    if (recordKey(next) !== recordKey(plan)) dispatch({ type: "replace", plan: next });
    setRecordBase(recordKey(next));
  }, [session, profile.data, recordBase, plan, blank]);

  async function save() {
    // Saving writes the plan's credits and taken courses to the record. Unless the student
    // changed them here, send the record's current ones, so an old copy never undoes a change
    // made on the dashboard.
    let toSave = plan;
    if (session) {
      try {
        const fresh = unwrap(await api.GET("/me/profile"));
        toSave = planToSave(plan, fresh, recordBase);
        if (recordKey(toSave) !== recordKey(plan)) dispatch({ type: "replace", plan: toSave });
      } catch {
        // Keep the plan as it is; the server keeps the taken courses a plan cannot show.
      }
    }
    const ok = upsertPlan({ ...initial, remoteId, name: state.name, state: toSave, years: undefined });
    if (!session) {
      setSaveMsg(ok ? "Saved on this device. Log in to save it to your account." : "Could not save: this browser is blocking storage.");
      return;
    }
    // An import on login that ran while this plan was open stored the account plan's id.
    const accountPlanId = remoteId ?? storedRemoteId(initial.localId);
    try {
      const res = accountPlanId
        ? await api.PATCH("/plans/{plan_id}", { params: { path: { plan_id: accountPlanId } }, body: { name: state.name, state: toSave } })
        : await api.POST("/plans", { body: { name: state.name, is_primary: initial.isPrimary, state: toSave } });
      if (res.response.status === 501) {
        setSaveMsg("Saving to your account is not available yet. Your plan is saved on this device.");
      } else if (res.data) {
        setRemoteId(res.data.id);
        setSavedSnapshot(JSON.stringify(toSave));
        setRecordBase(recordKey(toSave));
        void queryClient.invalidateQueries({ queryKey: PROFILE_KEY });
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
          <div>
            <span className="planner-label">Before you start</span>
            <h3 className="font-display text-title-md font-normal leading-tight">Test, placement and transfer credits</h3>
          </div>
          <CreditsEditor credits={plan.credits ?? []} catalogYear={plan.catalog_year} onChange={(credits) => dispatch({ type: "credits", credits })} />
        </div>
      ),
    },
    {
      key: "issues" as const,
      label: "Check plan", // D11 PL-4: the same name as the toolbar button that opens it
      content: <IssuesTab verify={verify} selected={selectedIssue} onSelect={setSelectedIssue} />,
    },
  ];

  return (
    <PlannerContext.Provider value={ctx}>
      <div className="mx-auto flex w-full max-w-tool flex-col gap-5 px-4 pb-20 pt-5 sm:px-6 sm:pt-6 lg:px-10">
        <h1 className="sr-only">Planner</h1>
        <PlanHero
          name={state.name}
          onRename={(name) => dispatch({ type: "rename", name })}
          verdict={<PlanVerdict verify={verify} onOpen={() => setDrawer({ open: true, tab: "issues" })} />}
          catalogYear={plan.catalog_year}
          years={years}
          units={`${totals.units}${totals.unitsPartial ? "+" : ""}`}
          courses={totals.courses}
          graduation={lastTerm}
          graduationChoices={choices}
          onGraduation={(term) => dispatch({ type: "graduation", term })}
          programs={
            <ul className="flex flex-wrap items-center gap-2 xl:justify-end" aria-label="Programs on this plan">
              {(plan.programs ?? []).map((p) => {
                const summary = allPrograms.find((x) => x.id === p.program_id);
                return (
                  <li key={p.program_id} className="planner-chip flex min-h-11 animate-fade-in items-center gap-1 rounded-pill pl-4 text-body-sm text-ink">
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
                <Button variant="outline" size="sm" onClick={() => setPickPrograms(true)}>
                  + Program
                </Button>
              </li>
            </ul>
          }
        />

        {/* Toolbar: one floating glass bar, like a tool palette. The panels open on demand, so the
            grid keeps the page (FEEDBACK F4). */}
        <div className="planner-toolbar glass-rim">
          {/* D11 adapt: on a phone the panel buttons are one row that scrolls sideways; from 640px
              they wrap. */}
          <div className="flex min-w-0 items-center gap-1 overflow-x-auto [scrollbar-width:none] sm:flex-wrap sm:overflow-visible [&>*]:shrink-0">
            <DrawerButton active={drawer.tab === "requirements"} open={drawer.open} onClick={() => toggleDrawer("requirements")}>
              Requirements
            </DrawerButton>
            <DrawerButton active={drawer.tab === "goals"} open={drawer.open} onClick={() => toggleDrawer("goals")}>
              Goals
            </DrawerButton>
            <DrawerButton active={drawer.tab === "credits"} open={drawer.open} onClick={() => toggleDrawer("credits")}>
              Credits
              {(plan.credits ?? []).length > 0 && <span className="font-mono text-[12px] text-muted tabular-nums">{(plan.credits ?? []).length}</span>}
            </DrawerButton>
            <DrawerButton active={drawer.tab === "issues"} open={drawer.open} onClick={() => toggleDrawer("issues")}>
              Check plan{" "}
              {errorCount > 0 && <span className="sr-only">({errorCount} {errorCount === 1 ? "error" : "errors"})</span>}
              {errorCount > 0 && (
                <span aria-hidden="true" data-testid="issue-count" className="planner-count inline-flex min-w-5 animate-fade-in justify-center rounded-pill px-1.5 font-mono text-[12px] tabular-nums">
                  {errorCount}
                </span>
              )}
            </DrawerButton>
            <span aria-hidden="true" className="planner-toolbar-sep" />
            <button type="button" className="planner-seg planner-seg-ai" aria-haspopup="dialog" onClick={() => setAdvisorOpen(true)}>
              <SparkIcon className="text-primary" />
              Ask Quarterly
            </button>
          </div>
          <div className="flex flex-wrap items-center gap-1 sm:ml-auto">
            <button type="button" className="planner-seg" onClick={() => void save()}>
              Save
            </button>
            <Button size="sm" className="border-0 px-5" onClick={() => setGenerateOpen(true)}>
              Generate plan
            </Button>
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
        {items.length === 0 && programIds.length === 0 &&
          (session && onSetUp ? (
            <SetupCard catalogYear={plan.catalog_year} onSetUp={(next, generate) => onSetUp({ ...initial, remoteId, name: state.name, state: next, years: undefined }, generate)} />
          ) : (
            <Notice tone="info">
              New here? <Link to="/signup" className="font-medium">Sign up to set up your plan</Link> from your class year, programs and credits, or open Requirements and drag courses onto the grid.
            </Notice>
          ))}

        <DndContext sensors={sensors} collisionDetection={collision} onDragStart={onDragStart} onDragEnd={onDragEnd} onDragCancel={() => setDragging(null)} accessibility={{ announcements }}>
          <div className="mt-3 flex items-start gap-8">
            <section id="plan-grid" aria-label="Plan grid" className="min-w-0 flex-1">
              <PlanGrid
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
          <DragOverlay dropAnimation={null}>{dragging ? heldFile(dragging) : null}</DragOverlay>
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
