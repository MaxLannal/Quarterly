import { useEffect, useRef } from "react";
import { Link } from "react-router-dom";
import { SparkIcon } from "@/components/ui/icons";
import { useAuthLinks } from "@/features/auth/next";
import { courseHref, isInternalPath } from "@/features/ask/markdown";
import { relativeDay } from "@/features/forum/format";
import { cn } from "@/lib/utils";
import { useMarkSeen, useUpdatesDigest, useUpdatesFeed, type UpdateItem } from "./updates";

const KIND: Record<UpdateItem["kind"], { glyph: string; name: string }> = {
  thread: { glyph: "?", name: "Question" },
  reply: { glyph: "↳", name: "Reply" },
  review: { glyph: "★", name: "Review" },
  discussion: { glyph: "¶", name: "Discussion" },
  comment: { glyph: "“", name: "Comment" },
};

/**
 * "For you" in the companion: a two-sentence digest and the new Commons threads and replies,
 * reviews, discussions and comments picked for the student. Opening it marks them seen (the orb's
 * badge clears; the dots stay until the next visit).
 */
export function ForYou({ loggedIn, onNavigate }: { loggedIn: boolean; onNavigate: () => void }) {
  const links = useAuthLinks();
  const feed = useUpdatesFeed(loggedIn);
  const digest = useUpdatesDigest(loggedIn);
  const seen = useMarkSeen();
  const marked = useRef(false);

  const { mutate } = seen;
  useEffect(() => {
    // Only once both reads are done: the digest must still see what is new.
    if (loggedIn && feed.isSuccess && !digest.isFetching && !marked.current) {
      marked.current = true;
      mutate();
    }
  }, [loggedIn, feed.isSuccess, digest.isFetching, mutate]);

  if (!loggedIn) {
    return (
      <div className="flex flex-col gap-4 px-5 py-6">
        <p className="font-display text-[26px] leading-tight text-ink">
          What’s new, <em className="text-primary">for you</em>.
        </p>
        <p className="text-body-sm text-body">
          Log in and the companion keeps watch: new answers on questions you follow, reviews of courses in your routes, and threads that match your interests.
        </p>
        <div className="flex flex-wrap gap-2">
          <Link to={links.login} onClick={onNavigate} className="inline-flex min-h-11 items-center rounded-pill bg-primary px-5 text-button text-on-primary hover:bg-primary-hover">
            Log in
          </Link>
          <Link to={links.signup} onClick={onNavigate} className="inline-flex min-h-11 items-center rounded-pill border border-hairline-strong px-5 text-button text-ink hover:bg-surface-strong">
            Create an account
          </Link>
        </div>
      </div>
    );
  }

  if (feed.isPending) {
    return (
      <div role="status" className="flex flex-col gap-3 px-5 py-6" aria-label="Loading your updates">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="h-16 animate-pulse rounded-xl bg-surface-strong" />
        ))}
      </div>
    );
  }
  if (feed.isError) {
    return (
      <div role="alert" className="flex flex-col items-start gap-3 px-5 py-6">
        <p className="text-body-sm text-error">Your updates could not be loaded.</p>
        <button type="button" onClick={() => void feed.refetch()} className="min-h-11 rounded-pill border border-hairline-strong px-4 text-button text-ink hover:bg-surface-strong">
          Try again
        </button>
      </div>
    );
  }
  const data = feed.data;
  return (
    <div className="flex flex-col gap-4 px-4 py-5 sm:px-5">
      {digest.isPending && data.items.length > 0 && (
        <div role="status" aria-label="Writing your digest" className="rounded-xl border border-primary/10 bg-primary-wash/40 px-4 py-4">
          <div className="h-3 w-11/12 animate-pulse rounded-pill bg-primary/10" />
          <div className="mt-2.5 h-3 w-2/3 animate-pulse rounded-pill bg-primary/10" />
        </div>
      )}
      {digest.data?.text && (
        <div className="companion-digest rounded-xl border border-primary/15 bg-primary-wash/60 px-4 py-3.5">
          <p className="font-display text-[17px] leading-snug text-ink">{digest.data.text}</p>
          {digest.data.ai && (
            <p className="mt-2 flex items-center gap-1.5 text-caption text-muted">
              <SparkIcon size={12} />
              Written by an AI and can be wrong.
            </p>
          )}
        </div>
      )}
      {data.items.length === 0 ? (
        <div className="px-1 py-4">
          <p className="text-body-sm text-body">Nothing here yet. Follow a course or a forum question and new replies and reviews will show up here.</p>
          <Link to="/forum" onClick={onNavigate} className="mt-3 inline-flex min-h-11 items-center rounded-xs text-caption text-primary underline underline-offset-2">
            Browse the forum
          </Link>
        </div>
      ) : (
        <ul className="flex flex-col gap-2" aria-label="Updates">
          {data.items.map((item, i) => (
            <li key={`${item.kind}-${item.id}`} className="companion-item" style={{ animationDelay: `${Math.min(i, 8) * 40}ms` }}>
              <UpdateCard item={item} onNavigate={onNavigate} />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function UpdateCard({ item, onNavigate }: { item: UpdateItem; onNavigate: () => void }) {
  const kind = KIND[item.kind];
  const href = isInternalPath(item.href) ? item.href : "/forum";
  return (
    <div className={cn("relative rounded-xl border bg-surface-card p-3.5 transition-[border-color,box-shadow] hover:border-primary/30 hover:shadow-hover", item.is_new ? "border-primary/20" : "border-hairline")}>
      <div className="flex gap-3">
        <span aria-hidden="true" className="mt-0.5 inline-flex size-8 shrink-0 items-center justify-center rounded-pill bg-primary-wash font-display text-[17px] text-primary">
          {kind.glyph}
        </span>
        <div className="min-w-0 flex-1">
          <p className="flex items-center gap-2 text-caption text-muted">
            <span className="font-medium text-body-strong">{kind.name}</span>
            <span aria-hidden="true">·</span>
            <span>{relativeDay(item.day)}</span>
            {item.is_new && (
              <span className="ms-auto inline-flex items-center gap-1 text-[11px] font-semibold uppercase tracking-[0.08em] text-primary">
                <span aria-hidden="true" className="inline-block size-1.5 rounded-pill bg-primary" />
                New
              </span>
            )}
          </p>
          <Link to={href} onClick={onNavigate} className="mt-1 block text-body-sm font-medium text-ink after:absolute after:inset-0 after:rounded-xl hover:text-primary">
            {item.title}
          </Link>
          {item.snippet && <p className="mt-1 line-clamp-2 text-caption text-body">{item.snippet}</p>}
          <div className="relative z-[1] mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-caption">
            {item.course_code && (
              <Link to={courseHref(item.course_code)} onClick={onNavigate} className="group/chip -my-1.5 inline-flex min-h-11 items-center rounded-pill">
                <span className="rounded-pill border border-hairline px-2.5 py-1 font-medium tabular-nums text-primary group-hover/chip:border-primary/40">{item.course_code}</span>
              </Link>
            )}
            <span className="text-muted">{item.reason}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
