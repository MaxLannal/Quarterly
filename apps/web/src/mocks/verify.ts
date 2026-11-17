/**
 * A toy verifier for MSW only, so the planner has realistic-looking reports in tests and
 * mock-mode development. It is NOT the real verifier and decides nothing in production.
 */
import type { Issue, NodeProgress, PlanState, Report } from "@/api/types";
import { compareTerms, quarterOf, termLabel } from "@/features/planner/terms";
import { findCourse, matches, offeredIn, prereqsOf, programDetail } from "./data";
import type { components } from "@/api/schema";

type Node = components["schemas"]["ProgramDetail"]["rules"];

export function mockVerify(plan: PlanState): Report {
  const issues: Issue[] = [];
  const items = (plan.items ?? []).filter((i) => i.course);
  const byTerm = new Map<string, number>();

  for (const item of items) {
    const code = item.course as string;
    byTerm.set(item.term, (byTerm.get(item.term) ?? 0) + 1);
    if (!findCourse(code)) {
      issues.push({ code: "V01", level: "error", message: `${code} is not in the ${plan.catalog_year} catalog.`, course_ids: [code], term_ids: [item.term] });
      continue;
    }
    for (const pre of prereqsOf(code)) {
      // As the real verifier: an earlier quarter, or the same Summer quarter (summer sessions).
      const sameSummer = (t: string) => t === item.term && item.term.endsWith("-SU");
      const done = items.some((o) => o.course === pre && (compareTerms(o.term, item.term) < 0 || sameSummer(o.term)));
      if (!done) {
        issues.push({
          code: "V03",
          level: "error",
          message: `Prerequisite of ${code} in ${item.term} is not met: ${pre} is not in an earlier quarter. Requirement: ${pre}.`,
          course_ids: [code],
          term_ids: [item.term],
          fix_hints: [`Add ${pre} before ${termLabel(item.term)}.`],
        });
      }
    }
    if (item.status === "planned" && !offeredIn(code, quarterOf(item.term))) {
      issues.push({
        code: "V04",
        level: "warning",
        message: `${code} is not usually offered in ${termLabel(item.term).split(" ")[0]}.`,
        course_ids: [code],
        term_ids: [item.term],
      });
    }
  }
  for (const [term, n] of byTerm) {
    if (n > 4) {
      issues.push({ code: "V05", level: "warning", message: `${termLabel(term)} has ${n} courses; more than 4 needs a reason.`, term_ids: [term], course_ids: [] });
    }
  }

  const progress: NodeProgress[] = [];
  for (const pp of plan.programs ?? []) {
    const program = programDetail(pp.program_id);
    if (!program) continue;
    const used = new Set<string>();
    const codes = items.map((i) => i.course as string);
    const walk = (path: string, node: Node): boolean => {
      let have = 0;
      let need = 1;
      let taken: string[] = [];
      if (node.kind === "group") {
        const results = node.children.map((child, i) => walk(`${path}/${child.id ?? i + 1}`, child));
        need = node.all ? results.length : (node.n_of ?? 1);
        have = results.filter(Boolean).length;
      } else if (node.kind === "select") {
        need = node.count ?? 1;
        taken = codes.filter((c) => !used.has(c) && matches(c, node.from)).slice(0, need);
        have = taken.length;
      } else if (node.kind === "slot") {
        taken = codes.filter((c) => !used.has(c) && node.any_of.includes(c)).slice(0, 1);
        have = taken.length;
      } else {
        need = node.total.courses ?? 0;
        for (const part of node.parts) {
          const t = codes.filter((c) => !used.has(c) && matches(c, part.from)).slice(0, part.count[1]);
          t.forEach((c) => used.add(c));
          progress.push({
            node_id: `${path}/${part.id}`,
            program_id: program.id,
            label: part.label ?? part.id,
            have: t.length,
            need: part.count[0],
            satisfied: t.length >= part.count[0],
            unit: "courses",
            courses: t,
          });
          taken.push(...t);
        }
        have = Math.min(taken.length, need);
      }
      taken.forEach((c) => used.add(c));
      const satisfied = have >= need;
      progress.push({ node_id: path, program_id: program.id, label: node.label ?? null, have, need, satisfied, unit: "courses", courses: taken });
      if (!satisfied && node.kind !== "group") {
        issues.push({
          code: "V07",
          level: "error",
          message: `${program.name}: ${node.label ?? path} needs ${need - have} more course${need - have === 1 ? "" : "s"}.`,
          node_id: path,
          course_ids: [],
          term_ids: [],
        });
      }
      return satisfied;
    };
    walk(program.id, program.rules);
  }

  const errors = issues.filter((i) => i.level === "error").length;
  const warnings = issues.filter((i) => i.level === "warning").length;
  return {
    status: errors ? "errors" : warnings ? "warnings" : "valid",
    issues,
    progress,
    assumptions: ["Mock verifier: results are fake."],
    plan_hash: `mock-${items.length}`,
    core_version: "mock",
    certificate: null,
  };
}
