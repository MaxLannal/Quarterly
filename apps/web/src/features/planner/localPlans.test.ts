import { http, HttpResponse } from "msw";
import { importedPlans } from "@/mocks/handlers";
import { server } from "@/mocks/node";
import { importLocalPlans } from "./importOnLogin";
import { activePlan, deletePlan, loadPlans, plansToImport, STORAGE_KEY, storedRemoteId, upsertPlan, type LocalPlan } from "./localPlans";
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

  it("stores the account plan id, and an autosave from the plan opened before keeps it", async () => {
    await fetch(`${window.location.origin}/api/auth/login`, { method: "POST", body: "{}" });
    const opened = local("a");
    upsertPlan(opened);
    expect(await importLocalPlans(ACCOUNT)).toBe("imported");
    const remoteId = storedRemoteId("a");
    expect(remoteId).toMatch(/^[0-9a-f-]{36}$/);
    // The planner autosaves from the plan it opened with (no remoteId, no importedFor): Save must
    // still find the imported plan, and the next login must not import it again.
    upsertPlan({ ...opened, name: "Edited" });
    expect(storedRemoteId("a")).toBe(remoteId);
    expect(plansToImport(ACCOUNT)).toEqual([]);
    expect(loadPlans().plans[0]?.name).toBe("Edited");
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

describe("planner state in a local plan", () => {
  it("local plan keeps chat, proposals and history across save and load", () => {
    const extra: Partial<LocalPlan> = {
      chat: [{ kind: "user", text: "Hello" }],
      proposals: [{ id: "r:g1", changeSetId: null, groupId: "g1", title: "Intro", kind: "major", ops: [], why: "x", citations: [], rules: [], status: "proposed", runId: "r" }],
      history: [{ id: "h1", day: "2099-01-01", label: "Accepted Intro", ops: [], inverse: [] }],
      workingNotes: "- 2099-01-01 · avoid · x [TEST 10000]",
      profileAnswers: { interests: ["testing"] },
    };
    upsertPlan(local("a", extra));
    const stored = loadPlans().plans[0]!;
    expect(stored.chat).toEqual(extra.chat);
    expect(stored.proposals?.[0]?.title).toBe("Intro");
    expect(stored.history?.[0]?.label).toBe("Accepted Intro");
    expect(stored.workingNotes).toBe(extra.workingNotes);
    expect(stored.profileAnswers).toEqual({ interests: ["testing"] });
  });

  it("import on login copies working notes into an empty record and sends answers as proposals", async () => {
    await fetch(`${window.location.origin}/api/auth/login`, { method: "POST", body: "{}" });
    const sent: { patch: unknown[]; proposals: unknown[] } = { patch: [], proposals: [] };
    server.use(
      http.patch("*/api/me/profile", async ({ request }) => {
        sent.patch.push(await request.json());
        return HttpResponse.json({});
      }),
      http.post("*/api/me/profile/proposals", async ({ request }) => {
        sent.proposals.push(await request.json());
        return HttpResponse.json({}, { status: 201 });
      }),
    );
    upsertPlan(local("a", { workingNotes: "- 2099-01-01 · prefer · mornings", profileAnswers: { interests: ["testing"], pace: "early" } }));
    expect(await importLocalPlans("acct-1")).toBe("imported");
    expect(sent.patch).toEqual([{ working_notes: "- 2099-01-01 · prefer · mornings" }]);
    expect(sent.proposals).toEqual([
      { field: "interests", value: ["testing"] },
      { field: "pace", value: "early" },
    ]);
  });
});
