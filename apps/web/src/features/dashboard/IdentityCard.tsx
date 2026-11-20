import { useId, useState } from "react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Select } from "@/components/ui/input";
import { ProgramChecklist } from "@/features/programs/ProgramPicker";
import type { Profile } from "./api";
import { CAMPUS_YEAR, memberSince, programHref } from "./logic";
import { SaveStatus, useSaver } from "./parts";

const YEARS = [2026, 2027, 2028, 2029, 2030, 2031, 2032];

/**
 * The editable basics of the top block: class year and the programs the student is considering
 * (the name, email and member-since line are shown above them by the block itself).
 */
export function IdentityFields({ profile }: { profile: Profile }) {
  const saver = useSaver();
  const yearId = useId();
  const [picking, setPicking] = useState(false);
  const [selected, setSelected] = useState<string[]>(profile.intended_programs);
  const years = profile.class_year && !YEARS.includes(profile.class_year) ? [...YEARS, profile.class_year].sort() : YEARS;
  return (
    <div className="grid gap-3 sm:grid-cols-[minmax(0,13rem)_minmax(0,1fr)]">
      <div className="flex flex-col gap-1">
        <div className="flex items-center justify-between gap-2">
          <label htmlFor={yearId} className="text-[12px] font-bold uppercase tracking-[0.08em] text-muted">
            Class year
          </label>
          <SaveStatus state={saver.state} />
        </div>
        <Select
          id={yearId}
          compact
          value={profile.class_year ?? ""}
          onChange={(e) => saver.save({ class_year: e.target.value ? Number(e.target.value) : null })}
        >
          <option value="">Not sure yet</option>
          {years.map((y) => (
            <option key={y} value={y}>
              Class of {y}
            </option>
          ))}
        </Select>
      </div>
      <div className="flex min-w-0 flex-col gap-1">
        <p className="text-[12px] font-bold uppercase tracking-[0.08em] text-muted">Programs you're considering</p>
        <div className="flex flex-wrap items-center gap-x-3 gap-y-0">
          {profile.programs.length > 0 ? (
            profile.programs.map((p) => (
              <Link key={p.id} to={programHref(p.id)} className="inline-flex min-h-11 items-center text-body-sm text-primary underline underline-offset-2 hover:text-primary-hover">
                {p.name}
              </Link>
            ))
          ) : (
            <span className="text-body-sm text-muted">None yet; undecided is fine.</span>
          )}
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              setSelected(profile.intended_programs);
              setPicking(true);
            }}
          >
            {profile.programs.length ? "Change" : "Choose programs"}
          </Button>
        </div>
      </div>
      <Dialog open={picking} onClose={() => setPicking(false)} title="Programs you're considering" description="Quarterly holds some of the College's programs; pick any that interest you. You can change this any time.">
        <div className="flex max-h-[55vh] flex-col gap-4 overflow-y-auto pr-1">
          <ProgramChecklist catalogYear={CAMPUS_YEAR} selected={selected} onChange={setSelected} />
        </div>
        <div className="mt-5 flex justify-end gap-2">
          <Button variant="ghost" onClick={() => setPicking(false)}>
            Cancel
          </Button>
          <Button
            onClick={() => {
              saver.save({ intended_programs: selected.slice(0, 8) });
              setPicking(false);
            }}
          >
            Save programs
          </Button>
        </div>
      </Dialog>
    </div>
  );
}

/** "Member since …", with a capital letter. */
export function memberLine(profile: Profile): string {
  return capitalize(memberSince(profile.member_since));
}

function capitalize(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}
