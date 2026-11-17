"""Server-side markdown rendering (SPEC "Forum", prompt 08 item 7): no raw HTML, no images, and
links only to absolute http(s) URLs.

Two layers: markdown-it runs with HTML disabled (raw tags come out escaped) and with headings
and images switched off; nh3 (ammonia) then keeps only an allow-list of tags and attributes, so
a bug in either layer alone cannot ship script. Images are refused because a remote image would
tell its host the IP address of every reader.
"""

from __future__ import annotations

from functools import lru_cache

import nh3
from markdown_it import MarkdownIt

ALLOWED_TAGS = frozenset(
    {
        "p",
        "br",
        "strong",
        "em",
        "del",
        "s",
        "code",
        "pre",
        "blockquote",
        "ul",
        "ol",
        "li",
        "a",
        "hr",
    }
)
LINK_REL = "nofollow noopener noreferrer ugc"


@lru_cache(maxsize=1)
def _parser() -> MarkdownIt:
    md = MarkdownIt("commonmark", {"html": False, "linkify": False, "breaks": True})
    md.enable("strikethrough")
    # Headings would break the page outline; images would leak readers' addresses.
    md.disable(["heading", "lheading", "image"])
    return md


def _attribute_filter(tag: str, attribute: str, value: str) -> str | None:
    if tag == "a" and attribute == "href":
        lowered = value.strip().lower()
        return value if lowered.startswith(("https://", "http://")) else None
    if tag == "ol" and attribute == "start":
        return value if value.isdigit() and len(value) <= 6 else None
    return value


def render_markdown(source: str) -> str:
    """Safe HTML for a post or comment body."""
    html = _parser().render(source)
    return nh3.clean(
        html,
        tags=set(ALLOWED_TAGS),
        clean_content_tags={"script", "style"},
        attributes={"a": {"href"}, "ol": {"start"}},
        attribute_filter=_attribute_filter,
        url_schemes={"http", "https"},
        url_relative="deny",
        link_rel=LINK_REL,
        strip_comments=True,
    )
