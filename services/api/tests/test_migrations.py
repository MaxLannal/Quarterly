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
    "commons_thread",
    "commons_reply",
    "commons_pseudonym",
    "commons_vote",
    "commons_report",
    # The student record (Issue #14)
    "student_credit",
    "student_course",
    # The planner agent (issue #17): answers from the planner chat, waiting for the student
    "profile_proposal",
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


def test_0005_copies_the_primary_plan_into_the_student_record(fresh_db_url: str) -> None:
    """Issue #14 step 12: credits, completed and in-progress courses and the entry term of each
    primary plan move into the record; a second plan's copies are not used."""
    cfg = alembic_config(fresh_db_url)
    engine = create_engine(fresh_db_url)
    command.upgrade(cfg, "0004")
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO account (id, username, email, email_verified_day) VALUES "
                "('00000000-0000-0000-0000-000000000001', 'heron', 'h@uchicago.edu', CURRENT_DATE)"
            )
        )
        conn.execute(text("INSERT INTO catalog_year (id) VALUES ('2026-27')"))
        course = conn.execute(
            text(
                "INSERT INTO course (catalog_year, subject, number, code, title, source) VALUES "
                "('2026-27', 'PHYS', '13100', 'PHYS 13100', 'Mechanics', '{}') RETURNING id"
            )
        ).scalar_one()
        for name, primary in (("Main", True), ("Other", False)):
            plan = conn.execute(
                text(
                    "INSERT INTO plan (id, account_id, name, catalog_year, entry_term, "
                    "entry_year_level, graduation_term, is_primary) VALUES (gen_random_uuid(), "
                    "'00000000-0000-0000-0000-000000000001', :name, '2026-27', '2025-AU', 2, "
                    "'2028-SP', :primary) RETURNING id"
                ),
                {"name": name, "primary": primary},
            ).scalar_one()
            conn.execute(
                text(
                    "INSERT INTO credit (plan_id, kind, label, maps_to_course_id, units) "
                    "VALUES (:plan, 'AP', :label, :course, 100)"
                ),
                {"plan": plan, "label": f"AP for {name}", "course": course},
            )
            for status in ("completed", "planned"):
                conn.execute(
                    text(
                        "INSERT INTO plan_item (plan_id, course_id, term_id, status, grade) "
                        "VALUES (:plan, :course, :term, :status, 'A')"
                    ),
                    {
                        "plan": plan,
                        "course": course,
                        "term": "2025-AU" if status == "completed" else "2026-AU",
                        "status": status,
                    },
                )
    command.upgrade(cfg, "head")
    with engine.connect() as conn:
        profile = conn.execute(
            text(
                "SELECT entry_term, entry_year_level, expected_graduation_term FROM student_profile"
            )
        ).one()
        assert tuple(profile) == ("2025-AU", 2, "2028-SP")
        assert conn.execute(text("SELECT label FROM student_credit")).scalars().all() == [
            "AP for Main"
        ]
        taken = conn.execute(text("SELECT term_id, status, grade FROM student_course")).all()
        assert [tuple(t) for t in taken] == [("2025-AU", "completed", "A")]
        # 0010: the per-plan copies are gone from every plan (nothing read them, and a grade
        # the student removed on the dashboard stayed in them); planned courses stay.
        assert conn.execute(text("SELECT count(*) FROM credit")).scalar_one() == 0
        items = conn.execute(text("SELECT status, count(*) FROM plan_item GROUP BY status")).all()
        assert [tuple(i) for i in items] == [("planned", 2)]
    engine.dispose()


def test_0007_keeps_the_lock_of_a_taken_course(fresh_db_url: str) -> None:
    """Blocker 2 (review of PR #21): 0005 copied grading and units into the record but not the
    lock; 0007 adds `student_course.locked` and copies the lock from the primary plan's old
    copies (they stay in `plan_item` until the plan is saved again)."""
    cfg = alembic_config(fresh_db_url)
    engine = create_engine(fresh_db_url)
    command.upgrade(cfg, "0004")
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO account (id, username, email, email_verified_day) VALUES "
                "('00000000-0000-0000-0000-000000000003', 'heron', 'h@uchicago.edu', CURRENT_DATE)"
            )
        )
        conn.execute(text("INSERT INTO catalog_year (id) VALUES ('2026-27')"))
        courses = [
            conn.execute(
                text(
                    "INSERT INTO course (catalog_year, subject, number, code, title, source) "
                    "VALUES ('2026-27', 'PHYS', :n, :code, 'Mechanics', '{}') RETURNING id"
                ),
                {"n": number, "code": f"PHYS {number}"},
            ).scalar_one()
            for number in ("13100", "13200")
        ]
        plan = conn.execute(
            text(
                "INSERT INTO plan (id, account_id, name, catalog_year, entry_term, is_primary) "
                "VALUES (gen_random_uuid(), '00000000-0000-0000-0000-000000000003', 'Main', "
                "'2026-27', '2025-AU', true) RETURNING id"
            )
        ).scalar_one()
        for course, locked in zip(courses, (True, False), strict=True):
            conn.execute(
                text(
                    "INSERT INTO plan_item (plan_id, course_id, term_id, status, locked, grading) "
                    "VALUES (:plan, :course, '2025-AU', 'completed', :locked, 'pass_fail')"
                ),
                {"plan": plan, "course": course, "locked": locked},
            )
    command.upgrade(cfg, "head")
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT c.code, s.locked, s.grading FROM student_course s "
                "JOIN course c ON c.id = s.course_id ORDER BY c.code"
            )
        ).all()
        assert [tuple(r) for r in rows] == [
            ("PHYS 13100", True, "pass_fail"),
            ("PHYS 13200", False, "pass_fail"),
        ]
    command.downgrade(cfg, "0006")
    with engine.connect() as conn:
        columns = {c["name"] for c in inspect(conn).get_columns("student_course")}
        assert "locked" not in columns and "grading" in columns
    engine.dispose()


def test_0010_fills_an_empty_record_before_it_removes_the_copies(fresh_db_url: str) -> None:
    """0005 filled the record from the primary plan only. For an account with plans but no
    primary plan, 0010 first fills the empty record from the most recently updated plan, so
    removing the per-plan copies loses nothing. An account with a primary plan whose record the
    student emptied stays empty: the old copies never bring deleted grades back."""
    cfg = alembic_config(fresh_db_url)
    engine = create_engine(fresh_db_url)
    command.upgrade(cfg, "0004")
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO catalog_year (id) VALUES ('2026-27')"))
        course = conn.execute(
            text(
                "INSERT INTO course (catalog_year, subject, number, code, title, source) VALUES "
                "('2026-27', 'PHYS', '13100', 'PHYS 13100', 'Mechanics', '{}') RETURNING id"
            )
        ).scalar_one()
        account = "00000000-0000-0000-0000-000000000004"
        conn.execute(
            text(
                "INSERT INTO account (id, username, email, email_verified_day) VALUES "
                f"('{account}', 'heron', 'h@uchicago.edu', CURRENT_DATE)"
            )
        )
        for name, day in (("Old", "2026-11-01"), ("Newer", "2026-11-20")):
            plan = conn.execute(
                text(
                    "INSERT INTO plan (id, account_id, name, catalog_year, entry_term, "
                    "is_primary, updated_day) VALUES (gen_random_uuid(), :account, :name, "
                    "'2026-27', '2025-AU', false, :day) RETURNING id"
                ),
                {"account": account, "name": name, "day": day},
            ).scalar_one()
            conn.execute(
                text(
                    "INSERT INTO credit (plan_id, kind, label, units) "
                    "VALUES (:plan, 'AP', :label, 100)"
                ),
                {"plan": plan, "label": f"AP from {name}"},
            )
            conn.execute(
                text(
                    "INSERT INTO plan_item (plan_id, course_id, term_id, status, grading, grade) "
                    "VALUES (:plan, :course, '2025-AU', 'completed', 'pass_fail', :grade)"
                ),
                {"plan": plan, "course": course, "grade": "P" if name == "Newer" else "A"},
            )
        # A second account with a primary plan: 0005 fills its record from it.
        emptied = "00000000-0000-0000-0000-000000000005"
        conn.execute(
            text(
                "INSERT INTO account (id, username, email, email_verified_day) VALUES "
                f"('{emptied}', 'otter', 'o@uchicago.edu', CURRENT_DATE)"
            )
        )
        primary = conn.execute(
            text(
                "INSERT INTO plan (id, account_id, name, catalog_year, entry_term, is_primary) "
                f"VALUES (gen_random_uuid(), '{emptied}', 'Main', '2026-27', '2025-AU', true) "
                "RETURNING id"
            )
        ).scalar_one()
        conn.execute(
            text("INSERT INTO credit (plan_id, kind, label, units) VALUES (:p, 'AP', 'Old', 100)"),
            {"p": primary},
        )
        conn.execute(
            text(
                "INSERT INTO plan_item (plan_id, course_id, term_id, status, grade) "
                "VALUES (:p, :course, '2025-AU', 'completed', 'B')"
            ),
            {"p": primary, "course": course},
        )
    command.upgrade(cfg, "0009")
    with engine.begin() as conn:
        # The student then empties the record on the dashboard.
        for table in ("student_credit", "student_course"):
            conn.execute(text(f"DELETE FROM {table} WHERE account_id = '{emptied}'"))
    command.upgrade(cfg, "head")
    with engine.connect() as conn:
        assert conn.execute(text("SELECT label FROM student_credit")).scalars().all() == [
            "AP from Newer"
        ]
        taken = conn.execute(
            text("SELECT account_id::text, grading, grade FROM student_course")
        ).all()
        assert [tuple(t) for t in taken] == [(account, "pass_fail", "P")]
        # Its profile row now exists, with the plan's first quarter as the answer.
        entry = conn.execute(
            text("SELECT entry_term FROM student_profile WHERE account_id = :a"), {"a": account}
        ).scalar_one()
        assert entry == "2025-AU"
        assert conn.execute(text("SELECT count(*) FROM credit")).scalar_one() == 0
        assert conn.execute(text("SELECT count(*) FROM plan_item")).scalar_one() == 0
    engine.dispose()


def test_0005_downgrade_copies_the_record_back_into_the_primary_plan(fresh_db_url: str) -> None:
    cfg = alembic_config(fresh_db_url)
    engine = create_engine(fresh_db_url)
    command.upgrade(cfg, "head")
    account = "00000000-0000-0000-0000-000000000002"
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO account (id, username, email, email_verified_day) VALUES "
                f"('{account}', 'heron', 'h@uchicago.edu', CURRENT_DATE)"
            )
        )
        conn.execute(text("INSERT INTO catalog_year (id) VALUES ('2026-27')"))
        course = conn.execute(
            text(
                "INSERT INTO course (catalog_year, subject, number, code, title, source) VALUES "
                "('2026-27', 'PHYS', '13100', 'PHYS 13100', 'Mechanics', '{}') RETURNING id"
            )
        ).scalar_one()
        plan = conn.execute(
            text(
                "INSERT INTO plan (id, account_id, name, catalog_year, entry_term, is_primary) "
                f"VALUES (gen_random_uuid(), '{account}', 'Main', '2026-27', '2026-AU', true) "
                "RETURNING id"
            )
        ).scalar_one()
        conn.execute(
            text(
                "INSERT INTO student_credit (account_id, kind, label, units) "
                f"VALUES ('{account}', 'AP', 'AP Physics', 100)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO student_course (account_id, course_id, term_id, status, grade) "
                f"VALUES ('{account}', :course, '2026-AU', 'completed', 'A')"
            ),
            {"course": course},
        )
    command.downgrade(cfg, "0004")
    with engine.connect() as conn:
        labels = conn.execute(
            text("SELECT label FROM credit WHERE plan_id = :p"), {"p": plan}
        ).scalars()
        assert list(labels) == ["AP Physics"]
        items = conn.execute(
            text("SELECT term_id, status, grade FROM plan_item WHERE plan_id = :p"), {"p": plan}
        ).all()
        assert [tuple(i) for i in items] == [("2026-AU", "completed", "A")]
    engine.dispose()


def test_0011_replaces_courses_per_quarter_with_the_course_load(fresh_db_url: str) -> None:
    """Richard (2026-11-25): "courses per quarter" became a course load (conservative, normal or
    ambitious). A number of courses does not tell which load the student meant, so an old
    answer becomes "not answered"; the student's other answers stay."""
    cfg = alembic_config(fresh_db_url)
    engine = create_engine(fresh_db_url)
    command.upgrade(cfg, "0010")
    account = "00000000-0000-0000-0000-000000000011"
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO account (id, username, email, email_verified_day) VALUES "
                f"('{account}', 'heron', 'h@uchicago.edu', CURRENT_DATE)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO student_profile (account_id, pace, courses_per_term) "
                f"VALUES ('{account}', 'early', 4)"
            )
        )
        conn.execute(text("INSERT INTO catalog_year (id) VALUES ('2026-27')"))
        for number, status in (("14100", "completed"), ("14200", "in_progress")):
            course = conn.execute(
                text(
                    "INSERT INTO course (catalog_year, subject, number, code, title, source) "
                    f"VALUES ('2026-27', 'CMSC', '{number}', 'CMSC {number}', 'x', '{{}}') "
                    "RETURNING id"
                )
            ).scalar_one()
            conn.execute(
                text(
                    "INSERT INTO student_course (account_id, course_id, term_id, status, grade) "
                    f"VALUES ('{account}', :c, '2025-AU', '{status}', 'A')"
                ),
                {"c": course},
            )
    command.upgrade(cfg, "head")
    with engine.connect() as conn:
        row = conn.execute(text("SELECT pace, course_load FROM student_profile")).one()
        assert tuple(row) == ("early", None)
        # A course in progress has no grade (Richard, 2026-11-25): a grade stored before is gone.
        grades = conn.execute(text("SELECT status, grade FROM student_course ORDER BY status"))
        assert [tuple(g) for g in grades] == [("completed", "A"), ("in_progress", None)]
        columns = {c["name"] for c in inspect(conn).get_columns("student_profile")}
        assert "courses_per_term" not in columns
    with engine.begin() as conn, pytest.raises(Exception, match="course_load"):
        conn.execute(text("UPDATE student_profile SET course_load = 'heavy'"))
    engine.dispose()


def test_0012_adds_the_planner_agent_columns(fresh_db_url: str) -> None:
    cfg = alembic_config(fresh_db_url)
    engine = create_engine(fresh_db_url)
    command.upgrade(cfg, "head")
    insp = inspect(engine)
    assert "interests" in {c["name"] for c in insp.get_columns("student_profile")}
    assert "state" in {c["name"] for c in insp.get_columns("agent_run")}
    assert {"run_id", "meta"} <= {c["name"] for c in insp.get_columns("change_set")}
    assert {c["name"] for c in insp.get_columns("profile_proposal")} == {
        "id",
        "account_id",
        "field",
        "value",
        "source",
        "status",
        "created_day",
    }
    command.downgrade(cfg, "0011")
    insp = inspect(engine)
    assert "profile_proposal" not in insp.get_table_names()
    assert "interests" not in {c["name"] for c in insp.get_columns("student_profile")}
    assert "run_id" not in {c["name"] for c in insp.get_columns("change_set")}
    command.upgrade(cfg, "head")
    engine.dispose()
