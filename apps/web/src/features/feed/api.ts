/**
 * The Catalog page's browse rows (`GET /catalog/browse`) and the student ratings of a set of
 * courses (`GET /course-ratings`, logged in only), issue #19. Types come from the OpenAPI schema.
 */
import { useQuery } from "@tanstack/react-query";
import { api, unwrap } from "@/api/client";
import type { components } from "@/api/schema";

type S = components["schemas"];
export type CatalogBrowse = S["CatalogBrowse"];
export type CourseItem = S["CourseItem"];
export type CommentItem = S["CommentItem"];
export type NewCourse = S["NewCourse"];
export type RatingSummary = S["RatingSummary"];

export const browseKeys = {
  rows: (who: string) => ["catalog", "browse", who] as const,
  ratings: (who: string, codes: string) => ["catalog", "ratings", who, codes] as const,
};

/** The rows for this viewer (`who`: the account id, or "anon"; a login gives other rows). */
export function useCatalogBrowse(who: string, enabled = true) {
  return useQuery({
    queryKey: browseKeys.rows(who),
    queryFn: async () => unwrap(await api.GET("/catalog/browse")),
    enabled,
    staleTime: 5 * 60_000,
    retry: false,
  });
}

/**
 * Student ratings by course code, for a logged-in student only (the course page's rule). `who`
 * (the account id) is part of the key, so a later visitor never reads another student's cache.
 */
export function useCourseRatings(who: string | null, codes: readonly string[]) {
  const key = [...new Set(codes)].sort().join(",");
  return useQuery({
    queryKey: browseKeys.ratings(who ?? "anon", key),
    queryFn: async () => unwrap(await api.GET("/course-ratings", { params: { query: { codes: key } } })).ratings,
    enabled: who !== null && key.length > 0,
    staleTime: 60_000,
    retry: false,
  });
}

export function courseHref(code: string): string {
  return `/courses/${encodeURIComponent(code)}`;
}
