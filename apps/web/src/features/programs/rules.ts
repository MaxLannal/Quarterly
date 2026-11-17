/**
 * Program rule trees: node paths (same scheme as `planner_core.dsl.iter_nodes`) and plain-English
 * descriptions. Nothing here decides satisfaction; that is the verifier's `Report.progress`.
 */
import type { NodeProgress, Part, RuleNode, Selector } from "@/api/types";

export interface RuleEntry {
  path: string;
  node: RuleNode | null;
  part: Part | null;
  depth: number;
  label: string;
  children: RuleEntry[];
  /** True for nodes that pick courses (select, slot, part): clicking lists eligible courses. */
  selectable: boolean;
}

function nodeId(node: { id?: string | null }, index: number): string {
  return node.id ?? String(index + 1);
}

/** Build the display tree. The root's path is the program id; children add `/<id>`. */
export function ruleTree(programId: string, root: RuleNode): RuleEntry {
  function walk(path: string, node: RuleNode, depth: number): RuleEntry {
    const children: RuleEntry[] = [];
    if (node.kind === "group") {
      node.children.forEach((child, i) => children.push(walk(`${path}/${nodeId(child, i)}`, child, depth + 1)));
    } else if (node.kind === "bounded_parts") {
      node.parts.forEach((part) =>
        children.push({
          path: `${path}/${part.id}`,
          node: null,
          part,
          depth: depth + 1,
          label: part.label ?? part.id,
          children: [],
          selectable: true,
        }),
      );
    }
    return {
      path,
      node,
      part: null,
      depth,
      label: node.label ?? (depth === 0 ? "All requirements" : (node.id ?? path.split("/").pop() ?? path)),
      children,
      selectable: node.kind === "select" || node.kind === "slot",
    };
  }
  return walk(programId, root, 0);
}

export function flatten(entry: RuleEntry): RuleEntry[] {
  return [entry, ...entry.children.flatMap(flatten)];
}

export function selectorText(sel: Selector): string {
  const bits: string[] = [];
  if (sel.codes?.length) bits.push(sel.codes.join(", "));
  if (sel.subject) bits.push(`${sel.subject} courses`);
  if (sel.number_range) bits.push(`numbered ${sel.number_range[0]}–${sel.number_range[1]}`);
  if (sel.tags?.length) bits.push(`tagged ${sel.tags.join(" or ")}`);
  if (sel.list) bits.push(`from the list "${sel.list}"`);
  if (sel.union?.length) bits.push(`any of (${sel.union.map(selectorText).join("; ")})`);
  let text = bits.join(" ") || "any course";
  if (sel.exclude?.length) text += `, excluding ${sel.exclude.join(", ")}`;
  return text;
}

function countText(n: number | null | undefined, units: number | null | undefined): string {
  if (units) return `${units} units`;
  const c = n ?? 1;
  return `${c} course${c === 1 ? "" : "s"}`;
}

/** One line of plain English for a node or part. */
export function describe(entry: RuleEntry): string {
  if (entry.part) {
    const [lo, hi] = entry.part.count;
    const range = lo === hi ? `${lo}` : `${lo} to ${hi}`;
    return `${range} course${hi === 1 ? "" : "s"} from ${selectorText(entry.part.from)}`;
  }
  const node = entry.node;
  if (!node) return "";
  switch (node.kind) {
    case "group":
      return node.all ? "All of the following" : `${node.n_of ?? 1} of the following`;
    case "select":
      return `${countText(node.count, node.units)} from ${selectorText(node.from)}`;
    case "slot":
      return node.any_of.length === 1 ? `${node.any_of[0]}` : `One of ${node.any_of.join(", ")}`;
    case "bounded_parts": {
      const t = node.total;
      const total = t.units ? `${t.units} units` : `${t.courses ?? 0} courses`;
      return `${total} in total, from these parts`;
    }
  }
}

export function progressByNode(progress: NodeProgress[] | undefined): Map<string, NodeProgress> {
  return new Map((progress ?? []).map((p) => [p.node_id, p]));
}
