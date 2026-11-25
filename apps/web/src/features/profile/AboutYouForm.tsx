import { useState } from "react";
import { useCatalogYears } from "@/api/hooks";
import { Button } from "@/components/ui/button";
import { ChoiceRow } from "@/components/ui/input";
import { Spinner } from "@/components/ui/misc";
import { FormError, StepHeading } from "@/features/auth/ui";
import { errorText, usePatchProfile } from "@/features/dashboard/api";
import { defaultCatalogYear } from "@/features/planner/terms";
import { AnswerControl } from "./AnswerControls";
import { applies, firstYearEntry, graduationFor, useQuestions, type Profile, type ProfilePatch, type Question } from "./questions";

/** The registration form's answers (the step-1 fields of the student record). */
export interface AboutDraft {
  class_year: number | null;
  expected_graduation_term: string | null;
  intended_programs: string[];
  entry_term: string | null;
  entry_year_level: number | null;
  credits: Profile["credits"];
  taken_courses: Profile["taken_courses"];
}

export const EMPTY_ABOUT: AboutDraft = {
  class_year: null,
  expected_graduation_term: null,
  intended_programs: [],
  entry_term: null,
  entry_year_level: null,
  credits: [],
  taken_courses: [],
};

/**
 * The patch the form saves: a first-year starts in the Autumn four years before the class year,
 * in the first year; a transfer or later-year student sends what they entered, with credits and
 * taken courses. Tested in questions.test.ts.
 */
export function aboutPatch(d: AboutDraft, transferOrLater: boolean): ProfilePatch {
  const base: ProfilePatch = {
    class_year: d.class_year,
    expected_graduation_term: d.expected_graduation_term,
    intended_programs: d.intended_programs,
  };
  if (!transferOrLater) {
    return { ...base, entry_term: d.class_year ? firstYearEntry(d.class_year) : null, entry_year_level: 1 };
  }
  return {
    ...base,
    entry_term: d.entry_term,
    entry_year_level: d.entry_year_level,
    credits: d.credits.map((c) => ({ kind: c.kind, label: c.label, maps_to: c.maps_to ?? null, units: c.units ?? 0 })),
    taken_courses: d.taken_courses.map((c) => ({ course: c.course, term: c.term, status: c.status ?? "completed", grade: c.grade ?? null, grading: c.grading ?? "letter", units: c.units ?? null, locked: c.locked ?? false })),
  };
}

/** What the form refuses to save, or null. */
export function aboutProblem(d: AboutDraft, transferOrLater: boolean): string | null {
  if (!d.class_year) return "Choose your class year.";
  if (transferOrLater && !d.entry_term) return "Choose the quarter you started at UChicago.";
  if (transferOrLater && !d.entry_year_level) return "Choose the year you started in.";
  return null;
}

/**
 * Step 4 of sign-up, "About you" (Issue #16 D1): the step-1 questions of the question file
 * (class year, expected graduation, intended programs) and, behind "I transferred, or I am not
 * in my first year.", the first quarter, the year started in, credits and taken courses. Saved
 * with one PATCH /me/profile. Not a <form>: the credits editor nests a form of its own.
 */
export function AboutYouForm({ onSaved }: { onSaved: () => void }) {
  const questions = useQuestions();
  const years = useCatalogYears();
  const catalogYear = defaultCatalogYear(years.data?.map((y) => y.id));
  const patch = usePatchProfile();
  const [draft, setDraft] = useState<AboutDraft>(EMPTY_ABOUT);
  const [graduationTouched, setGraduationTouched] = useState(false);
  const [transfer, setTransfer] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (questions.isLoading) return <Spinner label="Loading the questions" />;
  if (questions.error || !questions.data) {
    return (
      <>
        <FormError message="The questions could not be loaded." />
        <Button type="button" variant="outline" onClick={() => void questions.refetch()}>
          Try again
        </Button>
      </>
    );
  }
  const set = questions.data;
  const step1 = set.questions.filter((q) => q.step === 1);
  const isTransferQuestion = (q: Question) => !!q.when && "transfer_or_later" in q.when;

  function change(q: Question, value: unknown) {
    setDraft((d) => {
      const next = { ...d, [q.field]: value } as AboutDraft;
      if (q.field === "class_year" && typeof value === "number" && !graduationTouched) next.expected_graduation_term = graduationFor(value);
      return next;
    });
    if (q.field === "expected_graduation_term") setGraduationTouched(true);
  }

  function control(q: Question) {
    return (
      <AnswerControl
        key={q.id}
        question={q}
        set={set}
        value={(draft as unknown as Record<string, unknown>)[q.field] ?? null}
        onChange={(v) => change(q, v)}
        classYear={draft.class_year}
        catalogYear={catalogYear}
        layout="form"
      />
    );
  }

  function save() {
    const problem = aboutProblem(draft, transfer);
    if (problem) return setError(problem);
    setError(null);
    patch.mutate(aboutPatch(draft, transfer), { onSuccess: onSaved, onError: (e) => setError(errorText(e, "Your answers")) });
  }

  return (
    <div className="flex flex-col gap-5">
      <StepHeading>About you</StepHeading>
      <p className="text-body-sm text-body">The planner uses these answers to set up your plan. You can change them at any time on your dashboard.</p>
      {step1.filter((q) => !isTransferQuestion(q)).map(control)}
      <ChoiceRow
        type="checkbox"
        className="font-medium"
        checked={transfer}
        onChange={(e) => {
          const on = e.target.checked;
          setTransfer(on);
          if (on && draft.class_year) setDraft((d) => ({ ...d, entry_term: d.entry_term ?? `${(d.class_year ?? 0) - 3}-AU`, entry_year_level: d.entry_year_level ?? 2 }));
        }}
      >
        I transferred, or I am not in my first year.
      </ChoiceRow>
      {transfer && (
        <div className="flex flex-col gap-5 rounded-[22px] border border-hairline bg-canvas-soft p-4">
          {step1.filter((q) => isTransferQuestion(q) && applies(q, draft as Partial<Profile>, true)).map(control)}
        </div>
      )}
      <FormError message={error} />
      <Button type="button" disabled={patch.isPending} onClick={save}>
        {patch.isPending ? "Saving…" : "Save and continue"}
      </Button>
    </div>
  );
}
