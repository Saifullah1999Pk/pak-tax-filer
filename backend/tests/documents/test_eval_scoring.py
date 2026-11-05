"""Scoring the extraction eval (feature 003, task T025; contracts/eval.md, SC-003, SC-004)."""

from fractions import Fraction

from evals.extraction.scoring import Case, score_case, summarise


def case(
    case_id: str = "salary-01-pdf",
    variant: str = "pdf",
    layout: str = "A",
    truth: dict[str, str | None] | None = None,
) -> Case:
    """A ground-truth case (salary certificate unless the truth says otherwise)."""
    return Case(
        id=case_id,
        file=f"{case_id}.pdf",
        doc_type="salary_certificate",
        variant=variant,
        layout=layout,
        truth=truth
        or {
            "tax_year": "2025-26",
            "gross_salary": "1800000.00",
            "taxable_salary": "1700000.00",
            "tax_deducted": "95000.00",
        },
    )


ALL_RIGHT = {
    "tax_year": ("2025-26", "high"),
    "gross_salary": ("1800000.00", "high"),
    "taxable_salary": ("1700000.00", "high"),
    "tax_deducted": ("95000.00", "high"),
}


def test_exact_normalised_match_is_correct() -> None:
    """Fails if a value equal to the truth after normalising isn't counted correct."""
    scores = score_case(case(), ALL_RIGHT)

    assert all(s.correct for s in scores)
    assert len(scores) == 4


def test_different_value_is_wrong() -> None:
    """Fails if a value off by anything counts as correct."""
    scores = score_case(case(), {**ALL_RIGHT, "gross_salary": ("1800000.01", "high")})

    assert [s.field for s in scores if not s.correct] == ["gross_salary"]


def test_not_found_is_correct_only_when_the_truth_is_absent() -> None:
    """Fails if "not found" is rewarded when the figure was printed, or punished when it wasn't."""
    absent = case(truth={**case().truth, "tax_deducted": None})
    missed = {**ALL_RIGHT, "tax_deducted": (None, "low")}

    assert all(s.correct for s in score_case(absent, missed))
    assert not next(s for s in score_case(case(), missed) if s.field == "tax_deducted").correct


def test_inventing_a_value_that_is_not_printed_is_wrong() -> None:
    """Fails if a value reported for a figure that isn't on the document counts as correct."""
    absent = case(truth={**case().truth, "tax_deducted": None})

    scores = score_case(absent, ALL_RIGHT)

    assert not next(s for s in scores if s.field == "tax_deducted").correct


def test_failed_extraction_makes_every_field_wrong() -> None:
    """Fails if a refused or errored case is skipped instead of counted wrong."""
    assert not any(s.correct for s in score_case(case(), None))


def test_accuracy_per_variant_field_and_layout() -> None:
    """Fails if accuracy isn't split by clean PDF vs photo, by field and by layout."""
    scores = [
        *score_case(case("a", "pdf", "A"), ALL_RIGHT),
        *score_case(case("b", "photo", "B"), {**ALL_RIGHT, "gross_salary": ("1", "low")}),
    ]

    summary = summarise(scores)

    assert summary.accuracy["pdf"] == Fraction(4, 4)
    assert summary.accuracy["photo"] == Fraction(3, 4)
    assert summary.per_field["gross_salary"] == Fraction(1, 2)
    assert summary.per_field["tax_year"] == Fraction(2, 2)
    assert summary.per_layout["B"] == Fraction(3, 4)


def test_wrong_but_high_share_is_among_wrong_values() -> None:
    """Fails if SC-004's share isn't "wrong values marked high" over all wrong values."""
    reported = {
        **ALL_RIGHT,
        "gross_salary": ("1", "high"),
        "taxable_salary": ("2", "low"),
        "tax_deducted": ("3", "medium"),
    }

    summary = summarise(score_case(case(), reported))

    assert summary.wrong_high_share == Fraction(1, 3)


def test_no_wrong_values_means_no_wrong_high_share() -> None:
    """Fails if a perfect run divides by zero or reports a share."""
    assert summarise(score_case(case(), ALL_RIGHT)).wrong_high_share == 0


def scores_with(pdf_right: int, photo_right: int, wrong_high: int, wrong: int) -> list:  # type: ignore[type-arg]
    """100 PDF fields and 100 photo fields with the given counts right; `wrong_high` of the
    wrong ones are marked high."""
    scores = []
    high_left = wrong_high
    for variant, right in (("pdf", pdf_right), ("photo", photo_right)):
        for index in range(25):
            reported = dict(ALL_RIGHT)
            for field_index, name in enumerate(ALL_RIGHT):
                if index * 4 + field_index >= right:
                    confidence = "high" if high_left > 0 else "low"
                    high_left -= confidence == "high"
                    reported[name] = ("0.01", confidence)
            scores += score_case(case(f"{variant}{index}", variant), reported)
    assert sum(not s.correct for s in scores) == wrong
    return scores


def test_bars_pass_exactly_at_the_limits() -> None:
    """Fails if 95% PDFs, 90% photos and 2% wrong-but-high don't pass (SC-003, SC-004)."""
    summary = summarise(scores_with(pdf_right=95, photo_right=90, wrong_high=0, wrong=15))

    assert summary.passed


def test_bars_fail_just_below_the_limits() -> None:
    """Fails if 94% on PDFs, 89% on photos, or too many wrong-but-high values pass."""
    assert not summarise(scores_with(94, 100, 0, 6)).passed
    assert not summarise(scores_with(100, 89, 0, 11)).passed
    assert not summarise(scores_with(95, 90, 1, 15)).passed  # 1 of 15 wrong is high: 6.7%
