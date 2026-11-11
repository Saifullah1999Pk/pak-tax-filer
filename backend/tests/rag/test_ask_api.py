"""POST /api/ask (feature 006, task T010; contracts/ask-and-tokens-api.md).

The service's behaviour is tested in test_ask_service.py; these tests check the HTTP layer:
authentication, JSON only, the question's length and the response's shape.
"""

# pytest fixtures receive other fixtures by name.
# pylint: disable=redefined-outer-name

from collections.abc import Iterator

import pytest
from httpx2 import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from rag_helpers import QUESTION, a_corpus, reply

from app.auth.models import User
from app.main import app
from app.rag.answer import FakeAnswerer
from app.rag.router import get_answerer
from app.rag.service import LABEL

pytestmark = pytest.mark.anyio

URL = "/api/ask"


@pytest.fixture
def answerer() -> Iterator[FakeAnswerer]:
    """The app's answerer, replaced by a fake giving a faithful reply."""
    fake = FakeAnswerer(reply())
    app.dependency_overrides[get_answerer] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_answerer, None)


async def test_an_answer_has_the_contract_shape(
    client: AsyncClient, db: AsyncSession, logged_in_user: User, answerer: FakeAnswerer
) -> None:
    """Fails if the response differs from the contract's fields."""
    del logged_in_user, answerer
    await a_corpus(db)

    response = await client.post(URL, json={"question": QUESTION})

    assert response.status_code == 200
    assert response.json() == {
        "status": "answered",
        "answer": reply().answer,
        "citations": [
            {
                "title": "Income Tax Ordinance, 2001",
                "kind": "law",
                "location": "§149(1)",
                "page": 327,
            }
        ],
        "uncovered_part": None,
        "tax_page_line": None,
        "label": LABEL,
    }


async def test_a_refusal_is_still_200_with_the_label(
    client: AsyncClient, logged_in_user: User
) -> None:
    """Fails if a refusal (here: no corpus yet) is an error status or loses the label."""
    del logged_in_user

    response = await client.post(URL, json={"question": QUESTION})

    assert response.status_code == 200
    assert response.json()["status"] == "not_ready"
    assert response.json()["citations"] == [] and response.json()["label"] == LABEL


async def test_asking_needs_a_login(client: AsyncClient) -> None:
    """Fails if anyone not logged in can use the assistant."""
    assert (await client.post(URL, json={"question": QUESTION})).status_code == 401


@pytest.mark.parametrize("question", ["", "   ", "x" * 1001], ids=["empty", "blank", "too-long"])
async def test_an_empty_or_over_long_question_is_422(
    client: AsyncClient, logged_in_user: User, question: str
) -> None:
    """Fails if an empty question or one over 1,000 characters reaches the AI."""
    del logged_in_user
    assert (await client.post(URL, json={"question": question})).status_code == 422


async def test_asking_accepts_json_only(client: AsyncClient, logged_in_user: User) -> None:
    """Fails if a form post (a cross-site request) is accepted (002 research R3)."""
    del logged_in_user
    assert (await client.post(URL, data={"question": QUESTION})).status_code == 415
