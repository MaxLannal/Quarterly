"""`make ingest-pilot`: run E1-E4 on the pilot programs (the hand seed's programs in
`data/seed/<year>/programs/`) and report node-level agreement with the hand seed.

    uv run python -m worker.ingest.pilot --fake        # free: FakeLLM scripted from the seed
    uv run python -m worker.ingest.pilot --estimate    # print the estimated cost, call nothing
    CONFIRM_SPEND=yes LLM_LIVE=true uv run python -m worker.ingest.pilot

A real run fetches each program's catalog pages (robots.txt, 1 request per second, the
contact address from CATALOG_CONTACT_EMAIL), then calls the models through the gateway behind
a spending cap (INGEST_COST_CAP_USD, default 25). It refuses to start unless both
CONFIRM_SPEND=yes and LLM_LIVE=true are set.

`--fake` runs the whole pipeline (snapshots, E2 reconciliation, E1 checks, both E3 runs with
their tools, validators (a)-(g), E4, the report) with `FakeLLM` answering exactly what the
hand seed says, on FAKE snapshots assembled from the seed's own quotes. It proves the
plumbing and the report, so it should show 100% agreement; it says nothing about how well a
real model reads the catalog.

The report lists every disagreement, per program, as Markdown (`docs/ingest-pilot/`).
A real run keeps the pages it fetched (MinIO and `source_snapshot`, so `make up` first);
nothing else is written to the database.
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import os
import re
import sys
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from api.seed.bundle import SeedBundle, load_bundle
from api.seed.models import ProgramSeed
from llm_gateway.api import FakeLLM, FakeTurn, ToolCall
from llm_gateway.routing import load_routing
from llm_gateway.types import Usage
from planner_core.dsl import expr_to_text
from planner_core.models import Expr, ProgramRules

from worker.ingest.catalog import CatalogView, from_bundle
from worker.ingest.compare import Agreement, count_nodes, node_agreement
from worker.ingest.courseleaf import https_url
from worker.ingest.e1 import formalize as e1_formalize
from worker.ingest.e2 import ProgramCandidate, ReferenceList, enumerate_programs
from worker.ingest.e3 import E3Context
from worker.ingest.e4 import english_of
from worker.ingest.golden import golden_runner
from worker.ingest.llm import CostCapReachedError, Metered
from worker.ingest.pipeline import ProgramOutcome, process_program
from worker.ingest.snapshots import Snapshot, SnapshotArchive, memory_archive
from worker.ingest.validators import references, sources_of

ROOT = Path(__file__).resolve().parents[4]
YEAR = "2026-27"
TARGET = 0.95
DEFAULT_CAP = 25.0
FAKE_BANNER = "FAKE snapshot assembled from the hand seed's quotes (not a real catalog page)"

#: Rough token use per call at list prices (assumptions, documented in docs/PROGRESS.md).
EST_E3 = Usage(input_tokens=150_000, output_tokens=15_000)  # ~10 turns re-reading the history
EST_E4 = Usage(input_tokens=15_000, output_tokens=3_000)
EST_E2 = Usage(input_tokens=60_000, output_tokens=4_000)
EST_E1 = Usage(input_tokens=700, output_tokens=150)


def family_of(name: str) -> str:
    return re.sub(r"\s*\((?:BA|BS|MS|MA)\b[^)]*\)\s*$", "", name).strip() or name


def pilot_sentences(
    bundle: SeedBundle, programs: list[ProgramSeed]
) -> list[tuple[str, str, Expr | None]]:
    """(course, prerequisite sentence, the seed's expression) for every course the pilot
    programs name that has a prerequisite sentence."""
    named: set[str] = set()
    for p in programs:
        named |= references(p.rules_only())[0]
    return [
        (c.code, c.prereq_text, c.prereq)
        for c in sorted(bundle.courses, key=lambda c: c.code)
        if c.code in named and c.prereq_text
    ]


def estimate(n_programs: int, n_sentences: int) -> float:
    routing = load_routing()

    def cost(task: str, usage: Usage) -> float:
        return routing.cost(routing.route(task).model, usage)

    per_program = (
        cost("e3_program_formalizer", EST_E3)
        + cost("e3b_second_opinion", EST_E3)
        + cost("e4_backtranslation_judge", EST_E4)
    )
    total = (
        n_programs * per_program
        + cost("e2_program_enumerator", EST_E2)
        + n_sentences * cost("e1_prereq_formalizer", EST_E1)
    )
    return round(total, 2)


# -------------------------------------------------------------------------- snapshots


def program_urls(program: ProgramSeed) -> list[str]:
    """The program's pages, as https (the seed cites them as http; the crawler fetches https)."""
    urls = [s.url for s in program.sources if s.url]
    urls += [src.url for _, src in sources_of(program.rules_only()) if src is not None and src.url]
    return list(dict.fromkeys(https_url(u) for u in urls))


def fake_pages(programs: list[ProgramSeed], archive: SnapshotArchive) -> dict[str, Snapshot]:
    """One FAKE page per URL, made of the seed's quotes for that URL."""
    quotes: dict[str, list[str]] = {}
    for p in programs:
        for s in p.sources:
            if s.url:
                quotes.setdefault(https_url(s.url), []).append(s.quote)
        for _, src in sources_of(p.rules_only()):
            if src is not None and src.url:
                quotes.setdefault(https_url(src.url), []).append(src.quote)
    pages = {}
    for url, items in quotes.items():
        body = "".join(f"<p>{html.escape(q)}</p>\n" for q in dict.fromkeys(items))
        doc = (
            f"<!doctype html><html><head><title>FAKE</title></head><body>"
            f'<h1 class="page-title">{FAKE_BANNER}: {html.escape(url)}</h1>\n{body}</body></html>'
        )
        pages[url] = archive.save(url, 200, doc.encode(), "text/html; charset=utf-8")
    return pages


def stored_archive(settings: Any) -> SnapshotArchive | None:
    """Real fetches are kept like the yearly run's: bytes in MinIO, a `source_snapshot` row
    each. None (with a message) when MinIO or the database cannot be reached."""
    import sqlalchemy as sa
    from sqlalchemy.orm import sessionmaker

    from worker.ingest.records import DbSnapshotLog
    from worker.ingest.snapshots import MinioStore

    store = MinioStore(
        endpoint=settings.minio_endpoint,
        access_key=settings.minio_root_user,
        secret_key=settings.minio_root_password.get_secret_value(),
        bucket=settings.minio_bucket,
        secure=settings.minio_secure,
    )
    engine = sa.create_engine(settings.database_url)
    try:
        store.ensure_bucket()
        with engine.connect() as conn:
            conn.execute(sa.text("SELECT 1"))
    except Exception as exc:  # any failure here means "start the stack first"
        print(
            f"ingest-pilot: MinIO or the database is not reachable ({type(exc).__name__}); "
            "start them with `make up`, then run again",
            file=sys.stderr,
        )
        return None
    return SnapshotArchive(store, DbSnapshotLog(sessionmaker(engine)))


def live_pages(
    programs: list[ProgramSeed], archive: SnapshotArchive, **crawler_kw: Any
) -> dict[str, Snapshot]:
    """`crawler_kw` is for tests (a mock transport and clock)."""
    from worker.ingest.crawler import Crawler
    from worker.ingest.settings import get_ingest_settings

    settings = get_ingest_settings()
    urls = [u for p in programs for u in program_urls(p)]
    hosts = {urllib.parse.urlsplit(u).netloc for u in urls}
    crawler = Crawler(
        archive=archive,
        contact=settings.catalog_contact_email,
        allowed_hosts=hosts,
        interval_s=settings.catalog_request_interval_s,
        **crawler_kw,
    )
    pages = {}
    for url in dict.fromkeys(urls):
        snap = crawler.fetch(url)
        if snap is not None and snap.status == 200:
            pages[url] = snap
    for skip in crawler.skipped:
        print(f"ingest-pilot: skipped {skip.url}: {skip.reason}", file=sys.stderr)
    return pages


# ------------------------------------------------------------------------- fake model


def rules_yaml(rules: ProgramRules) -> str:
    return yaml.safe_dump(
        rules.model_dump(mode="json", exclude_none=True), sort_keys=False, width=100
    )


def script_e3(fake: FakeLLM, task: str, rules: ProgramRules, snapshots: list[Snapshot]) -> None:
    text = rules_yaml(rules)
    fake.script.setdefault(task, []).extend(
        [
            FakeTurn(
                calls=tuple(
                    ToolCall("read_snapshot", {"id": s.id, "start": 0, "end": 10_000})
                    for s in snapshots
                )
            ),
            ToolCall("validate_rules", {"rules_yaml": text}),
            ToolCall("run_golden", {"program": rules.id}),
            ToolCall(
                "submit_rules",
                {"rules_yaml": text, "notes": "FAKE run: answered from the hand seed"},
            ),
        ]
    )


def candidate_of(program: ProgramSeed, pages: dict[str, Snapshot]) -> ProgramCandidate:
    urls = program_urls(program)
    return ProgramCandidate(
        id=program.id,
        name=program.name,
        type=program.type,
        degree=program.degree,
        family=family_of(program.name),
        url=urls[0],
        parent_id=program.parent_id,
        evidence=[pages[u].id for u in urls if u in pages],
    )


# ----------------------------------------------------------------------------- report


@dataclass
class ProgramReport:
    program_id: str
    seed_nodes: int
    agreement: Agreement | None
    outcome: ProgramOutcome | None
    error: str | None = None


@dataclass
class PilotReport:
    mode: str
    catalog_year: str
    programs: list[ProgramReport] = field(default_factory=list)
    e1: list[dict[str, Any]] = field(default_factory=list)
    e2: dict[str, Any] = field(default_factory=dict)
    spent: float = 0.0
    calls: int = 0
    stopped: str | None = None

    @property
    def agreed(self) -> int:
        return sum(p.agreement.agreed for p in self.programs if p.agreement)

    @property
    def total(self) -> int:
        return sum(p.agreement.total if p.agreement else p.seed_nodes for p in self.programs)

    @property
    def rate(self) -> float:
        return self.agreed / self.total if self.total else 0.0

    @property
    def e1_agreed(self) -> int:
        return sum(1 for r in self.e1 if r["same_as_seed"])


def _short(data: Any) -> str:
    if data is None:
        return "(none)"
    text = yaml.safe_dump(data, default_flow_style=True, sort_keys=True, width=10_000).strip()
    return text.replace("|", "\\|")[:400]


def render(report: PilotReport) -> str:
    lines = [
        f"# Pilot ingestion report ({report.mode})",
        "",
        f"- Date: {dt.date.today().isoformat()}; catalog year {report.catalog_year}",
        f"- Mode: {report.mode}"
        + (
            " (FakeLLM scripted from the hand seed, on FAKE snapshots built from the seed's quotes:"
            " this checks the pipeline and this report, not a model)"
            if report.mode == "fake"
            else ""
        ),
        f"- Node-level agreement with the hand seed: **{report.agreed}/{report.total} = "
        f"{report.rate:.1%}** (target {TARGET:.0%}: "
        f"{'met' if report.rate >= TARGET else 'NOT met'})",
        f"- E1 prerequisite sentences: {report.e1_agreed}/{len(report.e1)} match the seed "
        "expression; "
        f"{sum(1 for r in report.e1 if r['to_review'])} would go to the review queue",
        f"- E2 enumeration: {report.e2.get('found', 0)}/{report.e2.get('expected', 0)} pilot "
        "programs found; "
        f"reconciliation {'passed' if not report.e2.get('problems') else 'BLOCKED'}",
        f"- Spent: ${report.spent:.2f} in {report.calls} model calls",
    ]
    if report.stopped:
        lines.append(f"- Stopped early: {report.stopped}")
    lines += [
        "",
        "## Programs",
        "",
        "| Program | Nodes compared | Agreed | Agreement | Run A vs run B | Checks not passed "
        "| E4 differences |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for p in report.programs:
        o = p.outcome
        runs = o.runs_agreement if o else None
        failed = ", ".join(f"({c.id}) {c.name}" for c in o.failed_checks) if o else ""
        e4 = len(o.e4.differences or []) if o and o.e4 else "-"
        agreed = p.agreement.agreed if p.agreement else 0
        rate = f"{p.agreement.rate:.1%}" if p.agreement else f"failed: {p.error}"
        lines.append(
            f"| {p.program_id} | {p.agreement.total if p.agreement else p.seed_nodes} | {agreed} "
            f"| {rate} | "
            f"{f'{runs.rate:.1%}' if runs else '-'} | {failed or 'none'} | {e4} |"
        )
    lines += ["", "## Every disagreement with the hand seed", ""]
    any_disagreement = False
    for p in report.programs:
        if p.agreement is None:
            any_disagreement = True
            lines += [f"### {p.program_id}", "", f"No tree: {p.error}", ""]
            continue
        if not p.agreement.disagreements:
            continue
        any_disagreement = True
        lines += [
            f"### {p.program_id}",
            "",
            "| Node | What | Hand seed | E3 |",
            "| --- | --- | --- | --- |",
        ]
        for d in p.agreement.disagreements:
            lines.append(
                f"| `{d.path}` | {d.kind} | {_short(d.reference)} | {_short(d.candidate)} |"
            )
        lines.append("")
    if not any_disagreement:
        lines += ["None.", ""]
    lines += ["## Checks that did not pass", ""]
    flagged = False
    for p in report.programs:
        for c in p.outcome.failed_checks if p.outcome else []:
            flagged = True
            lines.append(f"- {p.program_id} ({c.id}) {c.name}: " + "; ".join(c.problems[:5]))
    if not flagged:
        lines.append("None.")
    lines += ["", "## E1 sentences that differ from the seed or need review", ""]
    rows = [r for r in report.e1 if not r["same_as_seed"] or r["to_review"]]
    if rows:
        lines += [
            "| Course | Sentence | Seed | E1 | Review reason |",
            "| --- | --- | --- | --- | --- |",
        ]
        for r in rows:
            sentence = r["sentence"].replace("|", "\\|")[:200]
            lines.append(
                f"| {r['course']} | {sentence} | {r['seed'] or '(none)'} | {r['e1'] or '(none)'} | "
                f"{'; '.join(r['errors']) or '-'} |"
            )
    else:
        lines.append("None.")
    if report.e2.get("problems"):
        lines += ["", "## E2 reconciliation problems", ""] + [
            f"- {x}" for x in report.e2["problems"]
        ]
    return "\n".join(lines) + "\n"


# -------------------------------------------------------------------------------- run


def run_pilot(
    llm: Any,
    bundle: SeedBundle,
    programs: list[ProgramSeed],
    pages: dict[str, Snapshot],
    *,
    mode: str,
    fake: FakeLLM | None = None,
    golden_root: Path | None = None,
) -> PilotReport:
    report = PilotReport(mode=mode, catalog_year=bundle.catalog_year)
    catalog: CatalogView = from_bundle(bundle)
    golden = golden_runner(bundle, golden_root or ROOT / "data" / "golden")
    candidates = [candidate_of(p, pages) for p in programs]

    try:
        # E2 over the pilot pages, reconciled against two lists built from the seed.
        lists = [
            ReferenceList(
                "hand seed program list",
                None,
                counts={
                    t: len({c.family.casefold() for c in candidates if c.type == t})
                    for t in {c.type for c in candidates}
                },
            ),
            ReferenceList(
                "pilot page list",
                None,
                urls={c.url for c in candidates},
                url_types=frozenset(c.type for c in candidates),
            ),
        ]
        if fake is not None:
            fake.script.setdefault("e2_program_enumerator", []).extend(
                [
                    ToolCall("list_pages", {}),
                    ToolCall(
                        "submit_programs",
                        {
                            "candidates": [c.model_dump(mode="json") for c in candidates],
                            "note": "FAKE",
                        },
                    ),
                ]
            )
        enumeration = enumerate_programs(
            llm, catalog_year=bundle.catalog_year, pages=list(pages.values()), lists=lists
        )
        found = {c.id for c in enumeration.candidates}
        report.e2 = {
            "expected": len(candidates),
            "found": len(found & {c.id for c in candidates}),
            "problems": enumeration.problems,
        }

        # E1 on the prerequisite sentences of the courses the pilot programs name.
        for code, sentence, seed_expr in pilot_sentences(bundle, programs):
            if fake is not None:
                fake.script.setdefault("e1_prereq_formalizer", []).append(
                    {
                        "prereq": seed_expr.model_dump(mode="json") if seed_expr else None,
                        "unparseable": seed_expr is None,
                    }
                )
            result = e1_formalize(llm, course=code, sentence=sentence, catalog=catalog)
            got = result.expr.model_dump(mode="json") if result.expr else None
            want = seed_expr.model_dump(mode="json") if seed_expr else None
            report.e1.append(
                {
                    "course": code,
                    "sentence": sentence,
                    "seed": expr_to_text(seed_expr) if seed_expr else None,
                    "e1": expr_to_text(result.expr) if result.expr else None,
                    "same_as_seed": got == want,
                    "to_review": not result.ok,
                    "errors": result.errors,
                }
            )

        # E3 (twice), the validators and E4, program by program.
        for program, candidate in zip(programs, candidates, strict=True):
            seed_rules = program.rules_only()
            snaps = [pages[u] for u in program_urls(program) if u in pages]
            if fake is not None:
                script_e3(fake, "e3_program_formalizer", seed_rules, snaps)
                script_e3(fake, "e3b_second_opinion", seed_rules, snaps)
                fake.script.setdefault("e4_backtranslation_judge", []).append(
                    {"english": english_of(seed_rules), "differences": []}
                )
            ctx = E3Context(candidate, bundle.catalog_year, snaps, catalog, golden)
            outcome = process_program(llm, ctx)
            rules = outcome.run_a.rules
            report.programs.append(
                ProgramReport(
                    program.id,
                    count_nodes(seed_rules),
                    node_agreement(seed_rules, rules) if rules is not None else None,
                    outcome,
                    error=outcome.run_a.error,
                )
            )
    except CostCapReachedError as exc:
        report.stopped = str(exc)
    report.spent = float(getattr(llm, "spent", 0.0))
    report.calls = int(getattr(llm, "calls", 0))
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Pilot ingestion: E1-E4 on the hand-seeded programs"
    )
    parser.add_argument("--fake", action="store_true", help="free: FakeLLM answers from the seed")
    parser.add_argument("--estimate", action="store_true", help="print the estimated cost and stop")
    parser.add_argument(
        "--programs", help="comma-separated program ids (default: every seeded program)"
    )
    parser.add_argument("--year", default=YEAR)
    parser.add_argument(
        "--out", type=Path, help="report path (default docs/ingest-pilot/report-<mode>.md)"
    )
    args = parser.parse_args(argv)

    bundle = load_bundle(ROOT / "data" / "seed" / args.year)
    programs = bundle.programs
    if args.programs:
        wanted = set(args.programs.split(","))
        programs = [p for p in programs if p.id in wanted]
        if missing := wanted - {p.id for p in programs}:
            print(f"ingest-pilot: unknown program(s) {sorted(missing)}", file=sys.stderr)
            return 2
    n_sentences = len(pilot_sentences(bundle, programs))
    mode = "fake" if args.fake else "live"
    out = args.out or ROOT / "docs" / "ingest-pilot" / f"report-{mode}.md"

    if args.fake:
        fake = FakeLLM()
        llm: Any = Metered(fake)
        pages = fake_pages(programs, memory_archive("fake"))
        print(
            f"ingest-pilot: FAKE run on {len(programs)} programs and {n_sentences} prerequisite "
            "sentences (no API calls)"
        )
        report = run_pilot(llm, bundle, programs, pages, mode=mode, fake=fake)
    else:
        from worker.ingest.settings import get_ingest_settings

        settings = get_ingest_settings()
        cap = float(
            os.environ.get("INGEST_COST_CAP_USD", settings.ingest_cost_cap_usd or DEFAULT_CAP)
        )
        cost = estimate(len(programs), n_sentences)
        print(
            f"ingest-pilot: {len(programs)} programs, {n_sentences} prerequisite sentences; "
            f"estimated cost about ${cost:.2f} at list prices; cap ${cap:.2f}"
        )
        if args.estimate:
            return 0
        if os.environ.get("CONFIRM_SPEND") != "yes" or not settings.llm_live:
            print(
                "ingest-pilot: not calling the real models. This costs money: ask Richard, "
                "then run\n"
                "  CONFIRM_SPEND=yes LLM_LIVE=true make ingest-pilot\n"
                "or try the free version: make ingest-pilot ARGS=--fake",
                file=sys.stderr,
            )
            return 2
        from llm_gateway.gateway import build_gateway

        gateway = build_gateway(
            anthropic_api_key=settings.anthropic_api_key.get_secret_value(),
            openrouter_api_key=settings.openrouter_api_key.get_secret_value(),
        )
        if gateway is None:
            print(
                "ingest-pilot: no ANTHROPIC_API_KEY or OPENROUTER_API_KEY in .env", file=sys.stderr
            )
            return 2
        archive = stored_archive(settings)
        if archive is None:
            return 2
        from api.agents.llm import db_sink

        llm = Metered(gateway, cap_usd=cap, on_record=db_sink)  # visible to the spend alarm
        pages = live_pages(programs, archive)
        report = run_pilot(llm, bundle, programs, pages, mode=mode)

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(report), encoding="utf-8")
    print(
        f"ingest-pilot: node-level agreement {report.agreed}/{report.total} = {report.rate:.1%} "
        f"(target {TARGET:.0%}); E1 {report.e1_agreed}/{len(report.e1)} same as the seed; "
        f"E2 found {report.e2.get('found', 0)}/{report.e2.get('expected', 0)}"
        + (" (reconciliation blocked)" if report.e2.get("problems") else "")
        + f"; spent ${report.spent:.2f}"
    )
    for p in report.programs:
        rate = f"{p.agreement.rate:.1%}" if p.agreement else "no tree"
        total = p.agreement.total if p.agreement else p.seed_nodes
        print(f"  {p.program_id}: {rate} of {total} nodes")
    print(
        f"ingest-pilot: report written to "
        f"{out.relative_to(ROOT) if out.is_relative_to(ROOT) else out}"
    )
    return 0 if report.rate >= TARGET and not report.stopped else 1


if __name__ == "__main__":
    sys.exit(main())
