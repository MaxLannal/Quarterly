import { Link } from "react-router-dom";

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

/** footer: canvas, body-sm in the body color, link columns, 64x48px padding at desktop. */
export function Footer() {
  return (
    <footer className="border-t border-hairline bg-canvas">
      <div className="mx-auto grid w-full max-w-content gap-10 px-4 py-12 sm:px-6 md:grid-cols-[2fr_repeat(3,1fr)] md:px-12 md:py-16">
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
