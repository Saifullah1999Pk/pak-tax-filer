"""The eval's synthetic cases (feature 003, task T026; research R6, contracts/eval.md)."""

# pytest fixtures receive other fixtures by name.
# pylint: disable=redefined-outer-name

import random
from collections import Counter
from pathlib import Path

import pytest
from evals.extraction.generate import (
    BANK,
    CASES_PER_TYPE,
    SALARY,
    SEED,
    generate,
    load_cases,
    make_certificate,
    text_lines,
)
from evals.extraction.scoring import Case

from app.documents.uploads import check_file


@pytest.fixture(scope="module")
def generated(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, list[Case]]:
    """The 80 cases, generated once for this file (it takes a few seconds)."""
    out = tmp_path_factory.mktemp("cases")
    return out, generate(out)


def test_eighty_cases_with_four_layouts_per_type(generated: tuple[Path, list[Case]]) -> None:
    """Fails if the set isn't 20 per type x {PDF, photo}, with at least 4 layouts per type."""
    out, cases = generated

    assert len(cases) == 80
    assert Counter((c.doc_type, c.variant) for c in cases) == {
        ("salary_certificate", "pdf"): 20,
        ("salary_certificate", "photo"): 20,
        ("bank_profit_certificate", "pdf"): 20,
        ("bank_profit_certificate", "photo"): 20,
    }
    for doc_type in ("salary_certificate", "bank_profit_certificate"):
        assert len({c.layout for c in cases if c.doc_type == doc_type}) >= 4
    assert load_cases(out) == cases


def test_every_file_passes_the_apps_upload_checks(generated: tuple[Path, list[Case]]) -> None:
    """Fails if a generated file would be refused before reaching the AI."""
    out, cases = generated
    for case in cases:
        checked = check_file(case.file, (out / case.file).read_bytes())
        assert checked.media_type == ("application/pdf" if case.variant == "pdf" else "image/jpeg")


def test_truth_includes_missing_figures(generated: tuple[Path, list[Case]]) -> None:
    """Fails if no case leaves a figure off (then "not found" would never be tested)."""
    missing = [c for c in generated[1] if None in c.truth.values()]

    assert {c.doc_type for c in missing} == {"salary_certificate", "bank_profit_certificate"}


def test_same_seed_gives_the_same_files(generated: tuple[Path, list[Case]], tmp_path: Path) -> None:
    """Fails if two runs differ, so results could change without any code change."""
    first, second = generated[0], tmp_path
    generate(second)

    for path in sorted(first.iterdir()):
        assert path.read_bytes() == (second / path.name).read_bytes(), path.name


def test_every_line_fits_on_the_page() -> None:
    """Fails if a line is too long to fit (a figure cut off at the edge can't be read)."""
    rng = random.Random(SEED)
    for doc_type in (SALARY, BANK):
        for index in range(CASES_PER_TYPE):
            for label, value in text_lines(make_certificate(rng, doc_type, index)):
                assert len(f"{label}: {value}" if label else value) <= 80, value
