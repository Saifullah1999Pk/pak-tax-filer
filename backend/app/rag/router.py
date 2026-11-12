"""POST /api/ask (feature 006, task T013; contracts/ask-and-tokens-api.md).

HTTP only: the service decides the answer or the refusal. Every outcome is a 200 with a status,
so the page always shows a message and the label; 401 and 422 are the only errors.
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, StringConstraints
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import current_user, require_json
from app.auth.models import User
from app.db import get_db
from app.rag.answer import GeminiAnswerer
from app.rag.embed import Embedder, GeminiEmbedder
from app.rag.service import Answerer, AskResult, Status, ask
from app.settings import get_settings

router = APIRouter(prefix="/api", tags=["ask"])


def get_embedder() -> Embedder:
    """The question embedder the app uses (tests replace it with a FakeEmbedder)."""
    # One attempt: a question has 15 s in all, so no time for the build's slow retries.
    return GeminiEmbedder(api_key=get_settings().gemini_api_key, attempts=1)


def get_answerer() -> Answerer:
    """The answer writer the app uses (tests replace it with a FakeAnswerer)."""
    settings = get_settings()
    return GeminiAnswerer(
        api_key=settings.gemini_api_key,
        model=settings.answer_model,
        effort=settings.answer_effort,
    )


class AskIn(BaseModel):
    """A question of 1 to 1,000 characters (blank ones are refused too)."""

    question: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)
    ]


class CitationOut(BaseModel):
    """Where a cited passage is: document, law or guidance, location and page."""

    title: str
    kind: str
    location: str
    page: int


class AskOut(BaseModel):
    """The contract's response."""

    status: Status
    answer: str
    citations: list[CitationOut]
    uncovered_part: str | None
    tax_page_line: str | None
    label: str

    @classmethod
    def of(cls, result: AskResult) -> "AskOut":
        """The response for a service result."""
        return cls(
            status=result.status,
            answer=result.answer,
            citations=[CitationOut(**vars(c)) for c in result.citations],
            uncovered_part=result.uncovered_part,
            tax_page_line=result.tax_page_line,
            label=result.label,
        )


@router.post("/ask", dependencies=[Depends(require_json)])
async def ask_question(
    body: AskIn,
    user: Annotated[User, Depends(current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    embedder: Annotated[Embedder, Depends(get_embedder)],
    answerer: Annotated[Answerer, Depends(get_answerer)],
) -> AskOut:
    """Answer from the FBR sources with citations, or say why not."""
    result = await ask(db, user.id, body.question, embedder, answerer)
    return AskOut.of(result)
