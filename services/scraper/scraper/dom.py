"""A small HTML tree and CSS-selector subset (standard library only), so the schedule parser
is driven by *selectors as data*. The self-repair agent can then propose new selectors, never
new code.

Supported selectors: `tag`, `.class`, `#id`, `[attr]`, `[attr=value]` (value optionally
quoted), compounds such as `tr.section-row[data-kind=lec]`, the descendant combinator
(a space), the child combinator (`>`), and alternatives separated by commas.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from html.parser import HTMLParser

VOID = {
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source",
    "track", "wbr",
}  # fmt: skip
BLOCK = {
    "address", "article", "aside", "blockquote", "br", "dd", "div", "dl", "dt", "footer",
    "h1", "h2", "h3", "h4", "h5", "h6", "header", "hr", "li", "main", "nav", "ol", "p", "pre",
    "section", "table", "tbody", "td", "th", "thead", "tr", "ul",
}  # fmt: skip
SKIP_TEXT = {"script", "style", "template", "noscript"}


@dataclass(eq=False)
class Node:
    tag: str
    attrs: dict[str, str] = field(default_factory=dict)
    children: list[Node | str] = field(default_factory=list)
    parent: Node | None = None

    @property
    def classes(self) -> set[str]:
        return set(self.attrs.get("class", "").split())

    def elements(self) -> list[Node]:
        return [c for c in self.children if isinstance(c, Node)]

    def iter(self) -> list[Node]:
        """Every descendant element, in document order."""
        out: list[Node] = []
        stack = list(reversed(self.elements()))
        while stack:
            node = stack.pop()
            out.append(node)
            stack.extend(reversed(node.elements()))
        return out

    def text(self) -> str:
        """Text content with whitespace collapsed."""
        return " ".join(self._raw_text(block_breaks=False).split())

    def lines(self) -> str:
        """Text content with one line per block element (for LLM input and quote checks)."""
        raw = self._raw_text(block_breaks=True)
        lines = (" ".join(line.split()) for line in raw.splitlines())
        return "\n".join(line for line in lines if line)

    def _raw_text(self, *, block_breaks: bool) -> str:
        parts: list[str] = []
        for child in self.children:
            if isinstance(child, str):
                parts.append(child)
            elif child.tag not in SKIP_TEXT:
                inner = child._raw_text(block_breaks=block_breaks)
                if block_breaks and child.tag in BLOCK:
                    parts.append(f"\n{inner}\n")
                else:
                    parts.append(f" {inner} " if child.tag in BLOCK else inner)
        return "".join(parts)

    def select(self, selector: str) -> list[Node]:
        return select(self, selector)

    def select_one(self, selector: str) -> Node | None:
        found = select(self, selector)
        return found[0] if found else None


class _Builder(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = Node("#document")
        self.stack = [self.root]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node = Node(tag, {k: (v or "") for k, v in attrs}, parent=self.stack[-1])
        self.stack[-1].children.append(node)
        if tag not in VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node = Node(tag, {k: (v or "") for k, v in attrs}, parent=self.stack[-1])
        self.stack[-1].children.append(node)

    def handle_endtag(self, tag: str) -> None:
        # Close up to the matching open tag; a stray end tag is ignored.
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                return

    def handle_data(self, data: str) -> None:
        self.stack[-1].children.append(data)


def parse_html(html: str) -> Node:
    builder = _Builder()
    builder.feed(html)
    builder.close()
    return builder.root


# ------------------------------------------------------------------------------- selectors


class SelectorError(ValueError):
    pass


_SIMPLE = re.compile(
    r"""
    (?P<tag>[a-zA-Z][a-zA-Z0-9-]*|\*)
  | \.(?P<cls>[a-zA-Z0-9_-]+)
  | \#(?P<id>[a-zA-Z0-9_-]+)
  | \[\s*(?P<attr>[a-zA-Z0-9_:-]+)\s*(?:=\s*(?P<val>"[^"]*"|'[^']*'|[^\]\s]+)\s*)?\]
    """,
    re.VERBOSE,
)


@dataclass(frozen=True)
class _Compound:
    tag: str | None
    classes: tuple[str, ...]
    id: str | None
    attrs: tuple[tuple[str, str | None], ...]

    def matches(self, node: Node) -> bool:
        if self.tag and self.tag != "*" and node.tag != self.tag:
            return False
        if self.id is not None and node.attrs.get("id") != self.id:
            return False
        if self.classes and not set(self.classes) <= node.classes:
            return False
        for name, value in self.attrs:
            if name not in node.attrs or (value is not None and node.attrs[name] != value):
                return False
        return True


def _compound(text: str) -> _Compound:
    pos = 0
    tag: str | None = None
    classes: list[str] = []
    ident: str | None = None
    attrs: list[tuple[str, str | None]] = []
    while pos < len(text):
        m = _SIMPLE.match(text, pos)
        if m is None or m.end() == pos:
            raise SelectorError(f"cannot read selector part {text!r}")
        if m.group("tag"):
            if pos != 0:
                raise SelectorError(f"a tag name must come first in {text!r}")
            tag = m.group("tag").lower()
        elif m.group("cls"):
            classes.append(m.group("cls"))
        elif m.group("id"):
            ident = m.group("id")
        else:
            val = m.group("val")
            if val is not None and val[:1] in "\"'":
                val = val[1:-1]
            attrs.append((m.group("attr").lower(), val))
        pos = m.end()
    return _Compound(tag, tuple(classes), ident, tuple(attrs))


def _chain(selector: str) -> list[tuple[str, _Compound]]:
    """[(combinator, compound)], the first combinator being " "."""
    tokens = selector.replace(">", " > ").split()
    if not tokens:
        raise SelectorError("empty selector")
    out: list[tuple[str, _Compound]] = []
    combinator = " "
    for token in tokens:
        if token == ">":
            if combinator == ">" or not out:
                raise SelectorError(f"misplaced '>' in {selector!r}")
            combinator = ">"
            continue
        out.append((combinator, _compound(token)))
        combinator = " "
    if combinator == ">":
        raise SelectorError(f"selector ends with '>': {selector!r}")
    return out


def _matches_chain(node: Node, chain: list[tuple[str, _Compound]], scope: Node) -> bool:
    combinator, last = chain[-1]
    if not last.matches(node):
        return False
    if len(chain) == 1:
        return True
    rest = chain[:-1]
    parent = node.parent
    if combinator == ">":
        return parent is not None and parent is not scope and _matches_chain(parent, rest, scope)
    while parent is not None and parent is not scope:
        if _matches_chain(parent, rest, scope):
            return True
        parent = parent.parent
    return False


def validate_selector(selector: str) -> None:
    for part in selector.split(","):
        _chain(part)


def select(scope: Node, selector: str) -> list[Node]:
    """Elements under `scope` matching any alternative, in document order, without repeats.
    Ancestors above `scope` never take part in a match."""
    chains = [_chain(part) for part in selector.split(",")]
    return [n for n in scope.iter() if any(_matches_chain(n, c, scope) for c in chains)]
