"""Calling Claude to read a certificate (feature 003, task T008, research R1 and R8).

`Extractor` is the interface the service depends on: `ClaudeExtractor` calls the real API,
`FakeExtractor` returns a recorded result so tests and CI need no API key. Every failure becomes
a short reason for the user; nothing from the document or the API's error text is logged.
"""

import base64
import logging
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal, Protocol, cast

import anthropic
from anthropic import AsyncAnthropic
from anthropic.types.beta import BetaContentBlockParam

from app.documents.extraction.prompt import SYSTEM_PROMPT, user_instruction
from app.documents.extraction.schemas import OUTPUT_SCHEMAS, ExtractedValue
from app.documents.models import DocType

logger = logging.getLogger(__name__)

# Server-side refusal fallback (research R1): a declined request is re-run on Anthropic's
# recommended fallback model inside the same call.
FALLBACK_BETA = "server-side-fallback-2026-07-01"
TIMEOUT_SECONDS = 60.0
MAX_TOKENS = 2048

Effort = Literal["low", "medium", "high", "xhigh", "max"]


@dataclass(frozen=True)
class ExtractionResult:
    """What an extractor found: fields by name, or the reason it failed."""

    fields: Mapping[str, ExtractedValue] = field(default_factory=dict)
    # The model that actually answered (a fallback model if the first one declined).
    model: str | None = None
    failure_reason: str | None = None


def failed(reason: str, model: str | None = None) -> ExtractionResult:
    """A failed extraction with a short reason for the user."""
    return ExtractionResult(model=model, failure_reason=reason)


class Extractor(Protocol):
    """Reads one certificate's figures."""

    async def extract(self, doc_type: DocType, content: bytes, media_type: str) -> ExtractionResult:
        """Read the figures for `doc_type` from the file's bytes."""


def _file_block(content: bytes, media_type: str) -> BetaContentBlockParam:
    """The PDF as a document block, or the photo as an image block."""
    data = base64.standard_b64encode(content).decode()
    if media_type == "application/pdf":
        return {
            "type": "document",
            "source": {"type": "base64", "media_type": "application/pdf", "data": data},
        }
    image_type = cast(Literal["image/jpeg", "image/png"], media_type)
    return {"type": "image", "source": {"type": "base64", "media_type": image_type, "data": data}}


class ClaudeExtractor:
    """Reads certificates with the Claude API (structured output, one call per document)."""

    def __init__(
        self,
        *,
        api_key: str | None,
        model: str,
        effort: str,
        client: AsyncAnthropic | None = None,
    ) -> None:
        self._api_key = api_key
        self._model = model
        # Checked against the API's values when the settings are loaded.
        self._effort = cast(Effort, effort)
        self._client = client

    def _get_client(self) -> AsyncAnthropic:
        if self._client is None:
            self._client = AsyncAnthropic(api_key=self._api_key, timeout=TIMEOUT_SECONDS)
        return self._client

    async def extract(self, doc_type: DocType, content: bytes, media_type: str) -> ExtractionResult:
        """Send the file and instructions to Claude and return the parsed fields."""
        if not self._api_key:
            return failed("Extraction isn't available: no AI service key is set up.")
        try:
            message = await self._get_client().beta.messages.parse(
                model=self._model,
                max_tokens=MAX_TOKENS,
                system=SYSTEM_PROMPT,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            _file_block(content, media_type),
                            {"type": "text", "text": user_instruction(doc_type)},
                        ],
                    }
                ],
                output_format=OUTPUT_SCHEMAS[doc_type],
                output_config={"effort": self._effort},
                fallbacks="default",
                betas=[FALLBACK_BETA],
                timeout=TIMEOUT_SECONDS,
            )
        except anthropic.APIError as exc:
            # Only the exception type is logged: never the document or the API's message.
            logger.warning("Extraction failed: %s", type(exc).__name__)
            return failed(_reason_for(exc))
        except ValueError:
            # The reply couldn't be parsed into the schema (e.g. a refusal with no JSON).
            return failed("The AI's answer was incomplete. Try again.")

        if message.stop_reason == "refusal":
            return failed("The AI declined to read this document.", message.model)
        parsed = message.parsed_output
        if message.stop_reason == "max_tokens" or parsed is None:
            return failed("The AI's answer was incomplete. Try again.", message.model)
        fields = {name: value for name, value in parsed if isinstance(value, ExtractedValue)}
        return ExtractionResult(fields=fields, model=message.model)


def _reason_for(exc: anthropic.APIError) -> str:
    """A short, safe reason for an API failure (typed exceptions, most specific first)."""
    if isinstance(exc, anthropic.RateLimitError):
        return "The AI service is busy. Try again in a minute."
    if isinstance(exc, anthropic.APITimeoutError):
        return "Reading the document took too long. Try again."
    if isinstance(exc, anthropic.APIConnectionError):
        return "Couldn't reach the AI service. Try again."
    if isinstance(exc, (anthropic.AuthenticationError, anthropic.PermissionDeniedError)):
        return "The AI service didn't accept the app's key."
    if isinstance(exc, anthropic.APIStatusError) and exc.status_code >= 500:
        return "The AI service had a problem. Try again."
    return "The AI service couldn't read this file."


class FakeExtractor:
    """Returns a recorded result instead of calling the API (tests and CI, research R8)."""

    def __init__(self, result: ExtractionResult) -> None:
        self.result = result
        self.calls: list[tuple[DocType, str]] = []

    async def extract(self, doc_type: DocType, content: bytes, media_type: str) -> ExtractionResult:
        """Record the call and return the recorded result."""
        del content  # Not needed: the result is fixed.
        self.calls.append((doc_type, media_type))
        return self.result
