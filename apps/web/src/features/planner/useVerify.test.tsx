import { act, renderHook } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import type { PlanState, Report } from "@/api/types";
import { server } from "@/mocks/node";
import { emptyPlan } from "./planModel";
import { useVerify, verifyPlan, VERIFY_DEBOUNCE_MS, type VerifyFn } from "./useVerify";

const REPORT: Report = { status: "valid", issues: [], progress: [], plan_hash: "h", core_version: "t" };

function planWith(n: number): PlanState {
  return {
    ...emptyPlan("2099-00"),
    items: Array.from({ length: n }, (_, i) => ({ course: `TEST 1000${i}`, term: "2099-AU", status: "planned", grading: "letter", locked: false })),
  };
}

describe("useVerify (debounce)", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("waits 300 ms after the last edit and verifies only the latest plan", async () => {
    const verify = vi.fn<VerifyFn>(async () => REPORT);
    const { result, rerender } = renderHook(({ plan }) => useVerify(plan, { verify }), { initialProps: { plan: planWith(0) } });
    expect(result.current.status).toBe("verifying");

    for (const n of [1, 2, 3]) {
      act(() => vi.advanceTimersByTime(VERIFY_DEBOUNCE_MS - 50));
      rerender({ plan: planWith(n) });
    }
    expect(verify).not.toHaveBeenCalled();

    await act(async () => {
      vi.advanceTimersByTime(VERIFY_DEBOUNCE_MS);
    });
    expect(verify).toHaveBeenCalledTimes(1);
    expect(verify.mock.calls[0]?.[0].items).toHaveLength(3);
    expect(result.current).toEqual({ status: "done", report: REPORT, error: null });
  });

  it("ignores a stale response once a newer verification starts", async () => {
    const resolvers: ((r: Report) => void)[] = [];
    const verify = vi.fn<VerifyFn>(() => new Promise<Report>((resolve) => resolvers.push(resolve)));
    const { result, rerender } = renderHook(({ plan }) => useVerify(plan, { verify }), { initialProps: { plan: planWith(1) } });
    await act(async () => {
      vi.advanceTimersByTime(VERIFY_DEBOUNCE_MS);
    });
    rerender({ plan: planWith(2) });
    await act(async () => {
      vi.advanceTimersByTime(VERIFY_DEBOUNCE_MS);
    });
    expect(verify).toHaveBeenCalledTimes(2);
    expect(verify.mock.calls[0]?.[1].aborted).toBe(true);
    await act(async () => resolvers[0]?.({ ...REPORT, status: "errors" }));
    expect(result.current.report).toBeNull();
    await act(async () => resolvers[1]?.(REPORT));
    expect(result.current.report?.status).toBe("valid");
  });
});

describe("verifyPlan", () => {
  it("posts the plan and returns the server report", async () => {
    const report = await verifyPlan(planWith(1), new AbortController().signal);
    expect(report.status).toBeDefined();
  });

  it("reports 501 as not available", async () => {
    server.use(http.post("*/api/verify", () => HttpResponse.json({ detail: "Not implemented yet (prompt 02)" }, { status: 501 })));
    const plan = planWith(0);
    const { result } = renderHook(() => useVerify(plan, { delay: 0 }));
    await vi.waitFor(() => expect(result.current.status).toBe("unavailable"));
  });
});
