"""Catalog lookups: cross-list groups, selector semantics (docs/CONTRACTS.md), lists, grades."""

from core_support import T, catalog, course, plan, ruleset
from planner_core.dsl import excepted, residency_fraction, share_applies
from planner_core.index import Index, PlanFacts, describe_selector, grade_ok
from planner_core.models import Selector
from planner_core.tree import stricter

CAT = catalog(
    [
        course("CMSC 25300", tags=["ml"]),
        course("ARTS 10100", core_tags=["arts"], units=50),
        "CMSC 29700",
        "MATH 20300",
        "SEQA 10100",
        "SEQA 10200",
        "SEQB 10100",
    ],
    crosslist_groups=[["TTIC 31020", "CMSC 25300"]],  # TTIC 31020 has no catalog row of its own
    course_lists=[
        {"name": "seqs", "courses": ["MATH 20300"], "sublists": ["seq-a", "seq-b", "seqs"]},
        {"name": "seq-a", "courses": ["SEQA 10100", "SEQA 10200"]},
        {"name": "seq-b", "courses": ["SEQB 10100"]},
    ],
    relations=[{"a": "SEQA 10100", "b": "SEQB 10100", "kind": "replaces"}],
)
IDX = Index(CAT, ruleset())


def sel(**fields: object) -> Selector:
    return Selector.model_validate(fields)


def test_cross_list_groups_are_one_course() -> None:
    assert IDX.canon("TTIC 31020") == IDX.canon("CMSC 25300") == "CMSC 25300"
    assert IDX.members("TTIC 31020") == ("CMSC 25300", "TTIC 31020")
    assert IDX.known("TTIC 31020") and not IDX.known("GONE 10000")
    assert IDX.units("ARTS 10100") == 50 and IDX.units("GONE 10000") == 100
    assert IDX.tags("TTIC 31020") == {"ml"} and IDX.tags("ARTS 10100") == {"core:arts"}
    assert IDX.alts("SEQA 10100") == {"SEQA 10100", "SEQB 10100"}


def test_selector_semantics() -> None:
    cs = sel(subject="CMSC", number_range=[20000, 29999], exclude=["CMSC 29700"])
    assert IDX.matches(cs, "CMSC 25300")
    assert IDX.matches(cs, "TTIC 31020")  # matches wherever its cross-listed partner does
    assert not IDX.matches(cs, "CMSC 29700") and not IDX.matches(cs, "MATH 20300")
    assert not IDX.matches(sel(subject="CMSC", exclude=["TTIC 31020"]), "CMSC 25300")
    assert IDX.matches(sel(codes=["TTIC 31020"]), "CMSC 25300")
    assert not IDX.matches(sel(codes=["MATH 20300"]), "CMSC 25300")
    assert IDX.matches(sel(tags=["core:arts"]), "ARTS 10100")
    assert IDX.matches(sel(tags=["ml", "zzz"]), "TTIC 31020")
    assert not IDX.matches(sel(tags=["ml"]), "ARTS 10100")
    # every criterion that is set must hold
    assert not IDX.matches(sel(subject="CMSC", tags=["core:arts"]), "CMSC 25300")
    # list membership includes sublists; union is the only "or" across criteria
    assert IDX.matches(sel(list="seqs"), "SEQB 10100") and IDX.matches(
        sel(list="seqs"), "MATH 20300"
    )
    assert not IDX.matches(sel(list="seqs"), "CMSC 25300")
    assert not IDX.matches(sel(list="no-such-list"), "CMSC 25300")
    either = sel(union=[{"subject": "MATH"}, {"tags": ["core:arts"]}])
    assert IDX.matches(either, "MATH 20300") and IDX.matches(either, "ARTS 10100")
    assert not IDX.matches(either, "CMSC 25300")
    assert IDX.matches(sel(number_range=[20000, 20300], union=[{"subject": "MATH"}]), "MATH 20300")


def test_lists_sequences_and_descriptions() -> None:
    assert IDX.list_members("seqs") == {"MATH 20300", "SEQA 10100", "SEQA 10200", "SEQB 10100"}
    assert IDX.sequences([sel(union=[{"list": "seqs"}])]) == {
        "seq-a": frozenset({"SEQA 10100", "SEQA 10200"}),
        "seq-b": frozenset({"SEQB 10100"}),
        "seqs": IDX.list_members("seqs"),
    }
    assert IDX.sequences([sel(subject="CMSC")]) == {}
    assert IDX.list_codes("seqs", limit=2) == ["MATH 20300", "SEQA 10100"]
    assert IDX.list_codes("nope") == []
    text = describe_selector(
        sel(codes=["CMSC 25300"], list="seqs", number_range=[10000, 19999], exclude=["MATH 20300"]),
        IDX,
    )
    assert text == (
        "CMSC 25300, courses numbered 10000-19999, the list seqs "
        "(e.g. MATH 20300, SEQA 10100, SEQA 10200, SEQB 10100), except MATH 20300"
    )
    assert describe_selector(sel(list="seqs")) == "the list seqs"


def test_grades() -> None:
    assert grade_ok("B", "C-") and grade_ok("C-", "C-") and not grade_ok("D+", "C-")
    assert grade_ok(None, "C-") and grade_ok("F", None)
    assert not grade_ok("P", "C-") and grade_ok("P", "P") and grade_ok("d", "p")
    assert not grade_ok("??", "C") and not grade_ok("A", "??")
    assert stricter("C", "B-") == "B-" and stricter("B", "C") == "B"
    assert (
        stricter(None, "C") == "C" and stricter("C", None) == "C" and stricter(None, None) is None
    )


def test_plan_facts() -> None:
    p = plan(
        {
            T[0]: ["ARTS 10100", {"slot_ref": "core/x"}, {"course": "MATH 20300", "units": 150}],
            T[1]: ["TTIC 31020", {"course": "SEQA 10100", "status": "transfer"}, "GONE 10000"],
        },
        credits=[{"kind": "AP", "label": "AP", "maps_to": "SEQB 10100", "units": 100}],
        entry_year_level=2,
    )
    facts = PlanFacts(p, IDX)
    assert facts.loads == {T[0]: 300, T[1]: 200} and facts.terms == [T[0], T[1]]
    assert facts.course_count(T[0]) == 3 and facts.course_count(T[1]) == 2
    assert facts.class_year(T[0]) == 2 and facts.class_year(T[3]) == 3
    assert set(facts.taken) == {
        "ARTS 10100",
        "MATH 20300",
        "CMSC 25300",
        "SEQA 10100",
        "SEQB 10100",
    }
    assert facts.taken["CMSC 25300"].ref == "TTIC 31020@2027-WI"
    assert facts.taken["SEQB 10100"].ref == "credit:SEQB 10100"
    # the credit for the replaced course counts as SEQA 10100, and comes before every term
    done = facts.done("SEQA 10100", T[0], strict=True)
    assert done is not None and done.status == "credit"
    assert facts.done("CMSC 25300", T[0]) is None and facts.done("TTIC 31020", T[1]) is not None
    assert facts.done("TTIC 31020", T[1], strict=True) is None


def test_share_and_residency_helpers() -> None:
    from core_support import college, program

    slot = {"slot": {"any_of": ["MATH 20300"]}}
    major, minor = program("math-ba", slot), program("math-minor", slot, type="minor")
    core = program("gen-ed", slot, type="major")
    policy = college(core_program_id="gen-ed", residency_min_fraction=0.5)
    assert share_applies("type:minor", minor, None) and not share_applies("type:minor", major, None)
    assert share_applies("core", core, policy) and not share_applies("core", core, None)
    assert share_applies("program:math-*", major, None) and share_applies("math-ba", major, None)
    assert not share_applies("program:cmsc-*", major, None)
    assert excepted("core/language", ["language"]) and excepted("core/hca/arts", ["core/hca/arts"])
    assert not excepted("language/x", ["language"])  # the program id is not a node id
    assert not excepted("core/arts", ["language"])
    assert residency_fraction(major, policy) == 0.5 and residency_fraction(major, None) is None
    assert residency_fraction(core, policy) is None
    own = program("x", slot, policy={"residency": {"min_fraction": 0.75}})
    assert residency_fraction(own, None) == 0.75
