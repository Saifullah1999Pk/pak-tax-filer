"""The wealth worked examples are complete and signed off by a human (feature 005, task T004;
FR-015). Named apart from 004's test_sign_off.py: same-named test files collide in pytest.

The reconciliation is tested against these examples, so they must be checked by hand against
FBR's sources first (task T003). test_every_example_is_signed_off fails until that is done.
"""

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

EXAMPLES_FILE = Path(__file__).with_name("worked_examples.yaml")
FIGURES = ("net_assets", "increase", "inflows", "outflows", "unreconciled")
DIRECTIONS = {"reconciled", "inflows_exceed_growth", "growth_exceeds_inflows"}
# specs/005-wealth-statement/research.md R6, in the order they are checked.
NOT_READY_REASONS = {
    "needs_previous_net_assets",
    "no_confirmed_salary_certificate",
    "profit_over_limit",
    "gross_below_taxable",
}


def load_examples() -> list[dict[str, Any]]:
    """Every worked example in the file."""
    data = yaml.safe_load(EXAMPLES_FILE.read_text(encoding="utf-8"))
    examples: list[dict[str, Any]] = data["examples"]
    return examples


EXAMPLES = load_examples()


@pytest.mark.parametrize("example", EXAMPLES, ids=[e["id"] for e in EXAMPLES])
def test_every_example_is_signed_off(example: dict[str, Any]) -> None:
    """Fails until a person has checked this example by hand and signed it (task T003)."""
    assert str(example.get("signed_off_by") or "").strip(), "signed_off_by is empty"
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(example.get("signed_off_date") or "")), (
        "signed_off_date must be YYYY-MM-DD"
    )


@pytest.mark.parametrize("example", EXAMPLES, ids=[e["id"] for e in EXAMPLES])
def test_every_example_is_complete(example: dict[str, Any]) -> None:
    """Fails if an example lacks its working, or a ready one lacks a figure or direction."""
    assert example["working"], "the hand working is missing"
    expected = example["expected"]
    reason = expected["not_ready_reason"]
    if reason is not None:
        assert reason in NOT_READY_REASONS
        assert not set(expected) & {*FIGURES, "direction"}, "a not-ready example has no figures"
        if reason == "gross_below_taxable":
            assert expected["certificate"], "the certificate must be named"
        return
    for figure in FIGURES:
        assert re.fullmatch(r"-?\d+", str(expected[figure])), f"{figure} must be whole rupees"
    assert expected["direction"] in DIRECTIONS


def test_every_not_ready_reason_and_direction_has_an_example() -> None:
    """Fails if a not-ready reason or a direction has no worked example (FR-015)."""
    reasons = {e["expected"]["not_ready_reason"] for e in EXAMPLES}
    directions = {e["expected"].get("direction") for e in EXAMPLES}
    assert NOT_READY_REASONS <= reasons
    assert DIRECTIONS <= directions
