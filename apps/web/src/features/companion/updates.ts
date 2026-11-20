import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, unwrap } from "@/api/client";
import type { components } from "@/api/schema";

export type UpdatesOut = components["schemas"]["UpdatesOut"];
export type UpdateItem = components["schemas"]["UpdateItem"];

const COUNT_KEY = ["me", "updates", "count"] as const;
const FEED_KEY = ["me", "updates", "feed"] as const;
const DIGEST_KEY = ["me", "updates", "digest"] as const;
/** How often the orb's badge asks for news while the tab is visible. */
export const POLL_MS = 90_000;

/** The orb's unread count: polled every 90 s while logged in and the tab is visible. */
export function useUnreadCount(enabled: boolean) {
  return useQuery({
    queryKey: COUNT_KEY,
    queryFn: async () => unwrap(await api.GET("/me/updates")).unread,
    enabled,
    refetchInterval: POLL_MS,
    refetchIntervalInBackground: false,
    staleTime: 30_000,
    retry: false,
  });
}

/** "For you": the items, fetched when the tab opens (fast: no model call). */
export function useUpdatesFeed(enabled: boolean) {
  return useQuery({
    queryKey: FEED_KEY,
    queryFn: async () => unwrap(await api.GET("/me/updates")),
    enabled,
    staleTime: 60_000,
    retry: 1,
  });
}

/** The two-sentence digest, asked for alongside the items (it may take a few seconds). */
export function useUpdatesDigest(enabled: boolean) {
  return useQuery({
    queryKey: DIGEST_KEY,
    queryFn: async () => {
      const out = unwrap(await api.GET("/me/updates", { params: { query: { digest: true } } }));
      return { text: out.digest ?? null, ai: out.digest_ai ?? false };
    },
    enabled,
    staleTime: 5 * 60_000,
    retry: false,
  });
}

/** Moves the high-water marks to the newest items: the badge clears, the feed keeps its dots
 * until it is fetched again. */
export function useMarkSeen() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async () => unwrap(await api.POST("/me/updates/seen", { body: {} })),
    onSuccess: () => client.setQueryData(COUNT_KEY, 0),
  });
}
