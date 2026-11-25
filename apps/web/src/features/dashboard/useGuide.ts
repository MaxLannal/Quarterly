import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";
import { QUESTIONS_KEY, type QuestionSet } from "@/features/profile/questions";
import { errorText, PROFILE_KEY, streamInterview, usePatchProfile, type InterviewRequest, type InterviewTurn, type Profile, type ProfilePatch, type StepEvent, type TurnEvent } from "./api";
import { memoryPatch, proposalFrom, type Proposal } from "./logic";

export type GuideStatus = "idle" | "thinking" | "error";

export interface Guide {
  turns: InterviewTurn[];
  current: TurnEvent | null;
  steps: StepEvent[];
  status: GuideStatus;
  error: string | null;
  /** The student's message while it is being answered (or failed to be). */
  pending: string | null;
  /** Answers the guide mapped to a field, waiting for Accept (one per question, newest first). */
  proposals: Proposal[];
  /** Answers accepted in this conversation. */
  accepted: Proposal[];
  begin: (options?: { seed?: TurnEvent | null; message?: string }) => void;
  reply: (text: string) => void;
  retry: () => void;
  accept: (proposal: Proposal, patch?: ProfilePatch) => void;
  dismiss: (proposal: Proposal) => void;
  stop: () => void;
}

const HISTORY = 16;

/**
 * The dashboard agent's conversation (POST /agents/interview, Issue #16). Each turn asks one
 * General Information question; the answer it mapped from the student's reply (`proposed`)
 * waits as a card until the student accepts it (PATCH /me/profile with the interview memory) or
 * changes it. The conversation is saved into the record's `interview` memory after every turn,
 * so the guide can resume.
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
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [accepted, setAccepted] = useState<Proposal[]>([]);
  const turnsRef = useRef<InterviewTurn[]>([]);
  const abort = useRef<AbortController | null>(null);
  const lastRequest = useRef<InterviewRequest | null>(null);
  useEffect(() => () => abort.current?.abort(), []);

  const profile = useCallback(() => client.getQueryData<Profile>(PROFILE_KEY), [client]);
  const questions = useCallback(() => client.getQueryData<QuestionSet>(QUESTIONS_KEY), [client]);
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
      // The question the student is answering: the last guide turn of the history.
      const asked = [...(body.history ?? [])].reverse().find((t) => t.role === "guide")?.topic ?? null;
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
          const proposal = turn.retry ? null : proposalFrom(turn, questions(), p, asked);
          if (proposal) setProposals((old) => [proposal, ...old.filter((o) => o.id !== proposal.id)]);
          if (body.mode !== "welcome_back") patch.mutate(memoryPatch(p, next));
        }
      } catch (e) {
        if (controller.signal.aborted) return;
        setStatus("error");
        setError(e instanceof Error && e.constructor === Error ? e.message : errorText(e));
      }
    },
    [patch, profile, questions],
  );

  const begin = useCallback(
    (options: { seed?: TurnEvent | null; message?: string } = {}) => {
      const memory = (profile()?.interview.turns ?? []).slice(-HISTORY);
      setProposals([]);
      setAccepted([]);
      setError(null);
      setStatus("idle");
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

  /** Saves the proposal (or the student's changed version of it) with the guide's memory. */
  const accept = useCallback(
    (proposal: Proposal, changed?: ProfilePatch) => {
      const p = profile();
      if (!p) return;
      patch.mutate({ ...(changed ?? proposal.patch), ...memoryPatch(p, turnsRef.current, [proposal.id]) });
      setProposals((list) => list.filter((x) => x.id !== proposal.id));
      setAccepted((list) => [...list.filter((x) => x.id !== proposal.id), proposal]);
    },
    [patch, profile],
  );

  const dismiss = useCallback((proposal: Proposal) => setProposals((list) => list.filter((x) => x.id !== proposal.id)), []);

  const stop = useCallback(() => {
    abort.current?.abort();
    setStatus((s) => (s === "thinking" ? "idle" : s));
  }, []);

  return { turns, current, steps, status, error, pending, proposals, accepted, begin, reply, retry, accept, dismiss, stop };
}
