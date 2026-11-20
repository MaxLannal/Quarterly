"""The Commons: course questions with a bot answer and nested replies (`/commons/*`),
docs/BEST-OF-UCHICAGO-PLAN.md. Owned by the "commons" work stream; the endpoints are added there."""

from fastapi import APIRouter

router = APIRouter(tags=["commons"])
