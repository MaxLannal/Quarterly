import { useEffect, useId, useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuthLinks } from "@/features/auth/next";
import { Button } from "@/components/ui/button";
import { Avatar } from "@/components/ui/card";
import { CloseIcon, MenuIcon, SearchIcon } from "@/components/ui/icons";
import { useSession } from "@/lib/session";
import { cn } from "@/lib/utils";

/** Pages with their own course search box; the bar hides its copy there (D11 H-1, CS-1). The
 * homepage has no search of its own since its question bar went (issue #15), so the top bar's
 * course search shows there too, on phones as well. */
const PAGE_HAS_SEARCH = new Set(["/courses"]);
const AUTH_PAGES = new Set(["/login", "/signup"]);

/** A forum page or thread: /courses/:code/i/:instructor[/t/:id]. */
const FORUM_PATH = /^\/courses\/[^/]+\/i\//;

/** Each link is the current section for its own path and the pages that belong to it. Four
 * tabs, one job each (issue #15): the homepage is not a tab; the wordmark links to it. */
const NAV: { to: string; label: string; current: (path: string) => boolean }[] =
  [
    { to: "/me", label: "Dashboard", current: (p) => /^\/me(\/|$)/.test(p) },
    // The only page where a student talks to the planner agent ("Ask Quarterly").
    {
      to: "/plan",
      label: "Planner",
      current: (p) => /^\/(plan|plans)(\/|$)/.test(p),
    },
    // Courses and programs share one item; a switch on each page moves between them (FEEDBACK 2026-11-16).
    {
      to: "/courses",
      label: "Catalog",
      current: (p) =>
        (/^\/courses(\/|$)/.test(p) && !FORUM_PATH.test(p)) ||
        /^\/programs(\/|$)/.test(p),
    },
    // The Forum opens the Commons (course questions with a bot answer); course x instructor
    // reviews stay at /instructors, linked from the Commons header.
    {
      to: "/forum",
      label: "Forum",
      current: (p) =>
        /^\/(forum|instructors|guidelines)(\/|$)/.test(p) || FORUM_PATH.test(p),
    },
  ];

/** The text wordmark (DESIGN.md "Brand & logo": no university marks), set in the display serif with
 * one point of red light after it (docs/DESIGN.md "Dark glass"). */
export function Wordmark({ className }: { className?: string }) {
  return (
    <Link
      to="/"
      className={cn(
        // The display-serif wordmark in warm white on the smoked-glass bar.
        "group flex min-h-11 shrink-0 items-center gap-[3px] rounded-xs font-display text-[33px] leading-none tracking-[-0.5px] text-ink",
        className,
      )}
    >
      Quarterly
      <span
        aria-hidden="true"
        className="mt-3 inline-block size-[7px] rounded-pill bg-primary shadow-[0_0_12px_2px_rgb(255_92_112/0.7)] transition-transform duration-300 group-hover:scale-125"
      />
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
          // On the frosted bar: a quiet filled pill that turns white, with the maroon halo, in use.
          "peer min-h-12 w-full min-w-0 rounded-pill border border-hairline-strong bg-[rgb(20_10_13/0.55)] pl-12 pr-4 backdrop-blur-xl text-body-md text-ink shadow-[inset_0_1px_2px_rgb(0_0_0/0.35)] transition-[border-color,background-color,box-shadow] duration-200 placeholder:text-muted",
          "hover:border-hairline-strong hover:bg-white/[0.07] focus-visible:outline-none focus:border-primary/70 focus:bg-white/[0.08] focus:shadow-[0_0_0_4px_rgb(255_92_112/0.14),0_0_30px_rgb(255_92_112/0.2)]",
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
              // The current page is a lit glass pill with a point of red light; the others are quiet.
              "relative flex min-h-11 items-center gap-2 rounded-pill px-4 text-[17px] font-medium tracking-[-0.01em] text-muted transition-[color,background-color,box-shadow] duration-200 hover:bg-white/[0.06] hover:text-ink md:px-3 xl:px-4",
              vertical && "w-full md:w-auto",
              current &&
                "bg-white/[0.08] text-ink shadow-[inset_0_0_0_1px_rgb(255_255_255/0.1),inset_0_1px_0_rgb(255_255_255/0.12)] hover:bg-white/[0.1]",
            )}
          >
            {current && (
              <span
                aria-hidden="true"
                className="size-1.5 rounded-pill bg-primary shadow-[0_0_10px_2px_rgb(255_92_112/0.65)]"
              />
            )}
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
  const hasSearch = !PAGE_HAS_SEARCH.has(location.pathname);

  const account = session ? (
    <Link
      to="/me"
      aria-current={location.pathname === "/me" ? "page" : undefined}
      className="flex min-h-12 items-center gap-2 rounded-pill bg-[rgb(20_10_13/0.55)] pl-1.5 pr-1.5 backdrop-blur-xl text-[16px] font-medium text-ink shadow-[inset_0_0_0_1px_var(--color-hairline)] transition-colors hover:bg-white/[0.09] aria-[current=page]:shadow-[inset_0_0_0_1px_rgb(255_92_112/0.45)] lg:pr-4"
    >
      <Avatar name={session.account.username} />
      {/* Below wide screens the avatar alone keeps the bar on one row; the name stays for screen readers. */}
      <span className="max-lg:sr-only">{session.account.username}</span>
    </Link>
  ) : AUTH_PAGES.has(location.pathname) ? null : (
    // D11 AU-3: no "Log in" pill on the login and sign-up pages themselves.
    <Button asChild variant="outline">
      <Link to={authLinks.login}>Log in</Link>
    </Button>
  );

  return (
    // Glass floating over the night: the wordmark on its own, the four tabs in a glass dock (centred
    // on wide screens), search and account on the right. A progressive blur under the bar softens
    // whatever scrolls beneath it (docs/DESIGN.md "Dark glass").
    <header className="nav-veil sticky top-0 z-30 px-3 pb-3 pt-3 sm:px-4 lg:px-6">
      <div className="relative mx-auto flex min-h-14 w-full flex-wrap items-center gap-x-3 gap-y-3 lg:flex-nowrap">
        <Wordmark className="h-12 px-1" />
        <nav
          id={panelId}
          aria-label="Main"
          className={cn(
            "nav-glass items-center gap-1 rounded-pill p-1.5 md:flex xl:absolute xl:left-1/2 xl:-translate-x-1/2",
            open
              ? "order-last flex w-full flex-col items-stretch rounded-[26px] md:order-none md:w-auto md:flex-row md:items-center md:rounded-pill"
              : "hidden",
          )}
        >
          <NavLinks vertical={open} />
        </nav>
        {/* D11 H-1/CS-1: home and course search have their own search box; one is enough. */}
        {hasSearch && (
          // Its own row below until the bar is wide enough for the tabs and a search.
          <div className="order-1 w-full lg:order-none lg:ml-auto lg:w-[17rem] lg:flex-none">
            <SearchBox />
          </div>
        )}
        <div className={cn("ml-auto flex items-center gap-2", hasSearch && "lg:ml-0")}>
          {account}
          <Button
            variant="outline"
            size="icon"
            className="text-ink md:hidden"
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
