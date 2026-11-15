"""CourseLeaf HTML, read by plain code (stdlib `html.parser`, no LLM).

- `parse_html` builds a small, forgiving element tree.
- `page_text` is the visible text with whitespace collapsed: what quotes are checked against.
- `links` lists `<a href>` targets (absolute), optionally inside one container.
- `course_blocks` reads `div.courseblock` entries: title line, description and the detail
  lines (`Prerequisite(s):`, `Equivalent Course(s):`, `Note(s):`, `Terms Offered:`).
"""

from __future__ import annotations

import html
import re
import urllib.parse
from collections.abc import Iterator
from dataclasses import dataclass, field
from html.parser import HTMLParser

VOID = {
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source",
    "track", "wbr",
}  # fmt: skip
#: Elements whose text is never shown.
HIDDEN = {"script", "style", "noscript", "template", "head"}
#: Elements that start a new line of text.
BLOCK = {
    "p", "div", "li", "ul", "ol", "tr", "td", "th", "table", "h1", "h2", "h3", "h4", "h5",
    "h6", "section", "article", "header", "footer", "nav", "main", "br", "dd", "dt", "dl",
    "blockquote",
}  # fmt: skip


@dataclass
class Element:
    tag: str
    attrs: dict[str, str] = field(default_factory=dict)
    children: list[Element | str] = field(default_factory=list)

    @property
    def classes(self) -> set[str]:
        return set(self.attrs.get("class", "").split())

    def iter(self) -> Iterator[Element]:
        yield self
        for child in self.children:
            if isinstance(child, Element):
                yield from child.iter()

    def find_all(
        self, tag: str | None = None, cls: str | None = None, id_: str | None = None
    ) -> list[Element]:
        return [
            el
            for el in self.iter()
            if (tag is None or el.tag == tag)
            and (cls is None or cls in el.classes)
            and (id_ is None or el.attrs.get("id") == id_)
        ]

    def find(
        self, tag: str | None = None, cls: str | None = None, id_: str | None = None
    ) -> Element | None:
        found = self.find_all(tag, cls, id_)
        return found[0] if found else None

    def lines(self) -> list[str]:
        """Visible text split at block elements and `<br>`, whitespace collapsed."""
        out: list[str] = []
        current: list[str] = []

        def flush() -> None:
            text = " ".join(" ".join(current).split())
            if text:
                out.append(text)
            current.clear()

        def walk(node: Element | str) -> None:
            if isinstance(node, str):
                current.append(node)
                return
            if node.tag in HIDDEN:
                return
            block = node.tag in BLOCK
            if block:
                flush()
            for child in node.children:
                walk(child)
            if block:
                flush()

        walk(self)
        flush()
        return out

    def text(self) -> str:
        return " ".join(self.lines())


class _Builder(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = Element("#document")
        self.stack = [self.root]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        el = Element(tag, {k: v or "" for k, v in attrs})
        self.stack[-1].children.append(el)
        if tag not in VOID:
            self.stack.append(el)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.stack[-1].children.append(Element(tag, {k: v or "" for k, v in attrs}))

    def handle_endtag(self, tag: str) -> None:
        # Close up to the matching open element; ignore a stray end tag.
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                return

    def handle_data(self, data: str) -> None:
        self.stack[-1].children.append(data)


def https_url(url: str) -> str:
    """The https form of an http URL (other URLs unchanged). The seed cites catalog pages as
    `http://...`; they are fetched and compared as https, so the same page is one URL."""
    parts = urllib.parse.urlsplit(url)
    return parts._replace(scheme="https").geturl() if parts.scheme == "http" else url


def parse_html(text: str) -> Element:
    builder = _Builder()
    builder.feed(text)
    builder.close()
    return builder.root


def normalize(text: str) -> str:
    """How quotes and page text are compared: entities decoded, whitespace collapsed (nothing
    else changes, so a quote must still be the page's exact words)."""
    return " ".join(html.unescape(text).replace("\u00a0", " ").split())


def page_text(source: str | Element) -> str:
    root = parse_html(source) if isinstance(source, str) else source
    body = root.find("body") or root
    return normalize("\n".join(body.lines()))


def page_title(source: str | Element) -> str | None:
    root = parse_html(source) if isinstance(source, str) else source
    for el in (root.find("h1", cls="page-title"), root.find("h1"), root.find("title")):
        if el is not None and el.text():
            return el.text()
    return None


def links(
    source: str | Element,
    base_url: str,
    *,
    within_id: str | None = None,
    within_class: str | None = None,
) -> list[tuple[str, str]]:
    """(absolute URL without fragment, link text), in page order, de-duplicated."""
    root = parse_html(source) if isinstance(source, str) else source
    scope: Element | None = root
    if within_id or within_class:
        scope = root.find(id_=within_id, cls=within_class)
    if scope is None:
        return []
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for a in scope.find_all("a"):
        href = a.attrs.get("href", "").strip()
        if not href or href.startswith(("mailto:", "javascript:", "#")):
            continue
        url = urllib.parse.urldefrag(urllib.parse.urljoin(base_url, href))[0]
        if url not in seen:
            seen.add(url)
            out.append((url, a.text()))
    return out


# --------------------------------------------------------------------------- course blocks

TITLE = re.compile(
    r"^(?P<subject>[A-Z]{2,5})\s+(?P<number>\d{5})\.\s+(?P<title>.+?)\.\s+"
    r"(?P<units>\d{3})(?:\s+to\s+\d{3})?\s+Units?\.?$"
)
DETAIL_LABELS = {
    "Instructor(s)": "instructors",
    "Terms Offered": "terms_offered",
    "Prerequisite(s)": "prerequisites",
    "Equivalent Course(s)": "equivalents",
    "Note(s)": "notes",
}
QUARTERS = {"Autumn": "AU", "Winter": "WI", "Spring": "SP", "Summer": "SU"}
CODE = re.compile(r"\b([A-Z]{2,5}) (\d{5})\b")


@dataclass(frozen=True)
class CourseBlock:
    title_line: str
    subject: str
    number: str
    title: str
    units: int
    description: str | None
    details: dict[str, str]

    @property
    def code(self) -> str:
        return f"{self.subject} {self.number}"


def _detail_fields(lines: list[str]) -> dict[str, str]:
    """`Instructor(s): A Terms Offered: Autumn` (one line in CourseLeaf) -> two fields."""
    pattern = re.compile("(" + "|".join(re.escape(k) for k in DETAIL_LABELS) + r"):")
    fields: dict[str, str] = {}
    for line in lines:
        matches = list(pattern.finditer(line))
        for i, match in enumerate(matches):
            end = matches[i + 1].start() if i + 1 < len(matches) else len(line)
            value = line[match.end() : end].strip()
            key = DETAIL_LABELS[match.group(1)]
            fields[key] = f"{fields[key]} {value}".strip() if key in fields else value
    return fields


def course_blocks(source: str | Element) -> tuple[list[CourseBlock], list[str]]:
    """(blocks, problems): a block whose title line does not parse is reported, not guessed."""
    root = parse_html(source) if isinstance(source, str) else source
    blocks: list[CourseBlock] = []
    problems: list[str] = []
    for div in root.find_all("div", cls="courseblock"):
        title_el = div.find("p", cls="courseblocktitle")
        if title_el is None:
            continue
        title_line = normalize(title_el.text())
        match = TITLE.match(title_line)
        if match is None:
            problems.append(f"course title line not understood: {title_line!r}")
            continue
        desc_el = div.find("p", cls="courseblockdesc")
        detail_lines: list[str] = []
        for el in div.find_all("p", cls="courseblockdetail"):
            detail_lines += [normalize(line) for line in el.lines()]
        blocks.append(
            CourseBlock(
                title_line=title_line,
                subject=match["subject"],
                number=match["number"],
                title=match["title"],
                units=int(match["units"]),
                description=normalize(desc_el.text()) if desc_el is not None else None,
                details=_detail_fields(detail_lines),
            )
        )
    return blocks, problems


def quarters_of(text: str) -> list[str]:
    return [q for name, q in QUARTERS.items() if name in text]


def codes_in(text: str) -> list[str]:
    out: list[str] = []
    for subject, number in CODE.findall(text):
        code = f"{subject} {number}"
        if code not in out:
            out.append(code)
    return out
