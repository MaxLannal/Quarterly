import type { Issue } from "@/api/types";
import { NotAvailable, Notice, Spinner } from "@/components/ui/misc";
import { cn } from "@/lib/utils";
import type { VerifyState } from "./useVerify";

const ORDER = { error: 0, warning: 1, info: 2 } as const;

export function sortIssues(issues: Issue[]): Issue[] {
  return [...issues].sort((a, b) => ORDER[a.level] - ORDER[b.level]);
}

interface IssuesTabProps {
  verify: VerifyState;
  selected: Issue | null;
  onSelect: (issue: Issue | null) => void;
}

export function IssuesTab({ verify, selected, onSelect }: IssuesTabProps) {
  if (verify.status === "unavailable") {
    return <NotAvailable feature="The verifier">Your plan is kept, but it cannot be checked yet.</NotAvailable>;
  }
  const report = verify.report;
  if (!report) {
    return verify.status === "error" ? (
      <Notice tone="red" role="alert">
        {verify.error}
      </Notice>
    ) : (
      <Spinner label="Checking your plan" />
    );
  }
  const issues = sortIssues(report.issues ?? []);
  return (
    <div className="space-y-3">
      {verify.status === "error" && (
        <Notice tone="red" role="alert">
          {verify.error} Showing the last result.
        </Notice>
      )}
      {issues.length === 0 ? (
        <p className="text-sm">No issues found.</p>
      ) : (
        <ul className="space-y-2" aria-label="Verifier issues">
          {issues.map((issue, i) => {
            const isSel = selected === issue;
            return (
              <li key={`${issue.code}-${i}`}>
                <button
                  type="button"
                  aria-pressed={isSel}
                  onClick={() => onSelect(isSel ? null : issue)}
                  className={cn(
                    "w-full rounded-md border border-l-4 p-2 text-left text-sm hover:bg-muted",
                    issue.level === "error" ? "border-l-red-700" : issue.level === "warning" ? "border-l-amber-600" : "border-l-blue-700",
                    isSel && "bg-blue-50 ring-2 ring-blue-600",
                  )}
                >
                  <span className="text-xs font-semibold uppercase">
                    {issue.level} · {issue.code}
                  </span>
                  <span className="block">{issue.message}</span>
                  {(issue.fix_hints ?? []).length > 0 && (
                    <span className="mt-1 block text-xs text-muted-foreground">Try: {(issue.fix_hints ?? []).join(" ")}</span>
                  )}
                </button>
              </li>
            );
          })}
        </ul>
      )}
      {(report.assumptions ?? []).length > 0 && (
        <details className="text-sm">
          <summary className="min-h-11 cursor-pointer py-2">Assumptions ({(report.assumptions ?? []).length})</summary>
          <ul className="list-disc pl-5 text-muted-foreground">
            {(report.assumptions ?? []).map((a) => (
              <li key={a}>{a}</li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}
