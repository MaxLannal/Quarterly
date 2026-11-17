import type { PlanItem } from "@/api/types";
import { highlightFor } from "./context";
import { addCourseOps, editorReducer, emptyPlan, initEditor, moveItemOps, planYears, removeItemOps, setCompletedOps, toggleLockOps, type EditorState } from "./planModel";
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

});

describe("years and the graduation quarter (FEEDBACK F3)", () => {
  it("a first-year gets four years and a second-year transfer three", () => {
    expect(planYears(emptyPlan("2099-00"))).toBe(4);
    expect(planYears({ ...emptyPlan("2099-00"), entry_year_level: 2 })).toBe(3);
    expect(planYears({ ...emptyPlan("2099-00"), entry_year_level: 3 })).toBe(2);
  });

  it("adds and removes the last year", () => {
    let s = editor([]);
    s = editorReducer(s, { type: "addYear" });
    expect(s.plan.graduation_term).toBe("2104-SP");
    expect(planYears(s.plan)).toBe(5);
    s = editorReducer(s, { type: "removeYear" });
    s = editorReducer(s, { type: "removeYear" });
    expect(s.plan.graduation_term).toBe("2102-SP");
    expect(planYears(s.plan)).toBe(3);
  });

  it("stops at seven years, the longest plan the API accepts", () => {
    let s = editor([]);
    for (let i = 0; i < 3; i += 1) s = editorReducer(s, { type: "addYear" });
    expect(s.plan.graduation_term).toBe("2106-SP");
    expect(planYears(s.plan)).toBe(7);
    const next = editorReducer(s, { type: "addYear" });
    expect(next.plan).toBe(s.plan);
    expect(next.error).toBe("A plan can be at most 7 years long.");
    expect(editorReducer(s, { type: "graduation", term: "2107-AU" }).error).toBe("A plan can be at most 7 years long.");
    expect(editorReducer(s, { type: "graduation", term: "2106-WI" }).error).toBeNull();
  });

  it("refuses to remove a year that has courses", () => {
    const s = editor([item("a", "TEST 10000", "2103-WI")]);
    const next = editorReducer(s, { type: "removeYear" });
    expect(next.plan).toBe(s.plan);
    expect(next.error).toBe("Your fourth year has courses. Move or remove them first.");
  });

  it("refuses to remove the only year", () => {
    const s = initEditor({ ...emptyPlan("2099-00"), entry_year_level: 4 }, "x");
    expect(editorReducer(s, { type: "removeYear" }).error).toBe("A plan needs at least one year.");
  });

  it("graduating early in Winter keeps the year but ends at Winter", () => {
    const s = editorReducer(editor([]), { type: "graduation", term: "2103-WI" });
    expect(s.plan.graduation_term).toBe("2103-WI");
    expect(planYears(s.plan)).toBe(4);
    expect(editorReducer(s, { type: "graduation", term: "2103-SU" }).error).toMatch(/Summer/);
    expect(editorReducer(s, { type: "graduation", term: "2098-SP" }).error).toMatch(/before/);
  });

  it("a course after the graduation quarter stays on the plan", () => {
    const s = editorReducer(editor([item("a", "TEST 10000", "2103-SP")]), { type: "graduation", term: "2103-WI" });
    expect(s.plan.items).toHaveLength(1);
    expect(addCourseOps("TEST 10100", "2104-AU").ok).toBe(true);
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
