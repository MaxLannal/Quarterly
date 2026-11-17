# Prompt 08 · Forum

> Recommended: Opus 5.5, effort `high`. Parallel with 07 (own worktree). Needs prompt 04 merged (login).

---

Context: `CLAUDE.md`, SPEC "Forum", the forum tables in "Data model", A4 in "Agent harnesses", and the forum mockup.

Build:
1. **Pages:** one per `course_instructor` row, created automatically; course-level aggregation view; instructor pages. All forum routes require login.
2. **Posts:** review (structured ratings required, one per account per page, editable) and discussion. Validation per the "Review ratings" table.
3. **Comments:** unlimited nesting stored with `ltree` paths; UI collapses below depth 6.
4. **Votes:** +1/-1, one per voter per item, changeable; Best (Wilson lower bound, z = 1.96), Top, New, Controversial, Hot (half-life 30 days) computed in SQL.
5. **Anonymity:** `author_ref` / `voter_ref` = HMAC(SERVER_HMAC_KEY, account_id || page_id); per-page two-word pseudonyms, stable within a page; relative or quarter-level timestamps only.
6. **Moderation:** regex scrub of emails and phone numbers; A4 classifier on submit (via llm_gateway, 3 s timeout -> hold for review); reports; admin moderation queue; suspension after 3 upheld removals.
7. **Rendering:** markdown sanitized server-side (no raw HTML, safe links only).
8. **Frontend:** forum page and thread view per the mockup; composer with community rules; report dialog.

Tests: sorting math; one-review-per-page rule; pseudonyms differ across pages for the same account; XSS payloads neutralized; a leaked-DB simulation cannot join posts across pages without the key; moderation fallback on timeout.

Done when `make check` and `make e2e` pass. Run `security-privacy-reviewer` and `spec-reviewer`, fix findings, update `docs/PROGRESS.md`.
