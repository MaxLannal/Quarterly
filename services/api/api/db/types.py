from typing import Any

from sqlalchemy.types import UserDefinedType


class Ltree(UserDefinedType[str]):
    """PostgreSQL `ltree` (comment paths)."""

    cache_ok = True

    def get_col_spec(self, **kw: Any) -> str:
        return "LTREE"
