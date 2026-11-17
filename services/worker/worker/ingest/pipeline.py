"""One program end to end, and the annual run (SPEC "Annual catalog pipeline" steps 2-7).

`process_program`: E3 run A and run B -> checks (a)-(g) (E4 for (e)) -> diff against last
year's published version -> a `VersionDraft` (status `review`) with its review item. When
the new tree means exactly what last year's published tree meant, and last year's quotes are
still on this year's pages, the program is marked "carry over": the version holds last
year's tree unchanged and the review item says so, so a curator can publish it in one step.
Publishing is always a curator action (Richard, 2026-11-14: agents never write published
data; docs/OPEN_QUESTIONS.md "Prompt 09").

`run_annual`: parse courses (code) -> E1 on every prerequisite sentence -> E2 with count
reconciliation (a mismatch stops the run) -> `process_program` for every candidate. It stops
calling models once the spending cap is reached.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from planner_core.dsl import iter_nodes, iter_parts
from planner_core.hashing import sha256_of
from planner_core.models import CourseList, ProgramRules

from worker.ingest import courseleaf
from worker.ingest.catalog import CatalogView
from worker.ingest.compare import Agreement, node_agreement
from worker.ingest.courses import StagedCatalog, course_batches, parse_courses
from worker.ingest.crawler import CatalogCrawl
from worker.ingest.e1 import formalize as e1_formalize
from worker.ingest.e1 import staged_requisite
from worker.ingest.e2 import (
    ProgramCandidate,
    ReferenceList,
    enumerate_programs,
    stated_counts,
    url_list,
)
from worker.ingest.e3 import RUN_A, RUN_B, E3Context, E3Run, formalize_program
from worker.ingest.e4 import E4Result, judge, node_text
from worker.ingest.golden import GoldenRunner
from worker.ingest.records import Results, ReviewDraft, VersionDraft
from worker.ingest.snapshots import Snapshot
from worker.ingest.validators import (
    Check,
    check_agreement,
    check_backtranslation,
    check_golden,
    check_quotes,
    check_references,
    check_size,
    sources_of,
)

logger = logging.getLogger("worker.ingest")

#: Program types the catalog's Programs of Study index lists (one page may hold several).
INDEX_TYPES = {"major", "minor", "bxms", "joint", "specialization", "track"}


@dataclass
class ProgramOutcome:
    candidate: ProgramCandidate
    catalog_year: str
    run_a: E3Run
    run_b: E3Run | None
    checks: list[Check] = field(default_factory=list)
    e4: E4Result | None = None
    runs_agreement: Agreement | None = None
    previous_agreement: Agreement | None = None
    decision: str = "review"  # review | carry_over | failed
    rules: ProgramRules | None = None
    version: VersionDraft | None = None
    review: ReviewDraft | None = None

    @property
    def failed_checks(self) -> list[Check]:
        return [c for c in self.checks if not c.ok and not c.skipped]


def _flags(outcome: ProgramOutcome) -> dict[str, list[str]]:
    flags: dict[str, list[str]] = {}

    def add(path: str, text: str) -> None:
        flags.setdefault(path, []).append(text)

    if outcome.runs_agreement is not None:
        for d in outcome.runs_agreement.disagreements:
            add(d.path, f"The second run disagrees here ({d.kind}).")
    if outcome.previous_agreement is not None:
        for d in outcome.previous_agreement.disagreements:
            add(d.path, f"Changed since last year ({d.kind}).")
    if outcome.e4 is not None and outcome.e4.differences:
        for diff in outcome.e4.differences:
            add(diff["path"] or "", f"Back-translation: {diff['problem']}")
    for check in outcome.checks:
        if check.id == "c":
            for problem in check.problems:
                add(problem.split(":", 1)[0], "The quote was not found on the page.")
    return flags


def review_nodes(
    rules: ProgramRules, flags: dict[str, list[str]], urls: dict[str, str]
) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    for path, unit in [*iter_nodes(rules), *iter_parts(rules)]:
        src = unit.source
        nodes.append(
            {
                "path": path,
                "kind": getattr(unit, "kind", "part"),
                "label": unit.label,
                "summary": node_text(unit),
                "quote": src.quote if src else None,
                "snapshot_id": src.snapshot_id if src else None,
                # The snapshot's own URL, never one the model wrote (it could be anything).
                "url": urls.get(src.snapshot_id or "") if src else None,
                "flags": flags.get(path, []),
            }
        )
    policy = [(p, s) for p, s in sources_of(rules) if "/policy/" in p]
    for path, src in policy:
        nodes.append(
            {
                "path": path,
                "kind": "policy",
                "label": path.rsplit("/", 1)[-1],
                "summary": "Program-wide rule",
                "quote": src.quote if src else None,
                "snapshot_id": src.snapshot_id if src else None,
                "url": urls.get(src.snapshot_id or "") if src else None,
                "flags": flags.get(path, []) + flags.get(f"{rules.id}/policy", []),
            }
        )
    general = flags.get("", [])
    if general and nodes:
        nodes[0]["flags"] = nodes[0]["flags"] + general
    return nodes


def process_program(
    llm: Any,
    ctx: E3Context,
    *,
    previous: ProgramRules | None = None,
    previous_year: str | None = None,
    second_run: bool = True,
) -> ProgramOutcome:
    run_a = formalize_program(llm, ctx, RUN_A)
    run_b = formalize_program(llm, ctx, RUN_B) if second_run else None
    out = ProgramOutcome(ctx.candidate, ctx.catalog_year, run_a, run_b)
    pid = ctx.candidate.id
    if run_a.rules is None:
        out.decision = "failed"
        out.review = ReviewDraft(
            target_type="ingest_run",
            target_id=f"{ctx.catalog_year}:{pid}"[:64],
            diff={
                "kind": "ingest_run",
                "catalog_year": ctx.catalog_year,
                "step": "program formalization",
                "program_id": pid,
                "problems": [run_a.error or "no tree"],
                "candidate": ctx.candidate.model_dump(mode="json"),
            },
            reason=f"{pid}: the formalizer did not produce a valid rule tree ({run_a.error}). "
            "Write the rules by hand or run it again.",
        )
        return out

    rules = run_a.rules
    texts, ids_by_url = ctx.texts, ctx.ids_by_url
    if run_b is not None and run_b.rules is not None:
        out.runs_agreement = node_agreement(rules, run_b.rules)
    out.e4 = judge(llm, rules, [(s.id, texts[s.id]) for s in ctx.snapshots])
    out.checks = [
        Check("a", ok=True),
        check_references(rules, ctx.catalog),
        check_quotes(rules, texts, ids_by_url),
        check_agreement(out.runs_agreement)
        if second_run
        else Check("d", True, ["second run off"], skipped=True),
        check_backtranslation(out.e4.differences),
        check_golden(run_a.golden),
        check_size(rules, ctx.candidate.type),
    ]

    out.rules = rules
    if previous is not None:
        out.previous_agreement = node_agreement(previous, rules)
        carried = previous.model_copy(update={"catalog_year": ctx.catalog_year})
        old_quotes = check_quotes(carried, texts, ids_by_url)
        if out.previous_agreement.identical and old_quotes.ok:
            out.decision = "carry_over"
            out.rules = carried
    urls = {s.id: s.url for s in ctx.snapshots}
    flags = _flags(out)
    failed = out.failed_checks
    if out.decision == "carry_over":
        reason = (
            f"{pid}: unchanged since {previous_year}. Last year's published rules still match "
            "this year's pages; publish to carry them over."
        )
    else:
        bits = [f"({c.id}) {c.name}" for c in failed]
        changed = (
            f"{len(out.previous_agreement.disagreements)} node(s) changed since {previous_year}; "
            if out.previous_agreement is not None
            else "new program; "
        )
        reason = f"{pid}: {changed}" + (
            "checks to look at: " + ", ".join(bits) if bits else "all checks passed"
        )
    assert out.rules is not None
    diff = {
        "kind": "program_version",
        "program_id": pid,
        "catalog_year": ctx.catalog_year,
        "decision_hint": out.decision,
        "rules": out.rules.model_dump(mode="json"),
        "second_run_rules": run_b.rules.model_dump(mode="json") if run_b and run_b.rules else None,
        "previous": {"catalog_year": previous_year, "rules": previous.model_dump(mode="json")}
        if previous is not None
        else None,
        "nodes": review_nodes(out.rules, flags, urls),
        "checks": [c.as_dict() for c in out.checks],
        "backtranslation": out.e4.answer.model_dump(mode="json") if out.e4.answer else None,
        "agreement_runs": out.runs_agreement.as_dict() if out.runs_agreement else None,
        "changes_from_previous": out.previous_agreement.as_dict()
        if out.previous_agreement
        else None,
        "notes": [n for n in (run_a.notes, run_b.notes if run_b else "") if n],
        "snapshots": [{"id": s.id, "url": s.url, "sha256": s.sha256} for s in ctx.snapshots],
        "cost_usd": round(sum(r.run.cost_usd for r in (run_a, run_b, out.e4) if r and r.run), 4),
    }
    out.review = ReviewDraft("program_version", "", diff, reason)
    c = ctx.candidate
    out.version = VersionDraft(
        program_id=pid,
        name=c.name,
        type=c.type,
        degree=c.degree,
        department=None,
        parent_id=c.parent_id,
        catalog_year=ctx.catalog_year,
        rules=out.rules.model_dump(mode="json"),
        sources=[
            {"url": s.url, "snapshot_id": s.id, "quote": courseleaf.page_title(s.text()) or s.url}
            for s in ctx.snapshots
        ],
        source_ids=[int(s.id) for s in ctx.snapshots if s.id.isdigit()],
        checksum=sha256_of(out.rules),
        review=out.review,
    )
    return out


def outcome_results(outcome: ProgramOutcome) -> Results:
    res = Results()
    for item in (outcome.run_a, outcome.run_b, outcome.e4):
        if item is not None and item.run is not None:
            res.runs.append(item.run)
    if outcome.version is not None:
        res.versions.append(outcome.version)
    elif outcome.review is not None:
        res.reviews.append(outcome.review)
    return res


# ------------------------------------------------------------------------ annual run


@dataclass
class AnnualInputs:
    catalog_year: str
    previous_year: str | None
    crawl: CatalogCrawl
    #: Last year's courses (`courses.previous_from_db` shape).
    previous_courses: dict[str, dict[str, Any]] = field(default_factory=dict)
    #: Last year's published program versions.
    previous_programs: dict[str, ProgramRules] = field(default_factory=dict)
    #: Named course lists, carried from last year (curated by hand).
    course_lists: list[CourseList] = field(default_factory=list)
    golden: GoldenRunner | None = None
    #: False when no model may be called (LLM_LIVE off): courses are still parsed and
    #: staged, and one review item says the agents were skipped.
    agents: bool = True


def _over_cap(llm: Any) -> bool:
    cap = getattr(llm, "cap_usd", None)
    return cap is not None and float(getattr(llm, "spent", 0.0)) >= float(cap)


def reference_lists(crawl: CatalogCrawl) -> list[ReferenceList]:
    lists = []
    if crawl.counts is not None and crawl.counts.status == 200:
        counted = stated_counts(crawl.counts)
        if counted.counts:
            lists.append(counted)
    if crawl.index_urls:
        lists.append(
            url_list("Programs of Study index", crawl.index, crawl.index_urls, INDEX_TYPES)
        )
    if crawl.az_urls:
        lists.append(
            url_list("A-Z index", crawl.azindex, crawl.az_urls, INDEX_TYPES, exhaustive=False)
        )
    return lists


def _program_snapshots(candidate: ProgramCandidate, crawl: CatalogCrawl) -> list[Snapshot]:
    pages = crawl.pages
    by_id = {s.id: s for s in pages.values()}
    chosen: dict[str, Snapshot] = {}
    if candidate.url in pages:
        chosen[pages[candidate.url].id] = pages[candidate.url]
    for sid in candidate.evidence:
        if sid in by_id:
            chosen[sid] = by_id[sid]
    return list(chosen.values())


def run_annual(llm: Any, inputs: AnnualInputs) -> Results:
    res = Results()
    year = inputs.catalog_year
    crawl = inputs.crawl

    # Step 2: courses (code only).
    staged: StagedCatalog = parse_courses(year, crawl.pages.values())
    catalog = CatalogView.build(year, staged.facts(), inputs.course_lists)
    snapshot_of = {code: c.source.get("snapshot_id") for code, c in staged.courses.items()}

    # Step 3: E1 on every prerequisite sentence.
    requisites: dict[str, dict[str, Any]] = {}
    for code, course in sorted(staged.courses.items()):
        if not course.prereq_text or not inputs.agents:
            continue
        if _over_cap(llm):
            res.reviews.append(_stopped(year, "prerequisites", llm))
            break
        result = e1_formalize(
            llm,
            course=code,
            sentence=course.prereq_text,
            catalog=catalog,
            snapshot_id=snapshot_of[code],
        )
        if result.run is not None:
            res.runs.append(result.run)
        if result.ok:
            requisites[code] = staged_requisite(result)
        elif result.review is not None:
            res.reviews.append(result.review)
    res.reviews += course_batches(
        staged, inputs.previous_courses, previous_year=inputs.previous_year, requisites=requisites
    )
    if staged.problems:
        res.reviews.append(
            ReviewDraft(
                "ingest_run",
                f"{year}:courses",
                {
                    "kind": "ingest_run",
                    "catalog_year": year,
                    "step": "course parsing",
                    "problems": staged.problems,
                },
                f"{len(staged.problems)} course block problem(s) need a look",
            )
        )

    # Step 4: E2 with count reconciliation.
    if not inputs.agents:
        res.reviews.append(
            ReviewDraft(
                "ingest_run",
                f"{year}:agents",
                {
                    "kind": "ingest_run",
                    "catalog_year": year,
                    "step": "agents",
                    "problems": ["LLM_LIVE is off: prerequisites and programs were not formalized"],
                },
                "Courses were fetched and staged; the agents were skipped because LLM_LIVE is off.",
            )
        )
        return res
    if _over_cap(llm):
        res.reviews.append(_stopped(year, "program enumeration", llm))
        return res
    pages = [s for s in (crawl.index, crawl.azindex, crawl.counts) if s is not None] + list(
        crawl.program_pages.values()
    )
    enumeration = enumerate_programs(
        llm, catalog_year=year, pages=pages, lists=reference_lists(crawl)
    )
    if enumeration.run is not None:
        res.runs.append(enumeration.run)
    if enumeration.blocked:
        res.reviews.append(enumeration.review(year))
        return res

    # Steps 5-7: each program.
    for candidate in enumeration.candidates:
        if _over_cap(llm):
            res.reviews.append(
                _stopped(year, f"program formalization (before {candidate.id})", llm)
            )
            break
        snapshots = _program_snapshots(candidate, crawl)
        if not snapshots:
            res.reviews.append(
                ReviewDraft(
                    "ingest_run",
                    f"{year}:{candidate.id}"[:64],
                    {
                        "kind": "ingest_run",
                        "catalog_year": year,
                        "step": "program formalization",
                        "program_id": candidate.id,
                        "problems": [f"no fetched page for {candidate.url}"],
                    },
                    f"{candidate.id}: its page was not fetched",
                )
            )
            continue
        ctx = E3Context(candidate, year, snapshots, catalog, inputs.golden)
        outcome = process_program(
            llm,
            ctx,
            previous=inputs.previous_programs.get(candidate.id),
            previous_year=inputs.previous_year,
        )
        res.extend(outcome_results(outcome))
    return res


def _stopped(year: str, step: str, llm: Any) -> ReviewDraft:
    return ReviewDraft(
        "ingest_run",
        f"{year}:cap",
        {
            "kind": "ingest_run",
            "catalog_year": year,
            "step": step,
            "problems": [f"spending cap ${float(getattr(llm, 'cap_usd', 0.0)):.2f} reached"],
        },
        f"The run stopped at the spending cap during {step}; raise INGEST_COST_CAP_USD and "
        "run again.",
    )
