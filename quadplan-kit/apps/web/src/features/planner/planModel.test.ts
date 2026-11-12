import type { PlanItem } from "@/api/types";
import { highlightFor } from "./context";
import { addCourseOps, editorReducer, emptyPlan, initEditor, moveItemOps, removeItemOps, setCompletedOps, toggleLockOps, type EditorState } from "./planModel";
import { dropResult } from "./Planner";

function editor(items: PlanItem[]): EditorState {
  return initEditor({ ...emptyPlan("2099-00"), items }, "Test plan");
}
const item = (id: string, course: string, term: string, extra: Partial<PlanItem> = {}): PlanItem => ({
  id,
  course,
  term,
  status: "planned",
  grading: "letter",
  locked: false,
  ...extra,
});

describe("drag and drop", () => {
  it("dropping a card on another quarter moves it", () => {
    const s = editor([item("a", "TEST 10000", "2099-AU")]);
    const r = dropResult({ kind: "item", itemId: "a" }, "2100-WI", s.plan.items ?? []);
    const next = editorReducer(s, { type: "edit", result: r! });
    expect(next.plan.items?.[0]?.term).toBe("2100-WI");
    expect(next.revision).toBe(1);
  });

  it("dropping on the same quarter changes nothing", () => {
    const s = editor([item("a", "TEST 10000", "2099-AU")]);
    const next = editorReducer(s, { type: "edit", result: dropResult({ kind: "item", itemId: "a" }, "2099-AU", s.plan.items ?? [])! });
    expect(next).toBe(s);
  });

  it("dropping a rail course adds it with an id", () => {
    const s = editor([]);
    const next = editorReducer(s, { type: "edit", result: dropResult({ kind: "course", code: "TEST 10100" }, "2099-AU", [])! });
    expect(next.plan.items).toHaveLength(1);
    expect(next.plan.items?.[0]).toMatchObject({ course: "TEST 10100", term: "2099-AU", status: "planned" });
    expect(next.plan.items?.[0]?.id).toBeTruthy();
  });

  it("dropping outside a quarter does nothing", () => {
    expect(dropResult({ kind: "course", code: "X" }, undefined, [])).toBeNull();
    expect(dropResult({ kind: "item", itemId: "missing" }, "2099-AU", [])).toBeNull();
  });

  it("a drop into Year 5 shows Year 5", () => {
    const s = editor([]);
    expect(s.years).toBe(4);
    const next = editorReducer(s, { type: "edit", result: addCourseOps("TEST 10000", "2103-AU") });
    expect(next.years).toBe(5);
    expect(editorReducer(next, { type: "years", years: 4 }).years).toBe(5);
  });
});

describe("lock", () => {
  it("a locked card cannot be dragged, moved or removed", () => {
    const s = editor([item("a", "TEST 10000", "2099-AU", { locked: true })]);
    const moved = editorReducer(s, { type: "edit", result: moveItemOps(s.plan.items![0]!, "2100-WI") });
    expect(moved.plan.items?.[0]?.term).toBe("2099-AU");
    expect(moved.error).toMatch(/locked/);
    const removed = editorReducer(s, { type: "edit", result: removeItemOps(s.plan.items![0]!) });
    expect(removed.plan.items).toHaveLength(1);
  });

  it("lock toggles and then blocks the move", () => {
    let s = editor([item("a", "TEST 10000", "2099-AU")]);
    s = editorReducer(s, { type: "edit", result: toggleLockOps(s.plan.items![0]!) });
    expect(s.plan.items?.[0]?.locked).toBe(true);
    s = editorReducer(s, { type: "edit", result: toggleLockOps(s.plan.items![0]!) });
    expect(s.plan.items?.[0]?.locked).toBe(false);
  });

  it("mark completed keeps the lock and the term", () => {
    const s = editor([item("a", "TEST 10000", "2099-AU", { locked: true })]);
    const next = editorReducer(s, { type: "edit", result: setCompletedOps(s.plan.items![0]!, true) });
    expect(next.error).toBeNull();
    expect(next.plan.items).toHaveLength(1);
    expect(next.plan.items?.[0]).toMatchObject({ course: "TEST 10000", term: "2099-AU", status: "completed", locked: true });
  });

  it("an op error is reported and the plan is unchanged", () => {
    const s = editor([]);
    const next = editorReducer(s, { type: "ops", ops: [{ op: "remove", course: "TEST 10000" }] });
    expect(next.plan).toBe(s.plan);
    expect(next.error).toMatch(/no plan item matches/);
    expect(editorReducer(next, { type: "dismissError" }).error).toBeNull();
  });
});

describe("issue highlighting", () => {
  const items = [item("a", "TEST 10000", "2099-AU"), item("b", "TEST 10000", "2100-AU"), item("c", "TEST 10100", "2100-WI")];
  it("highlights cards by course and term", () => {
    const h = highlightFor({ code: "V01", level: "error", message: "", course_ids: ["TEST 10000"], term_ids: ["2100-AU"] }, items);
    expect([...h.items]).toEqual(["b"]);
  });
  it("highlights quarters when the issue names only terms", () => {
    const h = highlightFor({ code: "V05", level: "warning", message: "", course_ids: [], term_ids: ["2100-WI"] }, items);
    expect([...h.items]).toEqual([]);
    expect([...h.terms]).toEqual(["2100-WI"]);
  });
});
