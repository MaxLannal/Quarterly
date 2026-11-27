import { useId, useState } from "react";
import { buttonVariants } from "@/components/ui/button";
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
    <section aria-labelledby={`${inputId}-title`} className="dash-guide dash-guide-float flex h-full flex-col p-6 text-on-dark sm:p-7">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <GuideMark size={14} className="dash-guide-star text-primary" />
          <h2 id={`${inputId}-title`} className="mono-label text-on-dark-soft">
            Your guide
          </h2>
        </div>
        {total > 0 && (
          <p className="mono-label tabular-nums text-on-dark-soft">
            {total - left.length} of {total} answered
          </p>
        )}
      </div>
      {!questions ? (
        <div aria-hidden="true" className="mt-6 flex flex-col gap-2">
          <div className="h-7 w-11/12 rounded-md bg-on-dark/10" />
          <div className="h-7 w-3/4 rounded-md bg-on-dark/10" />
        </div>
      ) : !turn || !next ? (
        <div className="mt-6 flex flex-1 flex-col gap-5">
          <p className="font-serif text-[24px] font-light leading-[1.25] text-on-dark sm:text-[27px]">You've answered every question. The planner uses your answers for a first plan; change any of them on the left, or go over them with me.</p>
          <div>
            <button type="button" onClick={() => onOpen()} className={buttonVariants()}>
              Go over my answers
            </button>
          </div>
        </div>
      ) : (
        <div className="mt-6 flex flex-1 flex-col gap-4">
          <p className="font-serif text-[26px] font-light leading-[1.22] tracking-[-0.2px] text-on-dark text-balance sm:text-[30px]">{next.text}</p>
          {next.help && <p className="text-caption text-on-dark-soft">{next.help}</p>}
          <div className="flex flex-wrap gap-2" role="group" aria-label="Quick answers">
            {(multi ? [] : replies).map((q) => (
              <button
                key={q}
                type="button"
                onClick={() => onOpen({ seed: turn, message: q })}
                className={cn("dash-chip dash-chip-button", next.type === "scale" && "w-11 px-0 tabular-nums")}
              >
                {q}
              </button>
            ))}
            {multi && (
              <button type="button" onClick={() => onOpen({ seed: turn })} className="dash-chip dash-chip-button">
                Choose your answers
              </button>
            )}
            <button type="button" onClick={() => onOpen({ seed: turn, message: SKIP })} className="min-h-11 rounded-pill px-4 text-body-sm text-on-dark-soft underline decoration-on-dark/30 underline-offset-4 transition-colors duration-300 hover:text-on-dark">
              {SKIP}
            </button>
          </div>
          <form
            className="mt-auto flex items-center gap-2 rounded-pill bg-black/30 py-1 pl-5 pr-1 shadow-[inset_0_0_0_1px_rgb(255_255_255/0.12),inset_0_1px_3px_rgb(0_0_0/0.35)] transition-shadow duration-300 focus-within:shadow-[inset_0_0_0_1px_var(--color-primary),0_0_0_4px_rgb(255_92_112/0.16)]"
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
            <button type="submit" className="min-h-11 rounded-pill bg-ink px-5 text-button text-canvas shadow-[0_6px_22px_rgb(255_60_90/0.3)] transition-[background-color,box-shadow] duration-300 hover:bg-white hover:shadow-[0_8px_30px_rgb(255_60_90/0.45)]">
              Answer
            </button>
          </form>
          <p className="text-caption text-on-dark-soft">Your guide is an AI and can be wrong. Nothing is saved until you accept it.</p>
        </div>
      )}
    </section>
  );
}
