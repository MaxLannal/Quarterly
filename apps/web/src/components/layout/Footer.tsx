import { Link } from "react-router-dom";

const LINKS = [
  { to: "/about", label: "About" },
  { to: "/privacy", label: "Privacy" },
  { to: "/guidelines", label: "Community guidelines" },
];

/** The panel's foot: the notice on every page (no University marks) and three links. 44px targets on touch (D3). */
export function Footer() {
  return (
    <footer className="mt-auto border-t border-hairline px-4 py-5 sm:px-6 lg:px-8">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-caption text-muted">
          Quarterly is a student project, not affiliated with the University of Chicago. It is not official advising.
        </p>
        <nav aria-label="Site links">
          <ul className="flex flex-wrap gap-x-5">
            {LINKS.map((l) => (
              <li key={l.to}>
                <Link to={l.to} className="inline-flex min-h-9 items-center rounded-xs text-caption text-body hover:text-ink hover:underline pointer-coarse:min-h-11">
                  {l.label}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
      </div>
    </footer>
  );
}
