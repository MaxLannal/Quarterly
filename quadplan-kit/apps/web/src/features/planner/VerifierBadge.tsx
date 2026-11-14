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
