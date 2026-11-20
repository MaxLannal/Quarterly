"""The feed (`/feed`, `/feed/categories`, `/agents/feed-notes`), docs/BEST-OF-UCHICAGO-PLAN.md.
Owned by the "feed" work stream; the endpoints are added there."""

from fastapi import APIRouter

router = APIRouter(tags=["feed"])
