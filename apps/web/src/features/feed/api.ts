/** Feed data: react-query hooks over the generated client (types come from the OpenAPI schema). */
import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { api, unwrap } from "@/api/client";
import type { components } from "@/api/schema";

type S = components["schemas"];
export type FeedPage = S["FeedPage"];
export type FeedItem = FeedPage["items"][number];
export type FeedTab = FeedPage["tab"];
export type CourseItem = S["CourseItem"];
export type CommentItem = S["CommentItem"];
export type BookItem = S["BookItem"];
export type WordsItem = S["WordsItem"];
export type ProgramItem = S["ProgramItem"];
export type QuestionItem = S["QuestionItem"];
export type ShelfBook = S["ShelfBook"];
export type FeedCategory = S["FeedCategory"];
export type FeedCategories = S["FeedCategories"];
export type FeedNotes = S["FeedNotes"];

/** One page is also one batch of AI notes (the notes endpoint takes at most 12 ids). */
export const PAGE_SIZE = 12;

export const feedKeys = {
  categories: (who: string) => ["feed", "categories", who] as const,
  feed: (who: string, tab: FeedTab, categories: string) => ["feed", "items", who, tab, categories] as const,
  notes: (who: string, tab: FeedTab, categories: string, ids: string[]) =>
    ["feed", "notes", who, tab, categories, ids.join("|")] as const,
};

export function useFeedCategories(who: string, enabled = true) {
  return useQuery({
    queryKey: feedKeys.categories(who),
    queryFn: async () => unwrap(await api.GET("/feed/categories")),
    enabled,
    staleTime: 5 * 60_000,
    retry: false,
  });
}

/** The feed, page by page. `categories` is a comma list ("" = no filter). */
export function useFeed(who: string, tab: FeedTab, categories: string, enabled = true) {
  return useInfiniteQuery({
    queryKey: feedKeys.feed(who, tab, categories),
    initialPageParam: undefined as string | undefined,
    queryFn: async ({ pageParam }) =>
      unwrap(
        await api.GET("/feed", {
          params: { query: { tab, categories, cursor: pageParam, limit: PAGE_SIZE } },
        }),
      ),
    getNextPageParam: (last) => last.next_cursor ?? undefined,
    enabled,
    staleTime: 5 * 60_000,
    retry: false,
  });
}

/** The AI curator's notes and headline for one page of items (deterministic when the AI is off). */
export function useFeedNotes(who: string, tab: FeedTab, categories: string, ids: string[], enabled = true) {
  return useQuery({
    queryKey: feedKeys.notes(who, tab, categories, ids),
    queryFn: async () =>
      unwrap(await api.POST("/agents/feed-notes", { body: { item_ids: ids, tab, categories } })),
    enabled: enabled && ids.length > 0,
    staleTime: 60 * 60_000,
    retry: false,
  });
}

/** Save the focus categories to the profile (the dashboard's PATCH /me/profile). */
export async function saveFocusToProfile(categories: string[]): Promise<void> {
  unwrap(await api.PATCH("/me/profile", { body: { feed_categories: categories } }));
}

export function courseHref(code: string): string {
  return `/courses/${encodeURIComponent(code)}`;
}

export function searchHref(word: string): string {
  return `/courses?q=${encodeURIComponent(word)}`;
}
