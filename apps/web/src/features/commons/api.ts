/** Commons data: react-query hooks over the generated client (types come from the OpenAPI schema). */
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef } from "react";
import { api, unwrap } from "@/api/client";
import type { components, paths } from "@/api/schema";
import { checkStream, readSse } from "@/api/sse";

type S = components["schemas"];
export type ThreadSummary = S["CommonsThreadSummary"];
export type ThreadDetail = S["CommonsThreadDetail"];
export type ThreadList = S["CommonsThreadList"];
export type Reply = S["CommonsReply"];
export type Citation = S["CommonsCitation"];
export type CourseRef = S["CommonsCourse"];
export type Presence = S["CommonsPresence"];
export type BotEvent = S["CommonsBotEvent"];
export type BotRequest = S["CommonsBotRequest"];
export type ThreadCreate = S["CommonsThreadCreate"];
export type ThreadUpdate = S["CommonsThreadUpdate"];
export type VoteValue = S["CommonsVoteIn"]["value"];
export type TargetType = S["CommonsVoteIn"]["target_type"];
type ListQuery = NonNullable<paths["/commons/threads"]["get"]["parameters"]["query"]>;
export type Sort = NonNullable<ListQuery["sort"]>;
export type ListFilters = Omit<ListQuery, "cursor" | "limit">;

export const SORTS: { key: Sort; label: string; hint: string }[] = [
  { key: "hot", label: "Hot", hint: "Votes and answers, newest first" },
  { key: "new", label: "New", hint: "Newest questions" },
  { key: "top", label: "Top", hint: "Most upvoted" },
  { key: "unanswered", label: "Unanswered", hint: "No student answer yet" },
  { key: "active", label: "Active", hint: "Latest replies" },
];

export const commonsKeys = {
  all: ["commons"] as const,
  list: (filters: ListFilters, limit: number) => ["commons", "list", filters, limit] as const,
  thread: (id: number) => ["commons", "thread", id] as const,
  presence: (id: number) => ["commons", "presence", id] as const,
};

export function useThreads(filters: ListFilters, { limit = 20, enabled = true } = {}) {
  return useInfiniteQuery({
    queryKey: commonsKeys.list(filters, limit),
    initialPageParam: undefined as string | undefined,
    queryFn: async ({ pageParam }) =>
      unwrap(await api.GET("/commons/threads", { params: { query: { ...filters, cursor: pageParam, limit } } })),
    getNextPageParam: (last) => last.next_cursor ?? undefined,
    enabled,
    retry: false,
  });
}

/** One page of threads, for small lists (similar questions, the rail). */
export function useThreadPage(filters: ListFilters, limit: number, enabled = true) {
  return useQuery({
    queryKey: commonsKeys.list(filters, limit),
    queryFn: async () => unwrap(await api.GET("/commons/threads", { params: { query: { ...filters, limit } } })),
    enabled,
    retry: false,
    staleTime: 30_000,
  });
}

export function useThread(id: number) {
  return useQuery({
    queryKey: commonsKeys.thread(id),
    queryFn: async () => unwrap(await api.GET("/commons/threads/{thread_id}", { params: { path: { thread_id: id } } })),
    enabled: Number.isFinite(id) && id > 0,
    retry: false,
  });
}

function useRefreshThread(id?: number) {
  const client = useQueryClient();
  return () => {
    if (id) void client.invalidateQueries({ queryKey: commonsKeys.thread(id) });
    void client.invalidateQueries({ queryKey: ["commons", "list"] });
  };
}

export function useCreateThread() {
  const refresh = useRefreshThread();
  return useMutation({
    mutationFn: async (body: ThreadCreate) => unwrap(await api.POST("/commons/threads", { body })),
    onSuccess: refresh,
  });
}

export function useUpdateThread(id: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (body: ThreadUpdate) =>
      unwrap(await api.PATCH("/commons/threads/{thread_id}", { params: { path: { thread_id: id } }, body })),
    onSuccess: (detail) => {
      client.setQueryData(commonsKeys.thread(id), detail);
      void client.invalidateQueries({ queryKey: ["commons", "list"] });
    },
  });
}

async function noContent(result: { error?: unknown; response: Response }) {
  if (!result.response.ok) unwrap({ data: undefined, error: result.error, response: result.response });
}

export function useDeleteThread(id: number) {
  const refresh = useRefreshThread(id);
  return useMutation({
    mutationFn: async () => noContent(await api.DELETE("/commons/threads/{thread_id}", { params: { path: { thread_id: id } } })),
    onSuccess: refresh,
  });
}

export function useCreateReply(threadId: number) {
  const refresh = useRefreshThread(threadId);
  return useMutation({
    mutationFn: async (body: { body_md: string; parent_id?: number | null }) =>
      unwrap(await api.POST("/commons/threads/{thread_id}/replies", { params: { path: { thread_id: threadId } }, body })),
    onSuccess: refresh,
  });
}

export function useUpdateReply(threadId: number) {
  const refresh = useRefreshThread(threadId);
  return useMutation({
    mutationFn: async ({ id, body_md }: { id: number; body_md: string }) =>
      unwrap(await api.PATCH("/commons/replies/{reply_id}", { params: { path: { reply_id: id } }, body: { body_md } })),
    onSuccess: refresh,
  });
}

export function useDeleteReply(threadId: number) {
  const refresh = useRefreshThread(threadId);
  return useMutation({
    mutationFn: async (id: number) => noContent(await api.DELETE("/commons/replies/{reply_id}", { params: { path: { reply_id: id } } })),
    onSuccess: refresh,
  });
}

export function useVote() {
  return useMutation({
    mutationFn: async (body: { target_type: TargetType; target_id: number; value: VoteValue }) =>
      unwrap(await api.POST("/commons/votes", { body })),
  });
}

export function useAccept(threadId: number) {
  const refresh = useRefreshThread(threadId);
  return useMutation({
    mutationFn: async (replyId: number | null) =>
      unwrap(await api.POST("/commons/threads/{thread_id}/accept", { params: { path: { thread_id: threadId } }, body: { reply_id: replyId } })),
    onSuccess: refresh,
  });
}

export function useFollow(threadId: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (follow: boolean) =>
      unwrap(await api.POST("/commons/threads/{thread_id}/follow", { params: { path: { thread_id: threadId } }, body: { follow } })),
    onSuccess: (out) => {
      client.setQueryData<ThreadDetail>(commonsKeys.thread(threadId), (old) => (old ? { ...old, following: out.following } : old));
    },
  });
}

export function useReport() {
  return useMutation({
    mutationFn: async (body: { target_type: TargetType; target_id: number; reason: string }) =>
      unwrap(await api.POST("/commons/reports", { body })),
  });
}

function visible(): boolean {
  return typeof document === "undefined" || document.visibilityState === "visible";
}

/** Live state of an open thread, polled every 3 s while the tab is visible. */
export function usePresence(threadId: number, enabled = true) {
  return useQuery({
    queryKey: commonsKeys.presence(threadId),
    queryFn: async () =>
      unwrap(await api.GET("/commons/threads/{thread_id}/presence", { params: { path: { thread_id: threadId } } })),
    enabled: enabled && threadId > 0,
    refetchInterval: () => (visible() ? 3000 : false),
    refetchIntervalInBackground: false,
    retry: false,
  });
}

/** "I am typing": at most one request every 4 s while the student types. */
export function useTypingPing(threadId: number, enabled: boolean) {
  const last = useRef(0);
  useEffect(() => {
    last.current = 0;
  }, [threadId]);
  return useCallback(() => {
    if (!enabled) return;
    const now = Date.now();
    if (now - last.current < 4000) return;
    last.current = now;
    void api.POST("/commons/threads/{thread_id}/typing", { params: { path: { thread_id: threadId } } }).catch(() => undefined);
  }, [enabled, threadId]);
}

/** POST /commons/threads/{id}/bot, yielding each event as it arrives. */
export async function* streamBot(threadId: number, body: BotRequest, signal?: AbortSignal): AsyncGenerator<BotEvent> {
  const { data, error, response } = await api.POST("/commons/threads/{thread_id}/bot", {
    params: { path: { thread_id: threadId } },
    body,
    parseAs: "stream",
    signal,
  });
  if (!response.ok && response.status !== 501) {
    const detail = error && typeof error === "object" && "detail" in error ? (error as { detail: unknown }).detail : null;
    throw new Error(typeof detail === "string" ? detail : `Request failed (${response.status})`);
  }
  yield* readSse<BotEvent>(checkStream(response, data));
}

/** Course autocomplete (GET /courses?q=), for the course filter, the picker and mentions. */
export function useCourseMatches(q: string, limit = 6) {
  const query = q.trim();
  return useQuery({
    queryKey: ["commons", "courses", query, limit],
    queryFn: async () => unwrap(await api.GET("/courses", { params: { query: { q: query, limit } } })),
    enabled: query.length >= 2,
    staleTime: 5 * 60_000,
    retry: false,
    placeholderData: (previous) => previous,
  });
}
