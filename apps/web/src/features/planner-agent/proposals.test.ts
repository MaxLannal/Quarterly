import type { ChangeOp, PlanState, PlannerProposalEvent } from "@/api/types";
import { applyOps } from "@/features/planner/changes";
import { emptyPlan } from "@/features/planner/planModel";
import { fromEvent, proposedBlocks, stillFits, withLocks } from "./proposals";

const add = (course: string, term: string): ChangeOp => ({ op: "add", course, slot_ref: null, term, status: "planned", grading: "letter", locked: false, units: null });
const plan = (items: { course: string; term: string }[] = []): PlanState => ({ ...emptyPlan("2099-00"), items: items.map((i) => ({ ...i, status: "planned", grading: "letter", locked: false })) });

function event(groupId: string, ops: ChangeOp[], extra: Partial<PlannerProposalEvent> = {}): PlannerProposalEvent {
  return { type: "proposal", change_set_id: null, group_id: groupId, title: `Group ${groupId}`, kind: "major", ops, why: "Because.", citations: [], rules: [], preview: null, ...extra };
}

describe("proposals", () => {
  it("fromEvent keeps the group and builds a stable id", () => {
    const p = fromEvent(event("g1", [add("TEST 10000", "2099-AU")]), "run-1");
    expect(p).toMatchObject({ id: "run-1:g1", changeSetId: null, groupId: "g1", title: "Group g1", status: "proposed", runId: "run-1" });
    expect(fromEvent(event("g1", [], { change_set_id: "cs-9" }), "run-1").id).toBe("cs-9");
  });

  it("proposedBlocks marks adds, moves and removes per term", () => {
    const base = plan([{ course: "TEST 10100", term: "2099-AU" }, { course: "TEST 20000", term: "2100-WI" }]);
    const ps = [
      fromEvent(event("g1", [add("TEST 10000", "2099-AU")]), "r"),
      fromEvent(event("g2", [{ op: "move", item_id: null, course: "TEST 10100", slot_ref: null, from_term: "2099-AU", to_term: "2100-SP" }]), "r"),
      fromEvent(event("g3", [{ op: "remove", item_id: null, course: "TEST 20000", slot_ref: null, term: "2100-WI" }]), "r"),
    ];
    const blocks = proposedBlocks(base, ps);
    expect(blocks.get("2099-AU")).toEqual([{ proposalId: "r:g1", course: "TEST 10000", action: "add" }]);
    expect(blocks.get("2100-SP")).toEqual([{ proposalId: "r:g2", course: "TEST 10100", action: "move-in" }]);
    expect(blocks.get("2100-WI")).toEqual([{ proposalId: "r:g3", course: "TEST 20000", action: "remove" }]);
  });

  it("proposedBlocks leaves stale proposals out", () => {
    const p = { ...fromEvent(event("g1", [add("TEST 10000", "2099-AU")]), "r"), status: "stale" as const };
    expect(proposedBlocks(plan(), [p]).size).toBe(0);
  });

  it("stillFits is false when the course is already in the plan", () => {
    const p = fromEvent(event("g1", [{ op: "move", item_id: null, course: "TEST 10100", slot_ref: null, from_term: "2099-AU", to_term: "2100-SP" }]), "r");
    expect(stillFits(plan([{ course: "TEST 10100", term: "2099-AU" }]), p)).toBe(true);
    expect(stillFits(plan(), p)).toBe(false);
    const again = fromEvent(event("g2", [add("TEST 10000", "2099-AU")]), "r");
    expect(stillFits(plan([{ course: "TEST 10000", term: "2100-WI" }]), again)).toBe(false);
  });

  it("applies a later group after a rejected one", () => {
    const first = fromEvent(event("g1", [add("TEST 10000", "2099-AU")]), "r");
    const second = fromEvent(event("g2", [add("TEST 10100", "2100-WI")]), "r");
    void first; // rejected: never applied
    const after = applyOps(plan(), withLocks(plan(), second.ops));
    expect(after.items?.map((i) => i.course)).toEqual(["TEST 10100"]);
  });

  it("withLocks locks the placed items", () => {
    const ops = withLocks(plan([{ course: "TEST 10100", term: "2099-AU" }]), [
      add("TEST 10000", "2099-AU"),
      { op: "move", item_id: null, course: "TEST 10100", slot_ref: null, from_term: "2099-AU", to_term: "2100-WI" },
    ]);
    const after = applyOps(plan([{ course: "TEST 10100", term: "2099-AU" }]), ops);
    expect(after.items?.every((i) => i.locked)).toBe(true);
  });
});
