"""No test may reach the real Gemini API, even with a key in the environment (003 research R8)."""

from app.documents.extraction.client import FakeExtractor
from app.documents.router import get_extractor
from app.main import app
from app.rag.answer import FakeAnswerer
from app.rag.embed import FakeEmbedder
from app.rag.router import get_answerer, get_embedder
from app.tax.router import get_summariser
from app.tax.summary import FakeSummariser
from app.wealth.router import get_wealth_summariser


def test_every_ai_service_is_faked_in_every_test() -> None:
    """Fails if the conftest guard is removed: tests would spend the free quota and depend on
    Google being up."""
    assert isinstance(app.dependency_overrides[get_extractor](), FakeExtractor)
    assert isinstance(app.dependency_overrides[get_summariser](), FakeSummariser)
    assert isinstance(app.dependency_overrides[get_wealth_summariser](), FakeSummariser)
    assert isinstance(app.dependency_overrides[get_embedder](), FakeEmbedder)
    assert isinstance(app.dependency_overrides[get_answerer](), FakeAnswerer)
