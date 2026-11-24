"""The homepage chapel (apps/web/public/home/course-chapel.json) shows real courses only.

Every [code, title] in the file must be a seeded course with exactly that title, so the picture
never shows a course the catalog does not have and a click always opens a real course page. If
this fails after a seed change, run `python3 tools/course-chapel/build.py`.
"""

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "apps" / "web" / "public" / "home" / "course-chapel.json"
SEED = ROOT / "data" / "seed" / "2026-27" / "courses"


def _seeded() -> dict[str, str]:
    out: dict[str, str] = {}
    for path in sorted(SEED.glob("*.yaml")):
        for course in yaml.safe_load(path.read_text())["courses"]:
            title = " ".join(str(course["title"]).replace("\u0096", "\u2013").split())
            out[str(course["code"])] = title
    return out


def test_every_title_on_the_homepage_is_a_seeded_course() -> None:
    data = json.loads(DATA.read_text())
    seeded = _seeded()
    courses = data["courses"]
    assert len(courses) == 1600
    assert len({title.casefold() for _, title in courses}) == len(courses)
    wrong = [(code, title) for code, title in courses if seeded.get(code) != title]
    assert wrong == []


def test_the_drawing_matches_its_size() -> None:
    field = json.loads(DATA.read_text())["field"]
    cells = field["cols"] * field["rows"]
    assert len(field["cls"]) == cells
    assert len(field["glow"]) == cells
    assert set(field["cls"]) <= set("01234")
