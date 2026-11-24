/**
 * The dashboard's data (docs/BEST-OF-UCHICAGO-PLAN.md): the profile (`/me/profile`), the
 * interviewing guide (`/agents/interview`) and what's new (`/me/updates`). Profile edits are
 * optimistic: the cache changes at once and rolls back if the server refuses. (The routes went in
 * issue #15.)
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError, NotAvailableError, unwrap } from "@/api/client";
import type { components } from "@/api/schema";
import { checkStream, readSse } from "@/api/sse";

type S = components["schemas"];
export type Profile = S["ProfileOut"];
export type ProfilePatch = S["ProfilePatch"];
export type Topic = S["InterviewTurnEvent"]["topic"];
export type InterviewTurn = S["InterviewTurn"];
export type InterviewRequest = S["InterviewRequest"];
export type InterviewEvent = S["InterviewEvent"];
export type TurnEvent = S["InterviewTurnEvent"];
export type StepEvent = S["DashboardStepEvent"];
export type ProgramRef = S["ProgramRef"];
export type UpdatesOut = S["UpdatesOut"];

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

/** Applies a patch to a profile the way the server will (lists replace, null clears). */
export function patched(profile: Profile, patch: ProfilePatch): Profile {
  const next: Profile = { ...profile };
  for (const [key, value] of Object.entries(patch) as [keyof ProfilePatch, unknown][]) {
    if (value === undefined) continue;
    if (key === "interview") {
      const memory = value as S["InterviewMemoryPatch"] | null;
      next.interview = memory
        ? { covered: memory.covered ?? profile.interview.covered, turns: memory.turns ?? profile.interview.turns }
        : { covered: [], turns: [] };
      continue;
    }
    if (key === "portrait") {
      next.portrait = (value as Profile["portrait"] | null) ?? { headline: "", summary: "", themes: [] };
      continue;
    }
    if (key === "follows") {
      next.follows = (value as Profile["follows"] | null) ?? { threads: [], courses: [] };
      continue;
    }
    const empty = Array.isArray(profile[key as keyof Profile]) ? [] : null;
    (next as Record<string, unknown>)[key] = value ?? empty;
  }
  return next;
}

/**
 * PATCH /me/profile, optimistic. `onSaved` runs when the server confirmed; on failure the cache
 * goes back to what it was and the error is returned for the page to show.
 */
export function usePatchProfile() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (patch: ProfilePatch) => unwrap(await api.PATCH("/me/profile", { body: patch })),
    onMutate: async (patch) => {
      await client.cancelQueries({ queryKey: PROFILE_KEY });
      const before = client.getQueryData<Profile>(PROFILE_KEY);
      if (before) client.setQueryData<Profile>(PROFILE_KEY, patched(before, patch));
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

export async function* streamInterview(body: InterviewRequest, signal?: AbortSignal): AsyncGenerator<InterviewEvent> {
  const { data, response } = await api.POST("/agents/interview", { body, parseAs: "stream", signal });
  yield* readSse<InterviewEvent>(checkStream(response, data));
}

/** What's new for the student (`GET /me/updates`); a missing endpoint is just empty. */
export function useDashboardUpdates(enabled: boolean) {
  return useQuery({
    queryKey: ["me", "updates", "dashboard"],
    queryFn: async () => {
      const result = await api.GET("/me/updates");
      if (result.response.status === 404 || result.response.status === 501) return null;
      return unwrap(result);
    },
    enabled,
    staleTime: 60_000,
    retry: false,
  });
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
