import { useState, type FormEvent } from "react";
import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import { Notice } from "@/components/ui/misc";
import { useImportOnLogin } from "@/features/planner/importOnLogin";
import { useSession } from "@/lib/session";
import { cn } from "@/lib/utils";

const NAV = [
  { to: "/plan", label: "Plan" },
  { to: "/courses", label: "Courses" },
  { to: "/programs", label: "Programs" },
  { to: "/instructors", label: "Forum" },
];

function SearchBox() {
  const navigate = useNavigate();
  const [q, setQ] = useState("");
  function submit(e: FormEvent) {
    e.preventDefault();
    const term = q.trim();
    navigate(term ? `/courses?q=${encodeURIComponent(term)}` : "/courses");
  }
  return (
    <form role="search" onSubmit={submit} className="flex w-full min-w-0 sm:w-auto sm:flex-1 md:max-w-sm">
      <label htmlFor="site-search" className="sr-only">
        Search courses
      </label>
      <input
        id="site-search"
        type="search"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="Search courses"
        className="min-h-11 min-w-0 flex-1 rounded-l-md border border-border bg-background px-3 text-sm"
      />
      <button type="submit" className="min-h-11 rounded-r-md border border-l-0 border-border bg-muted px-3 text-sm font-medium hover:bg-zinc-200">
        Search
      </button>
    </form>
  );
}

export function AppShell() {
  const { data: session } = useSession();
  const importStatus = useImportOnLogin();
  return (
    <div className="min-h-screen">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:bg-background focus:p-2">
        Skip to content
      </a>
      <header className="border-b border-border">
        <div className="mx-auto flex max-w-[1600px] flex-wrap items-center gap-x-2 gap-y-1 p-2">
          <Link to="/" className="flex min-h-11 items-center px-2 text-lg font-semibold text-primary">
            Quarterly
          </Link>
          <nav aria-label="Main" className="order-3 flex w-full gap-1 sm:order-none sm:w-auto">
            {NAV.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  cn("flex min-h-11 items-center rounded-md px-3 text-sm hover:bg-muted", isActive && "bg-muted font-semibold text-primary")
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
          <div className="order-4 flex w-full sm:order-none sm:ml-auto sm:w-auto sm:flex-1 sm:justify-end">
            <SearchBox />
          </div>
          <div className="ml-auto sm:ml-0">
            {session ? (
              <Link to="/account" className="flex min-h-11 items-center rounded-md px-3 text-sm font-medium hover:bg-muted">
                {session.account.username}
              </Link>
            ) : (
              <Link to="/login" className="flex min-h-11 items-center rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground hover:opacity-90">
                Log in
              </Link>
            )}
          </div>
        </div>
      </header>
      {importStatus === "imported" && (
        <div className="mx-auto max-w-[1600px] px-3 pt-2">
          <Notice tone="green" role="status">
            Your plans from this device were added to your account.
          </Notice>
        </div>
      )}
      <main id="main">
        <Outlet />
      </main>
    </div>
  );
}
