import { useEffect, useId, useMemo, useRef, useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { PageTitle } from "@/components/brand/TypeHero";
import { Button } from "@/components/ui/button";
import { controlClass } from "@/components/ui/input";
import { ErrorText } from "@/components/ui/misc";
import { useSession } from "@/lib/session";
import { cn } from "@/lib/utils";
import { useCourseMatches, useCreateThread, useThreadPage, type CourseRef } from "@/features/commons/api";
import { Composer, type ComposerHandle } from "@/features/commons/Composer";
import { CourseSearch } from "@/features/commons/CourseSearch";
import { clearDraft, readDraft, writeDraft } from "@/features/commons/drafts";
import { ArchGlyph, LoginCard } from "@/features/commons/parts";
import { TagInput } from "@/features/commons/TagInput";
import { plural, searchTerms, threadPath } from "@/features/commons/text";

const TITLE_MIN = 8;
const TITLE_MAX = 160;
const DETAILS_KEY = "new-question";
const META_KEY = "new-question-meta";

interface Meta {
  title: string;
  course: CourseRef | null;
  tags: string[];
}

function useDebounced<T>(value: T, ms: number): T {
  const [out, setOut] = useState(value);
  useEffect(() => {
    const t = window.setTimeout(() => setOut(value), ms);
    return () => window.clearTimeout(t);
  }, [value, ms]);
  return out;
}

/** "Already asked?": questions with the title's key words, as the student types. */
function Similar({ title, course }: { title: string; course: CourseRef | null }) {
  const debounced = useDebounced(title.trim(), 350);
  const terms = useMemo(() => searchTerms(debounced), [debounced]);
  const enabled = debounced.length >= 6 && terms.length > 0;
  const byWords = useThreadPage({ sort: "top", q: terms.slice(0, 2).join(" ") }, 5, enabled);
  const byFirst = useThreadPage({ sort: "top", q: terms[0] }, 5, enabled && terms.length > 1);
  const byCourse = useThreadPage({ sort: "top", course: course?.code }, 3, !!course && enabled);
  const seen = new Set<number>();
  const items = [...(byWords.data?.items ?? []), ...(byCourse.data?.items ?? []), ...(byFirst.data?.items ?? [])].filter((t) =>
    seen.has(t.id) ? false : (seen.add(t.id), true),
  );
  if (!enabled) return null;
  return (
    <div aria-live="polite" className="min-h-6">
      {items.length > 0 ? (
        <div className="animate-rise rounded-lg border border-hairline bg-canvas-soft px-4 py-3">
          <p className="text-caption-uppercase uppercase text-muted">Already asked?</p>
          <ul className="mt-1 flex flex-col">
            {items.slice(0, 5).map((t) => (
              <li key={t.id}>
                <Link to={threadPath(t.id)} target="_blank" className="group flex min-h-11 items-center justify-between gap-3 rounded-xs py-1 text-body-sm text-ink">
                  <span className="min-w-0 group-hover:text-primary group-hover:underline">{t.title}</span>
                  <span className="shrink-0 text-caption text-muted">
                    {t.accepted ? "accepted · " : ""}
                    {plural(t.answer_count, "answer")}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
          <p className="text-caption text-muted">They open in a new tab, so you keep what you wrote.</p>
        </div>
      ) : byWords.isSuccess ? (
        <p className="text-caption text-muted">No similar question yet. Yours will be the first.</p>
      ) : null}
    </div>
  );
}

function Tips() {
  return (
    <aside aria-label="Tips" className="flex flex-col gap-5 lg:sticky lg:top-8">
      <section className="relative overflow-hidden rounded-xl border border-hairline bg-surface-card p-6">
        <span aria-hidden="true" className="absolute inset-x-0 top-0 h-1 bg-primary" />
        <h2 className="font-display text-display-sm text-ink">A good question</h2>
        <ul className="mt-3 flex list-disc flex-col gap-2 pl-5 text-body-sm text-body">
          <li>Names the course: type a code like CMSC 14100 and pick it.</li>
          <li>Says what you already know, and what you are choosing between.</li>
          <li>Asks one thing. Start a new question for the next one.</li>
        </ul>
      </section>
      <section className="flex gap-3 rounded-xl border border-hairline bg-canvas-soft p-5 text-body-sm text-body">
        <span className="mt-0.5 inline-flex size-8 shrink-0 items-center justify-center rounded-pill bg-primary text-on-primary">
          <ArchGlyph size={18} />
        </span>
        <p>
          <strong className="font-medium text-ink">Quarterly AI answers first,</strong> from the catalog, the programs and what students wrote. It can be wrong;
          students answer below it. You appear under a random handle that is new on every question.
        </p>
      </section>
    </aside>
  );
}

export default function CommonsNewPage() {
  const { data: session, isLoading } = useSession();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const create = useCreateThread();
  const id = useId();
  const details = useRef<ComposerHandle>(null);
  const titleRef = useRef<HTMLInputElement>(null);

  const saved = useMemo(() => readDraft<Meta>(META_KEY), []);
  const [title, setTitle] = useState(() => params.get("title")?.slice(0, TITLE_MAX) || saved?.title || "");
  const [course, setCourse] = useState<CourseRef | null>(saved?.course ?? null);
  const [tags, setTags] = useState<string[]>(saved?.tags ?? []);
  const [body, setBody] = useState("");
  const [tried, setTried] = useState(false);

  // ?course=CMSC%2014100 prefills the course (once its title is known).
  const prefill = params.get("course") ?? "";
  const prefillMatch = useCourseMatches(prefill, 3);
  useEffect(() => {
    if (!prefill || course) return;
    const hit = prefillMatch.data?.items.find((c) => c.code.replace(" ", "").toUpperCase() === prefill.replace(" ", "").toUpperCase());
    if (hit) setCourse({ code: hit.code, title: hit.title });
  }, [prefill, prefillMatch.data, course]);

  useEffect(() => {
    if (title || course || tags.length) writeDraft<Meta>(META_KEY, { title, course, tags });
    else clearDraft(META_KEY);
  }, [title, course, tags]);

  // Start in the title field, unless it came filled in from the Commons' ask box.
  useEffect(() => {
    if (session && !params.get("title")) titleRef.current?.focus();
  }, [session, params]);

  const trimmed = title.trim();
  const titleProblem = trimmed.length < TITLE_MIN ? `Write a title of at least ${TITLE_MIN} characters.` : null;

  async function submit(text: string = body) {
    setTried(true);
    if (titleProblem) {
      titleRef.current?.focus();
      return;
    }
    const thread = await create.mutateAsync({ title: trimmed, body_md: text, course_code: course?.code ?? null, tags });
    clearDraft(META_KEY);
    clearDraft(DETAILS_KEY);
    navigate(threadPath(thread.id), { state: { asked: true } });
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    void submit().catch(() => undefined);
  }

  if (!isLoading && !session) {
    return (
      <div className="mx-auto w-full max-w-reading px-4 pb-24 pt-12 sm:px-6">
        <PageTitle kicker="The Commons" size="md" title={<>Ask the <em>quad</em>.</>} subline="Log in to ask. Anyone can read the Commons; asking and answering need an account, so the conversation stays among students." />
        <LoginCard className="mt-8">Log in or sign up with your uchicago.edu address to ask. You will appear under a random handle, new on every question.</LoginCard>
        <p className="mt-6 text-body-sm">
          <Link to="/forum" className="text-primary underline underline-offset-2">
            ← Back to the Commons
          </Link>
        </p>
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-content px-4 pb-24 pt-8 sm:px-6 sm:pt-12 lg:px-8">
      <p className="mb-6 text-caption">
        <Link to="/forum" className="inline-flex min-h-11 items-center text-muted hover:text-primary">
          ← The Commons
        </Link>
      </p>
      <PageTitle kicker="New question" size="md" title={<>Ask the <em>quad</em>.</>} subline="Quarterly AI answers within a minute; students add what it cannot know." />
      <div className="mt-10 grid gap-10 lg:grid-cols-[minmax(0,1fr)_320px]">
        <form onSubmit={onSubmit} noValidate aria-label="Ask a question" className="flex min-w-0 flex-col gap-7">
          <div className="flex flex-col gap-2">
            <div className="flex items-baseline justify-between gap-3">
              <label htmlFor={`${id}-title`} className="text-caption font-medium text-ink">
                Your question
              </label>
              <span className={cn("text-caption tabular-nums", trimmed.length > TITLE_MAX - 20 ? "text-warning" : "text-muted")}>
                {trimmed.length} / {TITLE_MAX}
              </span>
            </div>
            <input
              ref={titleRef}
              id={`${id}-title`}
              value={title}
              maxLength={TITLE_MAX}
              autoComplete="off"
              onChange={(e) => setTitle(e.target.value)}
              placeholder="MATH 15300 or MATH 16300 for a likely math major?"
              aria-invalid={tried && !!titleProblem ? true : undefined}
              aria-describedby={`${id}-title-hint`}
              className={cn(controlClass, "min-h-14 font-display text-[22px] leading-snug sm:text-[24px]")}
            />
            <p id={`${id}-title-hint`} className="text-caption text-muted">
              One question, as you would ask a friend who knows.
            </p>
            {tried && titleProblem && <ErrorText>{titleProblem}</ErrorText>}
            <Similar title={title} course={course} />
          </div>

          <CourseSearch label="Which course is it about? (optional)" value={course} onChange={setCourse} card placeholder="Type a code or title, like CMSC 14100" />

          <Composer
            ref={details}
            label="Details (optional)"
            placeholder="What do you already know? What are you choosing between? Mention courses by code."
            draftKey={DETAILS_KEY}
            optional
            rows={6}
            hideSubmit
            onChange={setBody}
            onSubmit={(text) => submit(text)}
          />

          <TagInput value={tags} onChange={setTags} />

          <div className="flex flex-col gap-3 border-t border-hairline pt-6">
            {create.error && <ErrorText>{create.error.message}</ErrorText>}
            <div className="flex flex-wrap items-center gap-3">
              <Button type="submit" disabled={create.isPending}>
                {create.isPending ? "Posting…" : "Post question"}
              </Button>
              <Button asChild variant="ghost">
                <Link to="/forum">Cancel</Link>
              </Button>
              <span className="text-caption text-muted">You appear as a random handle. Emails and phone numbers are removed.</span>
            </div>
          </div>
        </form>
        <Tips />
      </div>
    </div>
  );
}
