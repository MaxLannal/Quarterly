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
