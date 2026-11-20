"""The Quarterly shelf (`data/feed/books.yaml`): real, well-known books the feed pairs with
courses by keyword. "Reading for the curious, not a syllabus": no course assigns them, and the
page says so."""

from __future__ import annotations

import os
import re
from collections.abc import Iterable
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from api.feed.categories import BY_KEY

#: The overlap a pairing needs: a keyword in the title (3) or three in the description.
MIN_SCORE = 3


class Book(BaseModel):
    slug: str = Field(pattern=r"^[a-z0-9-]+$")
    title: str
    author: str
    year: int
    year_label: str | None = None
    categories: list[str] = Field(min_length=1)
    keywords: list[str] = Field(min_length=1)

    @property
    def id(self) -> str:
        return f"book:{self.slug}"

    @property
    def when(self) -> str:
        if self.year_label:
            return self.year_label
        return f"{-self.year} BCE" if self.year < 0 else str(self.year)


class Shelf(BaseModel):
    books: list[Book]


def shelf_path() -> Path:
    """`FEED_SHELF` if set, else `data/feed/books.yaml` in the nearest folder above this file or
    the working directory (the repository root; `/app/data` in the API image)."""
    explicit = os.environ.get("FEED_SHELF")
    if explicit:
        return Path(explicit)
    for base in (Path(__file__).resolve(), Path.cwd()):
        for folder in (base, *base.parents):
            candidate = folder / "data" / "feed" / "books.yaml"
            if candidate.is_file():
                return candidate
    raise FileNotFoundError("data/feed/books.yaml not found (set FEED_SHELF)")


@lru_cache(maxsize=1)
def load_shelf() -> tuple[Book, ...]:
    raw = yaml.safe_load(shelf_path().read_text(encoding="utf-8"))
    books = Shelf.model_validate(raw).books
    slugs = [b.slug for b in books]
    if len(set(slugs)) != len(slugs):
        raise ValueError("books.yaml: duplicate slugs")
    for book in books:
        unknown = [c for c in book.categories if c not in BY_KEY]
        if unknown:
            raise ValueError(f"books.yaml: {book.slug} names unknown categories {unknown}")
    return tuple(books)


def by_slug() -> dict[str, Book]:
    return {b.slug: b for b in load_shelf()}


@dataclass(frozen=True)
class _Compiled:
    book: Book
    keys: tuple[tuple[str, re.Pattern[str]], ...]


@lru_cache(maxsize=1)
def _compiled() -> tuple[_Compiled, ...]:
    out = []
    for book in load_shelf():
        keys = tuple(
            (k.lower(), re.compile(r"\b" + re.escape(k.lower()) + r"(?:s|es)?\b"))
            for k in book.keywords
        )
        out.append(_Compiled(book, keys))
    return tuple(out)


def keyword_score(book_keys: Iterable[tuple[str, re.Pattern[str]]], title: str, text: str) -> int:
    """How strongly a course's lowercased `title` and `text` (title + description) speak to a
    book: 3 per keyword in the title, 1 per keyword only in the description."""
    score = 0
    for plain, pattern in book_keys:
        if plain not in text:
            continue  # cheap test first; the regex checks whole words
        if plain in title and pattern.search(title):
            score += 3
        elif pattern.search(text):
            score += 1
    return score


def books_for_course(title: str, description: str | None, category: str, n: int = 2) -> list[Book]:
    """At most `n` shelf books for a course. A book needs a real overlap (a keyword in the
    title, or three in the description); one of the course's own category ranks first."""
    low_title = title.lower()
    text = f"{low_title} {(description or '').lower()}"
    scored: list[tuple[int, int, Book]] = []
    for i, c in enumerate(_compiled()):
        score = keyword_score(c.keys, low_title, text)
        if score < MIN_SCORE:
            continue
        total = score + (2 if category in c.book.categories else 0)
        scored.append((total, -i, c.book))
    scored.sort(key=lambda t: (t[0], t[1]), reverse=True)
    return [b for _, _, b in scored[:n]]


def book_keys(book: Book) -> tuple[tuple[str, re.Pattern[str]], ...]:
    for c in _compiled():
        if c.book.slug == book.slug:
            return c.keys
    return ()
