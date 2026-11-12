"""Database fixtures: each test gets a throwaway database on the DATABASE_URL server, so
parallel runs (worktrees, CI) never collide. Set QP_ALLOW_NO_DB=1 to skip DB tests instead of
failing when no server is reachable."""

import os
import uuid
from collections.abc import Iterator

import pytest
from alembic import command
from api.config import get_settings
from api_test_support import alembic_config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError


@pytest.fixture
def fresh_db_url() -> Iterator[str]:
    base = make_url(get_settings().database_url)
    name = f"qp_test_{uuid.uuid4().hex[:12]}"
    admin = create_engine(base.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            conn.execute(text(f'CREATE DATABASE "{name}"'))
    except OperationalError as exc:
        admin.dispose()
        if os.environ.get("QP_ALLOW_NO_DB"):
            pytest.skip(f"no database server: {exc}")
        raise
    try:
        yield base.set(database=name).render_as_string(hide_password=False)
    finally:
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        admin.dispose()


@pytest.fixture
def migrated_db_url(fresh_db_url: str) -> str:
    command.upgrade(alembic_config(fresh_db_url), "head")
    return fresh_db_url
