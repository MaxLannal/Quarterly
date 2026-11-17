/** Curator review queue: react-query hooks over the generated client (types from the OpenAPI schema). */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, unwrap } from "@/api/client";
import type { components, paths } from "@/api/schema";

type S = components["schemas"];
export type ReviewItem = S["ReviewItemOut"];
export type ReviewNode = S["ReviewNode"];
export type ReviewCheck = S["ReviewCheck"];
export type ReviewDecision = S["ReviewDecision"];
export type ProgramVersion = S["ProgramVersionOut"];
type ListQuery = NonNullable<paths["/admin/review-items"]["get"]["parameters"]["query"]>;
export type ReviewStatus = NonNullable<ListQuery["status"]>;

export const reviewKeys = {
  all: ["review"] as const,
  list: (status: ReviewStatus) => ["review", "items", status] as const,
};

export function useReviewItems(status: ReviewStatus, enabled: boolean) {
  return useQuery({
    queryKey: reviewKeys.list(status),
    queryFn: async () => unwrap(await api.GET("/admin/review-items", { params: { query: { status, limit: 200 } } })),
    enabled,
    retry: false,
  });
}

export function useReviewDecision() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, body }: { id: number; body: ReviewDecision }) =>
      unwrap(await api.POST("/admin/review-items/{item_id}/decision", { params: { path: { item_id: id } }, body })),
    onSuccess: () => client.invalidateQueries({ queryKey: reviewKeys.all }),
  });
}

export function usePublishVersion() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (versionId: number) =>
      unwrap(await api.POST("/admin/program-versions/{version_id}/publish", { params: { path: { version_id: versionId } } })),
    onSuccess: () => client.invalidateQueries({ queryKey: reviewKeys.all }),
  });
}
