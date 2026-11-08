#!/usr/bin/env python3
"""Build a local copy of the UChicago College Catalog for the catalog chatbot.

Crawls the program and policy pages linked from Programs of Study, respects
robots.txt, waits between requests, and writes:

  data/catalog.json   structured pages, sections, and courses (with prerequisite
                      and equivalent-course links for later graphs)
  data/catalog.md     compact text version that goes into Claude's context
  data/stats.json     page, course, and token estimates

Usage:  python3 build_catalog.py            (about 4 minutes; rerun to resume)
        python3 build_catalog.py --delay 4  (slower, gentler crawl)
        python3 build_catalog.py --refresh  (download every page again)

Each page is saved in data/raw/ as it arrives. If the site stops responding,
the crawl pauses, builds from what it has, and a rerun fetches only the rest.

Check that your use fits the University's terms, and ask the College or the
Registrar about an official data feed if you deploy this beyond a prototype.
Standard library only.
"""
import argparse
import html
import json
import random
import re
import socket
import time
import urllib.error
import urllib.request
import urllib.robotparser
from datetime import datetime, timezone
from pathlib import Path

BASE = "http://collegecatalog.uchicago.edu"
START = BASE + "/thecollege/programsofstudy/"
UA = "QuarterlyCatalogBot/0.1 (student prototype)"
SKIP = re.compile(r"/(search|css|js|fonts|images|archives|azindex|catalogcontents|gallery|custom404)/|\.(css|ico|xml|pdf|js)(\?|$)")
CODE = re.compile(r"\b([A-Z]{4})\s(\d{5})\b")
DETAIL_LABELS = re.compile(r"(Instructor\(s\)|Terms Offered|Prerequisite\(s\)|Corequisite\(s\)|Equivalent Course\(s\)|Note\(s\)|Distribution)\s*:\s*")

CORE_PAGES = {"humanities": "Humanities", "civilizationstudies": "Civilization Studies", "artscore": "Arts",
              "socialsciences": "Social Sciences", "physicalsciences": "Physical Sciences",
              "biologicalsciencescore": "Biological Sciences", "mathematicalsciencescore": "Mathematical Sciences"}
OUT = Path(__file__).resolve().parent / "data"
RAW = OUT / "raw"  # saved copies of each page, so reruns resume


RETRY_CODES = (429, 500, 502, 503, 504)
BACKOFF = (0, 10, 30, 60)  # seconds to wait before each attempt


def fetch(url, robots, delay):
    """Return (html, None) or (None, reason). Waits between requests and backs off when the site pushes back."""
    if robots and not robots.can_fetch(UA, url):
        return None, "blocked by robots.txt"
    time.sleep(delay + random.uniform(0, delay / 2))
    reason = "unknown error"
    for attempt, pause in enumerate(BACKOFF):
        if pause:
            print(f"  {reason}, waiting {pause}s before trying again")
            time.sleep(pause)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode("utf-8", errors="ignore"), None
        except urllib.error.HTTPError as e:
            if e.code not in RETRY_CODES:
                return None, f"HTTP {e.code}"
            reason = f"the site is busy (HTTP {e.code})"
        except (urllib.error.URLError, ConnectionError, TimeoutError, socket.timeout) as e:
            reason = f"the site refused or dropped the connection ({getattr(e, 'reason', e)})"
    return None, reason


def text(fragment):
    fragment = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", fragment, flags=re.S)
    fragment = re.sub(r"<br\s*/?>|</(p|li|tr|h[1-6]|div)>", "\n", fragment)
    fragment = re.sub(r"</t[dh]>", "\t", fragment)
    fragment = re.sub(r"<[^>]+>", "", fragment)
    fragment = html.unescape(fragment).replace("\xa0", " ")
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in fragment.split("\n")]
    return "\n".join(ln for ln in lines if ln)


def main_content(page):
    m = re.search(r'<div[^>]+id="content"[^>]*>(.*?)<div[^>]+id="footer', page, re.S) \
        or re.search(r'<div[^>]+id="content"[^>]*>(.*)', page, re.S)
    return m.group(1) if m else page


def parse_courses(content, url):
    courses, sequence = [], None
    for kind, block in re.findall(r'<div class="courseblock (main|subsequence)">(.*?)</div>', content, re.S):
        title_html = re.search(r'courseblocktitle[^>]*>(.*?)</p>', block, re.S)
        if not title_html:
            continue
        title_line = text(title_html.group(1))
        m = re.match(r"([A-Z]{4} \d{5}(?:-\d{5})*)\.?\s+(.*?)\.?\s+(\d+(?:-\d+)?) Units?\.?$", title_line)
        code, title, units = (m.group(1), m.group(2).strip(), m.group(3)) if m else (title_line.split(".")[0], title_line, None)
        desc_html = re.search(r'courseblockdesc[^>]*>(.*?)</p>', block, re.S)
        detail_html = re.search(r'courseblockdetail[^>]*>(.*?)</p>', block, re.S)
        details = {}
        if detail_html:
            # Labels often share a line with the previous value ("...; J. Smith Terms Offered: Autumn"),
            # so split on the known labels rather than on line breaks.
            detail = text(detail_html.group(1))
            marks = list(DETAIL_LABELS.finditer(detail))
            for i, m in enumerate(marks):
                end = marks[i + 1].start() if i + 1 < len(marks) else len(detail)
                details[m.group(1)] = " ".join(detail[m.end():end].split())
        if kind == "main":
            sequence = code if "-" in code else None
        prereq = details.get("Prerequisite(s)", "")
        equiv = details.get("Equivalent Course(s)", "")
        courses.append({
            "code": code,
            "title": title,
            "units": units,
            "kind": "sequence-part" if kind == "subsequence" else "course",
            "description": text(desc_html.group(1)) if desc_html else "",
            "instructors": details.get("Instructor(s)", ""),
            "terms": details.get("Terms Offered", ""),
            "prerequisites": prereq,
            "notes": details.get("Note(s)", ""),
            "equivalent": equiv,
            "prereq_codes": sorted({" ".join(c) for c in CODE.findall(prereq)} - {code}),
            "equivalent_codes": sorted({" ".join(c) for c in CODE.findall(equiv)} - {code}),
            "part_of": sequence if kind == "subsequence" else None,
            "url": url,
        })
    return courses


def parse_sections(content):
    content = re.sub(r'<div class="courseblock (?:main|subsequence)">.*?</div>(?:\s*<!--.*?-->)?', "", content, flags=re.S)
    parts = re.split(r"<h([23])[^>]*>(.*?)</h\1>", content, flags=re.S)
    sections, heading = [], "Overview"
    body = parts[0]
    for i in range(1, len(parts), 3):
        if text(body):
            sections.append({"heading": heading, "text": text(body)})
        heading, body = text(parts[i + 1]) or heading, parts[i + 2]
    if text(body):
        sections.append({"heading": heading, "text": text(body)})
    return sections


def to_markdown(pages, courses):
    out = [f"# University of Chicago College Catalog (fetched {datetime.now(timezone.utc):%Y-%m-%d})\n"]
    for p in pages:
        out.append(f"\n## {p['title']}\nSource: {p['url']}\n")
        for s in p["sections"]:
            out.append(f"\n### {s['heading']}\n{s['text']}\n")
    out.append("\n## Course descriptions\n")
    for c in courses.values():
        fields = [f"{k}: {c[v]}" for k, v in (("Terms", "terms"), ("Prerequisites", "prerequisites"),
                  ("Instructors", "instructors"), ("Equivalent", "equivalent"), ("Notes", "notes")) if c[v]]
        out.append(f"\n{c['code']}. {c['title']}. {c['units'] or '?'} units. Listed on: {', '.join(c['listed_on'])}\n"
                   f"{c['description']}\n" + ("\n".join(fields) + "\n" if fields else ""))
    return "".join(out)


def cache_path(url):
    name = url.split("/thecollege/", 1)[-1].strip("/").replace("/", "__") or "index"
    return RAW / f"{name}.html"


def get_page(url, robots, delay, refresh):
    """Use the saved copy when there is one, so a rerun only fetches what's missing."""
    path = cache_path(url)
    if path.exists() and not refresh:
        return path.read_text(), None, True
    page, err = fetch(url, robots, delay)
    if page:
        path.write_text(page)
    return page, err, False


def parse_page(url, page):
    content = main_content(page)
    content = re.sub(r"<p>(?:\s*(?:<a href=\"#[^\"]*\">.*?</a>|\|)\s*)+</p>", "", content, flags=re.S)  # in-page link bar
    h1 = re.search(r"<title>(.*?)(?:\s*\|.*)?</title>", page, re.S)
    slug = url.rstrip("/").split("/")[-1]
    page_courses = parse_courses(content, url)
    return {"slug": slug, "url": url, "title": text(h1.group(1)) if h1 else slug,
            "sections": parse_sections(content), "course_codes": [c["code"] for c in page_courses]}, page_courses


def run(delay, refresh):
    RAW.mkdir(parents=True, exist_ok=True)
    robots = urllib.robotparser.RobotFileParser(BASE + "/robots.txt")
    try:
        robots.read()
    except Exception:
        robots = None
        print("Couldn't read robots.txt, so only pages linked from Programs of Study will be fetched.")

    start, err, _ = get_page(START, robots, 0, refresh)
    if not start:
        raise SystemExit(f"Couldn't load the Programs of Study page: {err}.\n"
                         "Check that http://collegecatalog.uchicago.edu opens in your browser, wait a few minutes, and run this again.")
    urls = [START]
    def queue(path):
        if SKIP.search(path):
            return
        path = path if path.endswith("/") else path + "/"
        if path != "/thecollege/" and BASE + path not in urls:
            urls.append(BASE + path)
    def queue_links(page):
        for href in re.findall(r'href="(/thecollege/[^"#?]+)"', page):
            queue(href)
    queue_links(start)
    for slug in ["thecore"] + list(CORE_PAGES):
        queue(f"/thecollege/{slug}/")
    sitemap, _ = fetch(BASE + "/sitemap.xml", None, 0)
    for loc in re.findall(r"<loc>\s*https?://[^/<]+(/thecollege/[^<#?]*?)\s*</loc>", sitemap or ""):
        queue(loc)
    if not sitemap:
        print("Couldn't read the sitemap. Following links between pages instead.")

    pages, courses, missing, dead, failed_in_a_row, stopped = [], {}, [], [], 0, False
    blocks_seen = entries_parsed = 0
    n = 0
    while n < len(urls):
        url = urls[n]
        n += 1
        if stopped and not cache_path(url).exists():
            missing.append(url)
            continue
        if url == START:
            page, err, cached = start, None, False
        else:
            page, err, cached = get_page(url, robots, delay, refresh and not stopped)
        print(f"[{n}/{len(urls)}] {'saved copy ' if cached else ''}{url}")
        if not page:
            print(f"  skipped: {err}")
            if err.startswith(("HTTP 4", "blocked")):
                dead.append(url)  # a broken link or a disallowed page; retrying won't help
                continue
            missing.append(url)
            failed_in_a_row += 1
            if failed_in_a_row >= 2 and not stopped:
                stopped = True
                print("\nThe catalog site stopped accepting requests, so the crawl is pausing here to avoid "
                      "adding load. Pages already saved are kept.\n")
            continue
        failed_in_a_row = 0
        queue_links(page)
        info, page_courses = parse_page(url, page)
        blocks_seen += len(re.findall(r'<div class="courseblock (?:main|subsequence)">', main_content(page)))
        entries_parsed += len(page_courses)
        pages.append(info)
        for c in page_courses:
            if c["code"] in courses:
                courses[c["code"]]["listed_on"].append(info["title"])
            else:
                c["listed_on"] = [info["title"]]
                courses[c["code"]] = c

    md = to_markdown(pages, courses)
    (OUT / "catalog.json").write_text(json.dumps({
        "source": START, "fetched_at": datetime.now(timezone.utc).isoformat(),
        "pages": pages, "courses": list(courses.values()), "missing_pages": missing}, ensure_ascii=False, indent=1))
    (OUT / "catalog.md").write_text(md)
    course_chars = sum(len(c["description"]) + len(c["prerequisites"]) + len(c["title"]) + 80 for c in courses.values())
    # Completeness check: undergraduate codes named as prerequisites that have no entry, aren't another
    # code for a listed course (cross-listing), and aren't part of a listed sequence.
    aliases = {r for c in courses.values() for r in c["equivalent_codes"]}
    seq_parts = {f"{k.split()[0]} {n}" for k in courses if "-" in k for n in k.split(" ", 1)[1].split("-")}
    not_found = sorted({r for c in courses.values() for r in c["prereq_codes"]
                        if r not in courses and r not in aliases and r not in seq_parts and int(r.split()[1]) < 30000})
    stats = {"pages": len(pages), "missing_pages": len(missing), "course_blocks_on_pages": blocks_seen,
             "course_entries_parsed": entries_parsed, "unique_courses": len(courses),
             "sequence_parts": sum(1 for c in courses.values() if c["kind"] == "sequence-part"),
             "cross_listed_codes": len(aliases - set(courses)),
             "prereqs_with_no_entry": not_found,
             "characters": len(md),
             "estimated_tokens": round(len(md) / 3.6), "estimated_course_tokens": round(course_chars / 3.6),
             "prerequisite_links": sum(len(c["prereq_codes"]) for c in courses.values())}
    (OUT / "stats.json").write_text(json.dumps(stats, indent=1))
    print(f"\nBuilt the catalog from {len(pages)} pages ({len(courses):,} courses)."
          + (f" Skipped {len(dead)} broken link{'s' if len(dead) != 1 else ''}." if dead else ""))
    got = {p["slug"]: len(p["course_codes"]) for p in pages}
    core_missing = [title for slug, title in CORE_PAGES.items() if slug not in got]
    if not core_missing:
        print(f"Core pages: all {len(CORE_PAGES)} found ({', '.join(CORE_PAGES.values())}).")
    else:
        print(f"Missing Core pages: {', '.join(core_missing)}. Run python3 build_catalog.py again in a few minutes to fetch them.")
    print(f"Parsed {entries_parsed:,} of {blocks_seen:,} course entries on those pages; "
          f"{len(courses):,} are unique after removing courses listed on more than one page.")
    if not_found:
        print(f"{len(not_found)} undergraduate course codes appear only as prerequisites, with no entry anywhere in the "
              "catalog. These are usually retired or renumbered courses. The list is in data/stats.json.")
    if missing:
        print(f"{len(missing)} pages are still missing. Wait about 10 minutes, then run python3 build_catalog.py again.\n"
              "It keeps every page it already saved and only fetches the missing ones. The chatbot works in the "
              "meantime, but it won't know about programs on the missing pages.")
    else:
        print("All pages fetched. Token figures in data/stats.json are estimates; "
              "for exact counts, run: python3 catalog_server.py --count-tokens")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--delay", type=float, default=2.0, help="seconds between requests (default 2)")
    ap.add_argument("--refresh", action="store_true", help="download every page again, for example for a new catalog year")
    args = ap.parse_args()
    run(args.delay, args.refresh)
