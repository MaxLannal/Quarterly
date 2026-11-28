import type { Report } from "@/api/types";
import { Badge } from "@/components/ui/misc";
import type { VerifyState } from "./useVerify";

function count(report: Report, level: "error" | "warning") {
  return (report.issues ?? []).filter((i) => i.level === level).length;
}

/** "Valid" only when the server says so (`Report.status`). */
export function reportText(report: Report): string {
  if (report.status === "valid") return "Valid";
  if (report.status === "warnings") {
    const n = count(report, "warning");
    return `${n} warning${n === 1 ? "" : "s"}`;
  }
  const n = count(report, "error");
  return `${n} error${n === 1 ? "" : "s"}`;
}

export function ReportBadge({ report }: { report: Report }) {
  const tone = report.status === "valid" ? "success" : report.status === "warnings" ? "warning" : "error";
  return (
    <Badge tone={tone} casing="normal">
      {reportText(report)}
    </Badge>
  );
}

export function VerifierBadge({ verify }: { verify: VerifyState }) {
  let body;
  if (verify.status === "unavailable") body = <Badge tone="neutral" casing="normal">Verifier not available yet</Badge>;
  else if (verify.status === "verifying" || (verify.status === "idle" && !verify.report)) {
    body = verify.report ? (
      <span className="inline-flex items-center gap-2">
        <ReportBadge report={verify.report} />
        <span className="text-caption text-muted">checking…</span>
      </span>
    ) : (
      <Badge tone="neutral" casing="normal">Checking…</Badge>
    );
  } else if (verify.report) body = <ReportBadge report={verify.report} />;
  else body = <Badge tone="error" casing="normal">Verifier error</Badge>;
  return (
    <span role="status" data-testid="verifier-badge" className="inline-flex min-h-11 items-center">
      {body}
    </span>
  );
}

/**
 * The plan check's verdict beside the plan's name (PL-1, D11): "Valid", "2 warnings" or "3 errors",
 * as a button that opens the plan check. "Valid" only when the server says so.
 */
export function PlanVerdict({ verify, onOpen }: { verify: VerifyState; onOpen: () => void }) {
  const checking = verify.status === "verifying" || (verify.status === "idle" && !verify.report);
  const text = verify.report ? reportText(verify.report) : verify.status === "unavailable" ? "Not checked yet" : checking ? "Checking…" : "Check failed";
  // A small pill (planner.css): a dot in the verdict's tone, then its words.
  const tone = verify.report ? verify.report.status : verify.status === "error" ? "errors" : "neutral";
  return (
    <button
      type="button"
      onClick={onOpen}
      data-testid="plan-verdict"
      data-tone={tone}
      data-checking={checking ? "true" : undefined}
      aria-label={`Plan check: ${text}. Open the plan check`}
      className="planner-verdict"
    >
      <span aria-hidden="true" className="planner-verdict-dot" />
      {text}
      {checking && verify.report && <span className="text-caption text-muted">checking…</span>}
    </button>
  );
}
