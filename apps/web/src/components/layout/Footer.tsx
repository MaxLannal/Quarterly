import { Link, useLocation } from "react-router-dom";
import { cn } from "@/lib/utils";

// The same sections as the top bar (D11 C-1): Plan, Catalog, Forum, and the site itself.
const COLUMNS: { title: string; links: { to: string; label: string }[] }[] = [
  {
    title: "Plan",
    links: [
      { to: "/plan", label: "Planner" },
      { to: "/plans", label: "My plans" },
      { to: "/me", label: "Your dashboard" },
    ],
  },
  {
    title: "Catalog",
    links: [
      { to: "/courses", label: "Course search" },
      { to: "/programs", label: "Program explorer" },
      { to: "/feed", label: "The feed" },
    ],
  },
  {
    title: "Forum",
    links: [
      { to: "/forum", label: "Questions" },
      { to: "/instructors", label: "Course reviews" },
      { to: "/guidelines", label: "Community guidelines" },
    ],
  },
  {
    title: "Quarterly",
    links: [
      { to: "/ask", label: "Ask Quarterly" },
      { to: "/about", label: "About Quarterly" },
      { to: "/privacy", label: "Privacy" },
    ],
  },
];

/**
 * Compact link rows (D3, FEEDBACK "Minor design changes"): 32px with a mouse, 44px targets on touch
 * screens (`pointer-coarse`); on a phone the link columns sit two across.
 *
 * footer: canvas, body-sm in the body color, link columns, 64px top and bottom at desktop. The
 * side padding is the page gutter (16/24/32px), so the footer's left edge lines up with the top
 * bar and the page content above it (DESIGN.md's 48px would sit 16px to the right of both).
 */
export function Footer() {
  // Same width as the top bar: the planner's wider tool width (DF-2) on /plan, 1200px elsewhere.
  const wide = useLocation().pathname === "/plan";
  return (
    <footer className="border-t border-hairline bg-canvas">
      <div
        className={cn(
          "mx-auto grid w-full grid-cols-2 gap-x-6 gap-y-8 px-4 py-10 sm:px-6 md:grid-cols-[2fr_repeat(4,1fr)] md:gap-10 md:py-12 lg:px-8",
          wide ? "max-w-tool" : "max-w-content",
        )}
      >
        <div className="col-span-2 max-w-xs md:col-span-1">
          <p className="font-display text-display-sm font-medium tracking-[-0.24px] text-ink">Quarterly</p>
          <p className="mt-2 text-body-sm text-body">
            Quarterly is a student project, not affiliated with the University
            of Chicago. It is not official advising.
          </p>
        </div>
        {COLUMNS.map((col) => (
          <nav key={col.title} aria-label={`${col.title} links`}>
            <p className="text-caption-uppercase uppercase text-muted">
              {col.title}
            </p>
            <ul className="mt-3 flex flex-col">
              {col.links.map((l) => (
                <li key={l.to}>
                  <Link
                    to={l.to}
                    className="inline-flex min-h-8 items-center rounded-xs text-body-sm text-body hover:text-ink hover:underline pointer-coarse:min-h-11"
                  >
                    {l.label}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>
        ))}
      </div>
    </footer>
  );
}
