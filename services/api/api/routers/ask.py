"""The Ask chatbot and the companion's chat (`POST /agents/ask`), docs/BEST-OF-UCHICAGO-PLAN.md.
Owned by the "ask" work stream; the endpoints are added there."""

from fastapi import APIRouter

router = APIRouter(tags=["ask"])
