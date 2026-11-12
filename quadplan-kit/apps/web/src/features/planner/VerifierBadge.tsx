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
  const tone = report.status === "valid" ? "green" : report.status === "warnings" ? "amber" : "red";
  return (
    <Badge tone={tone}>
      <span aria-hidden="true">{report.status === "valid" ? "✓" : report.status === "warnings" ? "⚠" : "⛔"}</span>
      {reportText(report)}
    </Badge>
  );
}

export function VerifierBadge({ verify }: { verify: VerifyState }) {
  let body;
  if (verify.status === "unavailable") body = <Badge tone="neutral">Verifier not available yet</Badge>;
  else if (verify.status === "verifying" || (verify.status === "idle" && !verify.report)) {
    body = verify.report ? (
      <span className="inline-flex items-center gap-1 opacity-70">
        <ReportBadge report={verify.report} />
        <span className="text-xs">checking…</span>
      </span>
    ) : (
      <Badge tone="neutral">Checking…</Badge>
    );
  } else if (verify.report) body = <ReportBadge report={verify.report} />;
  else body = <Badge tone="red">Verifier error</Badge>;
  return (
    <span role="status" data-testid="verifier-badge" className="inline-flex min-h-11 items-center">
      {body}
    </span>
  );
}
