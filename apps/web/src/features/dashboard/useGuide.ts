import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";
import { errorText, PROFILE_KEY, streamInterview, usePatchProfile, type InterviewRequest, type InterviewTurn, type Profile, type StepEvent, type TurnEvent } from "./api";
import { keepAll, memoryPatch, newFacts, type Fact } from "./logic";

export type GuideStatus = "idle" | "thinking" | "error";

export interface Guide {
  turns: InterviewTurn[];
  current: TurnEvent | null;
  steps: StepEvent[];
  status: GuideStatus;
  error: string | null;
  /** The student's message while it is being answered (or failed to be). */
  pending: string | null;
  facts: Fact[];
  kept: Fact[];
  begin: (options?: { seed?: TurnEvent | null; message?: string }) => void;
  reply: (text: string) => void;
  retry: () => void;
  keep: (fact: Fact) => void;
  drop: (fact: Fact) => void;
  keepEverything: () => void;
  stop: () => void;
}

const HISTORY = 16;

/**
 * The interviewing guide's conversation (POST /agents/interview). Each turn's noted facts wait as
 * chips until the student keeps (PATCH /me/profile) or drops them; the conversation itself is
 * saved into the profile's `interview` memory after every turn, so the guide can resume.
 */
export function useGuide(): Guide {
  const client = useQueryClient();
  const patch = usePatchProfile();
  const [turns, setTurns] = useState<InterviewTurn[]>([]);
  const [current, setCurrent] = useState<TurnEvent | null>(null);
  const [steps, setSteps] = useState<StepEvent[]>([]);
  const [status, setStatus] = useState<GuideStatus>("idle");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState<string | null>(null);
  const [facts, setFacts] = useState<Fact[]>([]);
  const [kept, setKept] = useState<Fact[]>([]);
  const turnsRef = useRef<InterviewTurn[]>([]);
  const abort = useRef<AbortController | null>(null);
  const lastRequest = useRef<InterviewRequest | null>(null);
  useEffect(() => () => abort.current?.abort(), []);

  const profile = useCallback(() => client.getQueryData<Profile>(PROFILE_KEY), [client]);
  const setAll = (next: InterviewTurn[]) => {
    turnsRef.current = next;
    setTurns(next);
  };

  const run = useCallback(
    async (body: InterviewRequest, studentText?: string) => {
      abort.current?.abort();
      const controller = new AbortController();
      abort.current = controller;
      lastRequest.current = body;
      setStatus("thinking");
      setError(null);
      setSteps([]);
      setPending(studentText ?? null);
      try {
        let got: TurnEvent | null = null;
        for await (const event of streamInterview(body, controller.signal)) {
          if (event.type === "step") setSteps((s) => [...s, event]);
          else if (event.type === "turn") got = event;
          else if (event.type === "error") throw new Error(event.message);
        }
        if (!got) throw new Error("Your guide did not answer. Try again.");
        const turn = got;
        const base = studentText ? [...turnsRef.current, { role: "student" as const, text: studentText }] : turnsRef.current;
        const next = [...base, { role: "guide" as const, text: turn.text, topic: turn.topic }];
        setAll(next);
        setCurrent(turn);
        setStatus("idle");
        setPending(null);
        const p = profile();
        if (p) {
          const noted = newFacts(p, turn.proposed);
          setFacts((old) => [...old.filter((f) => !noted.some((n) => n.id === f.id)), ...noted]);
          if (body.mode !== "welcome_back") patch.mutate(memoryPatch(p, next));
        }
      } catch (e) {
        if (controller.signal.aborted) return;
        setStatus("error");
        setError(e instanceof Error && e.constructor === Error ? e.message : errorText(e));
      }
    },
    [patch, profile],
  );

  const begin = useCallback(
    (options: { seed?: TurnEvent | null; message?: string } = {}) => {
      const memory = (profile()?.interview.turns ?? []).slice(-HISTORY);
      setFacts([]);
      setKept([]);
      if (options.seed) {
        const seeded = [...memory, { role: "guide" as const, text: options.seed.text, topic: options.seed.topic }];
        setAll(seeded);
        setCurrent(options.seed);
        if (options.message) void run({ mode: "reply", message: options.message, history: seeded.slice(-HISTORY) }, options.message);
        return;
      }
      setAll(memory);
      setCurrent(null);
      if (options.message) void run({ mode: "reply", message: options.message, history: memory }, options.message);
      else void run({ mode: "start", history: memory });
    },
    [profile, run],
  );

  const reply = useCallback(
    (text: string) => {
      const message = text.trim().slice(0, 2000);
      if (!message) return;
      void run({ mode: "reply", message, history: turnsRef.current.slice(-HISTORY) }, message);
    },
    [run],
  );

  const retry = useCallback(() => {
    const body = lastRequest.current;
    if (body) void run(body, body.mode === "reply" ? (body.message ?? undefined) : undefined);
  }, [run]);

  const keep = useCallback(
    (fact: Fact) => {
      const p = profile();
      if (!p) return;
      patch.mutate(fact.keep(p));
      setFacts((f) => f.filter((x) => x.id !== fact.id));
      setKept((k) => [...k, fact]);
    },
    [patch, profile],
  );

  const drop = useCallback((fact: Fact) => setFacts((f) => f.filter((x) => x.id !== fact.id)), []);

  const keepEverything = useCallback(() => {
    const p = profile();
    if (!p || facts.length === 0) return;
    patch.mutate(keepAll(p, facts));
    setKept((k) => [...k, ...facts]);
    setFacts([]);
  }, [facts, patch, profile]);

  const stop = useCallback(() => {
    abort.current?.abort();
    setStatus((s) => (s === "thinking" ? "idle" : s));
  }, []);

  return { turns, current, steps, status, error, pending, facts, kept, begin, reply, retry, keep, drop, keepEverything, stop };
}
