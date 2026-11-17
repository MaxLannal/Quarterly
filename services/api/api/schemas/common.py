from typing import Any

from fastapi import HTTPException
from pydantic import BaseModel


class Page[T](BaseModel):
    items: list[T]
    total: int
    limit: int
    offset: int


class ErrorOut(BaseModel):
    detail: str


NOT_IMPLEMENTED: dict[int | str, dict[str, Any]] = {
    501: {"model": ErrorOut, "description": "Not implemented yet"}
}


def not_implemented(prompt: str) -> HTTPException:
    """Stub marker: the endpoint's contract is frozen; its body arrives in `prompt`."""
    return HTTPException(status_code=501, detail=f"Not implemented yet (prompt {prompt})")
