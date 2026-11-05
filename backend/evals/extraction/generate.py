"""Generate the synthetic eval cases (feature 003, task T026, research R6, contracts/eval.md).

    docker compose exec backend python -m evals.extraction.generate

Writes 20 cases per certificate type, each as a clean PDF and a photo-like JPG (80 files), plus
ground_truth.json, to evals/extraction/cases/ (git-ignored). A fixed seed gives the same files
every time. Everything is synthetic: names and CNICs are obviously fake (Principle V).
"""

import argparse
import json
import random
import textwrap
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from decimal import Decimal
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen.canvas import Canvas

from evals.extraction.scoring import Case

SEED = 2026
CASES_PER_TYPE = 20
OUT_DIR = Path(__file__).parent / "cases"
TAX_YEAR = "2025-26"

SALARY = "salary_certificate"
BANK = "bank_profit_certificate"


@dataclass(frozen=True)
class Layout:
    """How one issuer prints its certificate: title, label wording and arrangement."""

    id: str
    title: str
    labels: dict[str, str]
    # "lines" (label: value), "table" (two columns) or "prose" (one sentence).
    style: str


LAYOUTS = {
    SALARY: [
        Layout(
            "S1",
            "SALARY CERTIFICATE",
            {
                "tax_year": "Tax Year",
                "gross_salary": "Gross Salary",
                "taxable_salary": "Taxable Salary",
                "tax_deducted": "Income Tax Deducted",
            },
            "lines",
        ),
        Layout(
            "S2",
            "CERTIFICATE OF SALARY AND TAX DEDUCTION",
            {
                "tax_year": "Period",
                "gross_salary": "Total Emoluments",
                "taxable_salary": "Taxable Income",
                "tax_deducted": "Tax Withheld u/s 149",
            },
            "table",
        ),
        Layout(
            "S3",
            "TO WHOM IT MAY CONCERN",
            {
                "tax_year": "tax year",
                "gross_salary": "gross salary",
                "taxable_salary": "chargeable to tax",
                "tax_deducted": "income tax deducted",
            },
            "prose",
        ),
        Layout(
            "S4",
            "ANNUAL SALARY STATEMENT",
            {
                "tax_year": "TY",
                "gross_salary": "Annual Salary",
                "taxable_salary": "Taxable Amount",
                "tax_deducted": "Tax Deducted",
            },
            "table",
        ),
    ],
    BANK: [
        Layout(
            "B1",
            "PROFIT CERTIFICATE",
            {
                "tax_year": "Tax Year",
                "profit_amount": "Gross Profit Paid",
                "tax_withheld": "Tax Withheld u/s 151",
            },
            "lines",
        ),
        Layout(
            "B2",
            "WITHHOLDING TAX CERTIFICATE",
            {
                "tax_year": "Period",
                "profit_amount": "Profit on Debt",
                "tax_withheld": "Withholding Tax",
            },
            "table",
        ),
        Layout(
            "B3",
            "TO WHOM IT MAY CONCERN",
            {
                "tax_year": "tax year",
                "profit_amount": "profit",
                "tax_withheld": "tax withheld under section 151",
            },
            "prose",
        ),
        Layout(
            "B4",
            "STATEMENT OF PROFIT PAID",
            {
                "tax_year": "TY",
                "profit_amount": "Total Profit Credited",
                "tax_withheld": "Income Tax Deducted",
            },
            "table",
        ),
    ],
}

# Ways certificates print the same amount and the same tax year.
AMOUNT_FORMATS: list[Callable[[Decimal], str]] = [
    lambda a: f"{a:,.0f}",
    lambda a: f"Rs. {a:,.0f}/-",
    lambda a: f"PKR {a:,.2f}",
    lambda a: _lakh(a),
]
TAX_YEAR_FORMATS = ["2025-26", "Tax Year 2026", "2025-2026", "2025/26"]


def _lakh(amount: Decimal) -> str:
    """South Asian grouping: 18,00,000."""
    digits = f"{amount:.0f}"
    head, tail = digits[:-3], digits[-3:]
    groups: list[str] = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    return ",".join([*groups, tail]) if groups else tail


@dataclass(frozen=True)
class Certificate:
    """One case: what is printed (text) and the truth the app should extract."""

    case_id: str
    doc_type: str
    layout: Layout
    printed: dict[str, str | None]
    truth: dict[str, str | None]
    distractors: list[tuple[str, str]]


def _amounts(rng: random.Random, doc_type: str) -> dict[str, Decimal]:
    if doc_type == SALARY:
        gross = Decimal(rng.randrange(600, 9000) * 1000)
        taxable = gross - Decimal(rng.randrange(0, 10)) * gross / 100
        deducted = (taxable * Decimal(rng.randrange(1, 15)) / 100).quantize(Decimal("1"))
        return {
            "gross_salary": gross,
            "taxable_salary": taxable.quantize(Decimal("1")),
            "tax_deducted": deducted,
        }
    profit = Decimal(rng.randrange(10, 2000) * 1000 + rng.randrange(0, 1000))
    return {"profit_amount": profit, "tax_withheld": (profit / 5).quantize(Decimal("1"))}


def make_certificate(rng: random.Random, doc_type: str, index: int) -> Certificate:
    """A case's printed values and truth; some miss a figure or break a rule on purpose."""
    layout = LAYOUTS[doc_type][index % 4]
    amounts = _amounts(rng, doc_type)
    last_field = list(amounts)[-1]
    if index == CASES_PER_TYPE - 1:
        # Breaks a rule (tax above the amount it is tax on); the AI must still copy it as printed.
        amounts[last_field] = amounts[list(amounts)[0]] + 1000
    fmt = AMOUNT_FORMATS[index % len(AMOUNT_FORMATS)]
    printed: dict[str, str | None] = {"tax_year": TAX_YEAR_FORMATS[index % 4]}
    truth: dict[str, str | None] = {"tax_year": TAX_YEAR}
    for name, amount in amounts.items():
        missing = name == last_field and index in (CASES_PER_TYPE - 3, CASES_PER_TYPE - 2)
        printed[name] = None if missing else fmt(amount)
        truth[name] = None if missing else f"{amount:.2f}"
    number = f"{index + 1:02d}"
    distractors = [("Name", f"Demo Person {number}"), ("CNIC", "00000-0000000-0 (synthetic)")]
    if doc_type == SALARY:
        distractors += [
            ("Allowances", fmt(Decimal(rng.randrange(10, 300) * 1000))),
            ("Net Salary Paid", fmt(Decimal(rng.randrange(500, 8000) * 1000))),
        ]
    else:
        distractors += [
            ("Account", "PK00 SYNT 0000 0000 0000 0000"),
            ("Closing Balance", fmt(Decimal(rng.randrange(100, 9000) * 1000))),
        ]
    return Certificate(
        f"{'salary' if doc_type == SALARY else 'bank'}-{number}",
        doc_type,
        layout,
        printed,
        truth,
        distractors,
    )


def text_lines(cert: Certificate) -> list[tuple[str, str]]:
    """What the certificate says, as (label, value) rows; prose is one row with no label."""
    labels = cert.layout.labels
    found = [(labels[name], value) for name, value in cert.printed.items() if value is not None]
    if cert.layout.style != "prose":
        return [*cert.distractors[:2], *found, *cert.distractors[2:]]
    values = {name: value for name, value in cert.printed.items() if value is not None}
    words = [f"For the {labels['tax_year']} {values['tax_year']}"]
    for name, value in values.items():
        if name != "tax_year":
            words.append(f"{labels[name]}: {value}")
    sentences = [
        f"This is to certify that {cert.distractors[0][1]} (CNIC {cert.distractors[1][1]}).",
        "; ".join(words) + ".",
        *(f"{label}: {value}." for label, value in cert.distractors[2:]),
    ]
    # Wrapped so every figure stays on the page, in the PDF and in the photo.
    return [("", line) for sentence in sentences for line in textwrap.wrap(sentence, 75)]


def write_pdf(cert: Certificate, path: Path) -> None:
    """A clean, text-based PDF; `invariant` keeps the bytes the same on every run."""
    canvas = Canvas(str(path), pagesize=A4, invariant=1)
    width, height = A4
    canvas.setFont("Helvetica-Bold", 15)
    canvas.drawString(60, height - 80, cert.layout.title)
    canvas.setFont("Helvetica", 11)
    y = height - 130
    for label, value in text_lines(cert):
        if not label:
            canvas.drawString(60, y, value)
        elif cert.layout.style == "table":
            canvas.rect(60, y - 6, width - 120, 22)
            canvas.drawString(68, y, label)
            canvas.drawRightString(width - 68, y, value)
        else:
            canvas.drawString(60, y, f"{label}: {value}")
        y -= 28
    canvas.setFont("Helvetica-Oblique", 9)
    canvas.drawString(60, 60, "Synthetic test document for pak-tax-filer. Not a real certificate.")
    canvas.save()


def write_photo(cert: Certificate, path: Path, rng: random.Random) -> None:
    """The same certificate as a phone photo: drawn, then rotated, blurred, unevenly lit."""
    page = Image.new("RGB", (1240, 1754), "white")
    draw = ImageDraw.Draw(page)
    title = ImageFont.load_default(size=34)
    body = ImageFont.load_default(size=24)
    draw.text((110, 140), cert.layout.title, fill="black", font=title)
    y = 240
    for label, value in text_lines(cert):
        if not label:
            draw.text((110, y), value, fill="black", font=body)
        elif cert.layout.style == "table":
            draw.rectangle((110, y - 10, 1130, y + 36), outline="black", width=2)
            draw.text((126, y), label, fill="black", font=body)
            draw.text((1114, y), value, fill="black", font=body, anchor="ra")
        else:
            draw.text((110, y), f"{label}: {value}", fill="black", font=body)
        y += 56
    photo = page.rotate(rng.uniform(-3, 3), expand=True, fillcolor=(90, 90, 90))
    photo = photo.filter(ImageFilter.GaussianBlur(rng.uniform(0.6, 1.4)))
    shade = Image.linear_gradient("L").resize(photo.size).point(lambda v: 150 + v * 105 // 255)
    photo = Image.composite(photo, Image.new("RGB", photo.size, (40, 40, 40)), shade)
    photo.save(path, format="JPEG", quality=rng.randrange(55, 75))


def generate(out_dir: Path = OUT_DIR, seed: int = SEED) -> list[Case]:
    """Write every case's files and ground_truth.json; return the cases."""
    rng = random.Random(seed)
    out_dir.mkdir(parents=True, exist_ok=True)
    cases = []
    for doc_type in (SALARY, BANK):
        for index in range(CASES_PER_TYPE):
            cert = make_certificate(rng, doc_type, index)
            for variant, suffix in (("pdf", "pdf"), ("photo", "jpg")):
                file = f"{cert.case_id}-{variant}.{suffix}"
                if variant == "pdf":
                    write_pdf(cert, out_dir / file)
                else:
                    write_photo(cert, out_dir / file, rng)
                cases.append(
                    Case(
                        id=f"{cert.case_id}-{variant}",
                        file=file,
                        doc_type=doc_type,
                        variant=variant,
                        layout=cert.layout.id,
                        truth=cert.truth,
                    )
                )
    truth = {"seed": seed, "cases": [asdict(case) for case in cases]}
    (out_dir / "ground_truth.json").write_text(json.dumps(truth, indent=2), encoding="utf-8")
    return cases


def load_cases(out_dir: Path = OUT_DIR) -> list[Case]:
    """The cases from ground_truth.json."""
    data = json.loads((out_dir / "ground_truth.json").read_text(encoding="utf-8"))
    return [Case(**case) for case in data["cases"]]


def main(argv: Sequence[str] | None = None) -> int:
    """Command line: generate the cases."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=OUT_DIR)
    args = parser.parse_args(argv)
    cases = generate(args.out)
    print(f"Wrote {len(cases)} files and ground_truth.json to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
