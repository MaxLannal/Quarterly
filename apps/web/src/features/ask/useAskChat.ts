import { useCallback, useEffect, useRef, useState } from "react";
import {
  historyOf,
  loadConversations,
  MAX_CHARS,
  mergeStep,
  newId,
  pendingAnswer,
  saveConversations,
  titleFrom,
} from "./conversations";
import { askErrorText, streamAsk } from "./stream";
import type { AskContext, AskMode, AssistantTurn, Conversation, Turn } from "./types";

const CUT_OFF = "The answer was cut off. Try again.";

export interface AskChat {
  conversations: Conversation[];
  active: Conversation | null;
  activeId: string | null;
  running: boolean;
  send: (text: string) => void;
  stop: () => void;
  retry: (turnId: string) => void;
  select: (id: string | null) => void;
  newChat: () => void;
  rename: (id: string, title: string) => void;
  remove: (id: string) => void;
  clearAll: () => void;
  setFeedback: (turnId: string, value: "up" | "down" | null) => void;
  /** Adds a conversation (e.g. one continued from the companion) and makes it active. */
  adopt: (conversation: Conversation) => void;
}

/**
 * The campus guide's conversations in one storage slot, and the streaming of answers into them.
 * `context` is read when a question is sent (the companion passes the current page).
 */
export function useAskChat({
  storageKey,
  mode,
  context,
  initialActive = "none",
}: {
  storageKey: string;
  mode: AskMode;
  context?: AskContext;
  /** "latest": continue the newest conversation (the companion); "none": start blank. */
  initialActive?: "latest" | "none";
}): AskChat {
  const [conversations, setConversations] = useState<Conversation[]>(() => loadConversations(storageKey));
  const [activeId, setActiveId] = useState<string | null>(() =>
    initialActive === "latest" ? (loadConversations(storageKey)[0]?.id ?? null) : null,
  );
  const [running, setRunning] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const convRef = useRef(conversations);
  convRef.current = conversations;
  const contextRef = useRef(context);
  contextRef.current = context;

  useEffect(() => {
    saveConversations(storageKey, conversations);
  }, [storageKey, conversations]);

  const patchTurn = useCallback((convId: string, turnId: string, fn: (t: AssistantTurn) => AssistantTurn) => {
    setConversations((cs) =>
      cs.map((c) =>
        c.id !== convId
          ? c
          : {
              ...c,
              updatedAt: Date.now(),
              turns: c.turns.map((t) => (t.id === turnId && t.role === "assistant" ? fn(t) : t)),
            },
      ),
    );
  }, []);

  const run = useCallback(
    async (convId: string, turnId: string, question: string, history: Turn[]) => {
      const controller = new AbortController();
      abortRef.current = controller;
      setRunning(true);
      let settled = false;
      try {
        const body = { message: question, history: historyOf(history), context: contextRef.current ?? {}, mode };
        for await (const ev of streamAsk(body, controller.signal)) {
          if (ev.type === "step") {
            const step = { tool: ev.tool, label: ev.label, status: ev.status };
            patchTurn(convId, turnId, (t) => ({ ...t, steps: mergeStep(t.steps, step) }));
          } else if (ev.type === "answer") {
            settled = true;
            patchTurn(convId, turnId, (t) => ({
              ...t,
              status: "done",
              text: ev.text,
              citations: ev.citations ?? [],
              courses: ev.courses ?? [],
              followups: ev.followups ?? [],
              ai: ev.ai ?? true,
              steps: t.steps.map((s) => (s.status === "started" ? { ...s, status: "done" } : s)),
            }));
          } else if (ev.type === "error") {
            settled = true;
            patchTurn(convId, turnId, (t) => ({ ...t, status: "error", error: ev.message }));
          }
        }
        if (!settled) patchTurn(convId, turnId, (t) => ({ ...t, status: "error", error: CUT_OFF }));
      } catch (error) {
        if (controller.signal.aborted) {
          if (!settled) patchTurn(convId, turnId, (t) => ({ ...t, status: "stopped" }));
        } else {
          patchTurn(convId, turnId, (t) => ({ ...t, status: "error", error: askErrorText(error) }));
        }
      } finally {
        if (abortRef.current === controller) abortRef.current = null;
        setRunning(false);
      }
    },
    [mode, patchTurn],
  );

  const send = useCallback(
    (raw: string) => {
      const question = raw.trim().slice(0, MAX_CHARS);
      if (!question || abortRef.current) return;
      const current = convRef.current.find((c) => c.id === activeId) ?? null;
      const conv: Conversation = current ?? { id: newId(), title: titleFrom(question), updatedAt: Date.now(), turns: [] };
      const answer = pendingAnswer();
      const turns: Turn[] = [...conv.turns, { id: newId(), role: "user", text: question }, answer];
      const next = { ...conv, turns, updatedAt: Date.now() };
      setConversations((cs) => [next, ...cs.filter((c) => c.id !== conv.id)]);
      setActiveId(conv.id);
      void run(conv.id, answer.id, question, conv.turns);
    },
    [activeId, run],
  );

  const retry = useCallback(
    (turnId: string) => {
      if (abortRef.current) return;
      const conv = convRef.current.find((c) => c.turns.some((t) => t.id === turnId));
      if (!conv) return;
      const at = conv.turns.findIndex((t) => t.id === turnId);
      const question = conv.turns[at - 1];
      if (!question || question.role !== "user") return;
      const answer = pendingAnswer();
      const turns = [...conv.turns.slice(0, at), answer, ...conv.turns.slice(at + 1)];
      setConversations((cs) => cs.map((c) => (c.id === conv.id ? { ...c, turns, updatedAt: Date.now() } : c)));
      void run(conv.id, answer.id, question.text, conv.turns.slice(0, at - 1));
    },
    [run],
  );

  const stop = useCallback(() => abortRef.current?.abort(), []);

  const newChat = useCallback(() => {
    abortRef.current?.abort();
    setActiveId(null);
  }, []);

  const select = useCallback((id: string | null) => {
    abortRef.current?.abort();
    setActiveId(id);
  }, []);

  const rename = useCallback((id: string, title: string) => {
    const clean = title.replace(/\s+/g, " ").trim().slice(0, 80);
    if (!clean) return;
    setConversations((cs) => cs.map((c) => (c.id === id ? { ...c, title: clean } : c)));
  }, []);

  const remove = useCallback(
    (id: string) => {
      if (id === activeId) {
        abortRef.current?.abort();
        setActiveId(null);
      }
      setConversations((cs) => cs.filter((c) => c.id !== id));
    },
    [activeId],
  );

  const clearAll = useCallback(() => {
    abortRef.current?.abort();
    setActiveId(null);
    setConversations([]);
  }, []);

  const setFeedback = useCallback((turnId: string, value: "up" | "down" | null) => {
    setConversations((cs) =>
      cs.map((c) => ({
        ...c,
        turns: c.turns.map((t) => (t.id === turnId && t.role === "assistant" ? { ...t, feedback: value } : t)),
      })),
    );
  }, []);

  const adopt = useCallback((conversation: Conversation) => {
    setConversations((cs) => [conversation, ...cs.filter((c) => c.id !== conversation.id)]);
    setActiveId(conversation.id);
  }, []);

  const active = conversations.find((c) => c.id === activeId) ?? null;
  return {
    conversations,
    active,
    activeId: active ? active.id : null,
    running,
    send,
    stop,
    retry,
    select,
    newChat,
    rename,
    remove,
    clearAll,
    setFeedback,
    adopt,
  };
}
