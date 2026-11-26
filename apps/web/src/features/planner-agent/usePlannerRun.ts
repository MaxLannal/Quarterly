/**
 * The planner agent in the page (issues #17 and #18): one hook streams `POST /agents/planner`
 * for a first plan and for chat messages, keeps the conversation and the open proposals, and
 * applies a proposal only when the student accepts it.
 *
 * - A saved plan (unchanged since its last save) accepts through
 *   `POST /plans/{id}/changesets/{cs}/apply`; the server re-bases planner proposals and locks
 *   the courses they place. 409 = the proposal no longer fits: it becomes stale.
 * - Any other plan applies the ops in the browser (`applyOps`, with locks).
 * - The conversation and the proposals are kept with the plan on this device (issue #18 D1:
 *   proposals stay until accepted or rejected); a saved plan also has its chat on the server.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { api, isNotAvailable } from "@/api/client";
import { streamPlanner, type PlannerBody } from "@/api/sse";
import type { ChangeOp, ChatTurn, PlanState, PlannerEvent } from "@/api/types";
import { fromEvent, stillFits, withLocks, type Proposal } from "./proposals";
import type { ThreadEntry } from "./thread";

export interface PlannerRunOptions {
  plan: PlanState;
  /** A saved plan of the account that has not changed since it was saved. */
  planId: string | null;
  loggedIn: boolean;
  initial: { chat?: ThreadEntry[]; proposals?: Proposal[]; workingNotes?: string; profileAnswers?: Record<string, unknown> };
  /** Applies ops in the browser and records them in the history; false when they do not fit. */
  applyLocal: (ops: ChangeOp[], label: string) => boolean;
  /** A saved plan changed on the server (an accepted proposal): show its new state. */
  replaceFromServer: (state: PlanState, label: string, ops: ChangeOp[]) => void;
  /** A first plan arrived with these proposals (the walkthrough starts). */
  onGenerated?: (proposals: Proposal[]) => void;
}

export interface PlannerRun {
  entries: ThreadEntry[];
  proposals: Proposal[];
  running: boolean;
  unavailable: boolean;
  /** The latest polite announcement for screen readers. */
  announcement: string;
  workingNotes: string;
  profileAnswers: Record<string, unknown>;
  generate: () => void;
  send: (text: string) => void;
  answer: (questionId: string, option: string | null, text: string | null) => void;
  clear: () => Promise<void>;
  accept: (id: string) => Promise<boolean>;
  reject: (id: string) => Promise<void>;
  acceptAll: () => Promise<void>;
  rejectAll: () => Promise<void>;
  askAgain: (id: string) => void;
}

const HISTORY_TURNS = 12;

function turnsOf(entries: ThreadEntry[]): ChatTurn[] {
  const turns: ChatTurn[] = [];
  for (const e of entries) {
    if (e.kind === "user") turns.push({ role: "user", text: e.text });
    else if (e.kind === "assistant") turns.push({ role: "assistant", text: e.text });
  }
  return turns.slice(-HISTORY_TURNS);
}

export function usePlannerRun(o: PlannerRunOptions): PlannerRun {
  const [entries, setEntries] = useState<ThreadEntry[]>(() => o.initial.chat ?? []);
  const [proposals, setProposals] = useState<Proposal[]>(() => o.initial.proposals ?? []);
  const [workingNotes, setWorkingNotes] = useState(o.initial.workingNotes ?? "");
  const [profileAnswers, setProfileAnswers] = useState<Record<string, unknown>>(() => o.initial.profileAnswers ?? {});
  const [running, setRunning] = useState(false);
  const [unavailable, setUnavailable] = useState(false);
  const [announcement, setAnnouncement] = useState("");
  const latest = useRef(o);
  latest.current = o;
  const proposalsRef = useRef(proposals);
  proposalsRef.current = proposals;
  const answersRef = useRef({ profileAnswers, workingNotes });
  answersRef.current = { profileAnswers, workingNotes };

  // A saved plan's conversation lives on the server: load it once when this device has none.
  const planId = o.planId;
  const hadChat = useRef(entries.length > 0);
  useEffect(() => {
    if (!planId || hadChat.current) return;
    let live = true;
    void api
      .GET("/agents/planner/history", { params: { query: { plan_id: planId } } })
      .then(({ data }) => {
        if (!live || !data) return;
        const restored: ThreadEntry[] = [];
        for (const e of data.entries ?? []) {
          if (e.role === "user") restored.push({ kind: "user", text: e.text ?? "" });
          else if (e.role === "assistant") restored.push({ kind: "assistant", text: e.text ?? "", citations: e.citations ?? [] });
        }
        if (restored.length) setEntries((xs) => (xs.length ? xs : restored));
      })
      .catch(() => undefined);
    return () => {
      live = false;
    };
  }, [planId]);

  const push = useCallback((e: ThreadEntry) => setEntries((xs) => [...xs, e]), []);
  const drop = useCallback((id: string) => setProposals((ps) => ps.filter((p) => p.id !== id)), []);
  const markStale = useCallback((id: string) => setProposals((ps) => ps.map((p) => (p.id === id ? { ...p, status: "stale" as const } : p))), []);

  const accept = useCallback(
    async (id: string, confirmationText: string | null = null): Promise<boolean> => {
      const p = proposalsRef.current.find((x) => x.id === id);
      if (!p || p.status !== "proposed") return false;
      const { planId: savedId, plan } = latest.current;
      const label = `Accepted: ${p.title}`;
      if (savedId && p.changeSetId) {
        const { data, response } = await api.POST("/plans/{plan_id}/changesets/{changeset_id}/apply", {
          params: { path: { plan_id: savedId, changeset_id: p.changeSetId } },
          body: { base_plan_hash: p.basePlanHash ?? "", confirmation_text: confirmationText },
        });
        if (response.status === 409) {
          markStale(id);
          return false;
        }
        if (!data) {
          push({ kind: "error", text: "Could not accept this proposal. Try again." });
          return false;
        }
        latest.current.replaceFromServer(data.state, label, p.ops);
        drop(id);
        setAnnouncement(label);
        return true;
      }
      if (!stillFits(plan, p) || !latest.current.applyLocal(withLocks(plan, p.ops), label)) {
        markStale(id);
        return false;
      }
      drop(id);
      setAnnouncement(label);
      return true;
    },
    [drop, markStale, push],
  );

  const run = useCallback(
    async (body: PlannerBody, kind: "generate" | "chat") => {
      const { plan, planId: savedId, loggedIn } = latest.current;
      const { profileAnswers: answers, workingNotes: notes } = answersRef.current;
      const full: PlannerBody = {
        ...body,
        plan,
        plan_id: savedId,
        ...(loggedIn ? {} : { profile_answers: answers, working_notes: notes || null }),
      };
      setRunning(true);
      setUnavailable(false);
      const fresh: Proposal[] = [];
      let runId = `${kind}-${Date.now()}`;
      const handle = (ev: PlannerEvent) => {
        switch (ev.type) {
          case "step":
            setEntries((xs) => {
              const last = xs.at(-1);
              const step = { name: ev.name, status: ev.status };
              if (last?.kind === "steps" && last.runId === runId) {
                const steps = last.steps.filter((s) => s.name !== ev.name).concat(step);
                return [...xs.slice(0, -1), { ...last, steps }];
              }
              return [...xs, { kind: "steps", runId, steps: [step] }];
            });
            break;
          case "question":
            runId = ev.run_id;
            push({ kind: "question", event: ev });
            setAnnouncement(`The planner asks: ${ev.text}`);
            break;
          case "plan":
            runId = ev.run_id;
            push({ kind: "plan", event: ev });
            break;
          case "proposal": {
            const p = fromEvent(ev, runId);
            fresh.push(p);
            setProposals((ps) => [...ps.filter((x) => x.id !== p.id), p]);
            proposalsRef.current = [...proposalsRef.current.filter((x) => x.id !== p.id), p];
            push({ kind: "proposal", proposalId: p.id });
            setAnnouncement(`New proposal: ${p.title}`);
            break;
          }
          case "message":
            push({ kind: "assistant", text: ev.text, citations: ev.citations ?? [] });
            break;
          case "confirm": {
            const match = proposalsRef.current.find((p) => JSON.stringify(p.ops) === JSON.stringify(ev.change_set.ops));
            if (match) void accept(match.id, ev.confirmation_text);
            else if (latest.current.applyLocal(ev.change_set.ops, "Applied a typed change")) push({ kind: "assistant", text: "Applied the change you typed.", citations: [] });
            break;
          }
          case "done":
            if (ev.working_notes) setWorkingNotes(ev.working_notes);
            if (ev.profile_answers) setProfileAnswers((a) => ({ ...a, ...ev.profile_answers }));
            break;
          case "error":
            push({ kind: "error", text: ev.message, reason: ev.reason ?? null });
            break;
        }
      };
      try {
        for await (const ev of streamPlanner(full)) handle(ev);
      } catch (err) {
        if (isNotAvailable(err)) setUnavailable(true);
        else push({ kind: "error", text: "The planner could not answer. Try again." });
      } finally {
        setRunning(false);
      }
      if (kind === "generate" && fresh.length) latest.current.onGenerated?.(fresh);
    },
    [accept, push],
  );

  const generate = useCallback(() => {
    void run({ mode: "generate", plan: latest.current.plan }, "generate");
  }, [run]);

  const send = useCallback(
    (text: string) => {
      const message = text.trim();
      if (!message) return;
      const history = latest.current.planId ? [] : turnsOf(entries);
      const pending = proposalsRef.current
        .filter((p) => p.status === "proposed" && p.ops.length && p.basePlanHash)
        .map((p) => ({ group_id: p.groupId, ops: p.ops, base_plan_hash: p.basePlanHash as string }));
      push({ kind: "user", text: message });
      void run({ mode: "chat", plan: latest.current.plan, message, history, pending }, "chat");
    },
    [entries, push, run],
  );

  const answer = useCallback(
    (questionId: string, option: string | null, text: string | null) => {
      const q = [...entries].reverse().find((e): e is Extract<ThreadEntry, { kind: "question" }> => e.kind === "question" && e.event.question_id === questionId);
      if (!q) return;
      const shown = option ?? text ?? "";
      setEntries((xs) => xs.map((e) => (e === q ? { ...e, answered: shown } : e)));
      push({ kind: "user", text: shown });
      void run({ mode: "generate", plan: latest.current.plan, run_id: q.event.run_id, answer: { question_id: questionId, option, text } }, "generate");
    },
    [entries, push, run],
  );

  const reject = useCallback(
    async (id: string): Promise<void> => {
      const p = proposalsRef.current.find((x) => x.id === id);
      if (!p) return;
      const { planId: savedId } = latest.current;
      drop(id);
      setAnnouncement(`Rejected: ${p.title}`);
      if (savedId && p.changeSetId) {
        await api.POST("/plans/{plan_id}/changesets/{changeset_id}/discard", { params: { path: { plan_id: savedId, changeset_id: p.changeSetId } } }).catch(() => undefined);
      }
    },
    [drop],
  );

  const acceptAll = useCallback(async () => {
    for (const p of [...proposalsRef.current]) {
      if (p.status === "proposed") await accept(p.id);
    }
  }, [accept]);

  const rejectAll = useCallback(async () => {
    for (const p of [...proposalsRef.current]) await reject(p.id);
  }, [reject]);

  const clear = useCallback(async () => {
    const { planId: savedId } = latest.current;
    if (savedId) await api.DELETE("/agents/planner/history", { params: { query: { plan_id: savedId } } }).catch(() => undefined);
    setEntries([]);
    setAnnouncement("The chat is cleared. Open proposals stay on your plan.");
  }, []);

  const askAgain = useCallback(
    (id: string) => {
      const p = proposalsRef.current.find((x) => x.id === id);
      if (!p) return;
      drop(id);
      send(`Your proposal "${p.title}" no longer fits my plan. Please propose it again for my plan as it is now.`);
    },
    [drop, send],
  );

  return { entries, proposals, running, unavailable, announcement, workingNotes, profileAnswers, generate, send, answer, clear, accept, reject, acceptAll, rejectAll, askAgain };
}
