import { useEffect, useId, useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuthLinks } from "@/features/auth/next";
import { Button } from "@/components/ui/button";
import { Avatar } from "@/components/ui/card";
import { CloseIcon, MenuIcon, SearchIcon } from "@/components/ui/icons";
import { useSession } from "@/lib/session";
import { cn } from "@/lib/utils";

/** Pages with their own course search box; the bar hides its copy there (D11 H-1, CS-1). */
const PAGE_HAS_SEARCH = new Set(["/", "/courses"]);
const AUTH_PAGES = new Set(["/login", "/signup"]);

/** A forum page or thread: /courses/:code/i/:instructor[/t/:id]. */
const FORUM_PATH = /^\/courses\/[^/]+\/i\//;

/** Each link is the current section for its own path and the pages that belong to it. */
const NAV: { to: string; label: string; current: (path: string) => boolean }[] =
  [
    {
      to: "/plan",
      label: "Plan",
      current: (p) => /^\/(plan|plans|onboarding)(\/|$)/.test(p),
    },
    // Courses and programs share one item; a switch on each page moves between them (FEEDBACK 2026-11-16).
    {
      to: "/courses",
      label: "Catalog",
      current: (p) =>
        (/^\/courses(\/|$)/.test(p) && !FORUM_PATH.test(p)) ||
        /^\/programs(\/|$)/.test(p),
    },
    {
      to: "/instructors",
      label: "Forum",
      current: (p) =>
        /^\/(instructors|guidelines)(\/|$)/.test(p) || FORUM_PATH.test(p),
    },
  ];

/** The text wordmark (DESIGN.md "Brand & logo": no university marks), set in Newsreader 500 so it
 * holds its own in the bar (D4, FEEDBACK "Minor design changes"). */
export function Wordmark({ className }: { className?: string }) {
  return (
    <Link
      to="/"
      className={cn(
        "flex min-h-11 shrink-0 items-center rounded-xs font-display text-display-sm font-medium tracking-[-0.24px] text-ink",
        className,
      )}
    >
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
    <form
      role="search"
      aria-label="Site search"
      onSubmit={submit}
      className="relative flex w-full min-w-0 items-center"
    >
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
          // A quiet filled field (D6, FEEDBACK "Minor design changes"): no outline until it is used;
          // the icon and placeholder say what it is. Focus: white, with the maroon ring.
          "min-h-11 w-full min-w-0 rounded-pill border border-transparent bg-surface-strong pl-11 pr-4 text-body-sm pointer-coarse:text-body-md text-ink transition-colors duration-150 placeholder:text-muted",
          "hover:bg-hairline-soft hover:border-hairline focus-visible:outline-none focus:border-primary focus:bg-surface-card focus:shadow-[inset_0_0_0_1px_var(--color-primary)]",
        )}
      />
      <Button
        type="submit"
        variant="ghost"
        size="icon"
        aria-label="Search"
        className="absolute left-0 text-muted hover:bg-transparent hover:text-ink"
      >
        <SearchIcon />
      </Button>
    </form>
  );
}

function NavLinks({ vertical = false }: { vertical?: boolean }) {
  const { pathname } = useLocation();
  return (
    <>
      {NAV.map((item) => {
        const current = item.current(pathname);
        return (
          <Link
            key={item.to}
            to={item.to}
            aria-current={current ? "page" : undefined}
            className={cn(
              "flex min-h-11 items-center rounded-pill px-4 text-nav-link text-ink transition-colors hover:bg-surface-strong",
              vertical && "w-full md:w-auto",
              current && "bg-primary-wash hover:bg-primary-wash",
            )}
          >
            {item.label}
          </Link>
        );
      })}
    </>
  );
}

/**
 * top-nav: canvas, 64px. Wordmark left, links next to it, search + account right. Below 768px the
 * links fold behind a Menu button; the search stays visible on its own row.
 */
export function TopNav() {
  const { data: session } = useSession();
  const authLinks = useAuthLinks();
  const [open, setOpen] = useState(false);
  const location = useLocation();
  const panelId = useId();

  useEffect(() => setOpen(false), [location.pathname]);

  const account = session ? (
    <Link
      to="/account"
      className="flex min-h-11 items-center gap-2 rounded-pill pl-1 pr-3 text-nav-link text-ink hover:bg-surface-strong"
    >
      <Avatar name={session.account.username} />
      {session.account.username}
    </Link>
  ) : AUTH_PAGES.has(location.pathname) ? null : (
    // D11 AU-3: no "Log in" pill on the login and sign-up pages themselves.
    <Button asChild variant="outline">
      <Link to={authLinks.login}>Log in</Link>
    </Button>
  );

  return (
    <header className="border-b border-hairline bg-canvas">
      <div
        className={cn(
          "mx-auto flex w-full flex-wrap",
          location.pathname === "/plan" ? "max-w-tool" : "max-w-content",
          "items-center gap-x-2 px-4 sm:px-6 md:h-16 md:flex-nowrap lg:px-8",
        )}
      >
        <Wordmark className="mr-2 h-16 md:h-auto" />
        <nav
          id={panelId}
          aria-label="Main"
          className={cn(
            "items-center gap-1 md:flex",
            open
              ? "order-last mb-3 flex w-full flex-col items-stretch border-t border-hairline pt-3 md:order-none md:mb-0 md:w-auto md:flex-row md:items-center md:border-0 md:pt-0"
              : "hidden",
          )}
        >
          <NavLinks vertical={open} />
        </nav>
        {/* D11 H-1/CS-1: home and course search have their own search box; one is enough. */}
        {!PAGE_HAS_SEARCH.has(location.pathname) && (
          <div className="order-1 w-full pb-3 md:order-none md:ml-auto md:w-auto md:max-w-[17rem] md:flex-1 md:pb-0">
            <SearchBox />
          </div>
        )}
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
