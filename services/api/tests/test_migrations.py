import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from api.db.base import Base
from api_test_support import alembic_config
from sqlalchemy import create_engine, inspect, text

pytestmark = pytest.mark.db

SPEC_TABLES = {
    # Catalog
    "catalog_year",
    "course",
    "crosslist_group",
    "course_relation",
    "requisite",
    "course_list",
    # Schedule
    "term",
    "instructor",
    "section",
    "course_instructor",
    "offering_pattern",
    # Programs (+ college_policy)
    "program",
    "program_version",
    "program_relation",
    "college_policy",
    # Attributes
    "attribute_def",
    "attribute_value",
    # Provenance and review
    "source_snapshot",
    "extraction_run",
    "review_item",
    # Plans and goals
    "plan",
    "plan_program",
    "plan_item",
    "credit",
    "goal",
    "verification_report",
    "change_set",
    # Agents and LLM usage
    "agent_run",
    "chat_message",
    "llm_call",
    # Forum
    "post",
    "review_rating",
    "comment",
    "vote",
    "pseudonym",
    "report",
    "moderation_action",
    "forum_summary",
    # Accounts (decision 5)
    "account",
    # Campus companion (docs/BEST-OF-UCHICAGO-PLAN.md)
    "student_profile",
    "pathway",
    "commons_thread",
    "commons_reply",
    "commons_pseudonym",
    "commons_vote",
    "commons_report",
}


def test_upgrade_downgrade_upgrade(fresh_db_url: str) -> None:
    cfg = alembic_config(fresh_db_url)
    engine = create_engine(fresh_db_url)
    command.upgrade(cfg, "head")
    insp = inspect(engine)
    assert set(insp.get_table_names()) == SPEC_TABLES | {"alembic_version"}
    with engine.connect() as conn:
        exts = set(conn.execute(text("SELECT extname FROM pg_extension")).scalars())
    assert {"ltree", "pg_trgm"} <= exts
    assert "ix_course_code" in {i["name"] for i in insp.get_indexes("course")}
    assert "ix_section_term_course" in {i["name"] for i in insp.get_indexes("section")}
    assert any(i["column_names"] == ["plan_hash"] for i in insp.get_indexes("verification_report"))
    assert any(
        u["column_names"] == ["course_id", "instructor_id"]
        for u in insp.get_unique_constraints("course_instructor")
    )
    assert {c["name"] for c in insp.get_columns("account")} >= {
        "email",
        "email_verified_day",
        "created_day",
    }
    command.downgrade(cfg, "base")
    assert set(inspect(engine).get_table_names()) == {"alembic_version"}
    command.upgrade(cfg, "head")
    assert set(inspect(engine).get_table_names()) >= SPEC_TABLES
    engine.dispose()


def test_models_match_migration(migrated_db_url: str) -> None:
    engine = create_engine(migrated_db_url)
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    engine.dispose()
    assert diff == []


def test_user_rows_have_day_level_dates_only(migrated_db_url: str) -> None:
    """CLAUDE.md: no exact timestamps for users."""
    insp = inspect(create_engine(migrated_db_url))
    user_tables = [
        "account",
        "plan",
        "plan_item",
        "goal",
        "change_set",
        "post",
        "comment",
        "vote",
        "report",
        "pseudonym",
        "review_rating",
        "chat_message",
        "review_item",
        "student_profile",
        "pathway",
        "commons_thread",
        "commons_reply",
        "commons_vote",
        "commons_report",
    ]
    for table in user_tables:
        for col in insp.get_columns(table):
            assert "TIMESTAMP" not in str(col["type"]).upper(), f"{table}.{col['name']}"


def test_email_lives_only_on_account(migrated_db_url: str) -> None:
    insp = inspect(create_engine(migrated_db_url))
    holders = [
        t for t in insp.get_table_names() for c in insp.get_columns(t) if "email" in c["name"]
    ]
    assert sorted(set(holders)) == ["account"]
