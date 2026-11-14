import { Link, useLocation } from "react-router-dom";
import { cn } from "@/lib/utils";

const COLUMNS: { title: string; links: { to: string; label: string }[] }[] = [
  {
    title: "Plan",
    links: [
      { to: "/plan", label: "Planner" },
      { to: "/plans", label: "My plans" },
      { to: "/programs", label: "Program explorer" },
    ],
  },
  {
    title: "Read",
    links: [
      { to: "/courses", label: "Course search" },
      { to: "/instructors", label: "Instructors" },
    ],
  },
  {
    title: "Quarterly",
    links: [
      { to: "/guidelines", label: "Community guidelines" },
      { to: "/privacy", label: "Privacy" },
      { to: "/about", label: "About Quarterly" },
    ],
  },
];

/**
 * footer: canvas, body-sm in the body color, link columns, 64px top and bottom at desktop. The
 * side padding is the page gutter (16/24/32px), so the footer's left edge lines up with the top
 * bar and the page content above it (DESIGN.md's 48px would sit 16px to the right of both).
 */
export function Footer() {
  // Same width as the top bar: the planner's wider tool width (DF-2) on /plan, 1200px elsewhere.
  const wide = useLocation().pathname === "/plan";
  return (
    <footer className="border-t border-hairline bg-canvas">
      <div className={cn("mx-auto grid w-full gap-10 px-4 py-12 sm:px-6 md:grid-cols-[2fr_repeat(3,1fr)] md:py-16 lg:px-8", wide ? "max-w-tool" : "max-w-content")}>
        <div className="max-w-xs">
          <p className="font-display text-display-sm text-ink">Quarterly</p>
          <p className="mt-2 text-body-sm text-body">Plan four years of courses and read what students say about each class.</p>
        </div>
        {COLUMNS.map((col) => (
          <nav key={col.title} aria-label={`${col.title} links`}>
            <p className="text-caption-uppercase uppercase text-muted">{col.title}</p>
            <ul className="mt-2">
              {col.links.map((l) => (
                <li key={l.to}>
                  <Link to={l.to} className="inline-flex min-h-11 items-center rounded-xs text-body-sm text-body hover:text-ink hover:underline">
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
