# Richard's feedback: issues and change requests

Write down anything you notice: something broken, something confusing, or something you want changed. Plain words are fine; no need to be technical.

**How it works**
- Add new items under **New**, newest at the top. Copy the template below, or just write one line.
- When I start work, I read this file first, then move each item I take to **In progress**.
- When an item is finished, I move it to **Done** with the date and a short note of what changed. If I need an answer from you first, I write the question under the item.
- Items you want built some other time go under **Later**.
- Product decisions that come out of an item are also recorded in `docs/OPEN_QUESTIONS.md`, and the work itself in `docs/PROGRESS.md`.

**Template**

```
### Short title
- Date: 2026-11-15
- Where: the page or feature (for example "planner on a phone", "forum page", "Generate plan")
- What happened, or what you want: ...
- How important: must fix / should fix / nice to have
- Screenshot (optional): put the file in docs/feedback/ and write its name here
```

---

## New

<!-- Add new items here, newest first. -->
## In progress

## Later

## Done

### Generate Plan Faliure
- Date: 2026-11-14
- Where: Generate Plan
- Issue: I click on "generate plan" and got the response "No plan fits all of these settings. The generator found plans, but none passed verification. This is a bug; it has been reported."
- How important: Must fix
- Status: New Issue
- Resolved in 6ef392c: the cause was a credit (or completed course) whose code is not in the catalog, which made every generated option fail its check; the generator now names it ("Fix these first, then generate again: ..."), never says "bug", and onboarding refuses unknown codes. Tests: `test_unknown_things_already_in_the_plan_are_named_before_solving`, `e2e/onboarding.spec.ts`.

### Locations of Summer Quarter
- Date: 2026-11-14
- Where: Planner
- What you want: Move the summer quarter of each year under the year after. For example, the summer quarter of 2026 should fall under the academic year 2026-2027. This is because a transfer student may take the summer quarter before the autumn quarter they are admitted for, and a graduating student cannot take courses in the summer. It makes sense to add it before. 
- How important: Must fix
- Status: New Issue
- Resolved in 8faf56b (backend 7d50e2a): every academic year now runs Summer, Autumn, Winter, Spring (Summer 2026 is in 2026–27) and nothing follows the last Spring. Proof: `test_summer_opens_the_academic_year`, `terms.test.ts`, e2e `feedback-ui.spec.ts` "F2: ...", screenshots `plan-years-1440.png` / `-390.png`.

### Number of Years
- Date: 2026-11-14
- Where: Planner
- What you want: The default number of years for a transfer student should be how many years they have left. For example, if I come in as a second-year transfer student, I should have three years left. We should give the user the option to add years and also delete years. Some users also graduate early, so they may graduate in the winter or autumn quarter. That needs to also be an option. 
- How important: Must fix
- Status: New Issue
- Resolved in 8faf56b (backend 7d50e2a): plans end at a graduation quarter (default: the years left, so three for a second-year transfer); "Add a year", "Remove last year" and "Graduating in" (Autumn, Winter or Spring) change it, and the generator stops there. Proof: `test_years_left_and_graduation_quarter`, `test_graduation_quarter_is_saved_and_respected`, `planModel.test.ts`, e2e "F3: ...", screenshots `plan-years-*`.

### Planner GUI
- Date: 2026-11-14
- Where: Planner
- What you want: improve the organization of the Planner graphical user interface. Embed issue goals and requirements as a window, like a bar that can pop up from the right, if this makes sense. For the program requirements, write it out like a tree that is organized vertically. Only include, very simply, the course code in bold and the name of the course in small text. Most of the users that are using this aren't anticipated to graduate, so you can keep the error very subtle. Embed "Error" as a button, whereas the student can use "Add" to check for error once they have a complete plan. The AI advisor should be incorporated as another page from another pop-up window from the top, and the graphical user interface has to be clear that this is generative AI. On the page where you chat with the AI, you need to make it look like you are chatting with an AI. Use design.md for inspiration. 
- How important: Must fix
- Status: New Issue
- Resolved in 8faf56b: requirements, goals and the plan check live in a right-hand drawer; requirements are a vertical tree (bold code, small name); errors are only a small count on "Check plan"; the AI advisor opens from the top, labelled "Generative AI", as a chat with bubbles, an AI avatar and a typing indicator. Proof: e2e "F4: ..." tests, `AdvisorPanel.test.tsx`, screenshots `plan-drawer-*`, `plan-check-*`, `plan-advisor-*`.

### Text
- Date: 2026-11-14
- Where: Everywhere
- What you want: review every line of text that is not instructional to the reader and that doesn't contribute to the content of the page. Remove them if it's not necessary. 
- How important: Must fix
- Status: New Issue
- Resolved in 8faf56b: filler lines removed across the Generate dialog, quarter picker, advisor, course search, program explorer, instructors, forum, planner, footer and home (list in `docs/DESIGN-IMPLEMENTATION.md`); legal lines kept (footer not-affiliated line, "Not official advising"). Proof: e2e "F5: filler lines are gone; the legal lines stay".

### GUI Polishing
- Date: 2026-11-14
- Where: Everywhere
- What you want: please do, when you're building this out, refer to design.md and add some tasteful animation to the workflow of a user interacting with the page. Try and think, improve, and polish the current graphical user interface. 
- How important: Must fix
- Status: New Issue
- Resolved in 8faf56b: subtle motion (dialogs, drawer and advisor slide-ins, list items, placed cards, button press), none under reduced motion; layout and spacing polished per DESIGN.md. Proof: e2e "F6: the drawer and the advisor animate in" and "F6: with reduced motion, nothing animates"; refreshed screenshots.

### "End suspension" button for admins
- Date: 2026-11-14
- Where: moderation queue (admin)
- What you want: a way for an admin to end a suspension early (P08-14 in `docs/OPEN_QUESTIONS.md`).
- How important: later, by Richard's decision
- Status: parked until you ask for it. It would sit on the removal decision that started the suspension, because admins never see who is suspended.
- Resolved in 6c07395 (API b09f3f1): the moderation page lists active suspensions (by the removal that started them, never the author) with "End suspension". Proof: `test_an_admin_can_end_a_suspension_early`, e2e "admin moderation queue: remove and choose to suspend the author".
