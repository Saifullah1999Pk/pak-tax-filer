"""Configuration from environment variables (feature 002, research R2; feature 003, R1/R4).

Values are never written in code or committed files: docker-compose.yml sets them for local
development, and CI sets them for tests.
"""

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

_TRUE = {"true", "1", "yes"}
_FALSE = {"false", "0", "no"}
# The thinking levels Gemini accepts (google-genai ThinkingLevel), lower-cased.
_EFFORTS = ("minimal", "low", "medium", "high")


@dataclass(frozen=True)
class Settings:
    """The app's settings; read once per process with get_settings()."""

    database_url: str
    # Send the session cookie over HTTPS only. On unless explicitly turned off, so a missing
    # setting fails safe; only local development over plain HTTP sets COOKIE_SECURE=false.
    cookie_secure: bool
    # Gemini API key (free, from AI Studio) for document extraction. Optional, so tests and CI
    # (fake extractor) run without one; extraction then fails with a clear reason. Kept out of
    # repr so printing or logging the settings never reveals it.
    gemini_api_key: str | None = field(default=None, repr=False)
    # Research R1: Flash-Lite passed the eval (T029); Flash timed out on the free tier.
    extraction_model: str = "gemini-3.5-flash-lite"
    extraction_effort: str = "low"
    # Research R4: uploaded files live in a Docker volume, never under the app's own folder.
    upload_dir: Path = Path("/data/uploads")


def load_settings(environ: Mapping[str, str]) -> Settings:
    """Build Settings from an environment mapping, refusing missing or unclear values."""
    database_url = environ.get("DATABASE_URL", "")
    if not database_url:
        raise ValueError("DATABASE_URL is not set; docker-compose.yml sets it for the backend.")

    raw = environ.get("COOKIE_SECURE", "true").strip().lower()
    if raw in _TRUE:
        cookie_secure = True
    elif raw in _FALSE:
        cookie_secure = False
    else:
        raise ValueError(f"COOKIE_SECURE must be true or false, not {raw!r}.")

    effort = environ.get("EXTRACTION_EFFORT", "low").strip().lower()
    if effort not in _EFFORTS:
        raise ValueError(f"EXTRACTION_EFFORT must be one of {', '.join(_EFFORTS)}, not {effort!r}.")

    return Settings(
        database_url=database_url,
        cookie_secure=cookie_secure,
        gemini_api_key=environ.get("GEMINI_API_KEY", "").strip() or None,
        extraction_model=environ.get("EXTRACTION_MODEL", "").strip() or "gemini-3.5-flash-lite",
        extraction_effort=effort,
        upload_dir=Path(environ.get("UPLOAD_DIR", "").strip() or "/data/uploads"),
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """The process's settings, read from os.environ on first use."""
    return load_settings(os.environ)


# The tax years the app can calculate: the one list the profile offers (FR-017, research R13).
# A year is added here only together with its FBR rates (feature 004 tests that each has them).
SUPPORTED_TAX_YEARS: tuple[str, ...] = ("2025-26",)
