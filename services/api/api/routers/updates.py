"""The companion's "what is new for you" (`/me/updates`), docs/BEST-OF-UCHICAGO-PLAN.md.
Owned by the "ask" work stream; the endpoints are added there."""

from fastapi import APIRouter

router = APIRouter(tags=["updates"])
