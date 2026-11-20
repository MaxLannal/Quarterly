"""The personal dashboard: profile, the interviewing guide and routes (`/me/profile`,
`/me/routes`, `/agents/interview`, `/agents/routes`), docs/BEST-OF-UCHICAGO-PLAN.md.
Owned by the "me" work stream; the endpoints are added there."""

from fastapi import APIRouter

router = APIRouter(tags=["profile"])
