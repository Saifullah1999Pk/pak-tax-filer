"""Embeddings for search (feature 006, task T006; research R3 amended 2026-11-11).

Gemini's `gemini-embedding-001` at 768 dimensions, through `google-genai` like the rest of the
app: passages as retrieval documents, questions as retrieval queries (Gemini tunes the two
differently). The build embeds a few hundred passages in batches, pausing and retrying when the
free tier says "too many requests"; a lasting failure raises, so a build never stores part of
the corpus. Embeddings only place text for search; they never touch a tax figure.
"""

import asyncio
import hashlib
import logging
import math
import re
from collections.abc import Awaitable, Callable
from typing import Protocol

import httpx2
from google import genai
from google.genai import errors, types

from app.rag.models import EMBEDDING_DIMENSIONS

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "gemini-embedding-001"
# Worth waiting for: rate limits and Google's own short outages.
_RETRYABLE = {429, 500, 502, 503, 504}


class EmbeddingError(Exception):
    """Embeddings couldn't be made (no key, a lasting API failure, or an unexpected reply)."""


class Embedder(Protocol):
    """Turns texts into vectors for pgvector."""

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Vectors for passages, in the same order."""
        ...  # pylint: disable=unnecessary-ellipsis

    async def embed_query(self, text: str) -> list[float]:
        """The vector for one question."""
        ...  # pylint: disable=unnecessary-ellipsis


class GeminiEmbedder:
    """Gemini embeddings (free tier); any failure is an EmbeddingError."""

    def __init__(  # pylint: disable=too-many-arguments
        self,
        *,
        api_key: str | None,
        model: str = EMBEDDING_MODEL,
        http_client: httpx2.AsyncClient | None = None,
        batch_size: int = 50,
        attempts: int = 4,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._http_client = http_client
        self._batch_size = batch_size
        self._attempts = attempts
        self._sleep = sleep

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Vectors for passages, batch by batch, in the same order."""
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self._batch_size):
            batch = texts[start : start + self._batch_size]
            vectors += await self._embed(batch, "RETRIEVAL_DOCUMENT")
        return vectors

    async def embed_query(self, text: str) -> list[float]:
        """The vector for one question."""
        return (await self._embed([text], "RETRIEVAL_QUERY"))[0]

    async def _embed(self, texts: list[str], task_type: str) -> list[list[float]]:
        if not self._api_key:
            raise EmbeddingError("No GEMINI_API_KEY is set.")
        client = genai.Client(
            api_key=self._api_key,
            http_options=types.HttpOptions(
                retry_options=types.HttpRetryOptions(attempts=1),
                httpx_async_client=self._http_client,
            ),
        )
        contents = [types.Content(parts=[types.Part(text=text)]) for text in texts]
        config = types.EmbedContentConfig(
            task_type=task_type, output_dimensionality=EMBEDDING_DIMENSIONS
        )
        for attempt in range(1, self._attempts + 1):
            try:
                response = await client.aio.models.embed_content(
                    model=self._model, contents=contents, config=config
                )
            except errors.APIError as exc:
                if exc.code not in _RETRYABLE or attempt == self._attempts:
                    raise EmbeddingError(f"Gemini embeddings failed ({exc.code}).") from exc
                # 2, 4, 8 ... seconds: the free tier's limits are per minute.
                logger.info("Embeddings: %s, retrying (attempt %d)", exc.code, attempt)
                await self._sleep(2.0**attempt)
                continue
            except httpx2.HTTPError as exc:
                raise EmbeddingError("Gemini embeddings could not be reached.") from exc
            return _vectors(response, len(texts))
        raise EmbeddingError("Gemini embeddings failed.")  # not reached; keeps mypy content


def _vectors(response: types.EmbedContentResponse, count: int) -> list[list[float]]:
    embeddings = response.embeddings or []
    vectors = [list(e.values or []) for e in embeddings]
    if len(vectors) != count or any(len(v) != EMBEDDING_DIMENSIONS for v in vectors):
        raise EmbeddingError("Gemini returned embeddings of an unexpected count or size.")
    return vectors


class FakeEmbedder:
    """Repeatable vectors for tests: each word adds weight to a few fixed places, so texts that
    share words land close together. No network."""

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """One vector per text."""
        return [_bag_of_words(text) for text in texts]

    async def embed_query(self, text: str) -> list[float]:
        """The vector for one question."""
        return _bag_of_words(text)


# Words too common to say what a text is about; the fake ignores them, as a real model in effect
# does, so "What is the sales tax on cars?" doesn't look like every passage with "is" and "tax".
_FILLER = frozenset(
    "a an and any at by do does for from i in is it its my of on or the this to under what "
    "when where which who with tax taxes".split()
)


def _bag_of_words(text: str) -> list[float]:
    vector = [0.0] * EMBEDDING_DIMENSIONS
    for word in re.findall(r"[a-z0-9]+", text.lower()):
        if word in _FILLER:
            continue
        digest = hashlib.sha256(word.encode()).digest()
        vector[int.from_bytes(digest[:4], "big") % EMBEDDING_DIMENSIONS] += 1.0
    norm = math.sqrt(sum(x * x for x in vector)) or 1.0
    return [x / norm for x in vector] if any(vector) else [1.0] + [0.0] * (EMBEDDING_DIMENSIONS - 1)
