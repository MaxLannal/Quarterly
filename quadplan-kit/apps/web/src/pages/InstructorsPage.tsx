import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { EmptyState, LoadingState, PageContainer, PageHeader } from "@/components/layout/page";
import { Button } from "@/components/ui/button";
import { Avatar } from "@/components/ui/card";
import { Input, Label } from "@/components/ui/input";
import { ErrorText } from "@/components/ui/misc";
import { useInstructors } from "@/features/forum/api";
import { plural } from "@/features/forum/format";

/** Instructor directory. Names are public (P03-12); ratings and reviews need a login. */
export default function InstructorsPage() {
  const [draft, setDraft] = useState("");
  const [q, setQ] = useState("");
  const list = useInstructors(q);

  function submit(e: FormEvent) {
    e.preventDefault();
    setQ(draft.trim());
  }

  const items = list.data?.items ?? [];
  return (
    <PageContainer as="section" width="reading">
      <PageHeader
        title="Instructors"
        description="Find an instructor to see the courses they teach. Ratings, reviews and discussion are for logged-in students."
      />
      <form role="search" aria-label="Search instructors" onSubmit={submit} className="mb-8 flex flex-wrap items-end gap-3">
        <div className="flex min-w-0 flex-1 flex-col gap-1.5">
          <Label htmlFor="instructor-q">Search instructors</Label>
          <Input id="instructor-q" type="search" value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="Name" />
        </div>
        <Button type="submit" variant="outline">
          Search
        </Button>
      </form>
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
          <p role="status" className="mb-2 text-caption text-muted">
            {plural(list.data?.total ?? items.length, "instructor")}
          </p>
          <ul className="divide-y divide-hairline border-y border-hairline">
            {items.map((i) => (
              <li key={i.slug}>
                <Link
                  to={`/instructors/${encodeURIComponent(i.slug)}`}
                  className="flex min-h-12 items-center gap-3 rounded-sm px-1 py-3 hover:bg-surface-strong"
                >
                  <Avatar name={i.display_name} />
                  <span className="min-w-0">
                    <span className="block text-title-sm text-ink">{i.display_name}</span>
                    {i.department && <span className="block text-caption text-muted">{i.department}</span>}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </>
      )}
    </PageContainer>
  );
}
