#!/usr/bin/env python3
"""Catalog chatbot server.

The full catalog is too large for one context window, so every request carries:
  - a cached map of the whole catalog: College-wide policy pages in full, every
    program page with its section headings, and an index of every course
    (code, title, units, terms)
  - tools that fetch full course descriptions, program requirements, and
    full-text search results, returned as citable search results

Usage:
  python3 catalog_server.py                  start at http://localhost:8000
  python3 catalog_server.py --count-tokens   exact token counts for the catalog
  python3 catalog_server.py --ask "..."      one question from the terminal

Environment: ANTHROPIC_API_KEY (required for answers), ANTHROPIC_MODEL
(default claude-sonnet-5-5), PORT (8000), CACHE_TTL (1h or 5m).
Run build_catalog.py first. Standard library only.
"""
import argparse
import json
import math
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data" / "catalog.json"
PLAN = HERE / "data" / "plan.json"
PAGE = "quarterly.html"
API_BASE = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com").rstrip("/")
API_KEY = (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN") or "").strip()
DIRECT = "api.anthropic.com" in API_BASE
# Gateways don't all support every Claude API feature. These switch off automatically if the provider rejects them.
COMPAT = {"citations": os.environ.get("CITATIONS", "on") != "off", "ttl": True}
MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5-5")
CACHE_TTL = os.environ.get("CACHE_TTL", "1h")
MAX_STEPS = 8
MAX_HISTORY = 12

POLICY_SLUGS = {"programsofstudy", "curriculum", "minors", "degreerequirements", "academicregulationsprocedures",
                "examinationcreditandtransfercredit", "transfercredit", "transferstudents", "currentstudents",
                "graduation", "academiccalendar", "jointdegreeprograms", "certificates", "academicadvising",
                "academicstandards", "accreditationexams", "apibalevelexams", "gradingandacademicstatus",
                "languagecompetency", "placementexams", "registration", "takingcourses"}
CODE_RE = re.compile(r"\b([A-Za-z]{4})\s?(\d{5})\b")
STOP = set("""a an and are as at be by can do does for from has have how i if in is it its me my of on or our so
than that the their them then there these this to was what when where which who will with would you your about into
not any all more most also may must should one each""".split())


# ---------- Catalog and search ----------

def course_text(c):
    lines = [f"{c['code']}. {c['title']}." + (f" {c['units']} Units." if c.get("units") else "")]
    if c.get("description"):
        lines.append(c["description"])
    for label, key in (("Instructor(s)", "instructors"), ("Terms Offered", "terms"), ("Prerequisite(s)", "prerequisites"),
                       ("Equivalent Course(s)", "equivalent"), ("Note(s)", "notes")):
        if c.get(key):
            lines.append(f"{label}: {c[key]}")
    if c.get("part_of"):
        lines.append(f"Part of sequence: {c['part_of']}")
    if c.get("listed_on"):
        lines.append("Listed on: " + ", ".join(c["listed_on"]))
    return "\n".join(lines)


def split_text(text, size=2500):
    parts, cur = [], ""
    for line in text.split("\n"):
        if cur and len(cur) + len(line) > size:
            parts.append(cur)
            cur = ""
        cur += line + "\n"
    if cur.strip():
        parts.append(cur)
    return parts


def tokenize(text):
    toks = [f"{a.lower()}{b}" for a, b in CODE_RE.findall(text)]
    for w in re.findall(r"[a-z0-9]+", text.lower()):
        if w in STOP or len(w) < 2:
            continue
        if len(w) > 4 and w.endswith("s") and not w.endswith("ss"):
            w = w[:-1]
        toks.append(w)
    return toks


def norm_code(raw):
    m = CODE_RE.search(raw or "")
    return f"{m.group(1).upper()} {m.group(2)}" if m else (raw or "").strip().upper()


class Catalog:
    def __init__(self, path):
        if not path.exists():
            raise SystemExit(f"No catalog found at {path}. Run: python3 build_catalog.py")
        d = json.loads(path.read_text())
        self.fetched_at = d.get("fetched_at", "")[:10]
        self.pages = d["pages"]
        self.courses = {c["code"]: c for c in d["courses"]}
        self.missing = d.get("missing_pages", [])
        self.parts = {}  # sequence code -> codes of its quarter-by-quarter parts
        for c in d["courses"]:
            if c.get("part_of"):
                self.parts.setdefault(c["part_of"], []).append(c["code"])
        self.aliases = {}  # cross-listed code -> code of the catalog entry
        for c in d["courses"]:
            for other in c.get("equivalent_codes", []):
                if other not in self.courses:
                    self.aliases.setdefault(other, c["code"])
        self.chunks = []
        for c in d["courses"]:
            self.chunks.append({"kind": "course", "code": c["code"], "title": f"{c['code']}. {c['title']}",
                                "source": c["url"], "text": course_text(c),
                                "codes": {x.replace(" ", "").lower() for x in [c["code"]] + c.get("equivalent_codes", [])}})
        for p in self.pages:
            for s in p["sections"]:
                for part in split_text(s["text"]):
                    self.chunks.append({"kind": "program", "title": f"{p['title']}: {s['heading']}",
                                        "source": p["url"], "text": part})
        self.tf, df = [], Counter()
        for ch in self.chunks:
            toks = tokenize(ch["title"]) * 2 + tokenize(ch["text"])
            counts = Counter(toks)
            self.tf.append((counts, len(toks)))
            df.update(counts.keys())
        n = len(self.chunks)
        self.avg = sum(l for _, l in self.tf) / max(n, 1)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def search(self, query, limit=8, kind="any"):
        q = set(tokenize(query))
        codes = {f"{a.lower()}{b}" for a, b in CODE_RE.findall(query)}
        scored = []
        for i, (counts, length) in enumerate(self.tf):
            ch = self.chunks[i]
            if kind != "any" and ch["kind"] != kind:
                continue
            s = 0.0
            for t in q:
                f = counts.get(t)
                if f:
                    s += self.idf.get(t, 0) * f * 2.4 / (f + 1.4 * (0.25 + 0.75 * length / self.avg))
            if ch["kind"] == "course" and (codes & ch["codes"] or ch["code"].replace(" ", "").lower()[:9] in codes):
                s += 50
            if s > 0:
                scored.append((s, i))
        scored.sort(reverse=True)
        return [self.chunks[i] for _, i in scored[:limit]]

    def get_course(self, raw):
        key = norm_code(raw)
        if key in self.aliases:
            key = self.aliases[key]
        return self.courses.get(key) or next((v for k, v in self.courses.items() if k.startswith(key)), None)

    def find_courses(self, query, term="", limit=30):
        """Typeahead for the planner: exact code, then code prefix, then full-text matches."""
        query, out, seen = query.strip(), [], set()
        def add(c):
            if c and c["code"] not in seen and (not term or term.lower() in (c.get("terms") or "").lower()):
                seen.add(c["code"])
                out.append(c)
        if not query:
            return []
        if CODE_RE.search(query):
            add(self.get_course(query))
        if re.fullmatch(r"[A-Za-z]{3,4}\s?\d{0,5}", query):
            prefix = query.upper().replace(" ", "")
            for code, c in self.courses.items():
                if len(out) >= limit:
                    break
                if code.replace(" ", "").startswith(prefix):
                    add(c)
        for hit in self.search(query, limit * 3, "course"):
            if len(out) >= limit:
                break
            add(self.courses.get(hit["code"]))
        return out[:limit]

    def brief(self, c, with_parts=True):
        b = {k: c.get(k) for k in ("code", "title", "units", "terms", "prerequisites", "part_of", "url")}
        b["prereq_codes"] = c.get("prereq_codes", [])
        b["equivalent_codes"] = c.get("equivalent_codes", [])
        if with_parts and self.parts.get(c["code"]):
            b["parts"] = [self.brief(self.courses[x], False) for x in self.parts[c["code"]] if x in self.courses]
        return b

    def full(self, c):
        b = self.brief(c)
        b.update({k: c.get(k) for k in ("description", "instructors", "notes", "equivalent", "listed_on")})
        return b

    def find_page(self, name):
        n = (name or "").strip().lower()
        for p in self.pages:
            if n in (p["slug"].lower(), p["title"].lower()):
                return p
        squashed = re.sub(r"[^a-z]", "", n)
        for p in self.pages:
            if n in p["title"].lower() or (squashed and squashed in p["slug"].lower()):
                return p
        return None

    def reference_text(self):
        out = [f'<catalog_snapshot fetched="{self.fetched_at}">\n<policy_pages>']
        for p in self.pages:
            if p["slug"] in POLICY_SLUGS:
                out.append(f"\n## {p['title']} ({p['url']})")
                out += [f"### {s['heading']}\n{s['text']}" for s in p["sections"]]
        out.append("</policy_pages>\n<program_pages>")
        for p in self.pages:
            if p["slug"] not in POLICY_SLUGS:
                heads = "; ".join(dict.fromkeys(s["heading"] for s in p["sections"]))
                out.append(f"- {p['title']} [{p['slug']}]: {heads}")
        out.append("</program_pages>\n<course_index>\ncode | title | units | terms offered")
        for c in self.courses.values():
            out.append(f"{c['code']} | {c['title']} | {c.get('units') or '?'} | {c.get('terms') or '-'}")
        out.append("</course_index>\n</catalog_snapshot>")
        return "\n".join(out)


# ---------- Prompt and tools ----------

INSTRUCTIONS = """You are Quarterly, an assistant that answers students' questions about the University of Chicago College Catalog. Your information comes from a snapshot of the catalog fetched on {date}.

What you have:
- In this prompt: the College-wide policy pages in full, a list of every program page with its section headings, and an index of every course with its code, title, units, and usual terms.
- Tools: search_catalog for full-text search, get_courses for full course descriptions and prerequisites, and get_program for a program's requirements and policies.
- Many courses are cross-listed under several codes, and the index shows only the code of the catalog entry. If a student names a code that isn't in the index, call get_courses with it anyway: cross-listed codes resolve to the main entry.

How to answer:
- Ground every factual statement in the catalog. Use the index to find candidate courses, then call get_courses or get_program before you state descriptions, prerequisites, or requirements. The index alone isn't enough for those.
- Cite the passages your answer relies on. Tool results support citations.
- If the catalog doesn't answer the question, say so plainly and suggest who to ask: the program's Director of Undergraduate Studies, the student's Academic Adviser, or the Registrar. Never invent courses, codes, requirements, or policies.
- The catalog lists courses and their usual terms, not the schedule for a given quarter. For sections, times, current instructors, or enrollment, point students to the University's class schedule.
- Requirements depend on catalog year, and this is one snapshot. Say so when it matters, for example for a student who entered in an earlier year.
- You can't approve petitions, substitutions, or exceptions.
- Lead with the answer. Write plainly and concisely, use bullets for lists of courses or steps, and write course codes exactly as the catalog does."""

TOOLS = [
    {"name": "search_catalog",
     "description": "Full-text search over every course description and every program page section in the catalog snapshot. Use it for topics, keywords, and policies, or when you aren't sure which course or program is relevant. Returns citable passages.",
     "input_schema": {"type": "object", "properties": {
         "query": {"type": "string", "description": "Keywords or a course code"},
         "kind": {"type": "string", "enum": ["any", "course", "program"], "description": "Limit to course descriptions or program pages"},
         "limit": {"type": "integer", "minimum": 1, "maximum": 15}},
         "required": ["query"]}},
    {"name": "get_courses",
     "description": "Full catalog entries for specific courses: description, units, terms offered, prerequisites, instructors, equivalent courses, and which program pages list them.",
     "input_schema": {"type": "object", "properties": {
         "codes": {"type": "array", "items": {"type": "string"}, "maxItems": 15, "description": "Course codes such as 'STAT 22000'"}},
         "required": ["codes"]}},
    {"name": "get_program",
     "description": "Text of one program page: requirements, grading, advising, minors, and contacts. Use a title or slug from the program_pages list. Pass section to read one section of a long page.",
     "input_schema": {"type": "object", "properties": {
         "program": {"type": "string"},
         "section": {"type": "string", "description": "Optional section heading to read"}},
         "required": ["program"]}},
]


def result_block(source, title, texts, tags=None):
    if tags is None:
        return {"type": "search_result", "source": source, "title": title,
                "content": [{"type": "text", "text": t} for t in texts if t.strip()] or [{"type": "text", "text": "(empty)"}],
                "citations": {"enabled": True}}
    body = "\n".join(t for t in texts if t.strip())
    key = (source, title)
    if key not in tags:
        tags[key] = {"tag": len(tags) + 1, "url": source, "title": title, "snippet": body[:300]}
    return {"type": "text", "text": f"[S{tags[key]['tag']}] {title} ({source})\n{body}"}


def run_tool(cat, name, args, tags=None):
    blocks = _run_tool(cat, name, args, tags)
    if tags is not None and any(b["text"].startswith("[S") for b in blocks):
        blocks.append({"type": "text", "text": "Cite these passages inline with their tags, for example [S1]."})
    return blocks


def _run_tool(cat, name, args, tags):
    if name == "search_catalog":
        hits = cat.search(args.get("query", ""), min(int(args.get("limit") or 8), 15), args.get("kind") or "any")
        if not hits:
            return [{"type": "text", "text": "No matches. Try different keywords, or check the course index in your prompt."}]
        return [result_block(h["source"], h["title"], [h["text"]], tags) for h in hits]
    if name == "get_courses":
        blocks, missing = [], []
        for raw in (args.get("codes") or [])[:15]:
            c = cat.get_course(raw)
            if c:
                blocks.append(result_block(c["url"], f"{c['code']}. {c['title']}", course_text(c).split("\n"), tags))
            else:
                missing.append(raw)
        if missing:
            blocks.append({"type": "text", "text": f"Not in the catalog snapshot: {', '.join(missing)}."})
        return blocks
    if name == "get_program":
        p = cat.find_page(args.get("program", ""))
        if not p:
            return [{"type": "text", "text": "No program page matches that name. Use a title or slug from the program_pages list."}]
        secs, want = p["sections"], (args.get("section") or "").lower()
        if want:
            secs = [s for s in secs if want in s["heading"].lower()] or secs
        picked, total = [], 0
        for s in secs:
            if picked and total + len(s["text"]) > 24000:
                break
            picked.append(s)
            total += len(s["text"])
        blocks = [result_block(p["url"], p["title"], [f"{s['heading']}\n{s['text']}" for s in picked], tags)]
        if len(picked) < len(secs):
            rest = "; ".join(s["heading"] for s in secs[len(picked):])
            blocks.append({"type": "text", "text": f"Page continues. Remaining sections: {rest}. Call get_program with a section to read one."})
        return blocks
    return [{"type": "text", "text": f"Unknown tool {name}."}]


# ---------- Claude API ----------

class ApiError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


def api(path, payload):
    headers = {"x-api-key": API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"}
    if not DIRECT:
        headers["Authorization"] = f"Bearer {API_KEY}"
    req = urllib.request.Request(API_BASE + path, data=json.dumps(payload).encode(), method="POST", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            msg = json.loads(e.read()).get("error", {}).get("message", "")
        except ValueError:
            msg = ""
        raise ApiError(e.code, msg or f"The API at {API_BASE} returned {e.code}.")
    except urllib.error.URLError as e:
        raise ApiError(502, f"Couldn't reach {API_BASE}: {e.reason}")


def system_blocks(cat):
    cache = {"type": "ephemeral"} if CACHE_TTL == "5m" or not COMPAT["ttl"] else {"type": "ephemeral", "ttl": CACHE_TTL}
    return [{"type": "text", "text": INSTRUCTIONS.format(date=cat.fetched_at)},
            {"type": "text", "text": cat.reference_text(), "cache_control": cache}]


def clean_history(history):
    msgs = [{"role": m["role"], "content": m["content"].strip()} for m in history
            if m.get("role") in ("user", "assistant") and isinstance(m.get("content"), str) and m["content"].strip()]
    msgs = msgs[-MAX_HISTORY:]
    while msgs and msgs[0]["role"] != "user":
        msgs.pop(0)
    merged = []
    for m in msgs:
        if merged and merged[-1]["role"] == m["role"]:
            merged[-1]["content"] += "\n\n" + m["content"]
        else:
            merged.append(m)
    if not merged or merged[-1]["role"] != "user":
        raise ApiError(400, "The last message has to be a question from the student.")
    return merged


def chat(cat, history):
    for _ in range(3):
        try:
            return _chat(cat, history)
        except ApiError as e:
            msg = str(e).lower()
            if e.status == 400 and COMPAT["citations"] and ("search_result" in msg or "citation" in msg):
                COMPAT["citations"] = False
                print("This provider doesn't accept citable search results. Switching to tagged-text sources.")
            elif e.status == 400 and COMPAT["ttl"] and "ttl" in msg:
                COMPAT["ttl"] = False
                print("This provider doesn't accept the 1-hour cache. Switching to the 5-minute cache.")
            else:
                raise
    raise ApiError(502, "The provider kept rejecting requests. Run python3 check_provider.py to see which features it supports.")


def _chat(cat, history):
    system = system_blocks(cat)
    tags = None if COMPAT["citations"] else {}
    messages, trace, usage = clean_history(history), [], Counter()
    for step in range(MAX_STEPS + 1):
        payload = {"model": MODEL, "max_tokens": 2048, "system": system, "tools": TOOLS, "messages": messages}
        if step == MAX_STEPS:
            payload["tool_choice"] = {"type": "none"}
        resp = api("/v1/messages", payload)
        for k, v in (resp.get("usage") or {}).items():
            if isinstance(v, int):
                usage[k] += v
        if resp.get("stop_reason") != "tool_use":
            return build_answer(cat, resp, trace, usage, tags)
        messages.append({"role": "assistant", "content": resp["content"]})
        results = []
        for blk in resp["content"]:
            if blk.get("type") == "tool_use":
                trace.append({"tool": blk["name"], "input": blk.get("input", {})})
                results.append({"type": "tool_result", "tool_use_id": blk["id"],
                                "content": run_tool(cat, blk["name"], blk.get("input", {}), tags)})
        messages.append({"role": "user", "content": results})
    raise ApiError(500, "The answer took too many steps.")


def tagged_segments(text, tags):
    """Turn '...claim [S2][S5]. More...' into segments and numbered sources, like native citations."""
    by_tag = {v["tag"]: v for v in tags.values()}
    segments, sources, number = [], [], {}
    pos = 0
    for m in re.finditer(r"\s?\[S\d+(?:\s*,\s*S?\d+)*\]", text):
        if not segments or m.start() > pos:
            segments.append({"text": text[pos:m.start()], "cites": []})
        for t in (int(x) for x in re.findall(r"\d+", m.group(0))):
            if t in by_tag:
                if t not in number:
                    number[t] = len(sources) + 1
                    src = by_tag[t]
                    sources.append({"n": number[t], "url": src["url"], "title": src["title"], "snippet": src["snippet"]})
                if number[t] not in segments[-1]["cites"]:
                    segments[-1]["cites"].append(number[t])
        pos = m.end()
    segments.append({"text": text[pos:], "cites": []})
    return segments, sources


def build_answer(cat, resp, trace, usage, tags=None):
    segments, sources, index = [], [], {}
    if tags is not None:
        text = "".join(b.get("text", "") for b in resp.get("content", []) if b.get("type") == "text")
        segments, sources = tagged_segments(text, tags)
    for blk in resp.get("content", []) if tags is None else []:
        if blk.get("type") != "text":
            continue
        cites = []
        for c in blk.get("citations") or []:
            key = (c.get("source") or c.get("url"), c.get("title"))
            if key not in index:
                index[key] = len(sources) + 1
                sources.append({"n": index[key], "url": key[0], "title": key[1], "snippet": (c.get("cited_text") or "")[:300]})
            if index[key] not in cites:
                cites.append(index[key])
        segments.append({"text": blk.get("text", ""), "cites": cites})
    courses = []
    for t in trace:
        if t["tool"] == "get_courses":
            courses += [norm_code(x) for x in t["input"].get("codes", [])]
    for s in sources:
        m = CODE_RE.match(s["title"] or "")
        if m:
            courses.append(norm_code(m.group(0)))
    courses = [c for c in dict.fromkeys(courses) if c in cat.courses]
    graph = {c: cat.courses[c].get("prereq_codes", []) for c in courses}
    return {"segments": segments, "sources": sources, "trace": trace, "courses": courses,
            "prereq_graph": graph, "stop_reason": resp.get("stop_reason"), "usage": dict(usage),
            "model": resp.get("model")}


# ---------- HTTP server ----------

def make_handler(cat):
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=str(HERE), **k)

        def log_message(self, fmt, *args):
            if "/api/" in (args[0] if args else ""):
                super().log_message(fmt, *args)

        def do_GET(self):
            url = urllib.parse.urlparse(self.path)
            q = {k: v[0] for k, v in urllib.parse.parse_qs(url.query).items()}
            if url.path in ("", "/"):
                self.path = "/" + PAGE
            elif url.path == "/api/status":
                return self.send_json(200, {"ok": True, "has_key": bool(API_KEY), "model": MODEL,
                                            "pages": len(cat.pages), "courses": len(cat.courses), "fetched_at": cat.fetched_at})
            elif url.path == "/api/courses":
                found = cat.find_courses(q.get("q", ""), q.get("term", ""), min(int(q.get("limit", "30") or 30), 60))
                return self.send_json(200, {"courses": [cat.brief(c) for c in found]})
            elif url.path == "/api/course":
                c = cat.get_course(q.get("code", ""))
                return self.send_json(200, cat.full(c)) if c else \
                    self.send_json(404, {"error": "That course isn't in the catalog snapshot."})
            elif url.path == "/api/programs":
                return self.send_json(200, {"programs": [{"slug": p["slug"], "title": p["title"], "url": p["url"]}
                                                         for p in cat.pages if p["slug"] not in POLICY_SLUGS]})
            elif url.path == "/api/plan":
                try:
                    return self.send_json(200, json.loads(PLAN.read_text()) if PLAN.exists() else {})
                except ValueError:
                    return self.send_json(200, {})
            elif url.path.startswith("/data/"):
                return self.send_error(404)
            return super().do_GET()

        def do_PUT(self):
            if self.path != "/api/plan":
                return self.send_error(404)
            length = int(self.headers.get("Content-Length", 0))
            if length > 2_000_000:
                return self.send_json(413, {"error": "That plan is too large to save."})
            try:
                plan = json.loads(self.rfile.read(length) or b"{}")
            except ValueError:
                return self.send_json(400, {"error": "The plan isn't valid JSON."})
            if not isinstance(plan, dict):
                return self.send_json(400, {"error": "The plan has to be a JSON object."})
            tmp = PLAN.with_suffix(".tmp")
            tmp.write_text(json.dumps(plan, indent=1))
            tmp.replace(PLAN)
            return self.send_json(200, {"ok": True})

        def do_POST(self):
            if self.path != "/api/chat":
                return self.send_error(404)
            if not API_KEY:
                return self.send_json(503, {"error": "No API key is set. Stop the server, set ANTHROPIC_API_KEY, and start it again."})
            try:
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
                self.send_json(200, chat(cat, body.get("messages", [])))
            except ValueError:
                self.send_json(400, {"error": "The request body isn't valid JSON."})
            except ApiError as e:
                self.send_json(e.status if 400 <= e.status < 600 else 502, {"error": str(e)})

        def send_json(self, code, obj):
            data = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
    return Handler


def count_tokens(cat, system):
    try:
        _count_tokens(cat, system)
    except ApiError as e:
        print(f"Token counting didn't work with {API_BASE} ({e}). Some gateways don't offer it; "
              "data/stats.json has estimates instead.")


def _count_tokens(cat, system):
    def count(sys_blocks, text):
        return api("/v1/messages/count_tokens", {"model": MODEL, "system": sys_blocks, "tools": TOOLS,
                                                 "messages": [{"role": "user", "content": text}]})["input_tokens"]
    base = count([{"type": "text", "text": "x"}], "x")
    prefix = count(system, "x") - base
    print(f"Cached prefix (policies, program list, course index): {prefix:,} tokens")
    md = (HERE / "data" / "catalog.md").read_text()
    total, step = 0, 400_000
    for i in range(0, len(md), step):
        total += count([{"type": "text", "text": "x"}], md[i:i + step]) - base
    print(f"Entire catalog as text: {total:,} tokens, about {total / 1_000_000:.1f}x a 1M-token context window")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--count-tokens", action="store_true")
    ap.add_argument("--ask")
    ap.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8000")))
    args = ap.parse_args()
    cat = Catalog(DATA)
    system = system_blocks(cat)
    if (args.count_tokens or args.ask) and not API_KEY:
        raise SystemExit("Set ANTHROPIC_API_KEY first.")
    try:
        if args.count_tokens:
            return count_tokens(cat, system)
        if args.ask:
            out = chat(cat, [{"role": "user", "content": args.ask}])
    except ApiError as e:
        raise SystemExit(f"Claude API error: {e}")
    if args.ask:
        print("".join(s["text"] + "".join(f"[{n}]" for n in s["cites"]) for s in out["segments"]))
        for s in out["sources"]:
            print(f"[{s['n']}] {s['title']} {s['url']}")
        print("model:", out.get("model"), "| usage:", out["usage"])
        return
    print(f"Catalog: {len(cat.courses):,} courses from {len(cat.pages)} pages, fetched {cat.fetched_at}.")
    if cat.missing:
        print(f"Note: {len(cat.missing)} catalog pages are missing. Run build_catalog.py again to fetch them.")
    print(f"Cached prefix: {len(system[1]['text']):,} characters. Run --count-tokens for exact tokens.")
    print((f"Answers: {MODEL} via {API_BASE}") if API_KEY else "No API key is set, so the chat will show setup instructions.")
    print(f"Open http://localhost:{args.port}  (Ctrl+C to stop)")
    try:
        ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(cat)).serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
