import { useEffect, useId, useState, type FormEvent } from "react";
import { Link, NavLink, useLocation, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Avatar } from "@/components/ui/card";
import { CloseIcon, MenuIcon, SearchIcon } from "@/components/ui/icons";
import { useSession } from "@/lib/session";
import { cn } from "@/lib/utils";

const NAV = [
  { to: "/plan", label: "Plan" },
  { to: "/courses", label: "Courses" },
  { to: "/programs", label: "Programs" },
  { to: "/instructors", label: "Forum" },
];

/** The text wordmark (DESIGN.md "Brand & logo": no university marks). */
export function Wordmark({ className }: { className?: string }) {
  return (
    <Link to="/" className={cn("flex min-h-11 shrink-0 items-center rounded-xs font-display text-display-sm text-ink", className)}>
      Quarterly
    </Link>
  );
}

function SearchBox() {
  const navigate = useNavigate();
  const [q, setQ] = useState("");
  function submit(e: FormEvent) {
    e.preventDefault();
    const term = q.trim();
    navigate(term ? `/courses?q=${encodeURIComponent(term)}` : "/courses");
  }
  return (
    <form role="search" onSubmit={submit} className="relative flex w-full min-w-0 items-center">
      <label htmlFor="site-search" className="sr-only">
        Search courses
      </label>
      <input
        id="site-search"
        type="search"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="Search courses"
        className={cn(
          "min-h-11 w-full min-w-0 rounded-pill border border-hairline-strong bg-surface-card pl-4 pr-12 text-body-sm text-ink placeholder:text-muted",
          "focus-visible:outline-none focus:border-primary focus:shadow-[inset_0_0_0_1px_var(--color-primary)]",
        )}
      />
      <Button type="submit" variant="ghost" size="icon" aria-label="Search" className="absolute right-0 text-muted hover:text-ink">
        <SearchIcon />
      </Button>
    </form>
  );
}

function NavLinks({ vertical = false }: { vertical?: boolean }) {
  return (
    <>
      {NAV.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          className={({ isActive }) =>
            cn(
              "flex min-h-11 items-center rounded-pill px-4 text-nav-link text-ink transition-colors hover:bg-surface-strong",
              vertical && "w-full md:w-auto",
              isActive && "bg-primary-wash hover:bg-primary-wash",
            )
          }
        >
          {item.label}
        </NavLink>
      ))}
    </>
  );
}

/**
 * top-nav: canvas, 64px. Wordmark left, links next to it, search + account right. Below 768px the
 * links fold behind a Menu button; the search stays visible on its own row.
 */
export function TopNav() {
  const { data: session } = useSession();
  const [open, setOpen] = useState(false);
  const location = useLocation();
  const panelId = useId();

  useEffect(() => setOpen(false), [location.pathname]);

  const account = session ? (
    <Link to="/account" className="flex min-h-11 items-center gap-2 rounded-pill pl-1 pr-3 text-nav-link text-ink hover:bg-surface-strong">
      <Avatar name={session.account.username} />
      {session.account.username}
    </Link>
  ) : (
    <Button asChild variant="outline">
      <Link to="/login">Log in</Link>
    </Button>
  );

  return (
    <header className="border-b border-hairline bg-canvas">
      <div className="mx-auto flex w-full max-w-tool flex-wrap items-center gap-x-2 px-4 sm:px-6 md:h-16 md:flex-nowrap lg:px-8">
        <Wordmark className="mr-2 h-16 md:h-auto" />
        <nav
          id={panelId}
          aria-label="Main"
          className={cn(
            "items-center gap-1 md:flex",
            open ? "order-last mb-3 flex w-full flex-col items-stretch border-t border-hairline pt-3 md:order-none md:mb-0 md:w-auto md:flex-row md:items-center md:border-0 md:pt-0" : "hidden",
          )}
        >
          <NavLinks vertical={open} />
        </nav>
        <div className="order-1 w-full pb-3 md:order-none md:ml-auto md:w-auto md:max-w-sm md:flex-1 md:pb-0">
          <SearchBox />
        </div>
        <div className="ml-auto flex items-center gap-1 md:ml-2">
          {account}
          <Button
            variant="ghost"
            size="icon"
            className="md:hidden"
            aria-expanded={open}
            aria-controls={panelId}
            aria-label="Menu"
            onClick={() => setOpen(!open)}
          >
            {open ? <CloseIcon size={20} /> : <MenuIcon size={20} />}
          </Button>
        </div>
      </div>
    </header>
  );
}
