"""The Ask chatbot and the companion's chat (`POST /agents/ask`), docs/BEST-OF-UCHICAGO-PLAN.md."""

from typing import Annotated, Literal

from pydantic import BaseModel, Field, RootModel


class AskTurn(BaseModel):
    role: Literal["user", "assistant"]
    text: str = Field(max_length=4000)


class AskContext(BaseModel):
    """Where the student asks from (the companion sends it; the Ask page usually does not)."""

    #: The page's path, e.g. "/courses/CMSC%2014100".
    page: str | None = Field(default=None, max_length=200)
    #: The course of a course page.
    course_code: str | None = Field(default=None, max_length=16)
    #: The Commons thread of a thread page.
    thread_id: int | None = Field(default=None, ge=1)


class AskRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    #: Earlier turns of this conversation, oldest first (the browser keeps conversations).
    history: list[AskTurn] = Field(default=[], max_length=12)
    context: AskContext = AskContext()
    #: "companion": the side panel on every page (shorter answers about the page).
    mode: Literal["ask", "companion"] = "ask"


AskCitationKind = Literal["course", "program", "post", "summary", "attribute", "thread", "guide"]


class AskCitation(BaseModel):
    """A source chip. `label` and `href` are built by the server from the id (never by the
    model): `href` is a path on this site, or an https page on uchicago.edu for `guide`."""

    kind: AskCitationKind
    id: str
    label: str
    href: str


class AskCourse(BaseModel):
    """A course the answer mentions; it exists in the catalog."""

    code: str
    title: str


class AskStepEvent(BaseModel):
    """The agent called a tool ("Searching the catalog for “quantum”")."""

    type: Literal["step"] = "step"
    tool: str
    label: str
    status: Literal["started", "done", "failed"]


class AskAnswerEvent(BaseModel):
    type: Literal["answer"] = "answer"
    #: Markdown subset: paragraphs, **bold**, *italic*, lists, `code`, [links](/path).
    text: str
    citations: list[AskCitation] = []
    #: Every real course the text mentions or cites, in order of first mention.
    courses: list[AskCourse] = []
    #: Up to three short questions the student may ask next.
    followups: list[str] = []
    #: False when the AI was unavailable and the answer is the deterministic search.
    ai: bool = True


class AskDoneEvent(BaseModel):
    type: Literal["done"] = "done"
    run_id: str


class AskErrorEvent(BaseModel):
    type: Literal["error"] = "error"
    message: str


class AskEvent(
    RootModel[
        Annotated[
            AskStepEvent | AskAnswerEvent | AskDoneEvent | AskErrorEvent,
            Field(discriminator="type"),
        ]
    ]
):
    """One Server-Sent Event `data:` payload from /agents/ask."""
