import { useEffect, useRef, useState } from "react";
import { api, ApiError, NotAvailableError, unwrap } from "@/api/client";
import type { PlanState, Report } from "@/api/types";

export const VERIFY_DEBOUNCE_MS = 300;

export type VerifyFn = (plan: PlanState, signal: AbortSignal) => Promise<Report>;

/** POST /verify. The server alone decides whether a plan is valid. */
export const verifyPlan: VerifyFn = async (plan, signal) =>
  unwrap(
    await api.POST("/verify", {
      body: {
        plan,
        options: { strictness: "normal", include_certificate: false, solver_time_limit_s: 2, checks: null },
      },
      signal,
    }),
  );

export type VerifyStatus = "idle" | "verifying" | "done" | "unavailable" | "error";

export interface VerifyState {
  status: VerifyStatus;
  /** The latest report received; kept while a newer verification is running. */
  report: Report | null;
  error: string | null;
}

/**
 * Debounced full verification: every plan change restarts a 300 ms timer; when it fires the
 * plan is POSTed to /verify and any older in-flight request is aborted, so only the latest
 * plan's report is shown.
 */
export function useVerify(
  plan: PlanState,
  { delay = VERIFY_DEBOUNCE_MS, verify = verifyPlan }: { delay?: number; verify?: VerifyFn } = {},
): VerifyState {
  const [state, setState] = useState<VerifyState>({ status: "idle", report: null, error: null });
  const inflight = useRef<AbortController | null>(null);

  useEffect(() => {
    setState((s) => (s.status === "verifying" ? s : { ...s, status: "verifying" }));
    const timer = setTimeout(() => {
      inflight.current?.abort();
      const controller = new AbortController();
      inflight.current = controller;
      verify(plan, controller.signal).then(
        (report) => {
          if (!controller.signal.aborted) setState({ status: "done", report, error: null });
        },
        (e: unknown) => {
          if (controller.signal.aborted) return;
          if (e instanceof NotAvailableError) {
            setState({ status: "unavailable", report: null, error: "The verifier is not available yet." });
          } else {
            const message = e instanceof ApiError ? e.message : "Could not reach the verifier.";
            setState((s) => ({ ...s, status: "error", error: message }));
          }
        },
      );
    }, delay);
    return () => clearTimeout(timer);
  }, [plan, delay, verify]);

  useEffect(() => () => inflight.current?.abort(), []);

  return state;
}
