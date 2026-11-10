"""Not ready: a reason and no figures at all (feature 005, task T019; research R6, FR-011).

Driven by the signed-off not-ready worked examples, which include their check order.
"""

from typing import Any

import pytest
from wealth_examples import EXAMPLES, run

NOT_READY = [e for e in EXAMPLES if e["expected"]["not_ready_reason"] is not None]
FIGURES = ("net_assets", "increase", "inflows", "outflows", "unreconciled", "direction")


@pytest.mark.parametrize("example", NOT_READY, ids=[e["id"] for e in NOT_READY])
def test_a_not_ready_statement_gives_its_reason_and_no_figures(example: dict[str, Any]) -> None:
    """Fails if a statement that can't be reconciled shows any figure, or the wrong reason."""
    result = run(example)

    assert result.not_ready_reason == example["expected"]["not_ready_reason"]
    assert all(getattr(result, figure) is None for figure in FIGURES)
    assert result.certificate == example["expected"].get("certificate")
    assert result.message  # what to do, in words (FR-011)
    if result.certificate:
        assert result.message.startswith(result.certificate)  # the certificate is named
    assert not result.steps and not result.where_to_look
