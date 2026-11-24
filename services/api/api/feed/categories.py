"""The feed's categories: families of catalog subjects a student can focus on.

Every subject in the catalog maps to exactly one category through `SUBJECT_CATEGORY`; a subject
the mapping does not know yet (a new department) falls into "more" (Interdisciplinary), so a
course is never left out of the feed. `tests/test_feed_units.py` checks that every seeded subject
is mapped by name, not by that fallback.

Each category carries a `motif`: the family of generated SVG illustrations its course spotlights
get on the page (lattices for mathematics, orbits for the physical sciences, ...). A few subjects
pick a motif of their own (music gets staves, film gets frames).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class Category:
    key: str
    label: str
    blurb: str
    motif: str


CATEGORIES: tuple[Category, ...] = (
    Category(
        "core",
        "The Core",
        "The shared conversation every College student joins: texts, problems, civilizations.",
        "arches",
    ),
    Category(
        "math",
        "Mathematics & Statistics",
        "Proof, structure and chance, from first analysis to the theory of measurement.",
        "lattice",
    ),
    Category(
        "physical",
        "Physical Sciences & Engineering",
        "Particles, planets, molecules and the machines that make quantum things useful.",
        "orbits",
    ),
    Category(
        "computing",
        "Computer & Data Science",
        "Algorithms, systems, machine learning and the craft of programs that think.",
        "circuit",
    ),
    Category(
        "life",
        "Life Sciences & Medicine",
        "Cells, genomes, brains, evolution and the health of whole populations.",
        "cells",
    ),
    Category(
        "mind",
        "Mind, Brain & Language",
        "How we perceive, learn, speak and grow: psychology, cognition and linguistics.",
        "waves",
    ),
    Category(
        "economics",
        "Economics & Business",
        "Markets, incentives, strategy and the money that moves through all of them.",
        "curves",
    ),
    Category(
        "society",
        "Society, Politics & Law",
        "Power, policy, justice and the lives of cities, from Chicago to the world.",
        "network",
    ),
    Category(
        "history",
        "History & Archaeology",
        "Empires, revolutions and everyday lives, read from archives and excavations.",
        "columns",
    ),
    Category(
        "philosophy",
        "Philosophy & Religion",
        "The oldest questions, asked again: being, knowing, ethics, scripture and faith.",
        "scrolls",
    ),
    Category(
        "literature",
        "Literature & Writing",
        "Novels, poems and essays to read closely, and workshops to write your own.",
        "pages",
    ),
    Category(
        "languages",
        "Languages",
        "Over forty languages, ancient and living, from Hittite and Sanskrit to Kreyòl.",
        "glyphs",
    ),
    Category(
        "arts",
        "Arts, Music, Theater & Film",
        "Studios, stages, screens and scores: making art and learning to see it.",
        "notes",
    ),
    Category(
        "area",
        "Area & Civilization Studies",
        "East Asia, South Asia, the Middle East, Latin America, Europe: whole worlds in depth.",
        "tiles",
    ),
    Category(
        "environment",
        "Environment & Geography",
        "Climate, the Earth's deep history and the maps that explain where things happen.",
        "maps",
    ),
    Category(
        "more",
        "Interdisciplinary",
        "Courses that cross the lines: science communication, signature seminars and more.",
        "constellation",
    ),
)

BY_KEY: dict[str, Category] = {c.key: c for c in CATEGORIES}
FALLBACK = "more"

#: Category key -> its subjects (space-separated codes).
_FAMILIES: dict[str, str] = {
    "core": "HUMA SOSC BPRO IRHU",
    "math": "MATH STAT CAAM FINM QMSA",
    "physical": "PHYS ASTR CHEM PHSC MENG MPHY PSMS",
    "computing": "CMSC DATA MACS TTIC MPCS CAPP DIGS",
    "life": (
        "BIOS BCMB BPHS CABI CCTS CPNS DVBI ECEV EVOL GENE HGEN IMMU MEDC MGCB "
        "MICR MOLM MOMN MPMM MSPH NCDV NPHP NSCI NURB ORGB PATH PBHS HLTH BMSC"
    ),
    "mind": "PSYC COGS LING CHDV",
    "economics": "ECON ECMA BUSN PECO",
    "society": (
        "PLSC SOCI PBPL PPHA LLSO HMRT INRE ANTH EDSO SSAD GNSE DEMS MAPS CHSS "
        "PUBD CEGU RDIN CHST PARR"
    ),
    "history": "HIST ARKE NEAA ANCM HIPS KNOW CLCV CLAS MDVL RENS",
    "philosophy": (
        "PHIL RLST AASR BIBL DVPR HCHR HIJD HREL ISLM JTAC RAME RETH RLVC THEO SCTH PUBT CDIN"
    ),
    "literature": "ENGL CMLT CRWR FNDL WRIT RLIT RLLT MAPH CCCT",
    "languages": (
        "AANL ARAB ARME ASLG BANG BASQ BCSN CATA CHIN CZEC FREN GREK GRMN HEBR "
        "HIND ITAL JAPN KAZK KORE KREY LATN MARA MOGK NELG NORW PERS POLI PORT "
        "RUSS SANS SPAN SWAH TAML TBTN TURK UGAR UKRA URDU UZBK YDDH"
    ),
    "arts": "ARTH ARTV ARCH MUSI TAPS CMST MADD",
    "area": "EALC SALC NEHC NELC LACS REES JWSC AMER GLST",
    "environment": "GEOS ENSC ENST GEOG GISC CCSG NTSC",
    "more": "SCPD SIGN TRNC NOCR",
}

#: Subject code -> category key. Every subject of the 2026-27 catalog is listed by name.
SUBJECT_CATEGORY: dict[str, str] = {
    subject: key for key, subjects in _FAMILIES.items() for subject in subjects.split()
}

#: Subjects whose illustrations use another motif than their category's.
SUBJECT_MOTIF: dict[str, str] = {
    "MUSI": "notes",
    "CMST": "frames",
    "ARTH": "frames",
    "ARTV": "frames",
    "MADD": "frames",
    "ARCH": "arches",
    "TAPS": "frames",
    "ASTR": "orbits",
    "CHEM": "lattice",
    "STAT": "curves",
    "LING": "glyphs",
    "NSCI": "waves",
    "GEOS": "maps",
    "CRWR": "pages",
}


def category_for(subject: str) -> Category:
    return BY_KEY[SUBJECT_CATEGORY.get(subject.upper(), FALLBACK)]


def motif_for(subject: str) -> str:
    return SUBJECT_MOTIF.get(subject.upper(), category_for(subject).motif)


def known_keys(keys: Iterable[str]) -> list[str]:
    """The valid category keys among `keys`, in catalog order, without duplicates."""
    wanted = {k.strip().lower() for k in keys if k and k.strip()}
    return [c.key for c in CATEGORIES if c.key in wanted]


def subjects_by_category(subjects: Iterable[str]) -> dict[str, list[str]]:
    """Category key -> the given subjects that fall in it (sorted); every key present."""
    out: dict[str, list[str]] = {c.key: [] for c in CATEGORIES}
    for subject in sorted(set(subjects)):
        out[category_for(subject).key].append(subject)
    return out
