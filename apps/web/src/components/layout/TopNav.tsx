import { useEffect, useId, useState, type FormEvent, type ReactNode } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuthLinks } from "@/features/auth/next";
import { Button } from "@/components/ui/button";
import { Avatar } from "@/components/ui/card";
import {
  BookIcon,
  CapIcon,
  ChatIcon,
  CloseIcon,
  FolderIcon,
  HomeIcon,
  LayersIcon,
  MenuIcon,
  SearchIcon,
  ShieldIcon,
  UsersIcon,
} from "@/components/ui/icons";
import { useSession } from "@/lib/session";
import { cn } from "@/lib/utils";

/*
 * The app shell's navigation ("Simple light", docs/DESIGN.md; after Max's reference of 2026-11-27):
 * a sidebar on the light frame with the wordmark, the four main tabs (issue #15: Dashboard,
 * Planner, Catalog, Forum; the current one is a black pill), a "Tools" list, and a black card at
 * the foot. Below 1024px the sidebar slides in from the left behind a Menu button. The top bar of
 * the panel holds the course search and the account.
 */

/** Pages with their own course search box; the top bar hides its copy there (D11 H-1, CS-1). */
const PAGE_HAS_SEARCH = new Set(["/courses"]);
const AUTH_PAGES = new Set(["/login", "/signup"]);

/** A forum page or thread: /courses/:code/i/:instructor[/t/:id]. */
const FORUM_PATH = /^\/courses\/[^/]+\/i\//;

type Item = { to: string; label: string; icon: (p: { size?: number }) => ReactNode; current: (path: string) => boolean };

const NAV: Item[] = [
  { to: "/me", label: "Dashboard", icon: HomeIcon, current: (p) => /^\/me(\/|$)/.test(p) },
  // The only page where a student talks to the planner agent ("Ask Quarterly").
  { to: "/plan", label: "Planner", icon: FolderIcon, current: (p) => /^\/(plan|plans)(\/|$)/.test(p) },
  // Courses and programs share one item; a switch on each page moves between them (FEEDBACK 2026-11-16).
  {
    to: "/courses",
    label: "Catalog",
    icon: BookIcon,
    current: (p) => (/^\/courses(\/|$)/.test(p) && !FORUM_PATH.test(p)) || /^\/programs(\/|$)/.test(p),
  },
  // The Forum opens the Commons; course x instructor reviews stay at /instructors.
  {
    to: "/forum",
    label: "Forum",
    icon: ChatIcon,
    current: (p) => /^\/(forum|instructors|guidelines)(\/|$)/.test(p) || FORUM_PATH.test(p),
  },
];

const TOOLS: Item[] = [
  { to: "/plans", label: "My plans", icon: LayersIcon, current: (p) => /^\/plans(\/|$)/.test(p) },
  { to: "/programs", label: "Programs", icon: CapIcon, current: (p) => /^\/programs(\/|$)/.test(p) },
  { to: "/instructors", label: "Instructors", icon: UsersIcon, current: (p) => /^\/instructors(\/|$)/.test(p) },
  { to: "/guidelines", label: "Guidelines", icon: ShieldIcon, current: (p) => /^\/guidelines(\/|$)/.test(p) },
];

/** The wordmark (DESIGN.md "Brand & logo": no university marks): a black tile with a Q, then the name. */
export function Wordmark({ className }: { className?: string }) {
  return (
    <Link to="/" className={cn("flex min-h-11 shrink-0 items-center gap-2.5 rounded-lg", className)}>
      <span aria-hidden="true" className="flex size-9 items-center justify-center rounded-[10px] bg-ink text-[18px] font-semibold text-on-primary">
        Q
      </span>
      <span className="text-[19px] font-semibold tracking-[-0.3px] text-ink">Quarterly</span>
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
    <form role="search" aria-label="Site search" onSubmit={submit} className="relative flex w-full min-w-0 items-center">
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
          // A quiet grey field; white with an ink line in use (D6).
          "peer min-h-11 w-full min-w-0 rounded-lg border border-transparent bg-surface-strong pl-11 pr-3 text-body-sm text-ink transition-[border-color,background-color,box-shadow] duration-150 placeholder:text-muted",
          "hover:bg-[#ebebe8] focus-visible:outline-none focus:border-ink focus:bg-canvas focus:shadow-[0_0_0_3px_rgb(17_17_17/0.08)]",
        )}
      />
      <Button type="submit" variant="ghost" size="icon" aria-label="Search" className="absolute left-0 text-muted hover:bg-transparent hover:text-ink">
        <SearchIcon size={18} />
      </Button>
    </form>
  );
}

/** `strong`: the current item is the black pill (the main tabs); otherwise a grey plate (Tools), so
 * only one black pill ever shows. */
function NavList({ items, label, strong = false }: { items: Item[]; label: string; strong?: boolean }) {
  const { pathname } = useLocation();
  return (
    <nav aria-label={label}>
      <ul className="flex flex-col gap-0.5">
        {items.map((item) => {
          const current = item.current(pathname);
          const Icon = item.icon;
          return (
            <li key={item.to}>
              <Link
                to={item.to}
                aria-current={current ? "page" : undefined}
                className={cn(
                  "flex min-h-11 items-center gap-3 rounded-lg px-3 text-nav-link text-muted transition-colors duration-150 hover:bg-[#ebebe8] hover:text-ink",
                  current &&
                    (strong
                      ? "bg-ink font-semibold text-on-primary hover:bg-ink hover:text-on-primary"
                      : "bg-[#e8e8e5] font-semibold text-ink hover:bg-[#e8e8e5]"),
                )}
              >
                <Icon size={19} />
                {item.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

/** The sidebar: a column on the frame from 1024px; below that, a panel that slides in. */
export function Sidebar({ open, onClose, id }: { open: boolean; onClose: () => void; id: string }) {
  return (
    <>
      {open && <div aria-hidden="true" className="fixed inset-0 z-40 animate-fade-in bg-scrim lg:hidden" onClick={onClose} />}
      <aside
        id={id}
        aria-label="Sidebar"
        className={cn(
          "fixed inset-y-0 left-0 z-50 flex w-[272px] flex-col overflow-y-auto bg-app px-4 pb-5 pt-5 transition-[translate,visibility] duration-200 ease-out",
          "lg:visible lg:sticky lg:top-0 lg:z-auto lg:h-screen lg:translate-x-0 lg:transition-none",
          // Closed on a small screen it is also invisible, so its links are out of the tab order and
          // the accessibility tree, not just off screen.
          open ? "visible translate-x-0 shadow-overlay" : "invisible -translate-x-full",
        )}
      >
        <div className="flex items-center justify-between px-1">
          <Wordmark />
          <Button variant="ghost" size="icon" className="lg:hidden" aria-label="Close menu" onClick={onClose}>
            <CloseIcon size={20} />
          </Button>
        </div>
        <div className="mt-8">
          <NavList items={NAV} label="Main" strong />
        </div>
        <p className="mb-2 mt-8 px-3 text-caption text-muted">Tools</p>
        <NavList items={TOOLS} label="Tools" />
        <div className="mt-auto pt-8">
          <div className="rounded-xl bg-ink p-4 text-on-dark">
            <p className="text-body-sm font-semibold">Plan your four years</p>
            <p className="mt-1 text-caption text-on-dark-soft">Every plan is checked against your program's rules.</p>
            <Link
              to="/plan"
              className="mt-3 flex min-h-11 items-center justify-center rounded-lg bg-canvas text-button text-ink transition-colors hover:bg-surface-strong"
            >
              Go to the planner
            </Link>
          </div>
        </div>
      </aside>
    </>
  );
}

/** The panel's top bar: the menu button and wordmark on small screens, the course search, the account. */
export function TopBar({ menuOpen, onMenu, menuId }: { menuOpen: boolean; onMenu: () => void; menuId: string }) {
  const { data: session } = useSession();
  const authLinks = useAuthLinks();
  const { pathname } = useLocation();
  const hasSearch = !PAGE_HAS_SEARCH.has(pathname);

  const account = session ? (
    <Link
      to="/me"
      aria-current={pathname === "/me" ? "page" : undefined}
      className="flex min-h-11 items-center gap-2.5 rounded-lg pl-1 pr-1 text-body-sm font-medium text-ink transition-colors hover:bg-surface-strong sm:pr-3"
    >
      <Avatar name={session.account.username} />
      <span className="max-sm:sr-only">{session.account.username}</span>
    </Link>
  ) : AUTH_PAGES.has(pathname) ? null : (
    // D11 AU-3: no "Log in" on the login and sign-up pages themselves.
    <Button asChild variant="outline">
      <Link to={authLinks.login}>Log in</Link>
    </Button>
  );

  return (
    <header className="flex flex-wrap items-center gap-x-3 gap-y-3 px-4 pt-4 sm:px-6 lg:px-8 lg:pt-6">
      <Button
        variant="outline"
        size="icon"
        className="lg:hidden"
        aria-expanded={menuOpen}
        aria-controls={menuId}
        aria-label="Menu"
        onClick={onMenu}
      >
        <MenuIcon size={20} />
      </Button>
      <Wordmark className="lg:hidden" />
      {hasSearch && (
        <div className="order-last w-full sm:order-none sm:ml-auto sm:max-w-[22rem] sm:flex-1 lg:ml-0">
          <SearchBox />
        </div>
      )}
      <div className="ml-auto flex items-center gap-2">{account}</div>
    </header>
  );
}

/** Opens and closes the sidebar on small screens (closes on navigation). */
export function useSidebar() {
  const [open, setOpen] = useState(false);
  const { pathname } = useLocation();
  const id = useId();
  useEffect(() => setOpen(false), [pathname]);
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);
  return { open, setOpen, id };
}
