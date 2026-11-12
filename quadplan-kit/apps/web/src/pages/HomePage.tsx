import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

export default function HomePage() {
  const navigate = useNavigate();
  const [q, setQ] = useState("");
  function submit(e: FormEvent) {
    e.preventDefault();
    navigate(q.trim() ? `/courses?q=${encodeURIComponent(q.trim())}` : "/courses");
  }
  return (
    <section className="mx-auto max-w-3xl space-y-6 px-4 py-10">
      <div className="space-y-2">
        <h1 className="text-3xl font-semibold text-primary">Quarterly</h1>
        <p className="text-lg">Plan four years of courses with a verifier that checks every requirement, and read what students say about each class.</p>
      </div>
      <form role="search" onSubmit={submit} className="flex gap-2" aria-label="Search courses and instructors">
        <label htmlFor="home-search" className="sr-only">
          Search courses and instructors
        </label>
        <input
          id="home-search"
          type="search"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Course code or title"
          className="min-h-11 flex-1 rounded-md border border-border bg-background px-3"
        />
        <button type="submit" className="min-h-11 rounded-md border border-border bg-muted px-4 font-medium hover:bg-zinc-200">
          Search
        </button>
      </form>
      <div className="flex flex-wrap gap-3">
        <Link to="/onboarding" className="flex min-h-11 items-center rounded-md bg-primary px-5 font-medium text-primary-foreground hover:opacity-90">
          Start planning
        </Link>
        <Link to="/instructors" className="flex min-h-11 items-center rounded-md border border-border px-5 font-medium hover:bg-muted">
          Browse reviews
        </Link>
        <Link to="/plan" className="flex min-h-11 items-center rounded-md px-3 font-medium text-primary underline">
          Open my plan
        </Link>
      </div>
      <p className="text-sm text-muted-foreground">
        No account needed to plan: your plan stays on this device until you log in.
      </p>
    </section>
  );
}
