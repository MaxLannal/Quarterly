"""The 60-word limit of the AI answer under a Commons question (issue #20): counting and clipping."""

from api.commons.words import ANSWER_WORDS, count_words, limit_words


def test_words_are_what_a_reader_sees() -> None:
    assert ANSWER_WORDS == 60
    assert count_words("Yes: **CMSC 14100** is fine.") == 5
    assert count_words("- one\n- two — three") == 3  # bullets and dashes are not words
    assert count_words("[the course page](/courses/CMSC%2014100)") == 3
    assert count_words("") == 0


def test_a_short_text_is_unchanged() -> None:
    text = "Take **MATH 15100** first.\n\n- Then MATH 15200."
    assert limit_words(text) == text


def test_a_long_text_ends_at_its_last_full_sentence() -> None:
    sentence = "This sentence has exactly seven words in it."
    text = " ".join([sentence] * 10)  # 80 words
    out = limit_words(text)
    assert count_words(out) <= 60
    assert out.endswith("in it.") and "…" not in out
    assert count_words(out) == 56


def test_a_long_text_with_no_sentence_end_is_cut_with_an_ellipsis() -> None:
    out = limit_words("**" + " ".join(["word"] * 100))
    assert count_words(out) == 60
    assert out.endswith("…**")  # the open bold is closed


def test_the_limit_can_be_smaller() -> None:
    assert limit_words("one two three four", 2) == "one two…"


def test_a_link_is_never_split() -> None:
    text = " ".join(["word"] * 58) + " [Intro to Programming](/courses/CMSC%2014100) after"
    out = limit_words(text)
    assert "[" not in out and out.endswith("word…")
    assert count_words(out) == 58
    whole = (
        " ".join(["word"] * 50) + " [Intro to Programming](/courses/CMSC%2014100) and more words"
    )
    assert "[Intro to Programming](/courses/CMSC%2014100)" in limit_words(whole)
    # A closed bracket that is not a link ("[sic]", "[1]") does not move the cut.
    plain = "Take CMSC 14100 [the intro course] first. " + "word " * 70
    assert count_words(limit_words(plain)) >= 30


def test_a_sentence_end_inside_a_link_is_not_a_place_to_stop() -> None:
    """Code review of the merge (2026-11-25): a period inside a link's text ("[Intro. to CS]")
    was taken as the last sentence end, so the answer ended with a broken "[Intro."."""
    words = " ".join(f"word{i}" for i in range(35))
    more = " ".join(f"more{i}" for i in range(40))
    link = "[Intro. to CS](/courses/CMSC%2014100)"
    out = limit_words(f"{words} See {link} {more}")
    assert count_words(out) <= 60
    assert link in out and out.endswith("…")
    # With a full sentence before the link, the answer ends there, not inside the link.
    first = " ".join(f"word{i}" for i in range(33)) + "."
    out = limit_words(f"{first} See {link} {more}")
    assert out.endswith("word32.") and "[" not in out
    # A limit that falls inside a link's target (a title in quotes has spaces) cuts before it.
    titled = " ".join(["word"] * 57) + ' See [CS](/courses/x "Intro to CS") after'
    assert "[" not in limit_words(titled)
