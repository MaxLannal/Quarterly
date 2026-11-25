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

## In progress

### Course-title chapel on the homepage
- Date: 2026-11-19
- Where: Homepage (landing page)
- What: I want you to design the opening page UI like this. Currently there is a Rockefeller Church in code. I want you to make this church very big such that it fills the screen. Then, take the course names and use those instead of code to illustrate the rockefeller church. Do this colorfully and have dynamic depth. When the mouse swipes over the letters, have a good visual effect that responds to the mouse and your fingers. (Asked in chat; not to be committed until the owner has seen it.)
- Second note (2026-11-20): Make the effects less wave-like. The ball shaped view is good but uchicago should have a more solemn, serious hardcore feel. Less wave vibrations. Less color vibrations. Change the overall color tone to different shades of maroon red. Have some Natural sunlight shifts that changes the colors a bit, or some moving clouds, or moving people, even when the mouse is not moving. Animate it. Main color tone: maroon and black and white.
- Third note (2026-11-20): Little too monotone, add some more dynamical depth in terms of maroon, white, and black. Add also some natural movement of dynamics or luster that is not too exaggerate for when mouse not landing.
- Fourth note (2026-11-20): Still doesn't look very much like a building. the colors mix, especially black and maroon. Need to be lighter red at some parts, denser and dark red at others. Don't just create the shape. Create the depth. Also, build faster.
- Status: committed on branch `feature/best-of-uchicago` in a28c853 (the patch as built), waiting for the owner's OK. Since then (2026-11-20, `docs/BEST-OF-UCHICAGO-PLAN.md`) the wordmark headline became the title "The Best of UChicago, within your reach.", the search box became a question bar for the Ask chatbot, and "Browse reviews" became "Explore the feed"; the chapel itself is unchanged.
  - The first screen is Rockefeller Chapel, as large as the screen allows (beside the wordmark, search and buttons on wide screens; the front with its spires fills a phone), drawn with 1,600 real course titles from `data/seed/2026-27` set in rows like courses of stone. The chapel is in reds only, evenly spaced in lightness from a dense dark red through the site's maroon to a pale rose, so it never mixes with black: recesses and the great window are dark red in heavy type, walls in half light maroon, sunlit walls light red in light type. Its brightness is ranked across all the stone (so shadow, half light and sun each get their share) and its detail sharpened, so windows, buttresses and spires stand out. The front, the nave and the tower each have their own depth and light, the corners where they meet fall into shadow, and the stone darkens near the ground. Trees and lawn are black and greys, the sky faint grey with white clouds.
  - Depth: the letters shift with the pointer by how near they are (the sky stays, the lawn moves most) and sway slowly when no mouse is there; on load the letters settle into place from the ground up in under a second, and the picture starts loading as soon as the page opens.
  - It moves on its own, slowly: the sun swings across the sky over about two minutes, so the carving of the stone is lit from one side and then the other (lit faces towards white, faces turned away towards black); white clouds with soft rims drift across the sky and their shadows cross the chapel; every 26 seconds a soft glint of light passes over the stone; the great window glows and dims a little. The lawn darkens to black towards the viewer and what is far is a little paler, so maroon, white and black also carry the depth.
  - Mouse and fingers: the letters under the pointer lift and magnify like a glass ball, with a short wake behind it (no ripples, no rainbow colours, after the owner's second note: "more solemn, serious"). The title under the mouse turns ink with a label of its code and full title; a click opens that course. Under reduced motion, and on a computer without a graphics processor, it is a still picture (the label and the click still work).
  - Replaces the ASCII scene, so the time-of-day and weather versions, the swaying trees, shooting stars and birds are gone, and the About page no longer credits Open-Meteo. The drawing still comes from the watermarked demo photo (OPEN_QUESTIONS DF-A1).
  - Proof: `layout.test.ts` (14), `test_course_chapel_data.py` (2), e2e `course-chapel.spec.ts` (5).

## Later

### Dashboard sections from Max's proposal, not in Issue #16
- Date: 2026-11-24
- Where: the dashboard (`/me`)
- What: Max's dashboard proposal in discussion #12 also lists a calendar (important UChicago days and registration dates), saved or starred courses from the catalog, "your class reviews and your posts" (comments on your posts, your past reviews, your favourite courses) and a profile picture. Issue #16 (step 29) leaves them out of this round. "Suggested from your planner chat" comes after Issue #17.

### Follow-ups noticed while working (suggested by Claude, 2026-11-16; not yet asked for)
- TRNC 10100's course page still offers "Add to plan" (the course API does not send tags yet); the plan check warns if it is added to a quarter.
- Design review deferrals (`docs/DESIGN-REVIEW.md`): PL-4 merge the planner's panel buttons into one control; AD-2 advisor as a side panel on desktop; CS-3 department and Core lists in course search; FO-4 naming of untitled reviews; PL-6 an explanation of "Difficulty"; A-4 the 401 on the logged-out session check.
- Journey C's preference check (major courses mostly in years 2-3) sometimes fails because the generator stops at its time limit (`docs/OPEN_QUESTIONS.md` E2E-2).
- Before launch: replace the watermarked demo photo behind the homepage chapel; Open-Meteo is free for non-commercial use only (`docs/OPEN_QUESTIONS.md` DF-A1).

### Follow-ups noticed while doing GitHub issues #15 and #19 (suggested by Claude, 2026-11-24; not yet asked for)
- No page lets a student follow a course any more (the routes and the Feed's buttons are gone), but the Catalog's spotlights and the dashboard's "What's new" still use followed courses. A "Follow" button on the course page would bring that back.
- Nothing marks "What's new" as seen since the companion went (`POST /me/updates/seen` has no caller), so its "New" dots show for a week. Issue #16 decides whether the card stays.
- The README's screenshots of the homepage and the Feed show removed parts (the question bar, the Feed); retake them after the integration run.

## Done

Every item below is finished. Newest first; each keeps Richard's original text, with the resolution under it.

| Item | Date | Fixed in |
|---|---|---|
| Minor design changes | 2026-11-16 | 6584a4a, 9e045fc, 60e867c, 75dfd83 ... |
| Minor issues | 2026-11-16 | 784bdb1, b44c09a |
| ASCII Scene | 2026-11-16 | 25e36f5 |
| Color strip before the course cade | 2026-11-16 | 86c961d |
| Course Search and Programs GUI | 2026-11-16 | 0abe529 |
| Select Course to map when Start Planning | 2026-11-16 | 4ab3360 |
| Check Summer Catalog | 2026-11-16 | 3254069 |
| Allow Summer Sequences | 2026-11-16 | f546d06 |
| Viewing and Editing Test, Placement and Transfer Credits | 2026-11-16 | 8385842 |
| Concatnating Error Messages | 2026-11-16 | 49cb235 |
| A more compact interface | 2026-11-16 | 8385842 |
| minor issues | 2026-11-16 | 49cb235 |
| Generate Plan Faliure | 2026-11-14 | 6ef392c |
| Locations of Summer Quarter | 2026-11-14 | 8faf56b |
| Number of Years | 2026-11-14 | 8faf56b |
| Planner GUI | 2026-11-14 | 8faf56b |
| Text | 2026-11-14 | 8faf56b |
| GUI Polishing | 2026-11-14 | 8faf56b |
| "End suspension" button for admins | 2026-11-14 | 6c07395 |

### Minor design changes
For every changes below, consult the installed plugin impeccable: https://github.com/pbakaus/impeccable

*Design pass (numbering added by Claude, 2026-11-16, for the design-pass goal; Richard's text unchanged): D1-D10 are the changes below in order (the first bullet is D1, the deletions, and D2, the larger wordmark), D11 is the full runthrough. Each tag names the Impeccable command used.*

- Delete the following text from homescreen because I think they're unncessary:
    - "No account needed to plan: your plan stays on this device until you log in."
    - "Rockefeller Chapel, live from Hyde Park · Weather by Open-Meteo.com"
    - "Plan your courses with a verifier that checks every requirement, and read what students say about each class." After delete, enlarge the quarterly word and slightly bold it. **[D1 `distill`: the deletions; D2 `typeset`: the larger, bolder word]**
    - D1 Resolved in 6584a4a: the subhead, the "No account needed" note and the chapel caption are gone; the Open-Meteo credit (its licence requires one) moved to the About page.
    - D2 Resolved in 9e045fc: "Quarterly" is 96px (64px on a phone) and one weight heavier (Newsreader 400).
- Make the menu list on the bottom of the screen more compact. Now the distance between each line is too long **[D3 `layout`]**
    - D3 Resolved in 60e867c: footer link rows are 32px with a mouse (44px targets stay on touch screens); on a phone the link columns sit two across.
- Make the quarterly character on the menu bar more bolded **[D4 `typeset`]**
    - D4 Resolved in 75dfd83: the top-bar wordmark (and the footer's) is Newsreader 500.
- Currently the "Courses/Program" switch on the course search is too big and the color is too bold. Make the design smaller, and make the color more obvious and subtle. you may also want to consider implementing some animation according to DESIGN.md **[D5 `quieter` + `animate`]**
    - D5 Resolved in 7401744: a small segmented control (light track, white pill, maroon label, 32px drawn with 44px targets); the pill slides from the side you left (200ms, still under reduced motion).
- The "Search courses" pill on the menu bar is too obvious. Make it more subtle. **[D6 `quieter`]**
    - D6 Resolved in 9447e95: a quiet filled field with no outline until hovered or focused, icon on the left, a little narrower; focus keeps the maroon ring.
- The rockerfeller chapel on the homescreen has a great design and great interactions. It still looks to faint. Increase the density of the ASCII character to make the image more solid. **[D7 `bolder`]**
    - D7 Resolved in 5e59e65: the finest level of the drawing (190 characters across at desktop), darker ink, more contrast and colour, softer edge fade. Screenshots `docs/screenshots/ascii-*.png`.
- Similar to the "My Plan" field, the Graduating in field should also be fixed, and can be edited with a pencil button from the side. It's size should be alot smaller and more subtle. **[D8 `distill`]**
    - D8 Resolved in c3bda96: "Graduating in Spring 2030" is a line of caption text with a pencil; the pencil opens the quarter list in place, like renaming the plan.
- At the planner -> credits -> edit field, "Counts as course (if known)" has a weirdly aligned text and is very big. Work on the design so it's not intrusive. **[D9 `layout`]**
    - D9 Resolved in 5ddae6c: the credit form is one column (Kind and Units share the first row); "Counts as course (if known)" sits on one line above a full-width field, with "(if known)" lighter.
- Change the color of the glowing orb behind "Quarterly" in the homescreen to be aligned with the theme color, not blue. If that is not feasible, delete it. **[D10 `colorize`]**
    - D10 Resolved in 1d0c891: the orb is maroon-derived (#A44A4A, maroon at 70% on the page colour). DESIGN.md records these approved departures.

Do a full runthrough with \impeccable to improve all UI and UX workflow components. Critique every part of the website and make improvements. **[D11 `critique` + `audit`, then `polish`; `harden` and `adapt` on the planner and forum; findings in docs/DESIGN-REVIEW.md]**
- D11 Resolved in db55ef4: every area was critiqued (three isolated design reviewers) and audited (detector, axe at 1440 and 390, overflow, target sizes); 62 findings with priorities are in `docs/DESIGN-REVIEW.md`. All 8 P1s and 49 of the P2/P3s are fixed (commits 9eeebf7 to db55ef4), PL-4 in part; 5 are deferred with a reason (none needs a decision now). Polish on every area, harden and adapt on the planner and forum. Screenshots: `docs/screenshots/before/` and `docs/screenshots/after/` (55 each).

### Minor issues
- TRNC 10100 is currently not in the catalog. It is transfer general credit and every transfer student will receive some of them. They do not count as a course for any specific programs but students can use it to meet credit requirements. Add this to the catalog.
- Expanded menu on Planner will move behind the course cards, it needs to be in front
- Resolved in 784bdb1: TRNC 10100 "Transfer General Credit" is in the catalog (100 units, can be received many times, counts for no program or the Core). Choose it under "Counts as course" for a transfer credit; its units count toward the degree total. It is tagged "credit only", so the plan generator never puts it in a quarter. Why it failed before: with no offering data and being repeatable, the generator treated it as a free elective for any quarter (it was seen placing it in a plan), which put transfer credit into planned quarters and slowed some solves. Proof: a generator test (placed without the tag, never with it), the seed tests, and journeys A-D passing with TRNC in the catalog.
- Resolved in b44c09a: a course card's open menu now sits in front of the cards below it (the card is lifted while its menu is open). e2e test (failed before the fix) and screenshot `fb1116-card-menu-in-front.png`.

### ASCII Scene
- Date 2026-11-16
- Where: Homepage (landing page)
- What: I want to implement some ascii art on my homepage. Look at /Users/richardgao/Downloads/ascii-scene and add it to my repo. For now, use the demo picture. Follow the instruction and make sure it blends well in a good location of the landing page. You may increase the density of the characters if you'd like. I would also want you to take the design a step further - fetch the current time and weather, and create different version of the schene that turns them in to unique animations according to the time of day and weather. I would also appriciate if you the user's cursor can interact with the ascii element, such as the tree will swing (like wind blow) when the cursor sweep over, a shooting star comes down the night sky when the user clicks. Things like this. Make your unique design choices and implement high quality design.
- Status: new
- Resolved in 25e36f5: the live chapel scene sits beside the homepage text (below it on a phone), straight on the page's background with dissolving edges and denser characters. It follows the real time of day (dawn, morning, noon, golden hour, dusk, night: sun, moon, twinkling stars, street lamps and glowing windows at night) and Hyde Park's weather (clear, cloudy, rain, storm with lightning, snow, fog).
  - Weather comes from our own server (`/api/weather`, asks Open-Meteo at most every 15 minutes), so a visitor's browser never contacts another site; the caption credits Open-Meteo.
  - Interaction: sweep the pointer across the trees and they sway like a gust; click the sky at night for a shooting star, or by day for a few birds. Under "reduce motion" the scene stays still.
  - Before launch (OPEN_QUESTIONS DF-A1): the drawing comes from the watermarked demo photo, so it needs your own photo; and Open-Meteo's free service is for non-commercial use only.
  - Proof: `test_weather.py`, e2e `ascii-scene.spec.ts`, screenshots `docs/screenshots/ascii-*.png` (six states at 1440, two at 1024 and 390); make e2e: 84 passed, journeys A-D passed.

### Color strip before the course cade
- Date: 2026-11-16
- Where: Planner
- Want: now I have zero idea what is the rational between the color strips between the course cards. Can you please assign a label to each of the colors, and explain your choice to me? We don't want to display a legend to the users on the colors, so your design decisions have to be naturally clear to the users.
- Status: New
- Resolved in 86c961d: the strip now says what kind of requirement a course fills, the same on every plan, and the requirement tree in the drawer uses the same colour for each program, so students learn it without a legend (each card also names its program and requirement in text). Was: the colour of the program's position on the plan, which meant nothing.
  - Maroon: your (first) major, with its tracks and specializations. The site's own colour for the main thing a plan is for.
  - Blue: a second major. Yellow: the Core (general education). Light green: a minor. Orange: a study-abroad block (away from campus). Mauve: a Bx/MS or joint degree (graduate-level work). Dark green: pre-professional.
  - Grey: counts toward no requirement (a free elective).
  - Proof: `stripKind.test.ts`, e2e `feedback-1116.spec.ts` "colour strips", screenshot `fb1116-colour-strips.png` (make e2e: 79 passed; journeys A-D passed after E2E-2).


### Course Search and Programs GUI
- Date: 2026-11-16
- Where: Course Search
- Want: Combine Courses and Program in to one menu item the menu bar, and enable a toggle under the Courses/Programs tab to switch between them. For the course search page, do not list the courses below the search field. Center the search field in the center to make it simplistic.
- Status: New
- Resolved in 0abe529 (test fix 2eda4c9): the top menu has one "Catalog" item for courses and programs, with a Courses / Programs switch at the top of both pages; course search is a single centered field (department, level, quarter and the rest under "More filters") and lists nothing until you search. Proof: e2e `courses.spec.ts` "course search lists nothing until a search", `feedback-1116.spec.ts` "catalog"; screenshots `fb1116-course-search-empty.png`, `-results.png`, `fb1116-programs-toggle.png` (make e2e passed).


### Select Course to map when Start Planning
- Date 2026-11-16
- Where: Start planning page
- Issue: When students are manually entering their test/transfer/placement credits, make the "Counts as course" a selection field. The User may enter course code, course name, but they have to ultimatly select an avaliable class. This resolves any mapping faliure.
- Status: New
- Resolved in 4ab3360: "Counts as course" is now a course picker: type a code or a name, then choose from the catalog's matches; text that was not chosen blocks saving, so a credit can never map to a missing course. Used in onboarding and the planner's Credits panel. Proof: e2e `onboarding.spec.ts`, `feedback-1116.spec.ts` "credits", journeys A-C (make e2e passed).


### Check Summer Catalog
- Date: 2026-11-16
- Where: Plan, catalog
- Issue: There are summer session classes that are clearly not documented. Refer to https://summer.uchicago.edu/undergraduates/undergraduate-course-finder/ and document these classes
- Status: new
- Resolved in 3254069 (offerings label 8385842): the 152 Summer Session courses open to College students are now in `data/seed/2026-27/summer_courses.yaml`, each citing its page on summer.uchicago.edu; the 108 that are in our course list are offered in Summer in the planner. The other 44 are not in the 2026-27 course list and the site states no units, so they are documented but not yet plannable (OPEN_QUESTIONS DF-S1, suggested default: add as 100-unit courses). Proof: `services/api/tests/test_seed_summer.py`.

### Allow Summer Sequences
- Date: 2026-11-16
- Where: Plan
- Issue: Summer classes can be taken in sequence during summer quarter, since the summer quarter are broken in to sessions. If the student are doing a sequence in the summer quarter and all of those course appears to be in the same quarter, allow it. But if they are skipping classes, produce a warning. For example, having HUMA 11500 and 11600 both in summer quarter is acceptable, but having HUMA 11500 and 11700 without 11600 is not. 
- Status: new
- Resolved in f546d06: in a Summer quarter a prerequisite in the same Summer quarter counts (HUMA 11500 and 11600 together is fine), a skipped course (11500 and 11700 without 11600) is still flagged, and other quarters are unchanged; the same rule is in the verifier, the certificate checker and the plan generator. Proof: `packages/planner_core/tests/test_summer_sequences.py`.

### Viewing and Editing Test, Placement and Transfer Credits
- Date: 2026-11-16
- Where: Plan
- Issue: Currently there is no way to edit the imported grades and transfer credits, or at least its not intuitive enough for the users to find it. Please have an interface that allows the users to check their imported test credit and transfer credit.
- Status: new
- Resolved in 8385842: a "Credits" button in the planner toolbar (with a count) opens a panel listing every AP, placement and transfer credit, with Edit, Remove and Add (the same catalog check as onboarding); onboarding uses the same editor. Proof: e2e `feedback-1116.spec.ts` "credits: ...", screenshot `docs/screenshots/fb1116-credits.png`.

### Concatnating Error Messages
- Date: 2026-11-16
- Where: Plan
- Issue: Currently the error message displayed is too verbose everywhere. User is very difficult to extract information form that chunk of test. Please, for every possible error method, you need to find a way to concatnate it and present it in a much simpler way. For instance, I am getting the error message "Prerequisite of MATH 20250 in 2026-AU is not met: MATH 16300 is not in the plan; MATH 16310 is not in the plan; MATH 15910 is not in the plan; MATH 15900 is not in the plan; MATH 19900 is not in the plan. Requirement: MATH 16300 or MATH 16310 or MATH 15910 or MATH 15900 or MATH 19900.", you can perhaps abbreviate to "Prerequisite not met. View prerequisite (with hyperlink)" in planner dashboard, and "Prerequisite of MATH 20250 not met. View prerequisite (with hyperlink)". A general rule of thumb moving foward is that we want to present to user the most essential information.
- Status: new
- Resolved in 49cb235: every issue now shows one short line: on a course card "Prerequisite not met. View prerequisite" (the link opens the course page at its prerequisites), in the plan check "Prerequisite of MATH 20250 not met." with the full message under "Details"; other checks show their first clause with readable quarter names. Proof: `issueText.test.ts`, e2e `planner.spec.ts` and `feedback-1116.spec.ts` "short issues: ...", screenshot `fb1116-planner-compact.png`.

### A more compact interface
- Date: 2026-11-16
- Where: Everywhere
- Issue: Keep the current interface but make the UI a bit more compact, so a laptop screen can display more info. This can be done by various ways (decreasing margins, round less on corners). Please still consult DESIGN.md for aesthetics.
- Status: new
- Resolved in 8385842: smaller corner radii (cards 8px, panels 10px; buttons keep the pill, DESIGN.md updated) and tighter spacing on every page and in the planner grid, with 44px touch targets kept. Proof: screenshots `docs/screenshots/fb1116-*.png`.

### minor issues
- "Three-year plan" or "Four-year plan" on planner -> change to "My Plan", and then add a light colored pencil icon beside it to allow user to change the name of the plan. Then, delete the plan name field on the top.
- Change "AI advisor" to "Ask Quarterly". Delete the grey "Generative AI" icon in the chatting interface.
- In course pages, fold the prerequisite graph as a small icon on the right of prerequisite "view prerequisite graph" and expand a window to diplay the graph. Move "instructors" and "student ratings" as a compacted overview below the title and above prerequisite.
- Resolved in 49cb235: the planner heading is the plan's name ("My Plan" by default) with a light pencil to rename it, and the plan-name field at the top is gone; "AI advisor" is now "Ask Quarterly" without the grey "Generative AI" badge (the sheet still says answers are written by an AI); on course pages the prerequisite graph opens in a window from "View prerequisite graph", and instructors and student ratings are a compact overview under the title. Proof: e2e `feedback-1116.spec.ts`, `courses.spec.ts`, `forum.spec.ts`; screenshots `fb1116-ask-quarterly.png`, `fb1116-course-overview.png`, `fb1116-prereq-graph.png`.

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
