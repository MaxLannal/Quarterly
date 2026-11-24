#!/usr/bin/env python3
"""Add the courses the hand-checked seed lacks, from the original catalog crawl.

The crawl is the prototype's `data/` folder (catalog-bot: `catalog.json` plus the saved pages
in `raw/`). Courses already in `data/seed/<year>/courses/*.yaml` are never touched. Everything
added goes to one file, `courses/zz_crawl_import.yaml`, so it is easy to review or delete.

- Every added course is `needs_review: true` ("Not yet hand-checked" in the app).
- Every `source.quote` is checked verbatim (whitespace collapsed) against the saved page it
  cites; a course whose quote cannot be found is skipped and listed in the report.
- Cross-listed codes become their own entries, quoting the page's "Equivalent Course(s): ..."
  line, the same way the hand-checked seed does it.
- Prerequisites stay as text (`prereq_text`); no structured `prereq` rules are invented.
- `terms_offered` is filled only when "Terms Offered" is a plain list of quarters and does not
  say the course is not offered this year.

Usage:
    python3 scripts/import_crawl_courses.py --crawl "~/Downloads/catalog-bot 2/data"
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from collections import Counter
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
CODE = re.compile(r"^[A-Z]{2,5} \d{5}$")
SEASONS = {"Autumn": "AU", "Winter": "WI", "Spring": "SP", "Summer": "SU"}
ORDER = ("AU", "WI", "SP", "SU")
NOT_THIS_YEAR = re.compile(
    r"not offered (in )?(this academic year|2026\s*[-\u2013]\s*(20)?27)", re.IGNORECASE
)
OUT_NAME = "zz_crawl_import.yaml"


def page_text(path: Path) -> str:
    s = path.read_text(encoding="utf-8", errors="replace")
    s = re.sub(r"<br\s*/?>", "\n", s, flags=re.IGNORECASE)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s).replace("\xa0", " ")
    return re.sub(r"\s+", " ", s)


def collapse(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace("\xa0", " ")).strip()


def quarters(text: str) -> list[str]:
    if not text or NOT_THIS_YEAR.search(text):
        return []
    words = [w.strip(",;") for w in text.split(".")[0].split()]
    if not words or not all(w in SEASONS for w in words):
        return []
    found = {SEASONS[w] for w in words}
    return [q for q in ORDER if q in found]


def title_units(c: dict) -> tuple[str, str | None]:
    """(title, raw units string). Repairs entries whose whole header landed in the title."""
    title, units = collapse(c["title"]), c["units"]
    m = re.match(
        rf"^{re.escape(c['code'])}\.\s+(.*?)\.?\s+(\d+)(?:\.\d+)?(?:\s+Units?\.?)?$", title
    )
    if m:
        return m.group(1), m.group(2)
    return title, units


def header_in_title(c: dict) -> str | None:
    """The verbatim header, when the crawl stored the whole header as the title."""
    title = collapse(c["title"])
    return title if title.startswith(f"{c['code']}. ") else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--crawl", type=Path, required=True, help="the prototype's data/ folder")
    ap.add_argument("--year", default="2026-27")
    ap.add_argument("--report", type=Path, help="write a JSON report here")
    args = ap.parse_args()

    crawl = args.crawl.expanduser()
    courses_dir = REPO / "data" / "seed" / args.year / "courses"
    out_path = courses_dir / OUT_NAME

    seed_codes: set[str] = set()
    for f in sorted(courses_dir.glob("*.yaml")):
        if f.name != OUT_NAME:
            seed_codes |= {c["code"] for c in yaml.safe_load(f.read_text())["courses"]}

    cat = json.loads((crawl / "catalog.json").read_text())
    raw_for = {p["url"]: crawl / "raw" / f"{p['slug']}.html" for p in cat["pages"]}
    texts: dict[str, str] = {}

    def on_page(url: str, quote: str) -> bool:
        if url not in texts:
            path = raw_for.get(url)
            texts[url] = page_text(path) if path and path.exists() else ""
        return quote in texts[url]

    crawl_courses = [c for c in cat["courses"] if CODE.match(c["code"])]
    skipped_codes = [c["code"] for c in cat["courses"] if not CODE.match(c["code"])]
    primary = {c["code"]: c for c in crawl_courses}

    # Pass 1: decide which codes are added and what each one quotes.
    added: dict[str, tuple[dict, str]] = {}  # code -> (crawl course it copies, quote)
    unverified: list[str] = []
    for code, c in primary.items():
        if code in seed_codes:
            continue
        title, units = title_units(c)
        # Titles ending in "?" or ")" get no period before the units on the page.
        candidates = [f"{code}. {title}. {units} Units.", f"{code}. {title} {units} Units."]
        candidates = candidates if units else []
        candidates.append(f"{code}. {title}.")
        if whole := header_in_title(c):
            candidates.insert(0, whole)
        quote = next((q for q in candidates if on_page(c["url"], q)), None)
        if quote is None:
            unverified.append(code)
            continue
        added[code] = (c, quote)

    alias_unverified: list[str] = []
    for c in crawl_courses:
        if not c["equivalent"]:
            continue
        quote = f"Equivalent Course(s): {collapse(c['equivalent'])}"
        for e in c["equivalent_codes"]:
            if e in seed_codes or e in primary or e in added:
                continue
            if on_page(c["url"], quote):
                added[e] = (c, quote)
            else:
                alias_unverified.append(e)

    final_codes = seed_codes | set(added)

    # Pass 2: build the entries.
    entries = []
    for code in sorted(added):
        c, quote = added[code]
        title, units = title_units(c)
        group = ({c["code"], *c["equivalent_codes"]} & final_codes) - {code}
        entry: dict = {"code": code, "title": title, "units": int(units) if units else 100}
        if c.get("description"):
            entry["description"] = collapse(c["description"])
        if c.get("notes"):
            entry["notes"] = collapse(c["notes"])
        if group:
            entry["crosslists"] = sorted(group)
        if c.get("prerequisites"):
            entry["prereq_text"] = collapse(c["prerequisites"])
        if q := quarters(c.get("terms") or ""):
            entry["terms_offered"] = q
        entry["source"] = {"url": c["url"], "quote": quote}
        entry["needs_review"] = True
        entries.append(entry)

    header = (
        f"# Added from the original catalog crawl (fetched {cat['fetched_at'][:10]}) by\n"
        "# scripts/import_crawl_courses.py: courses the hand-checked files lack.\n"
        "# Every source.quote was found verbatim (whitespace collapsed) on the saved page;\n"
        "# every entry needs review.\n"
    )
    out_path.write_text(
        header
        + yaml.safe_dump({"courses": entries}, sort_keys=False, allow_unicode=True, width=120)
    )

    report = {
        "seed_courses_before": len(seed_codes),
        "crawl_entries": len(cat["courses"]),
        "added_total": len(entries),
        "added_primary": sum(1 for code in added if code in primary),
        "added_crosslisted_aliases": sum(1 for code in added if code not in primary),
        "total_after": len(final_codes),
        "skipped_sequence_headers": len(skipped_codes),
        "skipped_unverified_quote": sorted(unverified),
        "skipped_alias_unverified_quote": sorted(set(alias_unverified)),
        "added_by_subject": dict(Counter(code.split()[0] for code in added).most_common()),
    }
    if args.report:
        args.report.write_text(json.dumps(report, indent=1))
    print(f"wrote {out_path.relative_to(REPO)}: {len(entries)} courses")
    for k, v in report.items():
        if k != "added_by_subject":
            print(f"  {k}: {len(v) if isinstance(v, list) else v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
