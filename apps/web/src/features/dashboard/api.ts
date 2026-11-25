/**
 * The dashboard's data (Issue #16): the student record (`/me/profile`), its Markdown export
 * (`/me/profile/export.md`) and the dashboard agent (`/agents/interview`). Record edits are
 * optimistic: the cache changes at once and rolls back if the server refuses. (The routes went in
 * issue #15, the "What's new" card in issue #16.)
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError, NotAvailableError, unwrap } from "@/api/client";
import type { components } from "@/api/schema";
import { checkStream, readSse } from "@/api/sse";
import { completenessOf, QUESTIONS_KEY, type QuestionSet } from "@/features/profile/questions";

type S = components["schemas"];
export type Profile = S["ProfileOut"];
export type ProfilePatch = S["ProfilePatch"];
export type InterviewTurn = S["InterviewTurn"];
export type InterviewRequest = S["InterviewRequest"];
export type InterviewEvent = S["InterviewEvent"];
export type TurnEvent = S["InterviewTurnEvent"];
export type StepEvent = S["DashboardStepEvent"];
export type ProgramRef = S["ProgramRef"];

export const PROFILE_KEY = ["me", "profile"] as const;

export function useProfile(enabled: boolean) {
  return useQuery({
    queryKey: PROFILE_KEY,
    queryFn: async () => unwrap(await api.GET("/me/profile")),
    enabled,
    staleTime: 30_000,
    retry: false,
  });
}

/**
 * Applies a patch to a profile the way the server will: lists replace, null clears, and the
 * ids of answered questions follow (a question's id is its field's name in the question file).
 */
export function patched(profile: Profile, patch: ProfilePatch): Profile {
  const next: Profile = { ...profile };
  const answered = new Set(profile.answered);
  for (const [key, value] of Object.entries(patch) as [keyof ProfilePatch, unknown][]) {
    if (value === undefined) continue;
    if (key === "interview") {
      const memory = value as S["InterviewMemoryPatch"] | null;
      next.interview = memory
        ? { covered: memory.covered ?? profile.interview.covered, turns: memory.turns ?? profile.interview.turns }
        : { covered: [], turns: [] };
      continue;
    }
    if (key === "follows") {
      next.follows = (value as Profile["follows"] | null) ?? { threads: [], courses: [] };
      continue;
    }
    if (key === "working_notes") {
      next.has_working_notes = !!value;
      continue;
    }
    if (key === "taken_courses") {
      // The server adds each course's title; keep the ones the page already knows.
      const titles = new Map(profile.taken_courses.map((c) => [c.course, c.title]));
      next.taken_courses = ((value as S["TakenCourse"][] | null) ?? []).map((c) => ({ ...c, title: titles.get(c.course) ?? "" }));
    } else if (key === "intended_programs") {
      const names = new Map(profile.programs.map((p) => [p.id, p.name]));
      const ids = (value as string[] | null) ?? [];
      next.intended_programs = ids;
      next.programs = ids.map((id) => ({ id, name: names.get(id) ?? id }));
    } else {
      const empty = Array.isArray(profile[key as keyof Profile]) ? [] : null;
      (next as Record<string, unknown>)[key] = value ?? empty;
    }
    const now = (next as Record<string, unknown>)[key];
    const counts = key === "terms_away" || key === "class_formats" ? now != null : Array.isArray(now) ? now.length > 0 : now != null;
    if (counts) answered.add(key);
    else answered.delete(key);
  }
  next.answered = [...answered];
  return next;
}

/**
 * PATCH /me/profile, optimistic. On failure the cache goes back to what it was and the error is
 * returned for the page to show.
 */
export function usePatchProfile() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (patch: ProfilePatch) => unwrap(await api.PATCH("/me/profile", { body: patch })),
    onMutate: async (patch) => {
      await client.cancelQueries({ queryKey: PROFILE_KEY });
      const before = client.getQueryData<Profile>(PROFILE_KEY);
      if (before) {
        const next = patched(before, patch);
        next.completeness = completenessOf(client.getQueryData<QuestionSet>(QUESTIONS_KEY), next);
        client.setQueryData<Profile>(PROFILE_KEY, next);
      }
      return { before };
    },
    onError: (_error, _patch, context) => {
      if (context?.before) client.setQueryData(PROFILE_KEY, context.before);
    },
    onSuccess: (profile) => {
      client.setQueryData(PROFILE_KEY, profile);
    },
  });
}

/** Downloads `student.md` (GET /me/profile/export.md) through the browser's save dialog. */
export async function downloadStudentMd(): Promise<void> {
  const { data, response } = await api.GET("/me/profile/export.md", { parseAs: "blob" });
  if (response.status === 501) throw new NotAvailableError();
  if (!response.ok || !data) throw new ApiError(response.status, `Request failed (${response.status})`);
  const url = URL.createObjectURL(data instanceof Blob ? data : new Blob([String(data)], { type: "text/markdown" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = "student.md";
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export async function* streamInterview(body: InterviewRequest, signal?: AbortSignal): AsyncGenerator<InterviewEvent> {
  const { data, response } = await api.POST("/agents/interview", { body, parseAs: "stream", signal });
  yield* readSse<InterviewEvent>(checkStream(response, data));
}

/** What to tell the student when a request failed. */
export function errorText(error: unknown, what = "That"): string {
  if (error instanceof ApiError) {
    if (error.status === 401) return "Your session ended. Log in again to keep going.";
    if (error.status === 409) return error.message;
    if (error.status === 422) return `${what} could not be saved: ${error.message.slice(0, 160)}`;
    if (error.status === 429) return "That's a lot for one day. Try again later.";
    if (error.status >= 500) return "Something went wrong on our side. Try again.";
  }
  if (error instanceof NotAvailableError) return "This is not available yet.";
  if (error instanceof TypeError) return "You seem to be offline. Check your connection.";
  return "Something went wrong. Try again.";
}
