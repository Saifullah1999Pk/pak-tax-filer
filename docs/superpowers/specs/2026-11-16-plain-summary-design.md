# Plain-code summaries on the Tax and Wealth pages (design, short)

**Date:** 2026-11-16 · **Branch:** `simplify/no-ai-where-not-needed` (before its PR)

## Why

The AI summaries were removed (the lead: AI only where reasoning is needed). Without them the
pages lost their short written answer, which Saifullah thinks makes them feel bare. The AI only
reworded numbers the code had already computed, so plain code can write the same sentences:
instant, never wrong, nothing to number-check.

## Goals

- A "Summary" panel with two or three plain sentences, back where the AI panel was (above "How it
  was worked out") on the Tax page, the Wealth page and the guided run's result (it reuses the Tax
  view).
- The same sentences in the PDFs (the PDF shows what the screen shows).

## Non-goals and anti-goals

- No AI anywhere in it, and no new figures: only amounts the result already holds.
- Never a combined salary + bank profit total (still a question for the lead; 004 spec
  clarification).
- No summary when there's no result: blocked (tax) or not ready (wealth) results already show their
  message, so `summary` is `null` there.
- The old `/summary` routes stay gone (404).

## Approaches

| | Approach | Trade-off |
|---|---|---|
| **A (chosen)** | Backend writes it; the result carries a `summary` field | One wording for screen, PDF and guided run; tested in Python; small contract change |
| B | Frontend writes it from the figures | No API change, but the PDF would need the wording twice |
| C | Bring back `/summary` with code text | An extra request and a loading state for text the result can carry |

Saifullah picked A.

## Decided

- **Tax** (`summary: string | null` on the tax result, and so on the workflow result): a salary
  sentence (tax for the year, surcharge if any, what employers deducted, and the balance in the
  page's words: "payable", "over-deducted" or "nothing to pay"); a bank-profit sentence only when
  there is bank profit ("over-withheld" for an overpayment). For example: "Your salary tax for
  2025-26 is Rs 72,000. Your employers deducted Rs 75,000, so Rs 3,000 was deducted too much."
- **Wealth** (`summary: string | null` on the wealth result): net assets this year and the increase
  over last year, then inflows and outflows. The existing result sentence and "where to look"
  checklist stay as they are, below it.
- Amounts written like the rest of the app ("Rs 72,000", grouped, whole rupees as stored).
- Contracts (004 `tax-api.md` + `api.yaml`, 005 `wealth-api.md` + `api.yaml`, 007's result) and
  the amended FRs (004 FR-011, 005 FR-010) say the summary is written by code.

## Left to the builder

Module names (e.g. `app/tax/summary.py`, alongside `app/wealth/breakdown.py`'s wording), exact sentence wording
within the rules above, and the tests (test first: each sentence case, `null` when blocked or not
ready, the PDF shows it, the page shows it).
