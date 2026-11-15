"""CatalogView: the courses and named course lists an ingestion agent may refer to.

Built from a seed bundle (the pilot), from staged course rows plus last year's course lists
(the annual run), or from the database."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from planner_core.models import CourseList


@dataclass(frozen=True)
class CourseFacts:
    code: str
    title: str
    units: int = 100
    crosslists: tuple[str, ...] = ()


@dataclass
class CatalogView:
    catalog_year: str
    courses: dict[str, CourseFacts] = field(default_factory=dict)
    lists: dict[str, CourseList] = field(default_factory=dict)

    def has_course(self, code: str) -> bool:
        return code in self.courses

    def has_list(self, name: str) -> bool:
        return name in self.lists

    def list_members(self, name: str, _seen: frozenset[str] = frozenset()) -> list[str]:
        cl = self.lists.get(name)
        if cl is None or name in _seen:
            return []
        out = list(cl.courses)
        for sub in cl.sublists:
            out += [c for c in self.list_members(sub, _seen | {name}) if c not in out]
        return out

    @classmethod
    def build(
        cls,
        catalog_year: str,
        courses: Iterable[CourseFacts],
        lists: Iterable[CourseList] = (),
    ) -> CatalogView:
        return cls(
            catalog_year=catalog_year,
            courses={c.code: c for c in courses},
            lists={cl.name: cl for cl in lists},
        )


def from_bundle(bundle: object) -> CatalogView:
    """A `api.seed.bundle.SeedBundle` as a CatalogView."""
    from api.seed.bundle import SeedBundle

    assert isinstance(bundle, SeedBundle)
    return CatalogView.build(
        bundle.catalog_year,
        (CourseFacts(c.code, c.title, c.units, tuple(c.crosslists)) for c in bundle.courses),
        bundle.course_lists,
    )


def from_db(session: object, catalog_year: str) -> CatalogView:
    """Courses and course lists of one catalog year from the database."""
    import sqlalchemy as sa
    from api.db import models as m
    from sqlalchemy.orm import Session

    assert isinstance(session, Session)
    rows = session.execute(
        sa.select(m.Course.id, m.Course.code, m.Course.title, m.Course.units).where(
            m.Course.catalog_year == catalog_year
        )
    ).all()
    by_id = {r.id: r.code for r in rows}
    lists = [
        CourseList(
            name=cl.name,
            label=cl.label,
            courses=[by_id[i] for i in cl.course_ids if i in by_id],
            sublists=list(cl.sublists),
        )
        for cl in session.scalars(
            sa.select(m.CourseList).where(m.CourseList.catalog_year == catalog_year)
        )
    ]
    return CatalogView.build(
        catalog_year, (CourseFacts(r.code, r.title, r.units) for r in rows), lists
    )
