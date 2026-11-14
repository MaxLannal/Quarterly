import type { Issue } from "@/api/types";
import { EmptyState } from "@/components/layout/page";
import { ErrorIcon, InfoIcon, WarningIcon } from "@/components/ui/icons";
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
      <Notice tone="error" role="alert">
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
        <Notice tone="error" role="alert">
          {verify.error} Showing the last result.
        </Notice>
      )}
      {issues.length === 0 ? (
        <EmptyState>No issues found.</EmptyState>
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
                    "w-full cursor-pointer rounded-lg border border-l-[3px] border-hairline bg-surface-card p-3 text-left text-body-sm text-ink transition-colors hover:bg-canvas-soft focus-visible:outline-offset-0",
                    issue.level === "error" ? "border-l-error" : issue.level === "warning" ? "border-l-warning-icon" : "border-l-info",
                    isSel && "border-primary bg-primary-wash hover:bg-primary-wash",
                  )}
                >
                  <span
                    className={cn(
                      "flex items-center gap-1.5 text-caption-uppercase uppercase",
                      issue.level === "error" ? "text-error" : issue.level === "warning" ? "text-warning" : "text-info",
                    )}
                  >
                    {issue.level === "error" ? <ErrorIcon size={14} /> : issue.level === "warning" ? <WarningIcon size={14} className="text-warning-icon" /> : <InfoIcon size={14} />}
                    {issue.level} · {issue.code}
                  </span>
                  <span className="mt-1 block">{issue.message}</span>
                  {(issue.fix_hints ?? []).length > 0 && (
                    <span className="mt-1 block text-caption text-muted">Try: {(issue.fix_hints ?? []).join(" ")}</span>
                  )}
                </button>
              </li>
            );
          })}
        </ul>
      )}
      {(report.assumptions ?? []).length > 0 && (
        <details className="text-body-sm">
          <summary className="flex min-h-11 cursor-pointer items-center rounded-md text-body-strong">Assumptions ({(report.assumptions ?? []).length})</summary>
          <ul className="list-disc space-y-1 pl-5 text-muted marker:text-gray-dark">
            {(report.assumptions ?? []).map((a) => (
              <li key={a}>{a}</li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}
