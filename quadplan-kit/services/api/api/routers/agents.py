from typing import Any

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from api.schemas.agents import AgentEvent, ChatRequest, GenerateRequest
from api.schemas.common import NOT_IMPLEMENTED, not_implemented

router = APIRouter(prefix="/agents", tags=["agents"], responses=NOT_IMPLEMENTED)

SSE: dict[int | str, dict[str, Any]] = {
    200: {
        "model": AgentEvent,
        "description": "Server-Sent Events; each `data:` line is one AgentEvent as JSON.",
        "content": {"text/event-stream": {}},
    }
}


@router.post("/generate", response_class=StreamingResponse, responses=SSE)
def generate(body: GenerateRequest) -> StreamingResponse:
    raise not_implemented("06/07")


@router.post("/chat", response_class=StreamingResponse, responses=SSE)
def chat(body: ChatRequest) -> StreamingResponse:
    raise not_implemented("07")
