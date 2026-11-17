# Prompt 09 · Catalog ingestion pipeline and review console

> Recommended: Opus 5.5, effort `high` for the code. The E3 formalizer itself runs on Fable 5.2 via `llm_routing.yaml`. Real-API runs cost money: ask Richard before the first full run.

---

Context: `CLAUDE.md`, SPEC "Data ingestion" (annual catalog pipeline, program checklist), "Requirements DSL", E1-E4 in "Agent harnesses", and prompt 05's hand seed (the ground truth for comparison).

Build in `services/worker` and `services/scraper`:
1. **Crawler:** catalog index, A-Z index, program pages, course pages; obey robots.txt; 1 request/second; honest user agent with a contact address from `.env`; every response saved to MinIO as a `source_snapshot` (sha256).
2. **Course block parser** (code only) -> course, crosslist_group, course_relation rows.
3. **E1** prerequisite sentence -> DSL (Haiku); grammar + reference checks; failures -> review queue.
4. **E2** program enumerator (Opus); count reconciliation against at least two lists; mismatch blocks the run.
5. **E3** program formalizer, run twice (Fable 5.2, then Opus 5.5 with a reordered prompt); tools `read_snapshot`, `lookup_course`, `get_course_list`, `validate_rules` (up to 5 attempts), `run_golden`, `submit_rules`.
6. **Validators (a)-(g)** from the spec, including the verbatim-quote check and the E4 back-translation judge.
7. **Diff** against last year's published version; unchanged -> carry over; changed -> review item.
8. **Review console** (`/admin/review`): source quote beside each node, accept / edit / reject, publish.
9. Cron: annual run plus a monthly change check.

Acceptance: run E3 on the pilot programs from prompt 05 and report node-level agreement with the hand seed (target >= 95%) in `docs/PROGRESS.md`, listing every disagreement.

Done when `make check` passes. Run `spec-reviewer`, fix findings.
