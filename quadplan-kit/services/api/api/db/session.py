from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from api.config import get_settings


@lru_cache
def get_engine(url: str | None = None) -> Engine:
    # hide_parameters: a database error never logs query values (post text, quotes).
    return create_engine(
        url or get_settings().database_url, pool_pre_ping=True, hide_parameters=True
    )


def get_session() -> Iterator[Session]:
    """FastAPI dependency."""
    with sessionmaker(get_engine())() as session:
        yield session
