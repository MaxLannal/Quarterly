import { Link, NavLink, Outlet } from "react-router-dom";

const NAV = [
  { to: "/plan", label: "Plan" },
  { to: "/courses", label: "Courses" },
  { to: "/programs", label: "Programs" },
  { to: "/instructors", label: "Forum" },
];

export function AppShell() {
  return (
    <div className="min-h-screen">
      <header className="border-b border-border">
        <nav aria-label="Main" className="mx-auto flex max-w-6xl flex-wrap items-center gap-2 p-2">
          <Link to="/" className="flex min-h-11 items-center px-2 font-semibold text-primary">
            Quarterly
          </Link>
          {NAV.map((item) => (
            <NavLink key={item.to} to={item.to} className="flex min-h-11 items-center px-3 hover:underline">
              {item.label}
            </NavLink>
          ))}
          <Link to="/login" className="ml-auto flex min-h-11 items-center px-3 hover:underline">
            Log in
          </Link>
        </nav>
      </header>
      <main>
        <Outlet />
      </main>
    </div>
  );
}
