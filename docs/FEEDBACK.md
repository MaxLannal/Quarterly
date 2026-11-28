# Richard's feedback: issues and change requests

Write down each thing that you see: something that is broken, something that is not clear, or something that you want to change. You can use plain words. Technical words are not necessary.

**How it works**
- Add new items under **New**. Put the newest item at the top.
- Copy the template below, or write only one line.
- When I start work, I read this file first. Then I move each item that I take to **In progress**.
- When I finish an item, I move it to **Done**. I add the date and a short note about what changed.
- If I need an answer from you before I do the work, I write the question under the item.
- Put items that you want me to build at a different time under **Later**.
- I also record each product decision that comes from an item in `docs/OPEN_QUESTIONS.md`. I record the work in `docs/PROGRESS.md`.

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
- Status: I committed the patch as built to branch `feature/best-of-uchicago` in a28c853. It waits for the owner's OK.
  - Changes after that commit (2026-11-20, `docs/BEST-OF-UCHICAGO-PLAN.md`): The wordmark headline became the title "The Best of UChicago, within your reach.". The search box became a question bar for the Ask chatbot. "Browse reviews" became "Explore the feed". The chapel did not change.
  - The first screen shows Rockefeller Chapel as large as the screen permits. On wide screens, the chapel is beside the wordmark, the search box and the buttons. On a phone, the front of the chapel with its spires fills the screen. The drawing uses 1,600 real course titles from `data/seed/2026-27`, set in rows like courses of stone.
  - The chapel uses only reds. Their lightness has equal steps from a dense dark red, through the site's maroon, to a pale rose. Thus the chapel never mixes with black:
    - Recesses and the great window: dark red, in heavy type.
    - Walls in half light: maroon.
    - Sunlit walls: light red, in light type.
  - The code ranks the brightness across all the stone. Thus shadow, half light and sun each get their share. The code also sharpens the detail, so the windows, buttresses and spires are clear.
  - The front, the nave and the tower each have their own depth and light. The corners where they meet are in shadow. The stone becomes darker near the ground. The trees and the lawn are black and grey. The sky is faint grey with white clouds.
  - Depth: The letters move with the pointer. The distance of a letter sets how much it moves: the sky does not move, and the lawn moves most. When no mouse is there, the letters sway slowly. When the page loads, the letters move into position from the ground up in less than one second. The picture starts to load immediately when the page opens.
  - The scene moves slowly without input:
    - The sun moves across the sky in approximately two minutes. Thus the light on the carved stone comes from one side and then from the other side. Lit faces go towards white. Faces that turn away go towards black.
    - White clouds with soft rims move across the sky. Their shadows cross the chapel.
    - Every 26 seconds, a soft glint of light moves across the stone.
    - The great window glows and becomes a little dimmer.
    - The lawn becomes black near the viewer, and far parts are a little paler. Thus maroon, white and black also show the depth.
  - Mouse and fingers: The letters under the pointer lift and become larger, as through a glass ball. A short wake follows the pointer. There are no ripples and no rainbow colours, because of the owner's second note ("more solemn, serious"). The title under the mouse changes to ink, and a label shows its code and full title. A click opens that course. With reduced motion, or on a computer without a graphics processor, the scene is a still picture. The label and the click continue to work.
  - This scene replaces the ASCII scene. Thus these parts are gone: the time-of-day and weather versions, the swaying trees, the shooting stars and the birds. The About page does not credit Open-Meteo now. The drawing still comes from the watermarked demo photo (OPEN_QUESTIONS DF-A1).
  - Proof: `layout.test.ts` (14), `test_course_chapel_data.py` (2), e2e `course-chapel.spec.ts` (5).
- Note (2026-11-27): On Max's redesign branch `claude/quarterly-ui-redesign-c953e9` (not pushed), the homepage shows Harper Library's reading room instead of the chapel. Max asked for it. The chapel code stays in the repository but is not shown; that branch replaces `course-chapel.spec.ts` with `harper.spec.ts`. Needs Richard: which picture to keep (`docs/OPEN_QUESTIONS.md` DG-1).

## Later

### Dashboard sections from Max's proposal, not in Issue #16
- Date: 2026-11-24
- Where: the dashboard (`/me`)
- What: Max's dashboard proposal in discussion #12 also lists these sections:
  - A calendar (important UChicago days and registration dates).
  - Saved or starred courses from the catalog.
  - The section "your class reviews and your posts" (comments on your posts, your past reviews, your favourite courses).
  - A profile picture.

  Issue #16 (step 29) does not include them in this round. "Suggested from your planner chat" comes after Issue #17.

### Follow-ups noticed while working (suggested by Claude, 2026-11-16; not yet asked for)
- The course page of TRNC 10100 still shows "Add to plan", because the course API does not send tags yet. If a student adds the course to a quarter, the plan check shows a warning.
- Deferred items from the design review (`docs/DESIGN-REVIEW.md`):
  - PL-4: Merge the panel buttons of the planner into one control.
  - AD-2: Show the advisor as a side panel on desktop.
  - CS-3: Department and Core lists in course search.
  - FO-4: Names for reviews that have no title.
  - PL-6: An explanation of "Difficulty".
  - A-4: The 401 on the session check when the user is logged out.
- The preference check of journey C (major courses mostly in years 2-3) sometimes fails. The cause is that the generator stops at its time limit (`docs/OPEN_QUESTIONS.md` E2E-2).
- Before launch: Replace the watermarked demo photo behind the homepage chapel. Open-Meteo is free only for non-commercial use (`docs/OPEN_QUESTIONS.md` DF-A1).

### Follow-ups noticed while doing GitHub issues #15 and #19 (suggested by Claude, 2026-11-24; not yet asked for)
- No page lets a student follow a course now, because the routes and the buttons of the Feed are gone. But the spotlights of the Catalog and "What's new" on the dashboard still use followed courses. A "Follow" button on the course page would restore that function.
- Since the companion is gone, nothing marks "What's new" as seen (`POST /me/updates/seen` has no caller). Thus its "New" dots show for one week. Issue #16 decides if the card stays. (No longer applies: issue #16 removed the card, and `GET /me/updates` was removed on 2026-11-25, OPEN_QUESTIONS M21-2.)
- The README screenshots of the homepage and the Feed show parts that are removed (the question bar, the Feed). Make these screenshots again after the integration run.

## Done

All items below are finished. The newest item is first. Each item keeps Richard's original text, and the resolution is under it.

| Item | Date | Fixed in |
|---|---|---|
| Problems with the current version | 2026-11-25 | 2838c6a |
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

### Problems with the current version
*Richard sent this in the chat on 2026-11-25. Claude copied it here with the resolutions.*

- Create an account step 4:
    - entering transfer credit should not be exclusive to transfer students. Most first year student could also have placement, test or transfer credits.
        - Resolved in 2838c6a: every student sees the credits question in step 4. Taken courses stay behind the transfer checkbox. The credits question does not count in the share of answered questions, because a student can have no credits.
    - Adding transfer credit UI in general need to be much more compact. Keep most information one line (like “Transfer credit: General Transfer Credit → TRNC 10100 · 700 units” shouldn’t be two lines), and fix UI misalignment on this page.
        - Resolved in 2838c6a: each credit is one line. A long name ends with "…", and the full line shows on hover. The units always show. Edit and remove are icon buttons. The add form has two rows. The fields of step 4 line up, and step 4 is a little wider. The kind "Transfer credit" is now "Transfer", so the example fits on one line. On a phone, the line leaves out the kind, so that the name shows.
    - With “in progress” Uchicago classes, you should disable the field where student can enter the grades (since they are currently taking it)
        - Resolved in 2838c6a: the grade field is disabled and empty for a course in progress. The server also drops such a grade. Migration 0011 removes the grades that were already stored on courses in progress.
    - You should add a back arrow to the previous steps if a misclick happens
        - Resolved in 2838c6a: steps 2 and 3 have "Back". It opens step 1 and keeps the email address, because a code works one time only. The screen after step 4 has "Back" to step 4, with the answers kept. Step 4 has no "Back", because step 3 made the account.
- Onboarding guide conversation
    - Courses per quarter is not an appropriate question. Student can only overload to 500 credits under a very specific set of rules (you can consult Uchicago course catalog for this), and most people take a mix of 300 to 400 credit quarters in the order to graduate. You should change it to conservative / normal / ambitious, where conservative plans tend to plan less and just enough to stay full time and complete the degree, and ambitous is maxing out 400 quarters every semester and overloading when condition is met.
        - Resolved in 2838c6a: the question is now "Course load" with three options: Conservative, Normal and Ambitious. Its help text uses the College's rules in `data/seed/2026-27/college_policy.yaml`. Migration 0011 replaces the old answer, so old answers show "Not answered". The planner does not read the course load yet. The planner agent (issue #17) will read it.

### Minor design changes
For every changes below, consult the installed plugin impeccable: https://github.com/pbakaus/impeccable

*Design pass: Claude added the numbers on 2026-11-16 for the design-pass goal. Richard's text did not change. D1-D10 are the changes below, in order. The first bullet holds two numbers: D1 (the deletions) and D2 (the larger wordmark). D11 is the full runthrough. Each tag gives the name of the Impeccable command that Claude used.*

- Delete the following text from homescreen because I think they're unncessary:
    - "No account needed to plan: your plan stays on this device until you log in."
    - "Rockefeller Chapel, live from Hyde Park · Weather by Open-Meteo.com"
    - "Plan your courses with a verifier that checks every requirement, and read what students say about each class." After delete, enlarge the quarterly word and slightly bold it. **[D1 `distill`: the deletions; D2 `typeset`: the larger, bolder word]**
    - D1 Resolved in 6584a4a: The subhead, the "No account needed" note and the chapel caption are gone. The Open-Meteo credit moved to the About page, because its licence requires a credit.
    - D2 Resolved in 9e045fc: "Quarterly" is 96px (64px on a phone) and one weight heavier (Newsreader 400).
- Make the menu list on the bottom of the screen more compact. Now the distance between each line is too long **[D3 `layout`]**
    - D3 Resolved in 60e867c: Footer link rows are 32px with a mouse. On touch screens, the targets stay at 44px. On a phone, the footer shows the link columns two across.
- Make the quarterly character on the menu bar more bolded **[D4 `typeset`]**
    - D4 Resolved in 75dfd83: The wordmark in the top bar (and in the footer) is Newsreader 500.
- Currently the "Courses/Program" switch on the course search is too big and the color is too bold. Make the design smaller, and make the color more obvious and subtle. you may also want to consider implementing some animation according to DESIGN.md **[D5 `quieter` + `animate`]**
    - D5 Resolved in 7401744: The switch is now a small segmented control: a light track, a white pill and a maroon label, drawn at 32px with 44px targets. The pill slides from the side that you left (200ms). With reduced motion, the pill stays still.
- The "Search courses" pill on the menu bar is too obvious. Make it more subtle. **[D6 `quieter`]**
    - D6 Resolved in 9447e95: The pill is now a quiet filled field. It has no outline until the user hovers over it or focuses it. The icon is on the left, and the field is a little narrower. Focus keeps the maroon ring.
- The rockerfeller chapel on the homescreen has a great design and great interactions. It still looks to faint. Increase the density of the ASCII character to make the image more solid. **[D7 `bolder`]**
    - D7 Resolved in 5e59e65: The drawing uses its finest level (190 characters across on a desktop). The ink is darker, with more contrast and colour. The edge fade is softer. Screenshots: `docs/screenshots/ascii-*.png`.
- Similar to the "My Plan" field, the Graduating in field should also be fixed, and can be edited with a pencil button from the side. It's size should be alot smaller and more subtle. **[D8 `distill`]**
    - D8 Resolved in c3bda96: "Graduating in Spring 2030" is a line of caption text with a pencil. The pencil opens the quarter list in place, the same as the pencil that renames the plan.
- At the planner -> credits -> edit field, "Counts as course (if known)" has a weirdly aligned text and is very big. Work on the design so it's not intrusive. **[D9 `layout`]**
    - D9 Resolved in 5ddae6c: The credit form is one column. Kind and Units share the first row. "Counts as course (if known)" is on one line above a full-width field, and "(if known)" is lighter.
- Change the color of the glowing orb behind "Quarterly" in the homescreen to be aligned with the theme color, not blue. If that is not feasible, delete it. **[D10 `colorize`]**
    - D10 Resolved in 1d0c891: The colour of the orb comes from maroon (#A44A4A, maroon at 70% on the page colour). DESIGN.md records these approved changes.

Do a full runthrough with \impeccable to improve all UI and UX workflow components. Critique every part of the website and make improvements. **[D11 `critique` + `audit`, then `polish`; `harden` and `adapt` on the planner and forum; findings in docs/DESIGN-REVIEW.md]**
- D11 Resolved in db55ef4:
  - Three isolated design reviewers critiqued every area. An audit also examined every area (detector, axe at 1440 and 390, overflow, target sizes).
  - `docs/DESIGN-REVIEW.md` holds 62 findings with priorities.
  - Commits 9eeebf7 to db55ef4 fix all 8 P1s and 49 of the P2/P3s, and fix PL-4 in part.
  - We deferred 5 findings, each with a reason. None of them needs a decision now.
  - Polish ran on every area. Harden and adapt ran on the planner and the forum.
  - Screenshots: `docs/screenshots/before/` and `docs/screenshots/after/` (55 each).

### Minor issues
- TRNC 10100 is currently not in the catalog. It is transfer general credit and every transfer student will receive some of them. They do not count as a course for any specific programs but students can use it to meet credit requirements. Add this to the catalog.
- Expanded menu on Planner will move behind the course cards, it needs to be in front
- Resolved in 784bdb1: TRNC 10100 "Transfer General Credit" is in the catalog.
  - It has 100 units. A student can receive it many times. It counts for no program and not for the Core.
  - For a transfer credit, choose it under "Counts as course". Its units count toward the degree total.
  - It has the tag "credit only", so the plan generator never puts it in a quarter.
  - The cause of the earlier failure: the course had no offering data and was repeatable. Thus the generator used it as a free elective for any quarter (we saw it put the course in a plan). This put transfer credit into planned quarters and made some solves slower.
  - Proof: a generator test (the generator places the course without the tag, and never with it), the seed tests, and journeys A-D, which pass with TRNC in the catalog.
- Resolved in b44c09a: The open menu of a course card is now in front of the cards below it. While its menu is open, the card lifts above the other cards. Proof: an e2e test (it failed before the fix) and the screenshot `fb1116-card-menu-in-front.png`.

### ASCII Scene
- Date 2026-11-16
- Where: Homepage (landing page)
- What: I want to implement some ascii art on my homepage. Look at /Users/richardgao/Downloads/ascii-scene and add it to my repo. For now, use the demo picture. Follow the instruction and make sure it blends well in a good location of the landing page. You may increase the density of the characters if you'd like. I would also want you to take the design a step further - fetch the current time and weather, and create different version of the schene that turns them in to unique animations according to the time of day and weather. I would also appriciate if you the user's cursor can interact with the ascii element, such as the tree will swing (like wind blow) when the cursor sweep over, a shooting star comes down the night sky when the user clicks. Things like this. Make your unique design choices and implement high quality design.
- Status: new
- Resolved in 25e36f5: The live chapel scene is beside the homepage text (below the text on a phone). It is directly on the page background, with edges that dissolve and with denser characters. The scene follows:
  - The real time of day: dawn, morning, noon, golden hour, dusk, night. It shows the sun, the moon, twinkling stars, and street lamps and glowing windows at night.
  - The weather in Hyde Park: clear, cloudy, rain, storm with lightning, snow, fog.
  - The weather comes from our own server (`/api/weather`). The server asks Open-Meteo a maximum of one time every 15 minutes. Thus the browser of a visitor never contacts a different site. The caption credits Open-Meteo.
  - Interaction: When the pointer moves across the trees, they sway as in a gust of wind. At night, a click on the sky shows a shooting star. By day, a click on the sky shows a few birds. With "reduce motion", the scene stays still.
  - Before launch (OPEN_QUESTIONS DF-A1): The drawing comes from the watermarked demo photo, so it needs your own photo. Also, the free service of Open-Meteo is only for non-commercial use.
  - Proof: `test_weather.py`, e2e `ascii-scene.spec.ts`, screenshots `docs/screenshots/ascii-*.png` (six states at 1440, two at 1024 and 390). make e2e: 84 passed, and journeys A-D passed.

### Color strip before the course cade
- Date: 2026-11-16
- Where: Planner
- Want: now I have zero idea what is the rational between the color strips between the course cards. Can you please assign a label to each of the colors, and explain your choice to me? We don't want to display a legend to the users on the colors, so your design decisions have to be naturally clear to the users.
- Status: New
- Resolved in 86c961d: The strip now shows the kind of requirement that a course fills. The colours are the same on every plan. The requirement tree in the drawer uses the same colour for each program. Thus students learn the colours without a legend. Each card also gives the name of its program and requirement in text. Before: the colour showed the position of the program on the plan, which had no meaning.
  - Maroon: your (first) major, with its tracks and specializations. This is the site's own colour, for the main purpose of a plan.
  - Blue: a second major.
  - Yellow: the Core (general education).
  - Light green: a minor.
  - Orange: a study-abroad block (away from campus).
  - Mauve: a Bx/MS or joint degree (graduate-level work).
  - Dark green: pre-professional.
  - Grey: the course counts toward no requirement (a free elective).
  - Proof: `stripKind.test.ts`, e2e `feedback-1116.spec.ts` "colour strips", screenshot `fb1116-colour-strips.png` (make e2e: 79 passed, and journeys A-D passed after E2E-2).


### Course Search and Programs GUI
- Date: 2026-11-16
- Where: Course Search
- Want: Combine Courses and Program in to one menu item the menu bar, and enable a toggle under the Courses/Programs tab to switch between them. For the course search page, do not list the courses below the search field. Center the search field in the center to make it simplistic.
- Status: New
- Resolved in 0abe529 (test fix 2eda4c9): The top menu has one "Catalog" item for courses and programs. A Courses / Programs switch is at the top of both pages. Course search is one centered field. Department, level, quarter and the other filters are under "More filters". The page shows no courses until you search. Proof: e2e `courses.spec.ts` "course search lists nothing until a search", `feedback-1116.spec.ts` "catalog". Screenshots: `fb1116-course-search-empty.png`, `-results.png`, `fb1116-programs-toggle.png` (make e2e passed).


### Select Course to map when Start Planning
- Date 2026-11-16
- Where: Start planning page
- Issue: When students are manually entering their test/transfer/placement credits, make the "Counts as course" a selection field. The User may enter course code, course name, but they have to ultimatly select an avaliable class. This resolves any mapping faliure.
- Status: New
- Resolved in 4ab3360: "Counts as course" is now a course picker. Type a code or a name, then choose from the matches in the catalog. If you did not choose the text from the matches, you cannot save. Thus a credit can never map to a missing course. Onboarding and the Credits panel of the planner use the picker. Proof: e2e `onboarding.spec.ts`, `feedback-1116.spec.ts` "credits", journeys A-C (make e2e passed).


### Check Summer Catalog
- Date: 2026-11-16
- Where: Plan, catalog
- Issue: There are summer session classes that are clearly not documented. Refer to https://summer.uchicago.edu/undergraduates/undergraduate-course-finder/ and document these classes
- Status: new
- Resolved in 3254069 (offerings label 8385842):
  - `data/seed/2026-27/summer_courses.yaml` now holds the 152 Summer Session courses that are open to College students. Each course cites its page on summer.uchicago.edu.
  - The planner offers in Summer the 108 courses that are in our course list.
  - The other 44 are not in the 2026-27 course list, and the site gives no units for them. Thus the file documents them, but a student cannot plan them yet (OPEN_QUESTIONS DF-S1, suggested default: add them as 100-unit courses).
  - Proof: `services/api/tests/test_seed_summer.py`.

### Allow Summer Sequences
- Date: 2026-11-16
- Where: Plan
- Issue: Summer classes can be taken in sequence during summer quarter, since the summer quarter are broken in to sessions. If the student are doing a sequence in the summer quarter and all of those course appears to be in the same quarter, allow it. But if they are skipping classes, produce a warning. For example, having HUMA 11500 and 11600 both in summer quarter is acceptable, but having HUMA 11500 and 11700 without 11600 is not. 
- Status: new
- Resolved in f546d06:
  - In a Summer quarter, a prerequisite in the same Summer quarter counts. Thus HUMA 11500 and 11600 together are permitted.
  - A skipped course (11500 and 11700 without 11600) still gets a flag.
  - Other quarters did not change.
  - The verifier, the certificate checker and the plan generator use the same rule.
  - Proof: `packages/planner_core/tests/test_summer_sequences.py`.

### Viewing and Editing Test, Placement and Transfer Credits
- Date: 2026-11-16
- Where: Plan
- Issue: Currently there is no way to edit the imported grades and transfer credits, or at least its not intuitive enough for the users to find it. Please have an interface that allows the users to check their imported test credit and transfer credit.
- Status: new
- Resolved in 8385842: A "Credits" button in the planner toolbar shows a count. The button opens a panel that lists every AP, placement and transfer credit. The panel has Edit, Remove and Add, with the same catalog check as onboarding. Onboarding uses the same editor. Proof: e2e `feedback-1116.spec.ts` "credits: ...", screenshot `docs/screenshots/fb1116-credits.png`.

### Concatnating Error Messages
- Date: 2026-11-16
- Where: Plan
- Issue: Currently the error message displayed is too verbose everywhere. User is very difficult to extract information form that chunk of test. Please, for every possible error method, you need to find a way to concatnate it and present it in a much simpler way. For instance, I am getting the error message "Prerequisite of MATH 20250 in 2026-AU is not met: MATH 16300 is not in the plan; MATH 16310 is not in the plan; MATH 15910 is not in the plan; MATH 15900 is not in the plan; MATH 19900 is not in the plan. Requirement: MATH 16300 or MATH 16310 or MATH 15910 or MATH 15900 or MATH 19900.", you can perhaps abbreviate to "Prerequisite not met. View prerequisite (with hyperlink)" in planner dashboard, and "Prerequisite of MATH 20250 not met. View prerequisite (with hyperlink)". A general rule of thumb moving foward is that we want to present to user the most essential information.
- Status: new
- Resolved in 49cb235: Every issue now shows one short line:
  - On a course card: "Prerequisite not met. View prerequisite". The link opens the course page at its prerequisites.
  - In the plan check: "Prerequisite of MATH 20250 not met.", with the full message under "Details".
  - Other checks show their first clause, with quarter names that are easy to read.
  - Proof: `issueText.test.ts`, e2e `planner.spec.ts` and `feedback-1116.spec.ts` "short issues: ...", screenshot `fb1116-planner-compact.png`.

### A more compact interface
- Date: 2026-11-16
- Where: Everywhere
- Issue: Keep the current interface but make the UI a bit more compact, so a laptop screen can display more info. This can be done by various ways (decreasing margins, round less on corners). Please still consult DESIGN.md for aesthetics.
- Status: new
- Resolved in 8385842: Corner radii are smaller: cards 8px, panels 10px. Buttons keep the pill shape, and DESIGN.md has the update. Spacing is tighter on every page and in the planner grid. The 44px touch targets did not change. Proof: screenshots `docs/screenshots/fb1116-*.png`.

### minor issues
- "Three-year plan" or "Four-year plan" on planner -> change to "My Plan", and then add a light colored pencil icon beside it to allow user to change the name of the plan. Then, delete the plan name field on the top.
- Change "AI advisor" to "Ask Quarterly". Delete the grey "Generative AI" icon in the chatting interface.
- In course pages, fold the prerequisite graph as a small icon on the right of prerequisite "view prerequisite graph" and expand a window to diplay the graph. Move "instructors" and "student ratings" as a compacted overview below the title and above prerequisite.
- Resolved in 49cb235:
  - The planner heading is the name of the plan ("My Plan" by default). A light pencil lets the user change the name. The plan-name field at the top is gone.
  - "AI advisor" is now "Ask Quarterly", without the grey "Generative AI" badge. The sheet still says that an AI writes the answers.
  - On course pages, "View prerequisite graph" opens the prerequisite graph in a window. Instructors and student ratings are a compact overview under the title.
  - Proof: e2e `feedback-1116.spec.ts`, `courses.spec.ts`, `forum.spec.ts`. Screenshots: `fb1116-ask-quarterly.png`, `fb1116-course-overview.png`, `fb1116-prereq-graph.png`.

### Generate Plan Faliure
- Date: 2026-11-14
- Where: Generate Plan
- Issue: I click on "generate plan" and got the response "No plan fits all of these settings. The generator found plans, but none passed verification. This is a bug; it has been reported."
- How important: Must fix
- Status: New Issue
- Resolved in 6ef392c: The cause was a credit (or a completed course) with a code that is not in the catalog. This code made every generated option fail its check. The generator now gives the name of that credit or course ("Fix these first, then generate again: ..."). It never says "bug". Onboarding refuses unknown codes. Tests: `test_unknown_things_already_in_the_plan_are_named_before_solving`, `e2e/onboarding.spec.ts`.

### Locations of Summer Quarter
- Date: 2026-11-14
- Where: Planner
- What you want: Move the summer quarter of each year under the year after. For example, the summer quarter of 2026 should fall under the academic year 2026-2027. This is because a transfer student may take the summer quarter before the autumn quarter they are admitted for, and a graduating student cannot take courses in the summer. It makes sense to add it before. 
- How important: Must fix
- Status: New Issue
- Resolved in 8faf56b (backend 7d50e2a): Every academic year now has the order Summer, Autumn, Winter, Spring (Summer 2026 is in 2026–27). No quarter follows the last Spring. Proof: `test_summer_opens_the_academic_year`, `terms.test.ts`, e2e `feedback-ui.spec.ts` "F2: ...", screenshots `plan-years-1440.png` / `-390.png`.

### Number of Years
- Date: 2026-11-14
- Where: Planner
- What you want: The default number of years for a transfer student should be how many years they have left. For example, if I come in as a second-year transfer student, I should have three years left. We should give the user the option to add years and also delete years. Some users also graduate early, so they may graduate in the winter or autumn quarter. That needs to also be an option. 
- How important: Must fix
- Status: New Issue
- Resolved in 8faf56b (backend 7d50e2a): Plans end at a graduation quarter. The default is the number of years left, thus three for a second-year transfer. "Add a year", "Remove last year" and "Graduating in" (Autumn, Winter or Spring) change the graduation quarter. The generator stops at that quarter. Proof: `test_years_left_and_graduation_quarter`, `test_graduation_quarter_is_saved_and_respected`, `planModel.test.ts`, e2e "F3: ...", screenshots `plan-years-*`.

### Planner GUI
- Date: 2026-11-14
- Where: Planner
- What you want: improve the organization of the Planner graphical user interface. Embed issue goals and requirements as a window, like a bar that can pop up from the right, if this makes sense. For the program requirements, write it out like a tree that is organized vertically. Only include, very simply, the course code in bold and the name of the course in small text. Most of the users that are using this aren't anticipated to graduate, so you can keep the error very subtle. Embed "Error" as a button, whereas the student can use "Add" to check for error once they have a complete plan. The AI advisor should be incorporated as another page from another pop-up window from the top, and the graphical user interface has to be clear that this is generative AI. On the page where you chat with the AI, you need to make it look like you are chatting with an AI. Use design.md for inspiration. 
- How important: Must fix
- Status: New Issue
- Resolved in 8faf56b:
  - Requirements, goals and the plan check are in a drawer on the right.
  - Requirements are a vertical tree (bold code, small name).
  - Errors show only as a small count on "Check plan".
  - The AI advisor opens from the top, with the label "Generative AI". It is a chat with bubbles, an AI avatar and a typing indicator.
  - Proof: e2e "F4: ..." tests, `AdvisorPanel.test.tsx`, screenshots `plan-drawer-*`, `plan-check-*`, `plan-advisor-*`.

### Text
- Date: 2026-11-14
- Where: Everywhere
- What you want: review every line of text that is not instructional to the reader and that doesn't contribute to the content of the page. Remove them if it's not necessary. 
- How important: Must fix
- Status: New Issue
- Resolved in 8faf56b: We removed filler lines from the Generate dialog, the quarter picker, the advisor, course search, the program explorer, instructors, the forum, the planner, the footer and home. `docs/DESIGN-IMPLEMENTATION.md` has the list. We kept the legal lines (the not-affiliated line in the footer, and "Not official advising"). Proof: e2e "F5: filler lines are gone; the legal lines stay".

### GUI Polishing
- Date: 2026-11-14
- Where: Everywhere
- What you want: please do, when you're building this out, refer to design.md and add some tasteful animation to the workflow of a user interacting with the page. Try and think, improve, and polish the current graphical user interface. 
- How important: Must fix
- Status: New Issue
- Resolved in 8faf56b: The pages now have subtle motion on dialogs, the drawer and advisor slide-ins, list items, placed cards and button presses. With reduced motion, nothing moves. We polished the layout and the spacing as DESIGN.md tells. Proof: e2e "F6: the drawer and the advisor animate in" and "F6: with reduced motion, nothing animates". The screenshots are new.

### "End suspension" button for admins
- Date: 2026-11-14
- Where: moderation queue (admin)
- What you want: a way for an admin to end a suspension early (P08-14 in `docs/OPEN_QUESTIONS.md`).
- How important: later, by Richard's decision
- Status: Parked until you ask for it. The button would be on the removal decision that started the suspension, because admins never see who is suspended.
- Resolved in 6c07395 (API b09f3f1): The moderation page lists active suspensions with "End suspension". It shows each suspension by the removal that started it, never by the author. Proof: `test_an_admin_can_end_a_suspension_early`, e2e "admin moderation queue: remove and choose to suspend the author".
