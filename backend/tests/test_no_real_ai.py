"""No test may reach the real Gemini API, even with a key in the environment (003 research R8)."""

from app.documents.extraction.client import FakeExtractor
from app.documents.router import get_extractor
from app.main import app
from app.tax.router import get_summariser
from app.tax.summary import FakeSummariser


def test_both_ai_services_are_faked_in_every_test() -> None:
    """Fails if the conftest guard is removed: tests would spend the free quota and depend on
    Google being up."""
    assert isinstance(app.dependency_overrides[get_extractor](), FakeExtractor)
    assert isinstance(app.dependency_overrides[get_summariser](), FakeSummariser)
