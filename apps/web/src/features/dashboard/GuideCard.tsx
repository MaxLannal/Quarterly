import { useId, useState, type CSSProperties } from "react";
import { remainingQuestions, type QuestionSet } from "@/features/profile/questions";
import { cn } from "@/lib/utils";
import type { Profile, TurnEvent } from "./api";
import { questionTurn, SKIP } from "./logic";
import { GuideMark } from "./parts";

/**
 * The dashboard agent on the dashboard (Issue #16): the next General Information question it
 * would ask, read from the question file (no AI call while the page loads), with its options as
 * buttons and a one-line box for a typed answer. Every answer opens the immersive guide, which
 * sends it to the agent. Once every question is answered it offers to go over them again.
 */
export function GuideCard({ profile, questions, onOpen }: { profile: Profile; questions: QuestionSet | undefined; onOpen: (options?: { seed?: TurnEvent | null; message?: string }) => void }) {
  const inputId = useId();
  const [draft, setDraft] = useState("");
  const left = remainingQuestions(questions, profile);
  const next = left[0];
  const total = (questions?.questions ?? []).filter((q) => q.step === 2).length;
  const turn = next ? questionTurn(next, total ? (total - left.length) / total : 0) : null;
  const replies = turn ? turn.quick_replies.filter((q) => q !== SKIP) : [];
  const multi = next?.type === "multi";

  return (
    <section aria-labelledby={`${inputId}-title`} className="relative isolate h-full overflow-hidden rounded-[22px] bg-surface-dark p-4 text-on-dark sm:p-5">
      <div aria-hidden="true" className="orb -right-24 -top-24 size-72" style={{ "--orb-color": "var(--color-primary)" } as CSSProperties} />
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <GuideMark size={16} className="text-primary" />
          <h2 id={`${inputId}-title`} className="text-caption-uppercase uppercase text-on-dark-soft">
            Your guide
          </h2>
        </div>
        {total > 0 && (
          <p className="text-caption tabular-nums text-on-dark-soft">
            {total - left.length} of {total} answered
          </p>
        )}
      </div>
      {!questions ? (
        <div aria-hidden="true" className="mt-3 flex flex-col gap-2">
          <div className="h-7 w-11/12 rounded-md bg-on-dark/10" />
          <div className="h-7 w-3/4 rounded-md bg-on-dark/10" />
        </div>
      ) : !turn || !next ? (
        <div className="mt-3 flex flex-col gap-4">
          <p className="font-serif text-[21px] font-light leading-[1.25] text-on-dark sm:text-[23px]">You've answered every question. The planner uses your answers for a first plan; change any of them on the left, or go over them with me.</p>
          <div>
            <button type="button" onClick={() => onOpen()} className="min-h-11 rounded-pill bg-primary px-5 text-button text-on-primary hover:bg-primary-hover">
              Go over my answers
            </button>
          </div>
        </div>
      ) : (
        <div className="mt-3 flex flex-col gap-3">
          <p className="font-serif text-[21px] font-light leading-[1.3] text-on-dark sm:text-[23px]">{next.text}</p>
          {next.help && <p className="text-caption text-on-dark-soft">{next.help}</p>}
          <div className="flex flex-wrap gap-2" role="group" aria-label="Quick answers">
            {(multi ? [] : replies).map((q) => (
              <button
                key={q}
                type="button"
                onClick={() => onOpen({ seed: turn, message: q })}
                className={cn("min-h-11 rounded-pill border border-on-dark/25 px-4 text-body-sm text-on-dark hover:bg-on-dark/10", next.type === "scale" && "w-11 px-0 tabular-nums")}
              >
                {q}
              </button>
            ))}
            {multi && (
              <button type="button" onClick={() => onOpen({ seed: turn })} className="min-h-11 rounded-pill border border-on-dark/25 px-4 text-body-sm text-on-dark hover:bg-on-dark/10">
                Choose your answers
              </button>
            )}
            <button type="button" onClick={() => onOpen({ seed: turn, message: SKIP })} className="min-h-11 rounded-pill px-4 text-body-sm text-on-dark-soft underline underline-offset-4 hover:bg-on-dark/10 hover:text-on-dark">
              {SKIP}
            </button>
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
              Your answer
            </label>
            <input id={inputId} value={draft} maxLength={2000} onChange={(e) => setDraft(e.target.value)} placeholder="Or type your answer…" className="min-h-11 min-w-0 flex-1 bg-transparent text-body-sm text-on-dark outline-none placeholder:text-on-dark-soft" />
            <button type="submit" className="min-h-11 rounded-pill bg-on-dark px-4 text-button text-ink hover:bg-on-dark-soft">
              Answer
            </button>
          </form>
          <p className="text-caption text-on-dark-soft">Your guide is an AI and can be wrong. Nothing is saved until you accept it.</p>
        </div>
      )}
    </section>
  );
}
