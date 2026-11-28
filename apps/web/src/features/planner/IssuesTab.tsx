import type { Issue } from "@/api/types";
import { Link } from "react-router-dom";
import { EmptyState, inlineLinkClass } from "@/components/layout/page";
import { ErrorIcon, InfoIcon, WarningIcon } from "@/components/ui/icons";
import { NotAvailable, Notice, Spinner } from "@/components/ui/misc";
import { cn } from "@/lib/utils";
import type { VerifyState } from "./useVerify";
import { hasDetails, summarizeIssue } from "./issueText";
import { VerifierBadge } from "./VerifierBadge";

const ORDER = { error: 0, warning: 1, info: 2 } as const;

export function sortIssues(issues: Issue[]): Issue[] {
  return [...issues].sort((a, b) => ORDER[a.level] - ORDER[b.level]);
}

interface IssuesTabProps {
  verify: VerifyState;
  selected: Issue | null;
  onSelect: (issue: Issue | null) => void;
}

/** The plan check: the verifier's status, then its issues. Opened from "Check plan" (FEEDBACK F4). */
export function IssuesTab(props: IssuesTabProps) {
  return (
    <div className="space-y-4">
      <div className="flex items-end justify-between gap-2">
        <div>
          <span className="planner-label">Verifier</span>
          <h3 className="font-display text-title-md font-normal leading-tight">Plan check</h3>
        </div>
        <VerifierBadge verify={props.verify} />
      </div>
      <IssuesList {...props} />
    </div>
  );
}

function IssuesList({ verify, selected, onSelect }: IssuesTabProps) {
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
        <ul className="space-y-2.5" aria-label="Verifier issues">
          {issues.map((issue, i) => {
            const isSel = selected === issue;
            const short = summarizeIssue(issue);
            return (
              <li
                key={`${issue.code}-${i}`}
                className={cn(
                  // PL-5 (D11): no coloured strip; the icon and level label carry the severity.
                  "animate-rise rounded-[18px] bg-canvas-soft text-body-sm text-ink  transition-[background-color,box-shadow] duration-300",
                  isSel && "bg-primary-wash ",
                )}
                style={{ animationDelay: `${Math.min(i, 8) * 30}ms` }}
              >
                <button
                  type="button"
                  aria-pressed={isSel}
                  onClick={() => onSelect(isSel ? null : issue)}
                  className="w-full cursor-pointer rounded-[18px] px-4 pb-2 pt-3 text-left transition-colors duration-300 hover:bg-canvas-soft focus-visible:outline-offset-0"
                >
                  <span
                    className={cn(
                      "text-[12px] font-semibold flex items-center gap-1.5",
                      issue.level === "error" ? "text-error" : issue.level === "warning" ? "text-warning" : "text-info",
                    )}
                  >
                    {issue.level === "error" ? <ErrorIcon size={14} /> : issue.level === "warning" ? <WarningIcon size={14} className="text-warning-icon" /> : <InfoIcon size={14} />}
                    {issue.level}
                  </span>
                  <span className="mt-1 block">{short.list}</span>
                </button>
                {(short.link || hasDetails(issue)) && (
                  <div className="flex flex-wrap items-baseline gap-x-3 px-4 pb-2 text-caption">
                    {short.link && (
                      <Link to={short.link.href} className={cn(inlineLinkClass, "inline-flex min-h-11 items-center")}>
                        {short.link.label}
                      </Link>
                    )}
                    {hasDetails(issue) && (
                      <details className="min-w-0 basis-full sm:basis-auto">
                        <summary className="inline-flex min-h-11 cursor-pointer items-center text-muted hover:text-ink">Details</summary>
                        <p className="text-body-sm text-body">{issue.message}</p>
                        {(issue.fix_hints ?? []).length > 0 && <p className="mt-1 text-muted">Try: {(issue.fix_hints ?? []).join(" ")}</p>}
                      </details>
                    )}
                  </div>
                )}
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
