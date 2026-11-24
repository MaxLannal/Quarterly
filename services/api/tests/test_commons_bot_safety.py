"""Review fixes for the Commons bot (spec review, 2026-11-20): its stored answer is public, so it
never reads login-only forum reviews, and it keeps only links to this site or to uchicago.edu."""

from api.agents.commons_bot import BOT_TOOLS, safe_answer


def test_the_public_answer_cannot_draw_on_login_only_forum_reviews() -> None:
    assert "get_forum_posts" not in BOT_TOOLS
    assert "get_forum_summary" not in BOT_TOOLS
    assert {"search_courses", "get_course", "search_commons", "campus_guide"} <= set(BOT_TOOLS)


def test_links_to_other_sites_are_reduced_to_their_text() -> None:
    text = (
        "See [the catalog](https://collegecatalog.uchicago.edu/x), "
        "[MATH 15100](/courses/MATH%2015100), [a prize](https://evil.example/p), "
        "<https://evil.example/q>, [sneaky](//evil.example) and "
        '[titled](https://phish.example "Official")'
    )
    out = safe_answer(text)
    assert "[the catalog](https://collegecatalog.uchicago.edu/x)" in out
    assert "[MATH 15100](/courses/MATH%2015100)" in out
    assert "evil.example/p" not in out and "a prize" in out
    assert "<https://evil.example/q>" not in out
    assert "(//evil.example)" not in out and "sneaky" in out
    assert "phish.example" not in out and "titled" in out


def test_a_lookalike_domain_is_not_trusted() -> None:
    assert safe_answer("[log in](https://uchicago.edu.evil.example/login)") == "log in"


def test_contact_details_are_scrubbed_like_student_posts() -> None:
    assert "someone@example.com" not in safe_answer("Write to someone@example.com for details.")
