"""Scoring the extraction eval (feature 003, task T025; contracts/eval.md, SC-003, SC-004).

A field is correct when its normalised value equals the ground truth exactly; "not found" is
correct only when the truth is absent. Ratios are exact fractions, so a bar is met or missed
without rounding doubts.
"""

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from fractions import Fraction

# SC-003 and SC-004.
BARS = {
    "pdf": Fraction(95, 100),
    "photo": Fraction(90, 100),
    # Read literally: of all wrong values, at most 2% may be marked high confidence.
    "wrong_high": Fraction(2, 100),
}

# What the app reported for each field: (normalised value as text or None, confidence).
Reported = Mapping[str, tuple[str | None, str]]


@dataclass(frozen=True)
class Case:
    """One generated certificate and the figures printed on it."""

    id: str
    file: str
    doc_type: str
    # "pdf" (clean) or "photo" (photo-like JPG).
    variant: str
    layout: str
    # Normalised as the app stores them ("1800000.00", "2025-26"); None if not printed.
    truth: Mapping[str, str | None]


@dataclass(frozen=True)
class FieldScore:
    """Whether one field of one case was read correctly, and how sure the app said it was."""

    case: Case
    field: str
    correct: bool
    confidence: str


def score_case(case: Case, reported: Reported | None) -> list[FieldScore]:
    """Score every field of a case; a failed extraction (None) makes every field wrong."""
    scores = []
    for field, truth in case.truth.items():
        value, confidence = (reported or {}).get(field, (None, "low"))
        correct = reported is not None and value == truth
        scores.append(FieldScore(case=case, field=field, correct=correct, confidence=confidence))
    return scores


@dataclass(frozen=True)
class Summary:
    """Accuracy by variant, field and layout, and the wrong-but-high share."""

    accuracy: Mapping[str, Fraction]
    per_field: Mapping[str, Fraction]
    per_layout: Mapping[str, Fraction]
    wrong_high_share: Fraction
    wrong: int
    total: int

    @property
    def passed(self) -> bool:
        """True when every bar in contracts/eval.md is met."""
        return (
            self.accuracy.get("pdf", Fraction(0)) >= BARS["pdf"]
            and self.accuracy.get("photo", Fraction(0)) >= BARS["photo"]
            and self.wrong_high_share <= BARS["wrong_high"]
        )


def _ratio(scores: Iterable[FieldScore], key: str) -> dict[str, Fraction]:
    right: defaultdict[str, int] = defaultdict(int)
    total: defaultdict[str, int] = defaultdict(int)
    for score in scores:
        group = score.field if key == "field" else getattr(score.case, key)
        total[group] += 1
        right[group] += score.correct
    return {group: Fraction(right[group], total[group]) for group in sorted(total)}


def summarise(scores: list[FieldScore]) -> Summary:
    """The eval's measures for the whole run."""
    wrong = [s for s in scores if not s.correct]
    high = sum(s.confidence == "high" for s in wrong)
    return Summary(
        accuracy=_ratio(scores, "variant"),
        per_field=_ratio(scores, "field"),
        per_layout=_ratio(scores, "layout"),
        wrong_high_share=Fraction(high, len(wrong)) if wrong else Fraction(0),
        wrong=len(wrong),
        total=len(scores),
    )


def _percent(value: Fraction) -> str:
    return f"{float(value) * 100:.1f}%"


def render(summary: Summary, model: str, tokens: Mapping[str, int]) -> str:
    """The report as Markdown, for report.md and the PR description (research R7)."""
    tick = {True: "✅", False: "❌"}
    pdf = summary.accuracy.get("pdf", Fraction(0))
    photo = summary.accuracy.get("photo", Fraction(0))
    lines = [
        f"# Extraction eval: {model}",
        "",
        f"**Result: {'PASS' if summary.passed else 'FAIL'}** "
        f"({summary.total - summary.wrong} of {summary.total} fields correct)",
        "",
        "| Measure | Result | Bar | |",
        "|---|---|---|---|",
        f"| Fields correct, clean PDFs | {_percent(pdf)} | ≥ 95% | {tick[pdf >= BARS['pdf']]} |",
        f"| Fields correct, photos | {_percent(photo)} | ≥ 90% | {tick[photo >= BARS['photo']]} |",
        f"| Wrong values marked high | {_percent(summary.wrong_high_share)} | ≤ 2% | "
        f"{tick[summary.wrong_high_share <= BARS['wrong_high']]} |",
        "",
        "| Field | Correct |",
        "|---|---|",
        *(f"| {field} | {_percent(value)} |" for field, value in summary.per_field.items()),
        "",
        "| Layout | Correct |",
        "|---|---|",
        *(f"| {layout} | {_percent(value)} |" for layout, value in summary.per_layout.items()),
        "",
        f"Tokens: {tokens.get('input', 0):,} input, {tokens.get('output', 0):,} output.",
    ]
    return "\n".join(lines) + "\n"
