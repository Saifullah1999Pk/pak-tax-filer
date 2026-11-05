"""FastAPI application entry point (uvicorn app.main:app)."""

from fastapi import FastAPI

from app.auth.router import router as auth_router
from app.profile.router import router as profile_router

app = FastAPI(title="pak-tax-filer")
app.include_router(auth_router)
app.include_router(profile_router)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness check: specs/001-repo-foundations/contracts/health.md (spec FR-003)."""
    return {"status": "ok"}
