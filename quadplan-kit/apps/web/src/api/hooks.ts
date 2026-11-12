import { useQueries, useQuery } from "@tanstack/react-query";
import { api, unwrap } from "./client";
import type { CourseDetail, CourseSummary, ProgramDetail } from "./types";

const STATIC = { staleTime: 5 * 60_000, retry: false } as const;

export function useCatalogYears() {
  return useQuery({
    queryKey: ["catalog-years"],
    queryFn: async () => unwrap(await api.GET("/catalog-years")),
    ...STATIC,
  });
}

export function useTerms(catalogYear: string | undefined) {
  return useQuery({
    queryKey: ["terms", catalogYear],
    queryFn: async () =>
      unwrap(await api.GET("/terms", { params: { query: { catalog_year: catalogYear } } })),
    ...STATIC,
  });
}

export interface CourseSearchParams {
  q?: string;
  subject?: string;
  level?: number;
  quarter?: "AU" | "WI" | "SP" | "SU";
  core_tag?: string;
  max_workload_hours?: number;
  max_difficulty?: number;
  catalog_year?: string;
  limit?: number;
  offset?: number;
}

export function useCourseSearch(params: CourseSearchParams, enabled = true) {
  return useQuery({
    queryKey: ["courses", params],
    queryFn: async () => unwrap(await api.GET("/courses", { params: { query: params } })),
    enabled,
    ...STATIC,
  });
}

async function fetchCourse(code: string, catalogYear?: string): Promise<CourseDetail> {
  return unwrap(
    await api.GET("/courses/{code}", {
      params: { path: { code }, query: { catalog_year: catalogYear } },
    }),
  );
}

export function useCourse(code: string | undefined, catalogYear?: string) {
  return useQuery({
    queryKey: ["course", code, catalogYear],
    queryFn: () => fetchCourse(code ?? "", catalogYear),
    enabled: Boolean(code),
    ...STATIC,
  });
}

/** Details for every course on the plan, keyed by code. Missing or failed ones are absent. */
export function useCourseMap(codes: string[], catalogYear?: string): Map<string, CourseDetail> {
  const unique = [...new Set(codes)].sort();
  const results = useQueries({
    queries: unique.map((code) => ({
      queryKey: ["course", code, catalogYear],
      queryFn: () => fetchCourse(code, catalogYear),
      ...STATIC,
    })),
  });
  const map = new Map<string, CourseDetail>();
  results.forEach((r) => {
    if (r.data) map.set(r.data.code, r.data);
  });
  return map;
}

export function usePrograms(catalogYear?: string) {
  return useQuery({
    queryKey: ["programs", catalogYear],
    queryFn: async () =>
      unwrap(await api.GET("/programs", { params: { query: { catalog_year: catalogYear } } })),
    ...STATIC,
  });
}

// openapi-fetch widens tuples (e.g. `number_range`) to arrays; narrow back to the schema type.
async function fetchProgram(id: string, catalogYear?: string): Promise<ProgramDetail> {
  return unwrap(
    await api.GET("/programs/{program_id}", {
      params: { path: { program_id: id }, query: { catalog_year: catalogYear } },
    }),
  ) as ProgramDetail;
}

export function useProgram(id: string | undefined, catalogYear?: string) {
  return useQuery({
    queryKey: ["program", id, catalogYear],
    queryFn: () => fetchProgram(id ?? "", catalogYear),
    enabled: Boolean(id),
    ...STATIC,
  });
}

export function usePlanPrograms(ids: string[], catalogYear?: string) {
  return useQueries({
    queries: ids.map((id) => ({
      queryKey: ["program", id, catalogYear],
      queryFn: () => fetchProgram(id, catalogYear),
      ...STATIC,
    })),
  });
}

export function useEligible(programId: string | undefined, node: string | undefined, catalogYear?: string) {
  return useQuery({
    queryKey: ["eligible", programId, node, catalogYear],
    queryFn: async (): Promise<CourseSummary[]> =>
      unwrap(
        await api.GET("/programs/{program_id}/eligible", {
          params: {
            path: { program_id: programId ?? "" },
            query: { node: node ?? "", catalog_year: catalogYear },
          },
        }),
      ),
    enabled: Boolean(programId && node),
    ...STATIC,
  });
}
