"""Rendering a PDF from the templates (feature 008, task T006; research R6).

Jinja2 HTML, then WeasyPrint. Figures are only formatted for reading, never calculated
(Principle I). WeasyPrint is CPU-bound, so it runs in a worker thread.
"""

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape
from starlette.concurrency import run_in_threadpool
from weasyprint import HTML

_TEMPLATES = Environment(
    loader=FileSystemLoader(Path(__file__).parent / "templates"),
    autoescape=select_autoescape(["html"]),
)


def rupees(amount: str | None) -> str:
    """ "1800000.00" -> "Rs 1,800,000.00"; the same reading the screens give (no arithmetic)."""
    if amount is None:
        return ""
    sign = "-" if amount.startswith("-") else ""
    whole, _, fraction = amount.lstrip("-").partition(".")
    grouped = f"{int(whole):,}" if whole.isdigit() else whole
    return f"{sign}Rs {grouped}{f'.{fraction}' if fraction else ''}"


def balance(amount: str | None, overpaid: str) -> str:
    """ "12000" -> "Rs 12,000 payable"; "-3000" -> "Rs 3,000 over-deducted"; "0" -> "Nothing to
    pay"; worded as the Tax page words it."""
    if amount is None:
        return ""
    if amount.lstrip("-").strip("0.") == "":
        return "Nothing to pay"
    if amount.startswith("-"):
        return f"{rupees(amount[1:])} {overpaid}"
    return f"{rupees(amount)} payable"


_TEMPLATES.globals.update(rupees=rupees, balance=balance)


def _render(template: str, context: dict[str, Any]) -> bytes:
    html = _TEMPLATES.get_template(template).render(**context)
    pdf: bytes = HTML(string=html).write_pdf()
    return pdf


async def render_pdf(template: str, **context: Any) -> bytes:
    """The PDF for a template and its context, rendered off the event loop."""
    return await run_in_threadpool(_render, template, context)
