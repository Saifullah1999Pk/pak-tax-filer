"""require_profile: later features refuse users without a profile (task T036, FR-022, R14)."""

from typing import Annotated

import pytest
from fastapi import Depends, FastAPI
from httpx2 import AsyncClient

from app.profile.dependencies import require_profile
from app.profile.models import TaxpayerProfile

pytestmark = pytest.mark.anyio


def add_test_route(app: FastAPI) -> None:
    """A stand-in for a later feature's endpoint that needs a profile."""

    @app.get("/test-only/needs-profile")
    async def needs_profile(
        profile: Annotated[TaxpayerProfile, Depends(require_profile)],
    ) -> dict[str, str]:
        return {"tax_year": profile.tax_year}


@pytest.fixture(autouse=True)
def test_route() -> None:
    """Register the stand-in route on the app once."""
    from app.main import app  # pylint: disable=import-outside-toplevel

    if not any(getattr(r, "path", "") == "/test-only/needs-profile" for r in app.routes):
        add_test_route(app)


@pytest.mark.usefixtures("logged_in_user")
async def test_without_a_profile_the_request_is_refused(client: AsyncClient) -> None:
    """Fails if a feature that needs the profile can run without one."""
    response = await client.get("/test-only/needs-profile")

    assert response.status_code == 409
    assert response.json() == {"detail": "Set up your profile first."}


@pytest.mark.usefixtures("logged_in_user")
async def test_with_a_profile_the_endpoint_receives_it(client: AsyncClient) -> None:
    """Fails if the saved profile isn't handed to the endpoint."""
    await client.put("/api/profile", json={"tax_year": "2025-26", "on_atl": True})

    response = await client.get("/test-only/needs-profile")

    assert response.status_code == 200
    assert response.json() == {"tax_year": "2025-26"}
