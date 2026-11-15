"""Forum -> course attributes: the numeric update (SPEC "Forum -> course attributes"). Pure.

For attribute a on subject s (a course, or a course x instructor page), with prior mean m and
prior weight k:

    a_s = (k * m + sum(w_i * r_i)) / (k + sum(w_i))

- m is the department-level average when the department has at least MIN_N ratings of that
  attribute (k = K_DEPARTMENT = 5), else the course's cold-start estimate (k = K_ESTIMATE = 2:
  "labelled estimate and weighted as 2 ratings", SPEC A3), else there is no prior (k = 0).
- w = 1 for structured ratings, 0.5 for values extracted from post text, and 0.5 for any rating
  older than four years.
- The confidence interval is the posterior mean +- 1.96 standard errors, where the variance is
  the weighted variance of the ratings (the scale's variance when there are fewer than two) and
  the effective count is k + sum(w); it is clamped to the attribute's scale.
- Forum-derived values are published only when n, the number of distinct posts behind the
  ratings (not their weight, and not the number of mentions), is at least MIN_N; below that the
  subject shows its estimate.
"""

from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass

K_DEPARTMENT = 5.0
K_ESTIMATE = 2.0
W_STRUCTURED = 1.0
W_TEXT = 0.5
W_OLD = 0.5
OLD_YEARS = 4
MIN_N = 3
Z = 1.96

#: Attribute -> (lowest, highest) value.
SCALES: dict[str, tuple[float, float]] = {
    "workload_hours": (0.0, 60.0),
    "difficulty": (1.0, 5.0),
    "intellectual_intensity": (1.0, 5.0),
    "recommend_rate": (0.0, 1.0),
    "pace": (1.0, 5.0),
    "grading_strictness": (1.0, 5.0),
}


@dataclass(frozen=True)
class Rating:
    value: float
    weight: float
    post_id: int | None = None
    source: str = "review"  # "review" (structured) or "text"


@dataclass(frozen=True)
class Prior:
    mean: float
    weight: float
    kind: str  # "department" or "estimate"


@dataclass(frozen=True)
class Estimate:
    value: float
    ci_low: float
    ci_high: float
    n: int
    weight: float


def count_posts(ratings: list[Rating]) -> int:
    """Distinct posts behind `ratings` (a rating without a post counts on its own)."""
    return len({r.post_id for r in ratings if r.post_id is not None}) + sum(
        r.post_id is None for r in ratings
    )


def rating_weight(source: str, day: dt.date, today: dt.date) -> float:
    """Structured 1, text 0.5; anything older than OLD_YEARS decays to 0.5."""
    weight = W_STRUCTURED if source == "review" else W_TEXT
    if (today - day).days > 365 * OLD_YEARS:
        weight = min(weight, W_OLD)
    return weight


def posterior(key: str, ratings: list[Rating], prior: Prior | None) -> Estimate | None:
    """The Bayesian average of `ratings` with `prior`; None when there is nothing to average."""
    low, high = SCALES[key]
    k = prior.weight if prior is not None else 0.0
    m = prior.mean if prior is not None else 0.0
    total = sum(r.weight for r in ratings)
    if k + total == 0:
        return None
    value = (k * m + sum(r.weight * r.value for r in ratings)) / (k + total)
    if total > 0 and len(ratings) >= 2:
        mean = sum(r.weight * r.value for r in ratings) / total
        variance = sum(r.weight * (r.value - mean) ** 2 for r in ratings) / total
    else:
        variance = ((high - low) ** 2) / 12  # a uniform spread over the scale
    half = Z * math.sqrt(variance / (k + total))
    return Estimate(
        value=round(min(high, max(low, value)), 3),
        ci_low=round(max(low, value - half), 3),
        ci_high=round(min(high, value + half), 3),
        n=count_posts(ratings),
        weight=round(total, 3),
    )


def department_prior(ratings: list[Rating]) -> Prior | None:
    """The department-level average, when the department has enough ratings."""
    if count_posts(ratings) < MIN_N:
        return None
    total = sum(r.weight for r in ratings)
    if total == 0:
        return None
    return Prior(
        mean=sum(r.weight * r.value for r in ratings) / total,
        weight=K_DEPARTMENT,
        kind="department",
    )


#: Attributes the forum updates. Pace and grading strictness come from the optional review
#: questions (Q11), so only from the reviews that answered them.
FORUM_KEYS = (
    "workload_hours",
    "difficulty",
    "intellectual_intensity",
    "recommend_rate",
    "pace",
    "grading_strictness",
)
