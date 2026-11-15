import { http, HttpResponse } from "msw";
import { importedPlans } from "@/mocks/handlers";
import { server } from "@/mocks/node";
import { importLocalPlans } from "./importOnLogin";
import { activePlan, deletePlan, loadPlans, plansToImport, STORAGE_KEY, upsertPlan, type LocalPlan } from "./localPlans";
import { emptyPlan } from "./planModel";

const local = (id: string, extra: Partial<LocalPlan> = {}): LocalPlan => ({
  localId: id,
  name: `Plan ${id}`,
  isPrimary: false,
  state: emptyPlan("2099-00"),
  updatedDay: "2099-01-01",
  ...extra,
});

describe("localPlans", () => {
  it("stores, activates and deletes plans", () => {
    expect(upsertPlan(local("a", { isPrimary: true }))).toBe(true);
    upsertPlan(local("b", { isPrimary: true }));
    const doc = loadPlans();
    expect(doc.activeId).toBe("b");
    expect(doc.plans.filter((p) => p.isPrimary).map((p) => p.localId)).toEqual(["b"]);
    deletePlan("b");
    expect(activePlan()?.localId).toBe("a");
  });

  it("survives a localStorage that throws", () => {
    const get = vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("SecurityError");
    });
    const set = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("QuotaExceededError");
    });
    expect(loadPlans().plans).toEqual([]);
    expect(upsertPlan(local("a"))).toBe(false);
    expect(activePlan()).toBeNull();
    get.mockRestore();
    set.mockRestore();
  });

  it("loads plans saved with the old years count (FEEDBACK F3)", () => {
    const old = { ...local("five"), years: 5 };
    const four = { ...local("four"), years: 4 };
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify({ version: 1, activeId: "five", plans: [old, four] }));
    const [a, b] = loadPlans().plans;
    expect(a?.state.graduation_term).toBe("2104-SP");
    expect(a && "years" in a).toBe(false);
    // Four was the old minimum: the default (years left from entry) applies.
    expect(b?.state.graduation_term ?? null).toBeNull();
    // A graduation quarter already on the plan wins.
    const set = { ...local("set", { state: { ...emptyPlan("2099-00"), graduation_term: "2102-WI" } }), years: 5 };
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify({ version: 1, activeId: "set", plans: [set] }));
    expect(loadPlans().plans[0]?.state.graduation_term).toBe("2102-WI");
  });

  it("ignores corrupt stored data", () => {
    window.localStorage.setItem(STORAGE_KEY, "{not json");
    expect(loadPlans().plans).toEqual([]);
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify({ version: 99 }));
    expect(loadPlans().plans).toEqual([]);
  });
});

describe("import on login", () => {
  const ACCOUNT = "acct-1";

  it("posts local plans to /plans/import once and keeps the local copy", async () => {
    await fetch(`${window.location.origin}/api/auth/login`, { method: "POST", body: "{}" });
    upsertPlan(local("a"));
    expect(await importLocalPlans(ACCOUNT)).toBe("imported");
    expect(importedPlans.map((p) => p.name)).toEqual(["Plan a"]);
    expect(loadPlans().plans).toHaveLength(1);
    expect(plansToImport(ACCOUNT)).toEqual([]);
    expect(await importLocalPlans(ACCOUNT)).toBe("idle");
  });

  it("keeps the local copy when the endpoint is not built yet (501)", async () => {
    server.use(http.post("*/api/plans/import", () => HttpResponse.json({ detail: "Not implemented yet" }, { status: 501 })));
    upsertPlan(local("a"));
    expect(await importLocalPlans(ACCOUNT)).toBe("unavailable");
    expect(plansToImport(ACCOUNT)).toHaveLength(1);
  });

  it("keeps the local copy on a network error", async () => {
    server.use(http.post("*/api/plans/import", () => HttpResponse.error()));
    upsertPlan(local("a"));
    expect(await importLocalPlans(ACCOUNT)).toBe("failed");
    expect(plansToImport(ACCOUNT)).toHaveLength(1);
  });
});
