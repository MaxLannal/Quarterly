"""The Ask chatbot and the companion's chat (`POST /agents/ask`), docs/BEST-OF-UCHICAGO-PLAN.md.

Streamed as Server-Sent Events: a `step` per tool call while the agent works, then the `answer`
and `done`. Works without a configured LLM (a deterministic search answers instead). Logged-out
use is allowed and rate-limited per client address (a Redis-only counter keyed by a hash of the
address and the day); a logged-in account has its own daily limit.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from llm_gateway.api import LLM, get_llm
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.agents.ask import AskRun
from api.agents.runtime import SSE_HEADERS, sse
from api.auth.ratelimit import DAY, Limit, account_subject, ip_subject
from api.auth.sessions import SessionData, optional_session
from api.auth.store import Store, get_store
from api.config import get_settings
from api.db import models as m
from api.db.session import get_session
from api.schemas.ask import AskErrorEvent, AskEvent, AskRequest

router = APIRouter(prefix="/agents", tags=["ask"])
logger = logging.getLogger("api.agents")

Db = Annotated[Session, Depends(get_session)]
Llm = Annotated[LLM, Depends(get_llm)]
MaybeSession = Annotated[SessionData | None, Depends(optional_session)]
RedisStore = Annotated[Store, Depends(get_store)]

#: Questions per day (docs/BEST-OF-UCHICAGO-PLAN.md; looser than the advisor's: answers are
#: short and read-only).
ASK_PER_ACCOUNT = Limit("agent-ask:account", 80, DAY)
ASK_PER_IP = Limit("agent-ask:ip", 40, DAY)

SSE: dict[int | str, dict[str, Any]] = {
    200: {
        "model": AskEvent,
        "description": "Server-Sent Events; each `data:` line is one AskEvent as JSON.",
        "content": {"text/event-stream": {}},
    }
}

FAILED = "Something went wrong on our side. Try again."


def _stream(db: Session, events: Iterator[BaseModel]) -> StreamingResponse:
    def body() -> Iterator[str]:
        try:
            for event in events:
                yield sse(event)
        except Exception:
            logger.exception("ask run failed")  # no request data in the message
            db.rollback()
            yield sse(AskErrorEvent(message=FAILED))

    return StreamingResponse(body(), media_type="text/event-stream", headers=SSE_HEADERS)


@router.post("/ask", response_class=StreamingResponse, responses=SSE)
def ask(
    body: AskRequest,
    request: Request,
    db: Db,
    store: RedisStore,
    session: MaybeSession,
    llm: Llm,
) -> StreamingResponse:
    # The campus chatbot: read tools only, cited answer; a search answers when the AI is off.
    account = db.get(m.Account, session.account_id) if session is not None else None
    if account is not None:
        ASK_PER_ACCOUNT.hit(store, account_subject(account.id))
    else:
        ASK_PER_IP.hit(store, ip_subject(request))
    run = AskRun(
        db=db,
        llm=llm,
        req=body,
        account=account,
        show_unpublished=get_settings().show_unpublished_programs,
    )
    return _stream(db, run.events())
