/** Forum data: react-query hooks over the generated client (types come from the OpenAPI schema). */
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, unwrap } from "@/api/client";
import type { components, paths } from "@/api/schema";

type S = components["schemas"];
export type ForumPage = S["ForumPageOut"];
export type Post = S["PostOut"];
export type PostDetail = S["PostDetail"];
export type Comment = S["CommentOut"];
export type PostCreate = S["PostCreate"];
export type PostUpdate = S["PostUpdate"];
export type ReviewRatings = S["ReviewRatingIn"];
export type RatingSummary = S["RatingSummary"];
export type CourseForum = S["CourseForumOut"];
export type InstructorSummary = S["InstructorSummary"];
export type InstructorDetail = S["InstructorDetail"];
export type ModerationItem = S["ModerationItemOut"];
export type VoteValue = S["VoteIn"]["value"];
export type TargetType = S["VoteIn"]["target_type"];
export type PostKind = PostCreate["kind"];
/** The posts list's `sort` query parameter, taken from the generated schema. */
type PostsQuery = NonNullable<paths["/forum/pages/{page_id}/posts"]["get"]["parameters"]["query"]>;
export type Sort = NonNullable<PostsQuery["sort"]>;

const PAGE_SIZE = 20;

export const forumKeys = {
  all: ["forum"] as const,
  page: (code: string, slug: string) => ["forum", "page", code, slug] as const,
  posts: (pageId: number, kind: PostKind, sort: Sort, term: string) => ["forum", "posts", pageId, kind, sort, term] as const,
  post: (id: number) => ["forum", "post", id] as const,
  pageById: (id: number) => ["forum", "page-by-id", id] as const,
  course: (code: string) => ["forum", "course", code] as const,
  queue: ["forum", "moderation"] as const,
};

export function useForumPage(code: string, slug: string, enabled = true) {
  return useQuery({
    queryKey: forumKeys.page(code, slug),
    queryFn: async () => unwrap(await api.GET("/forum/pages", { params: { query: { course: code, instructor: slug } } })),
    enabled,
    retry: false,
  });
}

/** A forum page by its id (advisor citations name pages and posts by id only). */
export function useForumPageById(id: number, enabled = true) {
  return useQuery({
    queryKey: forumKeys.pageById(id),
    queryFn: async () => unwrap(await api.GET("/forum/pages/{page_id}", { params: { path: { page_id: id } } })),
    enabled: enabled && Number.isFinite(id),
    retry: false,
    staleTime: 5 * 60_000,
  });
}

export function usePosts(pageId: number, kind: PostKind, sort: Sort, term: string) {
  return useInfiniteQuery({
    queryKey: forumKeys.posts(pageId, kind, sort, term),
    initialPageParam: 0,
    queryFn: async ({ pageParam }) =>
      unwrap(
        await api.GET("/forum/pages/{page_id}/posts", {
          params: {
            path: { page_id: pageId },
            query: { kind, sort, term: term || undefined, limit: PAGE_SIZE, offset: pageParam },
          },
        }),
      ),
    getNextPageParam: (last) => (last.offset + last.items.length < last.total ? last.offset + last.items.length : undefined),
    retry: false,
  });
}

export function usePost(id: number, enabled = true) {
  return useQuery({
    queryKey: forumKeys.post(id),
    queryFn: async () => unwrap(await api.GET("/forum/posts/{post_id}", { params: { path: { post_id: id } } })),
    enabled: enabled && Number.isFinite(id),
    retry: false,
  });
}

export function useCourseForum(code: string, enabled = true) {
  return useQuery({
    queryKey: forumKeys.course(code),
    queryFn: async () => unwrap(await api.GET("/forum/courses/{code}", { params: { path: { code } } })),
    enabled,
    retry: false,
  });
}

export function useInstructors(q: string) {
  return useQuery({
    queryKey: ["instructors", q],
    queryFn: async () => unwrap(await api.GET("/instructors", { params: { query: { q: q || undefined, limit: 100 } } })),
    retry: false,
  });
}

export function useInstructor(slug: string, loggedIn: boolean) {
  return useQuery({
    // The answer depends on the login (ratings are added for logged-in readers).
    queryKey: ["instructor", slug, loggedIn],
    queryFn: async () => unwrap(await api.GET("/instructors/{slug}", { params: { path: { slug } } })),
    retry: false,
  });
}

export function useModerationQueue(enabled: boolean) {
  return useQuery({
    queryKey: forumKeys.queue,
    queryFn: async () => unwrap(await api.GET("/admin/moderation", { params: { query: { limit: 100 } } })),
    enabled,
    retry: false,
  });
}

/** Invalidate every forum read after a write (lists, the thread, ratings, the queue). */
function useRefresh() {
  const client = useQueryClient();
  return () => client.invalidateQueries({ queryKey: forumKeys.all });
}

export function useCreatePost(pageId: number) {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: async (body: PostCreate) =>
      unwrap(await api.POST("/forum/pages/{page_id}/posts", { params: { path: { page_id: pageId } }, body })),
    onSuccess: refresh,
  });
}

export function useUpdatePost() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: async ({ id, body }: { id: number; body: PostUpdate }) =>
      unwrap(await api.PATCH("/forum/posts/{post_id}", { params: { path: { post_id: id } }, body })),
    onSuccess: refresh,
  });
}

export function useDeletePost() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: async (id: number) => {
      const { response, error } = await api.DELETE("/forum/posts/{post_id}", { params: { path: { post_id: id } } });
      if (!response.ok) unwrap({ data: undefined, error, response });
    },
    onSuccess: refresh,
  });
}

export function useCreateComment(postId: number) {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: async (body: { body_md: string; parent_id?: number | null }) =>
      unwrap(await api.POST("/forum/posts/{post_id}/comments", { params: { path: { post_id: postId } }, body })),
    onSuccess: refresh,
  });
}

export function useVote() {
  return useMutation({
    mutationFn: async (body: { target_type: TargetType; target_id: number; value: VoteValue }) =>
      unwrap(await api.POST("/forum/votes", { body })),
  });
}

export function useReport() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: async (body: { target_type: TargetType; target_id: number; reason: string }) =>
      unwrap(await api.POST("/forum/reports", { body })),
    onSuccess: refresh,
  });
}

export function useModerationDecision() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: async ({ item, decision }: { item: ModerationItem; decision: "approve" | "remove" }) =>
      unwrap(
        await api.POST("/admin/moderation/{target_type}/{target_id}/decision", {
          params: { path: { target_type: item.target_type, target_id: item.target_id } },
          body: { decision },
        }),
      ),
    onSuccess: refresh,
  });
}
