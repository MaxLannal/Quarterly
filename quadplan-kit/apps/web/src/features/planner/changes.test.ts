import type { ChangeOp, PlanItem, PlanState } from "@/api/types";
import { applyOps, ChangeOpError, opsForTerms, termsTouched } from "./changes";

const item = (course: string, term: string, extra: Partial<PlanItem> = {}): PlanItem => ({
  course,
  term,
  status: "planned",
  grading: "letter",
  locked: false,
  ...extra,
});

const plan = (items: PlanItem[]): PlanState => ({ catalog_year: "2099-00", entry_term: "2099-AU", entry_year_level: 1, items });

const add = (course: string, term: string): ChangeOp => ({ op: "add", course, term, status: "planned", grading: "letter", locked: false });

// Same semantics as packages/planner_core/planner_core/changes.py.
describe("applyOps", () => {
  it("adds, moves and removes in order without mutating the input", () => {
    const p = plan([item("TEST 10000", "2099-AU")]);
    const out = applyOps(p, [
      add("TEST 10100", "2100-WI"),
      { op: "move", course: "TEST 10000", to_term: "2100-SP" },
      { op: "remove", course: "TEST 10100" },
    ]);
    expect(out.items).toEqual([item("TEST 10000", "2100-SP")]);
    expect(p.items?.[0]?.term).toBe("2099-AU");
  });

  it("targets by item id and gives new items ids when asked", () => {
    let n = 0;
    const out = applyOps(plan([item("TEST 10000", "2099-AU", { id: "a" })]), [add("TEST 10100", "2099-AU"), { op: "move", item_id: "a", to_term: "2100-WI" }], {
      newId: () => `new-${++n}`,
    });
    expect(out.items?.map((i) => [i.id, i.term])).toEqual([
      ["a", "2100-WI"],
      ["new-1", "2099-AU"],
    ]);
  });

  it("refuses to move or remove a locked item until it is unlocked", () => {
    const p = plan([item("TEST 10000", "2099-AU", { locked: true })]);
    expect(() => applyOps(p, [{ op: "move", course: "TEST 10000", to_term: "2100-WI" }])).toThrow(ChangeOpError);
    expect(() => applyOps(p, [{ op: "remove", course: "TEST 10000" }])).toThrow(/locked/);
    const out = applyOps(p, [
      { op: "unlock", course: "TEST 10000" },
      { op: "move", course: "TEST 10000", to_term: "2100-WI" },
      { op: "lock", course: "TEST 10000" },
    ]);
    expect(out.items?.[0]).toMatchObject({ term: "2100-WI", locked: true });
  });

  it("rejects missing and ambiguous targets; the term disambiguates", () => {
    const p = plan([item("TEST 10000", "2099-AU"), item("TEST 10000", "2100-AU")]);
    expect(() => applyOps(p, [{ op: "remove", course: "TEST 99999" }])).toThrow(/no plan item matches TEST 99999/);
    expect(() => applyOps(p, [{ op: "remove", course: "TEST 10000" }])).toThrow(/matches 2 items/);
    const out = applyOps(p, [{ op: "move", course: "TEST 10000", from_term: "2100-AU", to_term: "2101-WI" }]);
    expect(out.items?.map((i) => i.term)).toEqual(["2099-AU", "2101-WI"]);
  });

  it("filters ops to selected quarters", () => {
    const ops: ChangeOp[] = [add("A", "2099-AU"), add("B", "2100-WI"), { op: "move", course: "C", from_term: "2100-SP", to_term: "2100-AU" }];
    expect(opsForTerms(ops, ["2100-WI"])).toEqual([ops[1]]);
    expect(opsForTerms(ops, ["2100-SP"])).toEqual([ops[2]]);
    expect(termsTouched(ops).sort()).toEqual(["2099-AU", "2100-AU", "2100-SP", "2100-WI"]);
  });
});
