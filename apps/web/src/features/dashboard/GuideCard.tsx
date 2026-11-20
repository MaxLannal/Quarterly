import { useQuery } from "@tanstack/react-query";
import { useId, useState, type CSSProperties } from "react";
import { Link } from "react-router-dom";
import { cn } from "@/lib/utils";
import { streamInterview, type Profile, type TurnEvent } from "./api";
import { isDraftChip } from "./GuideOverlay";
import { courseHref, filledTopics } from "./logic";
import { GuideMark } from "./parts";

/** The welcome-back greeting (the server caches it per profile; the page asks once a day). */
function useWelcome(profile: Profile, enabled: boolean) {
  return useQuery({
    queryKey: ["me", "welcome", profile.username, profile.updated_day],
    queryFn: async ({ signal }) => {
      let turn: TurnEvent | null = null;
      for await (const event of streamInterview({ mode: "welcome_back", history: [] }, signal)) {
        if (event.type === "turn") turn = event;
        else if (event.type === "error") throw new Error(event.message);
      }
      return turn;
    },
    enabled,
    staleTime: Infinity,
    retry: false,
  });
}

/**
 * The guide on the dashboard: a first invitation for a new student, then (once they told it
 * something) a greeting that remembers them ("Last time you told me…") with its quick replies and
 * a one-line composer. Everything opens the immersive guide.
 */
export function GuideCard({
  profile,
  onOpen,
  onDraftRoutes,
}: {
  profile: Profile;
  onOpen: (options?: { seed?: TurnEvent | null; message?: string }) => void;
  onDraftRoutes: () => void;
}) {
  const known = filledTopics(profile).length > 0 || profile.interview.turns.length > 0;
  const welcome = useWelcome(profile, known);
  const inputId = useId();
  const [draft, setDraft] = useState("");
  const turn = welcome.data ?? null;

  function chip(text: string) {
    if (isDraftChip(text)) onDraftRoutes();
    else if (/^(keep going|continue)/i.test(text)) onOpen();
    else onOpen({ seed: turn, message: text });
  }

  return (
    <section aria-labelledby={`${inputId}-title`} className="relative isolate h-full overflow-hidden rounded-xxl bg-surface-dark p-6 text-on-dark sm:p-8">
      <div aria-hidden="true" className="orb -right-24 -top-24 size-72" style={{ "--orb-color": "var(--color-primary)" } as CSSProperties} />
      <div className="flex items-center gap-2">
        <GuideMark size={16} className={cn("text-primary", welcome.isFetching && "dash-thinking")} />
        <h2 id={`${inputId}-title`} className="text-caption-uppercase uppercase text-on-dark-soft">
          Your guide
        </h2>
      </div>
      {!known ? (
        <div className="mt-4 flex flex-col gap-5">
          <p className="font-display text-[26px] font-light leading-[1.2] text-on-dark sm:text-[32px]">
            Hi, I'm your guide. Give me ten minutes, one question at a time, and I'll draw a portrait of what you want from <em className="italic text-[color:var(--color-on-inverse-soft)]">UChicago</em>.
          </p>
          <div className="flex flex-wrap gap-2">
            <button type="button" onClick={() => onOpen()} className="min-h-11 rounded-pill bg-primary px-5 text-button text-on-primary hover:bg-primary-hover">
              Start the conversation
            </button>
          </div>
        </div>
      ) : (
        <div className="mt-4 flex flex-col gap-5">
          {welcome.isLoading ? (
            <div aria-hidden="true" className="flex flex-col gap-2">
              <div className="h-7 w-11/12 rounded-md bg-on-dark/10" />
              <div className="h-7 w-3/4 rounded-md bg-on-dark/10" />
            </div>
          ) : turn ? (
            <p className="font-display text-[22px] font-light leading-[1.3] text-on-dark sm:text-[26px]">{turn.text}</p>
          ) : (
            <p className="font-display text-[22px] font-light leading-[1.3] text-on-dark sm:text-[26px]">Welcome back. Want to pick up where we left off, or draft a few routes?</p>
          )}
          {turn && turn.courses.length > 0 && (
            <ul className="flex flex-wrap gap-2">
              {turn.courses.map((c) => (
                <li key={c.code}>
                  <Link to={courseHref(c.code)} className="inline-flex min-h-11 items-center gap-2 rounded-pill border border-on-dark/25 px-3 text-caption text-on-dark hover:bg-on-dark/10">
                    <span className="uppercase tabular-nums text-on-dark-soft">{c.code}</span> {c.title}
                  </Link>
                </li>
              ))}
            </ul>
          )}
          <div className="flex flex-wrap gap-2">
            {(turn?.quick_replies.length ? turn.quick_replies : ["Keep going", "Draft my routes"]).map((q) => (
              <button
                key={q}
                type="button"
                onClick={() => chip(q)}
                className={cn("min-h-11 rounded-pill border px-4 text-body-sm", isDraftChip(q) ? "border-primary bg-primary text-on-primary hover:bg-primary-hover" : "border-on-dark/25 text-on-dark hover:bg-on-dark/10")}
              >
                {q}
              </button>
            ))}
          </div>
          <form
            className="flex items-center gap-2 rounded-pill border border-on-dark/20 bg-surface-dark-elevated py-1 pl-4 pr-1 focus-within:border-on-dark/50"
            onSubmit={(e) => {
              e.preventDefault();
              if (!draft.trim()) return;
              onOpen({ seed: turn, message: draft.trim() });
              setDraft("");
            }}
          >
            <label htmlFor={inputId} className="sr-only">
              Tell your guide something
            </label>
            <input id={inputId} value={draft} maxLength={2000} onChange={(e) => setDraft(e.target.value)} placeholder="Tell your guide something new…" className="min-h-11 min-w-0 flex-1 bg-transparent text-body-sm text-on-dark outline-none placeholder:text-on-dark-soft" />
            <button type="submit" className="min-h-11 rounded-pill bg-on-dark px-4 text-button text-ink hover:bg-on-dark-soft">
              Tell
            </button>
          </form>
          <p className="text-caption text-on-dark-soft">{turn?.fallback ? "Your guide is running without the AI right now." : "Your guide is an AI and can be wrong."}</p>
        </div>
      )}
    </section>
  );
}
