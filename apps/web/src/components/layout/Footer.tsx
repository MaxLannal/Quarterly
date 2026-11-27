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
  // Same width as the top bar: the planner's wider tool width (DF-2) on /plan, the content width elsewhere.
  const wide = useLocation().pathname === "/plan";
  return (
    <footer className="relative overflow-hidden text-on-night">
      <div
        className={cn(
          "mx-auto grid w-full grid-cols-2 gap-x-6 gap-y-10 px-5 pb-6 pt-16 sm:px-8 md:grid-cols-[2fr_repeat(4,1fr)] md:gap-10 md:pt-24 lg:px-10",
          wide ? "max-w-tool" : "max-w-content",
        )}
      >
        <div className="col-span-2 max-w-sm md:col-span-1">
          <p className="mono-label flex items-center gap-2 text-on-night-muted">
            <span aria-hidden="true" className="inline-block size-1.5 rounded-pill bg-primary shadow-[0_0_10px_2px_rgb(255_92_112/0.7)]" />
            A student project
          </p>
          <p className="mt-4 text-body-sm text-on-night-soft">
            Quarterly is a student project, not affiliated with the University
            of Chicago. It is not official advising.
          </p>
        </div>
        {COLUMNS.map((col) => (
          <nav key={col.title} aria-label={`${col.title} links`}>
            <p className="mono-label text-on-night-muted">{col.title}</p>
            <ul className="mt-4 flex flex-col">
              {col.links.map((l) => (
                <li key={l.to}>
                  <Link
                    to={l.to}
                    className="group inline-flex min-h-9 items-center rounded-xs text-body-sm text-on-night-soft transition-colors duration-300 hover:text-on-night pointer-coarse:min-h-11"
                  >
                    <span aria-hidden="true" className="h-px w-0 bg-primary transition-[width,margin] duration-300 group-hover:mr-2 group-hover:w-3" />
                    {l.label}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>
        ))}
      </div>
      {/* The wordmark as a horizon: huge, lit from above, sinking into the night (decorative). */}
      <div aria-hidden="true" className={cn("footer-horizon mx-auto w-full px-3 sm:px-6", wide ? "max-w-tool" : "max-w-content")}>
        <span className="footer-horizon-word">Quarterly</span>
      </div>
    </footer>
  );
}
