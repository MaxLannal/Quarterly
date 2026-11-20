import { useQueries, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useId, useMemo, useRef, useState, type ReactNode } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { TypeHero } from "@/components/brand/TypeHero";
import { PageContainer } from "@/components/layout/page";
import { Button } from "@/components/ui/button";
import { Notice } from "@/components/ui/misc";
import { useAuthLinks } from "@/features/auth/next";
import { AiHeadline } from "@/features/feed/AiHeadline";
import {
  feedKeys,
  feedNotesQuery,
  saveFocusToProfile,
  useFeed,
  useFeedCategories,
  type FeedItem,
  type FeedTab,
} from "@/features/feed/api";
import { arrange, estimateHeight, noteIds, tickerCourses } from "@/features/feed/arrange";
import { BookCard } from "@/features/feed/cards/BookCard";
import { CourseSpotlightCard } from "@/features/feed/cards/CourseSpotlightCard";
import { CommentCard, ProgramCard, QuestionCard, SkeletonCard } from "@/features/feed/cards/VoiceCards";
import { WordsCard } from "@/features/feed/cards/WordsCard";
import { FeedTabs, TABS } from "@/features/feed/FeedTabs";
import { FloatingWords } from "@/features/feed/FloatingWords";
import { FocusChips, type FocusStatus } from "@/features/feed/FocusChips";
import { Masonry } from "@/features/feed/Masonry";
import * as prefs from "@/features/feed/prefs";
import { Ticker } from "@/features/feed/Ticker";
import { useInView } from "@/features/feed/hooks";
import { useMediaQuery } from "@/lib/motion";
import { useSession } from "@/lib/session";
import "@/features/feed/feed.css";

const TAB_KEYS = new Set<string>(TABS.map((t) => t.key));

interface Toast {
  message: string;
  undo: () => void;
}

/**
 * The Feed (docs/BEST-OF-UCHICAGO-PLAN.md): course spotlights with generated art and books from
 * the shelf, students' voices, word clouds, programs and open questions, in the categories the
 * student focuses on, with the AI curator's notes. Floating words drift behind it.
 */
export default function FeedPage() {
  const session = useSession();
  const account = session.data?.account ?? null;
  const loggedIn = account !== null;
  const who = account?.id ?? "anon";
  const auth = useAuthLinks();
  const queryClient = useQueryClient();
  const panelId = useId();

  const [params, setParams] = useSearchParams();
  const rawTab = params.get("tab") ?? "for_you";
  const tab = (TAB_KEYS.has(rawTab) ? rawTab : "for_you") as FeedTab;
  const setTab = (next: FeedTab) => {
    const p = new URLSearchParams(params);
    if (next === "for_you") p.delete("tab");
    else p.set("tab", next);
    setParams(p, { replace: true });
  };

  // ------------------------------------------------------------------ focus categories
  const categories = useFeedCategories(who, !session.isLoading);
  const [focus, setFocus] = useState<string[] | null>(null);
  const [focusStatus, setFocusStatus] = useState<FocusStatus>("idle");

  const persist = useCallback(
    async (keys: string[]) => {
      if (!loggedIn) {
        prefs.writeFocus(keys);
        setFocusStatus("local");
        return;
      }
      setFocusStatus("saving");
      try {
        await saveFocusToProfile(keys);
        prefs.writePendingFocus(null);
        setFocusStatus("saved");
        void queryClient.invalidateQueries({ queryKey: feedKeys.categories(who) });
      } catch {
        prefs.writePendingFocus(keys);
        setFocusStatus("pending");
      }
    },
    [loggedIn, queryClient, who],
  );

  // The starting focus: the profile's (or a choice it has not accepted yet), else this browser's.
  useEffect(() => {
    if (session.isLoading || focus !== null) return;
    if (!loggedIn) {
      setFocus(prefs.readFocus());
      return;
    }
    if (!categories.data && !categories.isError) return;
    const pending = prefs.readPendingFocus();
    if (pending) {
      setFocus(pending);
      void persist(pending);
    } else {
      setFocus(categories.data?.selected ?? prefs.readFocus());
    }
  }, [session.isLoading, loggedIn, categories.data, categories.isError, focus, persist]);

  const changeFocus = (keys: string[]) => {
    setFocus(keys);
    void persist(keys);
  };

  // ------------------------------------------------------------------ the feed
  const focusParam = (focus ?? []).join(",");
  const canFollow = tab !== "following" || loggedIn;
  const feed = useFeed(who, tab, focusParam, focus !== null && canFollow);
  const pages = useMemo(() => feed.data?.pages ?? [], [feed.data]);

  const [hidden, setHidden] = useState<Set<string>>(() => new Set(prefs.readHidden()));
  const [less, setLess] = useState<Record<string, number>>(() => prefs.readLess());
  const [saved, setSaved] = useState(() => prefs.readSaved());
  const savedIds = useMemo(() => new Set(saved.map((s) => s.id)), [saved]);
  const items = useMemo(() => arrange(pages, hidden, less), [pages, hidden, less]);
  // Cards rise in once, when they first arrive; moving between columns does not replay it.
  const arrived = useRef(new Set<string>());
  useEffect(() => {
    for (const item of items) arrived.current.add(item.id);
  }, [items]);
  const arrival = (item: { id: string }) => (arrived.current.has(item.id) ? "" : "feed-card");

  // The AI curator: one call per loaded page (cached on the server for the day).
  const notes = useQueries({ queries: pages.map((page) => feedNotesQuery(who, tab, focusParam, noteIds(page))) });
  const aiNotes = useMemo(() => {
    const out: Record<string, string> = {};
    for (const q of notes) if (q.data?.ai) Object.assign(out, q.data.notes);
    return out;
  }, [notes]);
  const first = notes[0];
  const headlineAi = Boolean(first?.data?.ai);
  const headline = headlineAi && first?.data ? first.data.headline : (pages[0]?.headline ?? "");

  // ------------------------------------------------------------------ actions
  const [toast, setToast] = useState<Toast | null>(null);
  useEffect(() => {
    if (!toast) return;
    const t = window.setTimeout(() => setToast(null), 7000);
    return () => window.clearTimeout(t);
  }, [toast]);

  const toggleSave = (item: FeedItem & { kind: "course" }) => {
    prefs.toggleSaved({ id: item.id, label: `${item.code} ${item.title}`, href: `/courses/${encodeURIComponent(item.code)}` });
    setSaved(prefs.readSaved());
  };

  const showLess = (item: FeedItem & { kind: "course" }) => {
    const before = { hidden: new Set(hidden), less: { ...less } };
    const nextHidden = new Set(hidden).add(item.id);
    const key = item.category.key;
    const nextLess = { ...less, [key]: Math.min((less[key] ?? 0) + 1, 9) };
    setHidden(nextHidden);
    setLess(nextLess);
    prefs.writeHidden([...nextHidden]);
    prefs.writeLess(nextLess);
    setToast({
      message: `Hidden. You will see less ${item.category.label} here.`,
      undo: () => {
        setHidden(before.hidden);
        setLess(before.less);
        prefs.writeHidden([...before.hidden]);
        prefs.writeLess(before.less);
        setToast(null);
      },
    });
  };

  // ------------------------------------------------------------------ infinite scroll
  const [sentinel, nearEnd] = useInView<HTMLDivElement>("900px");
  const { hasNextPage, isFetchingNextPage, fetchNextPage, isError } = feed;
  const lastAuto = useRef(0);
  useEffect(() => {
    if (!nearEnd || !hasNextPage || isFetchingNextPage || isError) return;
    if (pages.length === lastAuto.current) return; // one automatic load per page reached
    lastAuto.current = pages.length;
    void fetchNextPage();
  }, [nearEnd, hasNextPage, isFetchingNextPage, isError, fetchNextPage, pages.length]);

  const wide = useMediaQuery("(min-width: 1100px)");
  const medium = useMediaQuery("(min-width: 700px)");
  const columns = wide ? 3 : medium ? 2 : 1;
  const loading = focus === null || feed.isLoading;

  const render = (item: FeedItem) => {
    const note = aiNotes[item.id];
    switch (item.kind) {
      case "course":
        return (
          <CourseSpotlightCard
            item={item}
            note={note}
            saved={savedIds.has(item.id)}
            onToggleSave={() => toggleSave(item)}
            onLess={() => showLess(item)}
          />
        );
      case "comment":
        return <CommentCard item={item} note={note} />;
      case "book":
        return <BookCard item={item} note={note} />;
      case "words":
        return <WordsCard item={item} note={note} />;
      case "program":
        return <ProgramCard item={item} note={note} />;
      case "question":
        return <QuestionCard item={item} note={note} />;
    }
  };

  return (
    <div className="relative isolate">
      <FloatingWords />
      <div className="relative z-10">
        <TypeHero
          shape="river"
          label="Bands of course titles flowing across the page"
          kicker="The Feed"
          title={
            <>
              A river of <em>ideas</em>, chosen for you.
            </>
          }
          subline="Course spotlights with books from the Quarterly shelf, students' voices and open questions, in the categories you choose. The curator learns what you are into."
        >
          <FocusChips categories={categories.data?.categories} selected={focus ?? []} onChange={changeFocus} status={focusStatus} />
        </TypeHero>
        <Ticker courses={tickerCourses(items)} />

        <PageContainer className="pt-8 sm:pt-10">
          <div className="flex flex-wrap items-end justify-between gap-3 rounded-t-lg bg-canvas/85">
            <div className="min-w-0 flex-1">
              <FeedTabs active={tab} onChange={setTab} panelId={panelId} />
            </div>
            <SavedList saved={saved} />
          </div>

          <div id={panelId} role="tabpanel" aria-labelledby={`feed-tab-${tab}`} className="mt-6 flex flex-col gap-6">
            {canFollow && !loading && items.length > 0 && (
              <div className="max-w-[52rem] rounded-lg bg-canvas/80 py-1">
                <AiHeadline headline={headline} ai={headlineAi} pending={Boolean(first?.isLoading)} />
              </div>
            )}

            {!canFollow && (
              <EmptyState title="Follow courses and routes to fill this tab">
                <p>Log in to see the courses on your routes and the questions you follow, with what is new on them.</p>
                <div className="flex flex-wrap gap-2">
                  <Button asChild>
                    <Link to={auth.login}>Log in</Link>
                  </Button>
                  <Button asChild variant="outline">
                    <Link to={auth.signup}>Create an account</Link>
                  </Button>
                </div>
              </EmptyState>
            )}

            {isError && (
              <Notice tone="error" role="alert">
                <p>The feed could not load. Check your connection and try again.</p>
                <button type="button" onClick={() => void feed.refetch()} className="mt-1 inline-flex min-h-11 items-center font-medium underline">
                  Try again
                </button>
              </Notice>
            )}

            {canFollow && loading && !isError && (
              <Masonry
                items={Array.from({ length: columns * 2 }, (_, i) => ({ id: `s${i}` }))}
                columns={columns}
                estimate={(s) => (Number(s.id.slice(1)) % 2 ? 300 : 560)}
                render={(s) => <SkeletonCard tall={Number(s.id.slice(1)) % 2 === 0} />}
              />
            )}

            {canFollow && !loading && !isError && items.length === 0 && (
              tab === "following" ? (
                <EmptyState title="Nothing to follow yet">
                  <p>
                    Keep a route on your dashboard, or follow a question in the Forum, and its courses and new answers will flow
                    in here.
                  </p>
                  <div className="flex flex-wrap gap-2">
                    <Button asChild>
                      <Link to="/me">Plan routes on your dashboard</Link>
                    </Button>
                    <Button asChild variant="outline">
                      <Link to="/forum">Browse the Forum</Link>
                    </Button>
                  </div>
                </EmptyState>
              ) : (
                <EmptyState title="The river is quiet here">
                  <p>Nothing matches this focus yet. Choose other categories, or clear your focus to see everything.</p>
                  <Button variant="outline" onClick={() => changeFocus([])}>
                    Clear focus
                  </Button>
                </EmptyState>
              )
            )}

            {!loading && items.length > 0 && (
              <section aria-label="Feed items" aria-busy={isFetchingNextPage}>
                <Masonry items={items} columns={columns} estimate={estimateHeight} render={render} itemClassName={arrival} />
              </section>
            )}

            {isFetchingNextPage && (
              <Masonry
                items={Array.from({ length: columns }, (_, i) => ({ id: `n${i}` }))}
                columns={columns}
                estimate={() => 400}
                render={(s) => <SkeletonCard tall={s.id === "n0"} />}
              />
            )}

            <div ref={sentinel} aria-hidden="true" className="h-px" />
            {!loading && items.length > 0 && (
              <div className="flex flex-col items-center gap-3 py-6 text-center">
                {hasNextPage ? (
                  <Button variant="outline" onClick={() => void fetchNextPage()} disabled={isFetchingNextPage}>
                    {isFetchingNextPage ? "Loading more…" : "Load more"}
                  </Button>
                ) : (
                  <p className="max-w-reading font-serif text-[22px] font-light italic text-body">
                    That is today&rsquo;s river. Come back tomorrow, or try{" "}
                    <button type="button" className="text-primary underline underline-offset-4" onClick={() => setTab(tab === "explore" ? "for_you" : "explore")}>
                      {tab === "explore" ? "For you" : "Explore"}
                    </button>
                    .
                  </p>
                )}
                <p className="text-caption text-muted">Books are from the Quarterly shelf: reading for the curious, not a syllabus.</p>
              </div>
            )}
          </div>
        </PageContainer>
      </div>

      {toast && (
        <div role="status" className="feed-toast fixed inset-x-0 bottom-6 z-50 mx-auto flex w-[min(92vw,30rem)] items-center justify-between gap-3 rounded-pill bg-surface-dark px-5 py-2 text-body-sm text-on-dark shadow-overlay">
          <span>{toast.message}</span>
          <button type="button" onClick={toast.undo} className="inline-flex min-h-11 shrink-0 items-center px-2 font-medium text-on-dark underline underline-offset-4">
            Undo
          </button>
        </div>
      )}
    </div>
  );
}

function EmptyState({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="flex max-w-reading flex-col gap-3 rounded-xl border border-dashed border-hairline-strong bg-canvas-soft p-8 text-body-md text-body">
      <h2 className="font-display text-[28px] font-bold text-ink tracking-[-0.02em]">{title}</h2>
      {children}
    </div>
  );
}

/** The courses saved with the bookmark (kept in this browser). */
function SavedList({ saved }: { saved: prefs.SavedItem[] }) {
  if (saved.length === 0) return null;
  return (
    <details className="relative">
      <summary className="inline-flex min-h-11 cursor-pointer list-none items-center gap-2 rounded-pill px-4 text-caption font-medium text-ink shadow-[inset_0_0_0_1px_var(--color-hairline-strong)] hover:bg-surface-strong">
        Saved <span className="rounded-pill bg-primary px-2 text-on-primary">{saved.length}</span>
      </summary>
      <ul className="absolute right-0 z-30 mt-2 flex max-h-80 w-72 flex-col overflow-y-auto rounded-lg border border-hairline bg-surface-card p-2 shadow-overlay">
        {saved.map((s) => (
          <li key={s.id}>
            <Link to={s.href} className="flex min-h-11 items-center rounded-md px-3 text-caption text-ink hover:bg-primary-wash hover:text-primary">
              {s.label}
            </Link>
          </li>
        ))}
      </ul>
    </details>
  );
}
