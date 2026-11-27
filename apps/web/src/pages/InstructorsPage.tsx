import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { EmptyState, LoadingState, PageContainer } from "@/components/layout/page";
import { Button } from "@/components/ui/button";
import { Avatar } from "@/components/ui/card";
import { ArrowIcon, SearchIcon } from "@/components/ui/icons";
import { ErrorText } from "@/components/ui/misc";
import { Kicker } from "@/features/courses/Glass";
import { useInstructors } from "@/features/forum/api";
import { plural } from "@/features/forum/format";
import { useSession } from "@/lib/session";

/**
 * The Forum's front door (D11 FO-1): most students arrive with a course, so the page leads there,
 * and keeps the instructor directory (names are public, P03-12; reviews need a login).
 *
 * Dark glass: a cover with two ways in side by side (a glass card that leads to the Catalog, and
 * the instructor search as a glass command field), then the directory as a grid of glass tiles.
 */
export default function InstructorsPage() {
  const { data: session } = useSession();
  const [draft, setDraft] = useState("");
  const [q, setQ] = useState("");
  const list = useInstructors(q);

  function submit(e: FormEvent) {
    e.preventDefault();
    setQ(draft.trim());
  }

  const items = list.data?.items ?? [];
  return (
    <PageContainer as="section" className="max-w-[1240px]">
      <header className="qg-hero flex flex-col gap-4 pb-10 pt-4 sm:pt-12">
        <Kicker>Reviews <span aria-hidden="true" className="text-muted-soft">//</span> by instructor</Kicker>
        <h1 className="font-display text-display-lg text-ink [text-shadow:0_0_60px_rgb(255_92_112/0.22)] sm:text-display-mega">Forum</h1>
        <p className="max-w-[40rem] text-[19px] leading-[1.55] text-body">Reviews and discussion for each course, one page for each instructor who teaches it.</p>
      </header>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
        <div className="qg-tile qg-edge flex flex-col items-start gap-4 p-7 sm:p-8">
          <Kicker>01 <span aria-hidden="true" className="text-muted-soft">//</span> Start from a course</Kicker>
          <p className="text-body-md text-body">Know the course? Its page lists the instructors and links to their reviews.</p>
          <Button asChild>
            <Link to="/courses">Find a course</Link>
          </Button>
          {!session && <p className="text-caption text-muted">Log in to read and write reviews.</p>}
        </div>
        <form role="search" aria-label="Search instructors" onSubmit={submit} className="qg-tile flex flex-col justify-center gap-4 p-7 sm:p-8">
          <Kicker>02 <span aria-hidden="true" className="text-muted-soft">//</span> Or by name</Kicker>
          <label htmlFor="instructor-q" className="text-body-md text-body">
            Or search by instructor
          </label>
          <div className="qg-command min-h-16">
            <span aria-hidden="true" className="qg-command-ring">
              <span />
            </span>
            <SearchIcon size={18} className="qg-command-icon" />
            <input id="instructor-q" type="search" value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="Name" className="h-12 text-body-md" />
            <Button type="submit" variant="outline">
              Search
            </Button>
          </div>
        </form>
      </div>

      <div className="mt-16">
        {list.isLoading ? (
          <LoadingState label="Loading instructors" />
        ) : list.error ? (
          <ErrorText>{list.error.message}</ErrorText>
        ) : items.length === 0 ? (
          <EmptyState title={q ? `No instructor matches "${q}"` : "No instructors yet"}>
            Instructors appear once the quarterly schedule has been loaded.
          </EmptyState>
        ) : (
          <>
            <div className="mb-6 flex flex-wrap items-end justify-between gap-3 border-b border-hairline pb-4">
              <div className="flex flex-col gap-2">
                <Kicker>03 <span aria-hidden="true" className="text-muted-soft">//</span> Directory</Kicker>
                <h2 className="font-display text-display-sm text-ink sm:text-display-md">Instructors</h2>
              </div>
              <p role="status" className="font-mono text-[11.5px] uppercase tracking-[0.16em] text-muted">
                {plural(list.data?.total ?? items.length, "instructor")}
              </p>
            </div>
            <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {items.map((i, n) => (
                <li key={i.slug} data-spotlight="" className="qg-tile qg-tile-link qg-rise group" style={{ ["--i" as string]: n }}>
                  <Link to={`/instructors/${encodeURIComponent(i.slug)}`} className="flex min-h-12 items-center gap-4 rounded-[24px] p-5">
                    <Avatar name={i.display_name} className="size-11 text-[13px]" />
                    <span className="min-w-0 flex-1">
                      <span className="block font-display text-[24px] leading-tight text-ink transition-colors duration-300 group-hover:text-primary-hover">{i.display_name}</span>
                      {i.department && <span className="mt-1 block font-mono text-[11px] uppercase tracking-[0.14em] text-muted">{i.department}</span>}
                    </span>
                    <span aria-hidden="true" className="inline-flex size-9 shrink-0 items-center justify-center rounded-pill border border-hairline text-muted transition-[translate,color,border-color] duration-300 group-hover:translate-x-0.5 group-hover:border-primary/50 group-hover:text-primary">
                      <ArrowIcon size={14} />
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          </>
        )}
      </div>
    </PageContainer>
  );
}
