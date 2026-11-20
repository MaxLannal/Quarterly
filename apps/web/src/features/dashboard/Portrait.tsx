import { useEffect, useId, useRef, useState } from "react";
import { Textarea } from "@/components/ui/input";
import { CloseIcon } from "@/components/ui/icons";
import { cn } from "@/lib/utils";
import type { Profile, Topic } from "./api";
import { Constellation } from "./Constellation";
import { HorizonGlyph } from "./HorizonGlyph";
import { GOAL_LABELS, WORKLOAD_LABELS, withItem, withoutItem, type Goal, type ListField, type Workload } from "./logic";
import { AskGuide, ChipField, DashCard, SaveStatus, useSaver } from "./parts";

type Ask = (topic: Topic) => void;

function useListSaver(field: ListField) {
  const saver = useSaver();
  return {
    ...saver,
    change: (items: string[]) => saver.save({ [field]: items }),
  };
}

/** The portrait's headline and summary, written by the guide and kept by the student. */
export function PortraitHeader({ profile, onAsk }: { profile: Profile; onAsk: Ask }) {
  const { headline, summary, themes } = profile.portrait;
  if (!headline && !summary) {
    return (
      <div className="flex flex-col gap-2">
        <p className="font-display text-display-sm text-ink sm:text-display-md">
          Your portrait is still <em className="text-primary">a sketch</em>.
        </p>
        <p className="max-w-reading text-body-md text-body">
          Talk with your guide for a few minutes. At the end it writes a short portrait of you; keep it, and it stays here.
        </p>
        <div>
          <button type="button" onClick={() => onAsk("interests")} className="inline-flex min-h-11 items-center rounded-pill px-1 text-button text-primary underline underline-offset-4">
            Start the conversation
          </button>
        </div>
      </div>
    );
  }
  return (
    <figure className="flex flex-col gap-3">
      <blockquote className="font-display text-[32px] font-extrabold leading-[1.08] tracking-[-1px] text-ink sm:text-[44px]">
        <span aria-hidden="true" className="text-primary">“</span>
        {headline}
        <span aria-hidden="true" className="text-primary">”</span>
      </blockquote>
      {summary && <p className="max-w-reading text-body-md text-body">{summary}</p>}
      {themes.length > 0 && (
        <ul className="flex flex-wrap gap-2" aria-label="Themes">
          {themes.map((t) => (
            <li key={t} className="rounded-pill bg-primary-wash px-3 py-1 text-caption font-medium text-primary">
              {t}
            </li>
          ))}
        </ul>
      )}
      <figcaption className="text-caption text-muted">Written by your guide, an AI, from what you told it; it can be wrong. Kept by you.</figcaption>
    </figure>
  );
}

export function InterestsCard({ profile, onAsk }: { profile: Profile; onAsk: Ask }) {
  const s = useListSaver("interests");
  return (
    <DashCard id="interests" kicker="What pulls at you" title="Interests" status={<SaveStatus state={s.state} />}>
      <div className="flex flex-col gap-4">
        {profile.interests.length === 0 && <AskGuide onAsk={() => onAsk("interests")}>Physics, film, political theory? Name a few and they start orbiting here.</AskGuide>}
        <ChipField
          label="Interests"
          items={profile.interests}
          onChange={s.change}
          placeholder="Add an interest"
          suggestions={["Physics", "Philosophy", "Economics", "Computer science", "Film", "Biology"]}
          renderItems={(items, remove) => items.length > 0 && <Constellation items={items} onRemove={remove} center={profile.username} />}
        />
      </div>
    </DashCard>
  );
}

export function ResearchCard({ profile, onAsk }: { profile: Profile; onAsk: Ask }) {
  const s = useListSaver("research_areas");
  return (
    <DashCard id="research" kicker="Questions to carry" title="Research areas" status={<SaveStatus state={s.state} />}>
      <div className="flex flex-col gap-4">
        {profile.research_areas.length === 0 && <AskGuide onAsk={() => onAsk("research")}>A lab, an archive, a dataset: what would you like to work on with a professor someday?</AskGuide>}
        <ChipField label="Research areas" items={profile.research_areas} onChange={s.change} placeholder="Add a research area" />
      </div>
    </DashCard>
  );
}

const GOAL_SENTENCES: Record<Goal, (topics: string) => string> = {
  pass: () => "We'll keep your Core efficient: one well-placed Humanities sequence, then back to what you came for.",
  balance: (t) => `One Humanities sequence you'll like${t ? `, leaning toward ${t}` : ""}, and room for one more course if it calls.`,
  enjoy: (t) => (t ? `We'll look for the Core sequences and electives about ${t}.` : "Tell me which topics, and we'll look for the sequences and electives about them."),
  deep: (t) => `Humanities as a second home${t ? `, around ${t}` : ""}: sequences, electives, maybe a minor.`,
};
/** Compass points: the needle's angle for each goal. */
const GOAL_ANGLES: Record<Goal, number> = { pass: 0, balance: 90, enjoy: 180, deep: 270 };
const GOALS = Object.keys(GOAL_LABELS) as Goal[];

/** The humanities compass: what the student wants from the Humanities Core, and which topics. */
export function HumanitiesCard({ profile, onAsk }: { profile: Profile; onAsk: Ask }) {
  const goalSaver = useSaver();
  const topics = useListSaver("humanities_topics");
  const groupId = useId();
  const goal = profile.humanities_goal as Goal | null | undefined;
  const topicText = joinWords(profile.humanities_topics.map((t) => t.toLowerCase()));
  return (
    <DashCard
      id="humanities"
      kicker="The Core, your way"
      title={
        <>
          The humanities <em className="italic text-primary">compass</em>
        </>
      }
      status={<SaveStatus state={goalSaver.state.kind !== "idle" ? goalSaver.state : topics.state} />}
    >
      <div className="grid gap-6 md:grid-cols-[200px_minmax(0,1fr)] md:items-center">
        <Compass goal={goal ?? null} />
        <div className="flex min-w-0 flex-col gap-4">
          <fieldset>
            <legend id={groupId} className="mb-2 text-body-sm text-body">
              What do you want from Humanities in the Core?
            </legend>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              {GOALS.map((g) => (
                <label
                  key={g}
                  className={cn(
                    "flex min-h-11 cursor-pointer items-center gap-2 rounded-pill border px-4 text-body-sm transition-colors has-[:focus-visible]:outline has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-primary",
                    goal === g ? "border-primary bg-primary text-on-primary" : "border-hairline-strong bg-surface-card text-ink hover:bg-surface-strong",
                  )}
                >
                  <input type="radio" name={`${groupId}-goal`} value={g} checked={goal === g} onChange={() => goalSaver.save({ humanities_goal: g })} className="sr-only" />
                  <span aria-hidden="true" className={cn("inline-block size-2 rounded-pill", goal === g ? "bg-on-primary" : "bg-hairline-strong")} />
                  {GOAL_LABELS[g]}
                </label>
              ))}
            </div>
          </fieldset>
          {goal ? (
            <p className="font-display text-title-md italic text-body-strong">{GOAL_SENTENCES[goal](topicText)}</p>
          ) : (
            <AskGuide onAsk={() => onAsk("humanities")}>Just to pass, or to enjoy something specific? Your guide will help you pin it down.</AskGuide>
          )}
          <div>
            <p className="mb-2 text-caption-uppercase uppercase text-muted">Topics you'd enjoy</p>
            <ChipField label="Humanities topics" items={profile.humanities_topics} onChange={topics.change} placeholder="Greek tragedy, film, philosophy of mind…" suggestions={goal && goal !== "pass" ? ["Greek tragedy", "Film", "Philosophy of mind", "Poetry", "Art history"] : []} />
          </div>
          <NoteField label="A note to yourself" field="humanities_note" value={profile.humanities_note ?? ""} placeholder="Anything else about the humanities, in your words" />
        </div>
      </div>
    </DashCard>
  );
}

function Compass({ goal }: { goal: Goal | null }) {
  const angle = goal ? GOAL_ANGLES[goal] : 225;
  return (
    <svg viewBox="0 0 200 200" className="mx-auto w-40 md:w-full" role="img" aria-label={goal ? `Compass pointing to ${GOAL_LABELS[goal]}` : "Compass, no direction yet"}>
      <circle cx="100" cy="100" r="86" fill="var(--color-canvas-soft)" stroke="var(--color-hairline-strong)" />
      <circle cx="100" cy="100" r="66" fill="none" stroke="var(--color-hairline)" strokeDasharray="2 5" />
      {GOALS.map((g) => {
        const a = ((GOAL_ANGLES[g] - 90) * Math.PI) / 180;
        const on = goal === g;
        return (
          <g key={g}>
            <circle cx={100 + Math.cos(a) * 86} cy={100 + Math.sin(a) * 86} r={on ? 6 : 3.5} fill={on ? "var(--color-primary)" : "var(--color-ink)"} opacity={on ? 1 : 0.35} />
            <text x={100 + Math.cos(a) * 52} y={100 + Math.sin(a) * 52 + 4} textAnchor="middle" className={cn("font-sans text-[11px] font-semibold uppercase tracking-wider", on ? "fill-primary" : "fill-muted")}>
              {{ pass: "pass", balance: "balance", enjoy: "enjoy", deep: "deep" }[g]}
            </text>
          </g>
        );
      })}
      <g style={{ transform: `rotate(${angle}deg)`, transformOrigin: "100px 100px", transition: "transform 700ms cubic-bezier(0.2,0.7,0.2,1)" }}>
        <path d="M100 30 L108 100 L100 112 L92 100 Z" fill="var(--color-primary)" opacity={goal ? 1 : 0.35} />
        <path d="M100 170 L106 100 L100 92 L94 100 Z" fill="var(--color-ink)" opacity="0.25" />
      </g>
      <circle cx="100" cy="100" r="5" fill="var(--color-surface-card)" stroke="var(--color-ink)" />
    </svg>
  );
}

/** A free-text field saved when it loses focus (with a quiet "Saved"). */
export function NoteField({ label, field, value, placeholder, rows = 2 }: { label: string; field: "humanities_note" | "career_plans"; value: string; placeholder?: string; rows?: number }) {
  const id = useId();
  const saver = useSaver();
  const [draft, setDraft] = useState(value);
  const last = useRef(value);
  useEffect(() => {
    if (value !== last.current) {
      last.current = value;
      setDraft(value);
    }
  }, [value]);
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center justify-between gap-2">
        <label htmlFor={id} className="text-caption-uppercase uppercase text-muted">
          {label}
        </label>
        <SaveStatus state={saver.state} />
      </div>
      <Textarea
        id={id}
        rows={rows}
        maxLength={1200}
        value={draft}
        placeholder={placeholder}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={() => {
          const next = draft.trim();
          if (next === (value ?? "").trim()) return;
          last.current = next;
          saver.save({ [field]: next || null });
        }}
      />
    </div>
  );
}

export function CareerCard({ profile, onAsk }: { profile: Profile; onAsk: Ask }) {
  const paths = useListSaver("career_paths");
  const empty = !profile.career_plans && profile.career_paths.length === 0;
  return (
    <DashCard id="career" kicker="After the College" title="Career" status={<SaveStatus state={paths.state} />}>
      <div className="flex flex-col gap-4">
        {empty && <AskGuide onAsk={() => onAsk("career")}>A direction is plenty. Research, a startup, medicine, public service…</AskGuide>}
        <NoteField label="Your plans, in your words" field="career_plans" value={profile.career_plans ?? ""} placeholder="Where do you picture yourself after the College?" rows={3} />
        <div>
          <p className="mb-2 text-caption-uppercase uppercase text-muted">Paths</p>
          <ChipField label="Career paths" items={profile.career_paths} onChange={paths.change} placeholder="Add a path" suggestions={["Research / PhD", "Tech", "Medicine", "Law", "Public service", "Finance"]} />
        </div>
      </div>
    </DashCard>
  );
}

export function HorizonsCard({ profile, onAsk }: { profile: Profile; onAsk: Ask }) {
  const s = useListSaver("future_domains");
  const [undo, setUndo] = useState<string | null>(null);
  return (
    <DashCard
      id="horizons"
      kicker="Ten years out"
      title={
        <>
          Your <em className="italic text-primary">horizons</em>
        </>
      }
      status={<SaveStatus state={s.state} />}
    >
      <div className="flex flex-col gap-5">
        {profile.future_domains.length === 0 ? (
          <AskGuide onAsk={() => onAsk("future")}>Which fields do you want to head toward? Quantum computing, climate, AI and society…</AskGuide>
        ) : (
          <ul className="grid grid-cols-1 gap-3 min-[480px]:grid-cols-2 lg:grid-cols-4">
            {profile.future_domains.map((d, i) => (
              <li key={d} className="dash-rise group relative flex items-center gap-4 rounded-xl border border-hairline bg-surface-card p-3 lg:flex-col lg:items-start" style={{ ["--delay" as string]: `${i * 60}ms` }}>
                <HorizonGlyph word={d} size={84} />
                <p className="min-w-0 flex-1 pr-8 font-display text-title-md leading-snug text-ink">{d}</p>
                <button
                  type="button"
                  aria-label={`Remove ${d}`}
                  onClick={() => {
                    s.change(withoutItem(profile.future_domains, d));
                    setUndo(d);
                  }}
                  className="absolute right-1 top-1 inline-flex size-11 items-center justify-center rounded-pill text-muted hover:text-ink"
                >
                  <CloseIcon size={14} />
                </button>
              </li>
            ))}
          </ul>
        )}
        {undo && (
          <p role="status" className="flex items-center gap-2 text-caption text-muted">
            Removed “{undo}”.
            <button
              type="button"
              className="min-h-11 rounded-pill px-2 font-medium text-primary underline underline-offset-2"
              onClick={() => {
                s.change(withItem(profile.future_domains, undo));
                setUndo(null);
              }}
            >
              Undo
            </button>
          </p>
        )}
        <ChipField label="Future domains" items={profile.future_domains} onChange={s.change} placeholder="Add a field you're heading toward" renderItems={() => null} suggestions={["Quantum computing", "Climate", "AI and society", "Global health"]} />
      </div>
    </DashCard>
  );
}

const WORKLOAD_TEXT: Record<Workload, string> = {
  light: "Room to breathe: three courses most quarters.",
  balanced: "A steady four, with lighter quarters when you need them.",
  intense: "Full quarters and the hardest sequences early.",
};

export function ConstraintsCard({ profile, onAsk }: { profile: Profile; onAsk: Ask }) {
  const load = useSaver();
  const items = useListSaver("constraints");
  const groupId = useId();
  const workload = profile.workload as Workload | null | undefined;
  return (
    <DashCard id="constraints" kicker="Plan around" title="Workload & constraints" status={<SaveStatus state={load.state.kind !== "idle" ? load.state : items.state} />}>
      <div className="flex flex-col gap-4">
        <fieldset>
          <legend className="mb-2 text-body-sm text-body">How heavy should your quarters feel?</legend>
          <div className="inline-flex flex-wrap rounded-pill border border-hairline-strong bg-surface-card p-1">
            {(Object.keys(WORKLOAD_LABELS) as Workload[]).map((w) => (
              <label key={w} className={cn("flex min-h-11 cursor-pointer items-center rounded-pill px-4 text-body-sm has-[:focus-visible]:outline has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-primary", workload === w ? "bg-ink text-on-dark" : "text-ink hover:bg-surface-strong")}>
                <input type="radio" className="sr-only" name={`${groupId}-load`} value={w} checked={workload === w} onChange={() => load.save({ workload: w })} />
                {WORKLOAD_LABELS[w]}
              </label>
            ))}
          </div>
          {workload && <p className="mt-2 text-body-sm text-muted">{WORKLOAD_TEXT[workload]}</p>}
        </fieldset>
        {!workload && profile.constraints.length === 0 && <AskGuide onAsk={() => onAsk("constraints")}>A job, a sport, study abroad, a double major: anything to plan around?</AskGuide>}
        <ChipField label="Constraints" items={profile.constraints} onChange={items.change} placeholder="Add something to plan around" suggestions={["Part-time job", "Varsity sport", "Study abroad", "Pre-med"]} />
      </div>
    </DashCard>
  );
}

function joinWords(items: string[]): string {
  if (items.length <= 1) return items.join("");
  return `${items.slice(0, -1).join(", ")} and ${items[items.length - 1]}`;
}
