import { useId, useState } from "react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Avatar } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { Select } from "@/components/ui/input";
import { ProgramChecklist } from "@/features/programs/ProgramPicker";
import type { Profile } from "./api";
import { CAMPUS_YEAR, memberSince, programHref } from "./logic";
import { DashCard, SaveStatus, useSaver } from "./parts";

const YEARS = [2026, 2027, 2028, 2029, 2030, 2031, 2032];

/** Who the student is on Quarterly: name, email (from the account), class year, programs. */
export function IdentityCard({ profile }: { profile: Profile }) {
  const saver = useSaver();
  const yearId = useId();
  const [picking, setPicking] = useState(false);
  const [selected, setSelected] = useState<string[]>(profile.intended_programs);
  const years = profile.class_year && !YEARS.includes(profile.class_year) ? [...YEARS, profile.class_year].sort() : YEARS;
  return (
    <DashCard kicker="You" title="Identity" status={<SaveStatus state={saver.state} />} className="h-full">
      <div className="flex items-center gap-4">
        <Avatar name={profile.username} className="size-14 text-title-md" />
        <div className="min-w-0">
          <p className="truncate text-title-sm text-ink">{profile.username}</p>
          <p className="truncate text-body-sm text-body">{profile.email}</p>
          <p className="text-caption text-muted">{capitalize(memberSince(profile.member_since))}</p>
        </div>
      </div>
      <dl className="mt-6 flex flex-col gap-5">
        <div className="flex flex-col gap-1.5">
          <dt>
            <label htmlFor={yearId} className="text-caption-uppercase uppercase text-muted">
              Class year
            </label>
          </dt>
          <dd>
            <Select
              id={yearId}
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
          </dd>
        </div>
        <div className="flex flex-col gap-2">
          <dt className="text-caption-uppercase uppercase text-muted">Programs you're considering</dt>
          <dd className="flex flex-col items-start gap-2">
            {profile.programs.length > 0 ? (
              <ul className="flex flex-col gap-1">
                {profile.programs.map((p) => (
                  <li key={p.id}>
                    <Link to={programHref(p.id)} className="inline-flex min-h-11 items-center text-body-sm text-primary underline underline-offset-2 hover:text-primary-hover">
                      {p.name}
                    </Link>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-body-sm text-muted">None yet. Undecided is a fine place to start.</p>
            )}
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setSelected(profile.intended_programs);
                setPicking(true);
              }}
            >
              {profile.programs.length ? "Change programs" : "Choose programs"}
            </Button>
          </dd>
        </div>
      </dl>
      <p className="mt-5 text-caption text-muted">Only you see this page. Your email stays in your account and is never shown to anyone else.</p>
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
    </DashCard>
  );
}

function capitalize(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}
