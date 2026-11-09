"""Calling Gemini to read a certificate (feature 003, tasks T008 and T036; research R1 and R8).

`Extractor` is the interface the service depends on: `GeminiExtractor` calls Google's Gemini API
(free tier; it replaced Claude on 2026-11-08), `FakeExtractor` returns a recorded result so tests
and CI need no API key. Every failure becomes a short reason for the user; nothing from the
document or the API's error text is logged.
"""

import logging
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Protocol

import httpx2
from google import genai
from google.genai import errors, types
from pydantic import ValidationError

from app.documents.extraction.prompt import SYSTEM_PROMPT, user_instruction
from app.documents.extraction.schemas import OUTPUT_SCHEMAS, ExtractedValue
from app.documents.models import DocType

logger = logging.getLogger(__name__)

TIMEOUT_MS = 60_000
# Brief Google outages (500, 502, 503: common on the free tier) are retried: 3 attempts in all,
# a second or two apart. 504 (the 60-second deadline) and 429 (the free limit) are not.
RETRY = types.HttpRetryOptions(
    attempts=3, initial_delay=1.0, max_delay=4.0, http_status_codes=[500, 502, 503]
)
# Room for the JSON answer plus a little thinking; the answer itself is a few hundred tokens.
MAX_OUTPUT_TOKENS = 4096
THINKING_LEVELS = {
    "minimal": types.ThinkingLevel.MINIMAL,
    "low": types.ThinkingLevel.LOW,
    "medium": types.ThinkingLevel.MEDIUM,
    "high": types.ThinkingLevel.HIGH,
}
# Finish reasons meaning Gemini declined to answer.
DECLINED = {
    types.FinishReason.SAFETY,
    types.FinishReason.RECITATION,
    types.FinishReason.BLOCKLIST,
    types.FinishReason.PROHIBITED_CONTENT,
    types.FinishReason.SPII,
    types.FinishReason.IMAGE_SAFETY,
    types.FinishReason.IMAGE_PROHIBITED_CONTENT,
}
INCOMPLETE = "The AI's answer was incomplete. Try again."
DOC_LABELS = {
    "salary_certificate": "a salary certificate",
    "bank_profit_certificate": "a bank profit certificate",
}
DECLINED_REASON = "The AI declined to read this document."


@dataclass(frozen=True)
class ExtractionResult:
    """What an extractor found: fields by name, or the reason it failed."""

    fields: Mapping[str, ExtractedValue] = field(default_factory=dict)
    # The model version that answered.
    model: str | None = None
    failure_reason: str | None = None
    # True when the free tier's limit was hit (HTTP 429): the eval waits or stops on it.
    limit_reached: bool = False
    # True when the document isn't the type the user chose (FR-005a): the upload is refused.
    wrong_type: bool = False
    input_tokens: int = 0
    output_tokens: int = 0


def failed(
    reason: str, model: str | None = None, *, limit_reached: bool = False
) -> ExtractionResult:
    """A failed extraction with a short reason for the user."""
    return ExtractionResult(model=model, failure_reason=reason, limit_reached=limit_reached)


class Extractor(Protocol):
    """Reads one certificate's figures."""

    async def extract(self, doc_type: DocType, content: bytes, media_type: str) -> ExtractionResult:
        """Read the figures for `doc_type` from the file's bytes."""


def extraction_config(doc_type: DocType, effort: str) -> types.GenerateContentConfig:
    """The request settings: system prompt, JSON output in the type's schema, thinking level."""
    return types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        response_mime_type="application/json",
        response_json_schema=OUTPUT_SCHEMAS[doc_type].model_json_schema(),
        thinking_config=types.ThinkingConfig(thinking_level=THINKING_LEVELS[effort]),
        max_output_tokens=MAX_OUTPUT_TOKENS,
        http_options=types.HttpOptions(timeout=TIMEOUT_MS),
    )


class GeminiExtractor:
    """Reads certificates with the Gemini API (JSON-schema output, one call per document)."""

    def __init__(
        self,
        *,
        api_key: str | None,
        model: str,
        effort: str,
        client: genai.Client | None = None,
        http_client: httpx2.AsyncClient | None = None,
    ) -> None:
        self._api_key = api_key
        # Lets tests answer in place of Google while keeping the real retry settings.
        self._http_client = http_client
        self._model = model
        # Checked against Gemini's thinking levels when the settings are loaded.
        self._effort = effort
        self._client = client

    def _get_client(self) -> genai.Client:
        if self._client is None:
            self._client = genai.Client(
                api_key=self._api_key,
                http_options=types.HttpOptions(
                    retry_options=RETRY, httpx_async_client=self._http_client
                ),
            )
        return self._client

    async def extract(self, doc_type: DocType, content: bytes, media_type: str) -> ExtractionResult:
        """Send the file and instructions to Gemini and return the parsed fields."""
        if not self._api_key:
            return failed("Extraction isn't available: no AI service key is set up.")
        try:
            response = await self._get_client().aio.models.generate_content(
                model=self._model,
                contents=types.Content(
                    role="user",
                    parts=[
                        types.Part.from_bytes(data=content, mime_type=media_type),
                        types.Part.from_text(text=user_instruction(doc_type)),
                    ],
                ),
                config=extraction_config(doc_type, self._effort),
            )
        except errors.APIError as exc:
            # Only the type and status code are logged: never the document or the API's message.
            logger.warning("Extraction failed: %s %s", type(exc).__name__, exc.code)
            return failed(_api_reason(exc), limit_reached=exc.code == 429)
        except httpx2.TimeoutException:
            logger.warning("Extraction failed: timeout")
            return failed("Reading the document took too long. Try again.")
        except httpx2.TransportError as exc:
            logger.warning("Extraction failed: %s", type(exc).__name__)
            return failed("Couldn't reach the AI service. Try again.")
        return _result_from(doc_type, response, self._model)


def _result_from(
    doc_type: DocType, response: types.GenerateContentResponse, requested_model: str
) -> ExtractionResult:
    """The fields from a reply, or why it can't be used."""
    usage = response.usage_metadata

    def result(
        fields: Mapping[str, ExtractedValue] | None = None,
        reason: str | None = None,
        wrong_type: bool = False,
    ) -> ExtractionResult:
        return ExtractionResult(
            fields=fields or {},
            model=response.model_version or requested_model,
            failure_reason=reason,
            wrong_type=wrong_type,
            input_tokens=(usage.prompt_token_count or 0) if usage else 0,
            output_tokens=(usage.candidates_token_count or 0) if usage else 0,
        )

    if response.prompt_feedback is not None and response.prompt_feedback.block_reason:
        return result(reason=DECLINED_REASON)
    candidate = response.candidates[0] if response.candidates else None
    if candidate is not None and candidate.finish_reason in DECLINED:
        return result(reason=DECLINED_REASON)
    text = response.text
    if candidate is None or candidate.finish_reason == types.FinishReason.MAX_TOKENS or not text:
        return result(reason=INCOMPLETE)
    try:
        parsed = OUTPUT_SCHEMAS[doc_type].model_validate_json(text)
    except ValidationError:
        return result(reason=INCOMPLETE)
    seen = getattr(parsed, "document_type", doc_type.value)
    if seen != doc_type.value:
        return result(reason=_wrong_type_reason(doc_type, seen), wrong_type=True)
    return result(fields={name: v for name, v in parsed if isinstance(v, ExtractedValue)})


def _wrong_type_reason(chosen: DocType, seen: str) -> str:
    """Why a document of another type is refused (FR-005a), naming what it looks like."""
    expected = DOC_LABELS[chosen.value]
    if seen in DOC_LABELS:
        return (
            f"This looks like {DOC_LABELS[seen]}, not {expected}. "
            "Choose the right type and upload it again."
        )
    return f"This doesn't look like {expected}. Check the file and upload it again."


def _api_reason(exc: errors.APIError) -> str:
    """A short, safe reason for an API failure, told apart by status code, not message text."""
    if exc.code == 429:
        return "The free AI limit may be used up for now. Try again later."
    if exc.code in (401, 403):
        return "The AI service didn't accept the app's key."
    if isinstance(exc, errors.ServerError):
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
