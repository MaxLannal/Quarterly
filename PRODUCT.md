# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

All UChicago College undergraduates, with no single group favoured (confirmed by Richard, 2026-11-16). The incoming first-year with no plan is the main way in: "Start planning" is the front door. The groups the product serves (docs/SPEC.md "Users"):

- **Incoming first-year:** no credits, vague interests; needs a sensible first quarter and a few candidate paths.
- **Transfer student:** transfer credits, fewer quarters left; needs to know which credits count and what is still possible (e.g. Bx/MS).
- **Declared ambitious major:** e.g. CS + Math aiming for Bx/MS or a PhD; needs hard-course sequencing, overload checks and application timing.
- **Goal-constrained student:** pre-med, athlete, study abroad, early graduation; needs plans that respect fixed quarters and loads.
- **Forum reader and writer:** choosing between instructors or sections; needs honest, comparable experiences.

Right now the people using it are Richard and a few testers. A public launch to UChicago students comes later, after the catalog hand-check (confirmed by Richard, 2026-11-16).

## Product Purpose

Quarterly answers two questions UChicago's official tools leave open: "what should I take, given what I want?" and "what is this class actually like with this professor?" It has two halves of equal weight (confirmed by Richard, 2026-11-16) that share one course database:

- **Quarterly Planner:** takes a student from "I don't know my first class" to a full, goal-aware four-year plan. An AI agent proposes plans; a deterministic verifier proves each one.
- **Quarterly Forum:** one page per course × instructor with anonymous, Reddit-style threads and structured ratings. The ratings feed each course's workload, difficulty and intellectual-intensity scores, which the planner uses.

Success: a student ends with a plan on the four-year grid that the verifier marks valid, or a precise list of what is still wrong; and forum readers can compare instructors honestly.

## Positioning

**Plans are proven, not suggested.** Every plan, whether a student or the agent made it, is checked by a deterministic verifier that issues a certificate: which course satisfies which requirement, which earlier course satisfies each prerequisite. The product rule is "agents propose, code disposes": AI reads messy sources and talks to students; deterministic code decides what is true and what gets saved.

Supporting differences (docs/SPEC.md): goals are first-class (career-wide or per quarter, e.g. "Spring of 3rd year abroad", "Winter at most 45 hours a week"); course attributes are explicit, sourced and carry a confidence level; the forum is structured per course × instructor, so its ratings are comparable.

The College's official My Planner gives a layout and a degree audit but does not recommend courses. Student-built rating sites come and go and are not tied to a verified plan.

## Operating Context

- UChicago's quarter system: Autumn, Winter, Spring, and optional Summer; a degree needs 4200 units (the Core, at least one major, electives); full-time is 300 or 400 units a quarter.
- Students use Quarterly alongside the official My Planner (Stellic) audit and their College adviser. Quarterly is not official advising and says so on every page.
- Planning works without an account (the plan stays on the device); saving plans and the forum need an anonymous account.
- v1 scope: catalog year 2026-27; the Core, Computer Science (BA/BS, Bx/MS), Mathematics (BA/BS), Economics, and study-abroad civilization programs; the forum for courses in those departments.

## Capabilities and Constraints

**Capabilities (built):** onboarding (entry quarter, test/placement/transfer credits, programs, goals); four-year planner grid with drag and drop; requirement tree; live verifier with issue list and certificate; plan generator returning 2-3 verified variants with a rationale per quarter; "Ask Quarterly" advisor chat that drafts change sets the student confirms; course search, course pages with prerequisite graphs and offering history; program explorer; course × instructor forum with threads, votes, ratings and an AI summary with citations; anonymous accounts with export and delete; curator console.

**Constraints:**
- Only a plan the certificate checker accepts is "valid".
- AI never writes to the database; it drafts change sets or review items that a person applies.
- No catalog fact is invented: every seeded rule carries a verbatim source quote.
- Privacy: anonymous accounts; email stored only in the account record; never logged; no IP addresses in logs; day-level dates only for users; no visitor request leaves the site's own origin (fonts, icons, images and weather are served by Quarterly).
- AI features run only when Richard allows paid calls (CLAUDE.md API hold).

**Non-goals:** registering students for classes; replacing the official audit or advisers; publishing grades or official evaluations; identifying anyone.

**Undecided:** public launch date; catalog-rule readings deferred until before deployment (docs/OPEN_QUESTIONS.md); TRNC 10100 transfer general credit (in progress, docs/FEEDBACK.md).

## Brand Commitments

- **Name:** "Quarterly", with "Quarterly Planner" and "Quarterly Forum" for the two halves (SPEC decision 12). "QuadPlan" is a retired working name.
- **Independence:** Quarterly is not affiliated with the University of Chicago and shows no University logos or marks; every page says so (enforced by an e2e test).
- **Honesty about AI:** AI-written content is labelled ("Answers are written by an AI and can be wrong."); plans show the verifier's verdict, never an unverified claim.
- **Homepage chapel scene:** an animated ASCII drawing of Rockefeller Chapel that follows Hyde Park's time and weather (FEEDBACK "ASCII Scene"). The drawing comes from a watermarked demo photo and must be replaced by Richard's own photo before launch (docs/OPEN_QUESTIONS.md DF-A1).

## Evidence on Hand

- Real catalog data for 2026-27, hand-copied from the College Catalog with verbatim source quotes (`data/seed/2026-27/`), plus 152 Summer Session offerings. The hand check (`data/seed/REVIEW.md`) is deferred until before deployment.
- Golden plans that must pass or fail (`data/golden/`) and a live AI test report (`docs/LIVE-TEST-REPORT.md`).
- Screenshots of the built app (`docs/screenshots/`).
- **Absent, must not be fabricated:** real student reviews or ratings (the forum holds only test fixtures), user counts, testimonials, endorsements from the University, advisers or departments, and accuracy or outcome statistics.

## Product Principles

1. **Proven, not suggested.** Nothing is shown as valid unless the verifier and certificate say so; problems are stated precisely, with what to do next.
2. **People decide.** AI drafts plans, summaries and changes; a student's explicit action applies them.
3. **Every fact has a source.** Catalog rules quote their source; course attributes show their confidence and evidence; AI summaries cite posts.
4. **Private by default.** Anonymous accounts, nothing logged that identifies a person, planning without an account.
5. **Two halves that feed each other.** The planner and the forum carry equal weight; forum ratings inform planning, and planning leads students to the forum.

## Accessibility & Inclusion

- WCAG 2.1 AA: axe checks run in the end-to-end tests on the main pages at desktop and phone widths.
- Every control is a real button or link with a label, and a 44px target.
- Keyboard use throughout (menus, drag and drop has a keyboard alternative via "Move to…").
- Reduced motion is respected (animations, including the homepage scene, stand still).
