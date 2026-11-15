"""The program pipeline (two E3 runs, checks, E4, diff against last year) and the annual run
over the FAKE catalog server, with FakeLLM only."""

from __future__ import annotations

import copy
import json
from typing import Any

from ingest_rules import RULES, URL, candidate, catalog, fake_page, rules, rules_yaml
from llm_gateway.api import FakeLLM, ToolCall
from planner_core.models import ProgramRules
from worker.ingest.crawler import Crawler, crawl_catalog
from worker.ingest.e3 import E3Context
from worker.ingest.pipeline import AnnualInputs, outcome_results, process_program, run_annual
from worker.ingest.snapshots import memory_archive

NO_DIFF = {"english": "Take the fake science sequence.", "differences": []}


def script(
    fake: FakeLLM, run_a: str, run_b: str | None = None, e4: dict[str, Any] | None = None
) -> None:
    fake.script.setdefault("e3_program_formalizer", []).append(
        ToolCall("submit_rules", {"rules_yaml": run_a, "notes": "a"})
    )
    fake.script.setdefault("e3b_second_opinion", []).append(
        ToolCall("submit_rules", {"rules_yaml": run_b or run_a, "notes": ""})
    )
    fake.script.setdefault("e4_backtranslation_judge", []).append(e4 or NO_DIFF)


def ctx() -> E3Context:
    return E3Context(candidate(), "2099-00", [fake_page()], catalog())


def with_methods_constraint(value: bool) -> dict[str, Any]:
    data = copy.deepcopy(RULES)
    data["rules"]["group"]["children"][1]["constraints"] = {"no_pass_fail": value}
    return data


def test_unchanged_since_last_year_is_marked_carry_over() -> None:
    fake = FakeLLM()
    script(fake, rules_yaml())
    last_year = rules(catalog_year="2098-99")
    out = process_program(fake, ctx(), previous=last_year, previous_year="2098-99")
    assert out.decision == "carry_over"
    assert out.version is not None and out.version.rules["catalog_year"] == "2099-00"
    assert out.review is not None and "unchanged since 2098-99" in out.review.reason
    assert out.review.diff["decision_hint"] == "carry_over"
    res = outcome_results(out)
    assert [r.kind for r in res.runs] == ["e3", "e3b", "e4"]
    assert res.versions and not res.reviews
    json.dumps(out.review.diff)  # stored as JSONB


def test_a_changed_program_goes_to_review_with_flags() -> None:
    fake = FakeLLM()
    script(
        fake,
        rules_yaml(),
        rules_yaml(with_methods_constraint(False)),
        {
            "english": "...",
            "differences": [
                {"path": "fsci-bs/intro", "problem": "the page also allows FSCI 10150"}
            ],
        },
    )
    previous = ProgramRules.model_validate(
        {**with_methods_constraint(False), "catalog_year": "2098-99"}
    )
    out = process_program(fake, ctx(), previous=previous, previous_year="2098-99")
    assert out.decision == "review"
    failed = {c.id for c in out.failed_checks}
    assert failed == {"d", "e", "g"}
    nodes = {n["path"]: n for n in out.review.diff["nodes"]} if out.review else {}
    assert nodes["fsci-bs/methods"]["quote"] == "The BS also requires FSCI 20100."
    assert any("second run disagrees" in f for f in nodes["fsci-bs/methods"]["flags"])
    assert any("Changed since last year" in f for f in nodes["fsci-bs/methods"]["flags"])
    assert any("Back-translation" in f for f in nodes["fsci-bs/intro"]["flags"])
    assert out.review is not None and "1 node(s) changed since 2098-99" in out.review.reason
    assert out.version is not None and out.version.checksum.startswith("sha256:")


def test_when_the_formalizer_fails_a_person_is_asked() -> None:
    out = process_program(FakeLLM(), ctx())
    assert out.decision == "failed" and out.version is None
    assert out.review is not None and out.review.target_type == "ingest_run"
    assert outcome_results(out).reviews == [out.review]


# ----------------------------------------------------------------------- annual run


def crawl(server: Any, clock: Any) -> Any:
    crawler = Crawler(
        archive=memory_archive(),
        contact="bot@example.edu",
        allowed_hosts={server.host},
        clock=clock.time,
        sleep=clock.sleep,
    )
    return crawl_catalog(crawler, server.base_url, counts_url=f"{server.base_url}/programs-study/")


def candidates(base: str) -> list[dict[str, Any]]:
    page = f"{base}/thecollege/fakescience/"

    def c(id_: str, t: str, fam: str, url: str) -> dict[str, Any]:
        return {"id": id_, "name": id_, "type": t, "family": fam, "url": url, "evidence": []}

    return [
        c("fsci-bs", "major", "Fake Science", page),
        c("fsci-ba", "major", "Fake Science", page),
        c("fsci-minor", "minor", "Fake Science", page),
        c("fhis-ba", "major", "Fake History", f"{base}/thecollege/fakehistory/"),
    ]


E1_ANSWERS = [  # sorted by course code: FHIS 20100, FSCI 10150, FSCI 10200, FSCI 20100, FSCI 29900
    {"prereq": "FHIS 10100"},
    {"prereq": {"any": [{"placement": "FSCI 10150"}, {"consent": "instructor"}]}},
    {"prereq": {"any": ["FSCI 10100", "FSCI 10150"]}},
    {"prereq": {"all": ["FSCI 10200", {"standing": "third-year"}]}},
    {"prereq": None, "unparseable": True, "note": "consent only"},
]


def test_annual_run_end_to_end(catalog_server: Any, clock: Any) -> None:
    base = catalog_server.base_url
    tree = json.loads(json.dumps(RULES).replace(URL, f"{base}/thecollege/fakescience/"))
    fake = FakeLLM(
        script={
            "e1_prereq_formalizer": list(E1_ANSWERS),
            "e2_program_enumerator": [
                ToolCall("submit_programs", {"candidates": candidates(base)})
            ],
        }
    )
    script(fake, rules_yaml(tree))
    res = run_annual(
        fake,
        AnnualInputs(
            catalog_year="2099-00", previous_year=None, crawl=crawl(catalog_server, clock)
        ),
    )
    kinds = [r.target_type for r in res.reviews]
    # One course batch per subject, the E1 sentence it could not express, the course-block
    # problem, and the three programs the (scripted) formalizer did not answer for.
    assert kinds.count("course_batch") == 2
    batches = {r.target_id: r for r in res.reviews if r.target_type == "course_batch"}
    assert set(batches["2099-00:FSCI"].diff["requisites"]) == {
        "FSCI 10150",
        "FSCI 10200",
        "FSCI 20100",
    }
    assert [r.target_id for r in res.reviews if r.target_type == "requisite"] == [
        "2099-00:FSCI 29900"
    ]
    failed = [
        r.diff.get("program_id")
        for r in res.reviews
        if r.target_type == "ingest_run" and r.diff.get("program_id")
    ]
    assert failed == ["fsci-ba", "fsci-minor", "fhis-ba"]
    assert [v.program_id for v in res.versions] == ["fsci-bs"]
    version = res.versions[0]
    assert version.review.diff["checks"][2] == {
        "id": "c",
        "name": "Quotes are verbatim",
        "ok": True,
        "skipped": False,
        "problems": [],
    }
    assert [r.kind for r in res.runs].count("e1") == 5
    assert "e2" in [r.kind for r in res.runs]


def test_annual_run_stops_when_the_count_does_not_reconcile(
    catalog_server: Any, clock: Any
) -> None:
    base = catalog_server.base_url
    fake = FakeLLM(
        script={
            "e1_prereq_formalizer": list(E1_ANSWERS),
            "e2_program_enumerator": [
                ToolCall("submit_programs", {"candidates": candidates(base)[:2]})
            ],
        }
    )
    res = run_annual(
        fake,
        AnnualInputs(
            catalog_year="2099-00", previous_year=None, crawl=crawl(catalog_server, clock)
        ),
    )
    blocked = [r for r in res.reviews if r.target_id == "2099-00:e2"]
    assert blocked and "1 minors listed, 0 proposed" in " ".join(blocked[0].diff["problems"])
    assert not res.versions
    assert not any(c["task"].startswith("e3") for c in fake.calls)


def test_annual_run_without_agents_only_stages_courses(catalog_server: Any, clock: Any) -> None:
    fake = FakeLLM()
    res = run_annual(
        fake,
        AnnualInputs(
            catalog_year="2099-00",
            previous_year=None,
            crawl=crawl(catalog_server, clock),
            agents=False,
        ),
    )
    assert fake.calls == []
    assert {r.target_type for r in res.reviews} == {"course_batch", "ingest_run"}
    assert any("LLM_LIVE is off" in r.reason for r in res.reviews)
