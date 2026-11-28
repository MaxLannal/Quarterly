import type { ChangeOp, PlanState } from "@/api/types";
import { applyOps } from "@/features/planner/changes";
import { emptyPlan } from "@/features/planner/planModel";
import { historyKey, inverseOps } from "./history";

const base: PlanState = {
  ...emptyPlan("2099-00"),
  items: [
    { course: "TEST 10000", term: "2099-AU", status: "planned", grading: "letter", locked: false },
    { course: "TEST 10100", term: "2100-WI", status: "planned", grading: "letter", locked: false },
  ],
};
const summary = (p: PlanState) => (p.items ?? []).map((i) => `${i.course}@${i.term}${i.locked ? "*" : ""}`).sort();

describe("history", () => {
  it("inverseOps undoes add, move and remove", () => {
    const ops: ChangeOp[] = [
      { op: "add", course: "TEST 20000", slot_ref: null, term: "2100-SP", status: "planned", grading: "letter", locked: false, units: null },
      { op: "move", item_id: null, course: "TEST 10000", slot_ref: null, from_term: "2099-AU", to_term: "2100-SP" },
      { op: "remove", item_id: null, course: "TEST 10100", slot_ref: null, term: "2100-WI" },
    ];
    const after = applyOps(base, ops);
    expect(summary(applyOps(after, inverseOps(base, after)))).toEqual(summary(base));
  });

  it("inverseOps unlocks an accepted course before it removes it", () => {
    const after = applyOps(base, [
      { op: "add", course: "TEST 20000", slot_ref: null, term: "2100-SP", status: "planned", grading: "letter", locked: true, units: null },
      { op: "lock", item_id: null, course: "TEST 10000", slot_ref: null, term: "2099-AU" },
    ]);
    expect(summary(applyOps(after, inverseOps(base, after)))).toEqual(summary(base));
  });

  it("historyKey is per plan", () => {
    expect(historyKey("abc")).toBe("quarterly.history.v1:abc");
  });
});
