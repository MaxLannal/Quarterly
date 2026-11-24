/** The `/forum` page's data (issue #20): reviews and discussions in one list, and the rating statistics. */
import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { api, unwrap } from "@/api/client";
import type { components, paths } from "@/api/schema";

type S = components["schemas"];
export type ForumItem = S["ForumItemList"]["items"][number];
export type ReviewItem = S["ForumReviewItem"];
export type DiscussionItem = S["ForumDiscussionItem"];
export type ForumStats = S["ForumStats"];
export type RankedEntry = S["RankedEntry"];
type ItemsQuery = NonNullable<paths["/forum/items"]["get"]["parameters"]["query"]>;
export type ItemType = NonNullable<ItemsQuery["type"]>;
export type ItemFilters = Omit<ItemsQuery, "cursor" | "limit">;
export type Period = NonNullable<NonNullable<paths["/forum/stats"]["get"]["parameters"]["query"]>["period"]>;

export const TYPES: { key: ItemType | null; label: string }[] = [
  { key: null, label: "All" },
  { key: "review", label: "Reviews" },
  { key: "discussion", label: "Discussions" },
];

export const PERIODS: { key: Period; label: string }[] = [
  { key: "quarter", label: "This quarter" },
  { key: "year", label: "This year" },
];

export const boardKeys = {
  items: (filters: ItemFilters, loggedIn: boolean) => ["forum", "items", filters, loggedIn] as const,
  stats: (period: Period) => ["forum", "stats", period] as const,
};

export function useForumItems(filters: ItemFilters, loggedIn: boolean, limit = 20) {
  return useInfiniteQuery({
    // The answer depends on the login (reviews only for logged-in readers).
    queryKey: boardKeys.items(filters, loggedIn),
    initialPageParam: undefined as string | undefined,
    queryFn: async ({ pageParam }) =>
      unwrap(await api.GET("/forum/items", { params: { query: { ...filters, cursor: pageParam, limit } } })),
    getNextPageParam: (last) => last.next_cursor ?? undefined,
    retry: false,
  });
}

export function useForumStats(period: Period, enabled: boolean) {
  return useQuery({
    queryKey: boardKeys.stats(period),
    queryFn: async () => unwrap(await api.GET("/forum/stats", { params: { query: { period } } })),
    enabled,
    retry: false,
    staleTime: 60_000,
  });
}

export function itemKey(item: ForumItem): string {
  return item.type === "review" ? `review-${item.id}` : `discussion-${item.thread.id}`;
}

/** "4.21" for a score, "3.9" for an average. */
export function score(value: number, digits = 2): string {
  return value.toFixed(digits);
}
