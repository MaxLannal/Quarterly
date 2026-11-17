"""Per-page two-word pseudonyms (SPEC "Anonymity inside the forum"): random, stable on one page
("Quiet Heron"), drawn again on every other page so readers cannot link posts across pages.

The handle is random, not derived from the account, so it carries no information: knowing an
account's handle on one page says nothing about its handle elsewhere.
"""

from __future__ import annotations

import secrets

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from api.db import models as m

ADJECTIVES = (
    "Quiet", "Amber", "Brisk", "Calm", "Clever", "Copper", "Crisp", "Curious", "Dapper",
    "Distant", "Dusky", "Eager", "Early", "Fair", "Gentle", "Gilded", "Golden", "Hidden",
    "Hollow", "Humble", "Idle", "Ivory", "Jolly", "Keen", "Kind", "Lucid", "Lunar", "Mellow",
    "Misty", "Modest", "Nimble", "Noble", "Olive", "Pale", "Patient", "Plain", "Polar",
    "Proud", "Rapid", "Rustic", "Sable", "Scarlet", "Silent", "Silver", "Sleepy", "Slow",
    "Snowy", "Solar", "Steady", "Stormy", "Sunny", "Swift", "Tidy", "Velvet", "Vivid",
    "Wandering", "Warm", "Wary", "Wild", "Windy", "Wise", "Witty", "Woolly", "Young",
)  # fmt: skip
NOUNS = (
    "Heron", "Badger", "Beaver", "Bison", "Bluejay", "Cardinal", "Cedar", "Comet", "Crane",
    "Creek", "Falcon", "Fern", "Finch", "Fox", "Gopher", "Grouse", "Hare", "Hawk", "Hazel",
    "Ibis", "Juniper", "Kestrel", "Lark", "Linden", "Loon", "Lynx", "Maple", "Marten",
    "Meadow", "Mink", "Moose", "Moth", "Newt", "Oak", "Osprey", "Otter", "Owl", "Pine",
    "Plover", "Prairie", "Quail", "Raven", "Reed", "Robin", "Sparrow", "Spruce", "Squirrel",
    "Starling", "Stoat", "Swallow", "Sycamore", "Tern", "Thrush", "Trout", "Tulip", "Walnut",
    "Warbler", "Willow", "Wolf", "Wren", "Yarrow", "Aspen", "Birch", "Cricket",
)  # fmt: skip

DELETED = "[deleted account]"


def random_handle() -> str:
    return f"{secrets.choice(ADJECTIVES)} {secrets.choice(NOUNS)}"


def pseudonym_for(db: Session, ref: str, page_id: int) -> m.Pseudonym:
    """The pseudonym of `ref` on `page_id`, drawn on first use. Safe under concurrent first
    posts: conflicts on either unique key are ignored and the row is read back."""
    for attempt in range(64):
        existing = db.scalar(
            sa.select(m.Pseudonym).where(
                m.Pseudonym.author_ref == ref, m.Pseudonym.course_instructor_id == page_id
            )
        )
        if existing is not None:
            return existing
        handle = random_handle()
        if attempt >= 48:  # ~4,000 handles per page; past that, add a number
            handle = f"{handle} {secrets.randbelow(9000) + 1000}"
        db.execute(
            insert(m.Pseudonym)
            .values(author_ref=ref, course_instructor_id=page_id, handle=handle)
            .on_conflict_do_nothing()
        )
    raise RuntimeError("could not draw a free pseudonym")
