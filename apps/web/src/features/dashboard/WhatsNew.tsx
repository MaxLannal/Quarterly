import { Link } from "react-router-dom";
import { useDashboardUpdates } from "./api";
import { DashCard } from "./parts";

const KIND_LABELS = { thread: "Question", reply: "Reply", review: "Review", discussion: "Discussion", comment: "Comment" } as const;

/** Opens the companion (the floating orb on every page), if it is there. */
function openCompanion() {
  const orb = document.querySelector<HTMLButtonElement>("button.companion-orb");
  orb?.click();
}

/** What's new for this student on the forum (GET /me/updates, owned by the Ask work stream). */
export function WhatsNew() {
  const q = useDashboardUpdates(true);
  const items = q.data?.items.slice(0, 5) ?? [];
  return (
    <DashCard kicker="Since you were here" title="What's new" className="h-full">
      {q.isLoading ? (
        <div aria-hidden="true" className="flex flex-col gap-3">
          {[0, 1, 2].map((i) => (
            <div key={i} className="skeleton h-12" />
          ))}
        </div>
      ) : q.error || q.data === null ? (
        <p className="text-body-sm text-muted">News from the forum will show up here.</p>
      ) : items.length === 0 ? (
        <p className="text-body-sm text-muted">Nothing new yet. Follow a forum question or a course, and replies and reviews show up here.</p>
      ) : (
        <ul className="flex flex-col divide-y divide-hairline">
          {items.map((item) => (
            <li key={`${item.kind}:${item.id}`} className="py-2.5 first:pt-0">
              <Link to={item.href} className="group flex min-h-11 flex-col justify-center rounded-md">
                <span className="flex items-center gap-2 text-caption text-muted">
                  {item.is_new && <span aria-label="New" className="inline-block size-1.5 rounded-pill bg-primary" />}
                  {KIND_LABELS[item.kind]}
                  {item.course_code ? ` · ${item.course_code}` : ""} · {item.reason}
                </span>
                <span className="line-clamp-2 text-body-sm text-ink group-hover:text-primary group-hover:underline">{item.title}</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
      <button type="button" onClick={openCompanion} className="mt-3 inline-flex min-h-11 items-center rounded-pill px-1 text-button text-primary underline underline-offset-4 hover:text-primary-hover">
        Open your companion
      </button>
    </DashCard>
  );
}
