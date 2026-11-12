import pytest
from planner_core import CORE_VERSION, check_certificate, verify
from planner_core.changes import ChangeOpError, apply_ops
from planner_core.hashing import canonical_json, plan_hash, program_key, rules_hash
from planner_core.models import (
    AddOp,
    Catalog,
    Certificate,
    LockOp,
    MoveOp,
    PlanItem,
    PlanState,
    ProgramRules,
    RemoveOp,
    RuleSet,
    UnlockOp,
)
from planner_core.terms import (
    academic_year,
    is_before,
    parse_term,
    resolve_term_ref,
    term_at,
    term_key,
    year_index,
)


def plan(*items: PlanItem) -> PlanState:
    return PlanState(catalog_year="2026-27", entry_term="2026-AU", items=list(items))


def test_term_order_and_years() -> None:
    terms = ["2027-WI", "2026-AU", "2027-SU", "2027-SP", "2027-AU"]
    assert sorted(terms, key=term_key) == ["2026-AU", "2027-WI", "2027-SP", "2027-SU", "2027-AU"]
    assert is_before("2026-AU", "2027-WI") and not is_before("2027-WI", "2027-WI")
    assert academic_year("2027-WI") == 2026 and academic_year("2027-AU") == 2027
    assert year_index("2028-SP", "2026-AU") == 2
    assert term_at("2026-AU", 1, "AU") == "2026-AU"
    assert term_at("2026-AU", 2, "SP") == "2028-SP"
    assert resolve_term_ref("Y2-SP", "2026-AU") == "2028-SP"
    assert resolve_term_ref("2028-SP", "2026-AU") == "2028-SP"
    assert parse_term("2026-AU") == (2026, "AU")
    for bad in ("2026-FA", "26-AU"):
        with pytest.raises(ValueError):
            parse_term(bad)
    with pytest.raises(ValueError):
        resolve_term_ref("Y2-XX", "2026-AU")


def test_plan_hash_ignores_order_and_ids() -> None:
    a = PlanItem(course="CMSC 14100", term="2026-AU", id="1")
    b = PlanItem(course="CMSC 14200", term="2027-WI", id="2")
    h = plan_hash(plan(a, b))
    assert h.startswith("sha256:")
    assert plan_hash(plan(b.model_copy(update={"id": "9"}), a)) == h
    assert plan_hash(plan(a, b.model_copy(update={"term": "2027-SP"}))) != h
    assert canonical_json({"b": 1, "a": [1, 2]}) == '{"a":[1,2],"b":1}'


def test_rules_hash_and_key() -> None:
    program = ProgramRules.model_validate(
        {"id": "x", "catalog_year": "2026-27", "rules": {"slot": {"any_of": ["CMSC 14100"]}}}
    )
    assert program_key(program) == "x@2026-27"
    assert rules_hash(program) == rules_hash(program.model_copy(deep=True))


def test_apply_ops() -> None:
    base = plan(
        PlanItem(course="CMSC 14100", term="2026-AU"),
        PlanItem(course="CMSC 14200", term="2026-AU"),
        PlanItem(slot_ref="core/hca/arts", term="2027-WI"),
    )
    out = apply_ops(
        base,
        [
            AddOp(course="MATH 15100", term="2026-AU"),
            MoveOp(course="CMSC 14200", to_term="2027-WI"),
            RemoveOp(slot_ref="core/hca/arts"),
            LockOp(course="CMSC 14100"),
        ],
    )
    assert [(i.course or i.slot_ref, i.term, i.locked) for i in out.items] == [
        ("CMSC 14100", "2026-AU", True),
        ("CMSC 14200", "2027-WI", False),
        ("MATH 15100", "2026-AU", False),
    ]
    assert len(base.items) == 3  # input untouched
    with pytest.raises(ChangeOpError, match="locked"):
        apply_ops(out, [MoveOp(course="CMSC 14100", to_term="2027-SP")])
    unlocked = apply_ops(out, [UnlockOp(course="CMSC 14100", term="2026-AU")])
    assert apply_ops(unlocked, [RemoveOp(course="CMSC 14100")]).items[0].course == "CMSC 14200"
    with pytest.raises(ChangeOpError, match="no plan item"):
        apply_ops(base, [RemoveOp(course="MATH 20700", term="2026-AU")])
    twice = apply_ops(base, [AddOp(course="CMSC 14100", term="2027-AU")])
    with pytest.raises(ChangeOpError, match="give the term"):
        apply_ops(twice, [RemoveOp(course="CMSC 14100")])
    assert (
        len(
            apply_ops(
                twice, [MoveOp(course="CMSC 14100", from_term="2027-AU", to_term="2028-AU")]
            ).items
        )
        == 4
    )


def test_verifier_entry_points_are_stubs_until_prompt_02() -> None:
    rules = RuleSet(catalog_year="2026-27")
    catalog = Catalog(catalog_year="2026-27")
    with pytest.raises(NotImplementedError):
        verify(plan(), rules, catalog)
    cert = Certificate(plan_hash="sha256:x", rules={})
    with pytest.raises(NotImplementedError):
        check_certificate(plan(), rules, catalog, cert)
    assert CORE_VERSION
