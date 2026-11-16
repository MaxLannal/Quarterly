import { Link } from "react-router-dom";
import { cn } from "@/lib/utils";

/**
 * Courses and programs share one menu item, "Catalog"; this switch moves between them
 * (FEEDBACK "Course Search and Programs GUI", 2026-11-16).
 */
export function CatalogToggle({ current }: { current: "courses" | "programs" }) {
  const item = (key: "courses" | "programs", to: string, label: string) => (
    <Link
      to={to}
      aria-current={current === key ? "page" : undefined}
      className={cn(
        "inline-flex min-h-11 items-center rounded-pill px-5 text-body-sm font-medium transition-colors",
        current === key ? "bg-ink text-canvas" : "text-body hover:bg-canvas-soft hover:text-ink",
      )}
    >
      {label}
    </Link>
  );
  return (
    <nav aria-label="Courses or programs" className="inline-flex gap-1 rounded-pill border border-hairline-strong bg-surface-card p-1">
      {item("courses", "/courses", "Courses")}
      {item("programs", "/programs", "Programs")}
    </nav>
  );
}
