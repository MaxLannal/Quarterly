"""Summer Session offerings from the course finder at summer.uchicago.edu (Richard, FEEDBACK
"Check Summer Catalog", 2026-11-16) -> `data/seed/<year>/summer_courses.yaml`.

The finder is a static site: each course's data sits at
`/page-data/courses/<slug>/page-data.json` and the course list at
`/page-data/course-index/page-data.json`. Only courses open to College students ("Undergraduate"
or "Both") with a course code are kept; pre-college-only courses are not.

    uv run python -m api.seed.summer --fetch /tmp/summer-pages --year 2026-27
    uv run python -m api.seed.summer --from /tmp/summer-pages --year 2026-27

`--fetch` downloads every course page (one request a second) into that folder, then writes the
YAML; `--from` writes it from pages already downloaded.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

import yaml
from api.seed.bundle import load_bundle
from api.seed.models import SummerFile, SummerOffering

SITE = "https://summer.uchicago.edu"
AGENT = "Mozilla/5.0 (compatible; QuarterlyCatalogCheck)"
AUDIENCES = ("Undergraduate", "Both")
_CODE = re.compile(r"^([A-Z]{4}) (\d{5})(?: (\S+))?$")
ROOT = Path(__file__).resolve().parents[4]


def _codes(text: str | None) -> list[str]:
    """Course codes in a free-text cross-list field ("ANTH 21420/SOSC 20224, ...")."""
    return sorted({f"{a} {b}" for a, b in re.findall(r"\b([A-Z]{4}) (\d{5})\b", text or "")})


def parse(record: dict[str, Any], known: set[str]) -> SummerOffering | None:
    """One course page's data -> an offering, or None when it is not for College students or
    has no course code."""
    if record.get("courseType") not in AUDIENCES:
        return None
    raw = (record.get("courseCode") or "").strip()
    m = _CODE.match(raw)
    if m is None:
        return None
    code = f"{m[1]} {m[2]}"
    crosslists = [c for c in _codes(record.get("crossListedCourseCode")) if c != code]
    return SummerOffering.model_validate(
        {
            "code": code,
            "section": m[3],
            "title": (record.get("courseTitle") or "").strip(),
            "audience": record["courseType"],
            "session": record.get("startOfSession"),
            "start": record.get("courseStartDate"),
            "end": record.get("courseEndDate"),
            "modality": record.get("remoteOrCampus"),
            "core": bool(record.get("coreCourse")),
            "crosslists": crosslists,
            "in_catalog": code in known or any(c in known for c in crosslists),
            "source": {"url": f"{SITE}/courses/{record['courseSlug']}/", "quote": raw},
        }
    )


def build(records: list[dict[str, Any]], known: set[str], fetched: dt.date) -> SummerFile:
    offerings = [o for r in records if (o := parse(r, known)) is not None]
    offerings.sort(key=lambda o: (o.code, o.section or "", o.start or dt.date.min))
    summer = max((o.start.year for o in offerings if o.start), default=fetched.year)
    return SummerFile(summer=summer, fetched=fetched, summer_courses=offerings)


def to_yaml(summer: SummerFile) -> str:
    head = (
        f"# Summer Session {summer.summer} courses open to College students, from the course\n"
        f"# finder at {SITE}/undergraduates/undergraduate-course-finder/ (fetched "
        f"{summer.fetched}).\n"
        "# Written by `python -m api.seed.summer`; source.quote is the course code as the page\n"
        "# shows it. Courses with in_catalog: false are not in this catalog year's course list\n"
        "# and are not added to the planner (no units are stated; OPEN_QUESTIONS DF-S1).\n"
    )
    body = summer.model_dump(mode="json")
    rows = []
    for o in body["summer_courses"]:
        row = {k: v for k, v in o.items() if v not in (None, [], False) or k == "in_catalog"}
        row["source"] = {k: v for k, v in o["source"].items() if v is not None}
        rows.append(row)
    body["summer_courses"] = rows
    return head + yaml.safe_dump(body, sort_keys=False, allow_unicode=True, width=100)


def _get(url: str) -> Any:
    request = urllib.request.Request(url, headers={"User-Agent": AGENT})
    with urllib.request.urlopen(request, timeout=30) as resp:
        return json.load(resp)


def fetch(folder: Path, delay_s: float = 1.0) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    index = _get(f"{SITE}/page-data/course-index/page-data.json")
    found = index["result"]["data"]["allContentfulSuCourse"]
    nodes = found.get("nodes") or [e["node"] for e in found.get("edges", [])]
    for node in nodes:
        out = folder / f"{node['courseSlug']}.json"
        if out.exists():
            continue
        data = _get(f"{SITE}/page-data/courses/{node['courseSlug']}/page-data.json")
        out.write_text(json.dumps(data["result"]["data"]["contentfulSuCourse"]))
        time.sleep(delay_s)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Summer Session offerings -> seed YAML")
    where = parser.add_mutually_exclusive_group(required=True)
    where.add_argument("--fetch", type=Path, help="download the course pages into this folder")
    where.add_argument("--from", dest="source", type=Path, help="use pages already downloaded")
    parser.add_argument("--year", default="2026-27")
    args = parser.parse_args(argv)
    folder: Path = args.fetch or args.source
    if args.fetch:
        fetch(folder)
    records = [json.loads(p.read_text()) for p in sorted(folder.glob("*.json"))]
    year_dir = ROOT / "data" / "seed" / args.year
    known = {c.code for c in load_bundle(year_dir).courses}
    summer = build(records, known, dt.date.today())
    out = year_dir / "summer_courses.yaml"
    out.write_text(to_yaml(summer), encoding="utf-8")
    inside = sum(o.in_catalog for o in summer.summer_courses)
    print(
        f"summer: {len(summer.summer_courses)} offerings for College students "
        f"({inside} of courses in the catalog) -> {out.relative_to(ROOT)}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
