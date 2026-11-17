"""Sort orders (SPEC "Forum > Sorting"), computed in SQL, with plain-Python references that the
tests compare against.

- **Best:** lower bound of the Wilson score interval on the up-vote share, z = 1.96, so a 9-1
  item outranks a 1-0 item. No votes scores 0.
- **Top:** net score. **New:** day created (then id, newest first).
- **Controversial:** many votes near 50/50: (u + d) ** (min(u, d) / max(u, d)), 0 unless the
  item has both up and down votes (the reddit formula).
- **Hot:** net score decayed by age with a half-life of 30 days: score * 0.5 ** (age_days / 30).
  Ages are whole days, because only the day of a post is stored.

Ties break on the newer id.
"""

from __future__ import annotations

import math
from typing import Any, Literal

import sqlalchemy as sa
from sqlalchemy.sql.elements import ColumnElement

Sort = Literal["best", "new", "top", "controversial", "hot"]

Z = 1.96
HOT_HALF_LIFE_DAYS = 30.0


# ------------------------------------------------------------------------- Python references


def wilson_lower_bound(up: int, down: int, z: float = Z) -> float:
    n = up + down
    if n == 0:
        return 0.0
    p = up / n
    centre = p + z * z / (2 * n)
    spread = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n)
    return (centre - spread) / (1 + z * z / n)


def controversy(up: int, down: int) -> float:
    if up <= 0 or down <= 0:
        return 0.0
    return float((up + down) ** (min(up, down) / max(up, down)))


def hot(score: int, age_days: int) -> float:
    return score * 0.5 ** (age_days / HOT_HALF_LIFE_DAYS)


# ---------------------------------------------------------------------------------------- SQL


def _f(expr: Any) -> ColumnElement[float]:
    return sa.cast(expr, sa.Float)


def wilson_sql(up: Any, down: Any, z: float = Z) -> ColumnElement[float]:
    n = sa.func.nullif(_f(up) + _f(down), 0.0)
    p = _f(up) / n
    zz = z * z
    centre = p + zz / (2 * n)
    spread = z * sa.func.sqrt((p * (1 - p) + zz / (4 * n)) / n)
    return sa.func.coalesce((centre - spread) / (1 + zz / n), 0.0)


def controversy_sql(up: Any, down: Any) -> ColumnElement[float]:
    return sa.case(
        (
            sa.and_(up > 0, down > 0),
            sa.func.power(
                _f(up) + _f(down), _f(sa.func.least(up, down)) / _f(sa.func.greatest(up, down))
            ),
        ),
        else_=0.0,
    )


def hot_sql(score: Any, created_day: Any) -> ColumnElement[float]:
    age_days = _f(sa.func.current_date() - created_day)
    return _f(score) * sa.func.power(0.5, age_days / HOT_HALF_LIFE_DAYS)


def order_by(
    sort: Sort, *, up: Any, down: Any, score: Any, created_day: Any, id_: Any
) -> list[Any]:
    """ORDER BY clauses for `sort` (descending, newest id first on ties)."""
    key: Any
    if sort == "best":
        key = wilson_sql(up, down)
    elif sort == "top":
        key = score
    elif sort == "controversial":
        key = controversy_sql(up, down)
    elif sort == "hot":
        key = hot_sql(score, created_day)
    else:
        key = created_day
    return [sa.desc(key), sa.desc(id_)]
