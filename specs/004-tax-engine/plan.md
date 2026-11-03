# Implementation Plan: Deterministic Tax Engine

**Branch**: `004-tax-engine` | **Date**: 2026-11-03 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/004-tax-engine/spec.md`

## Summary

A pure, deterministic `calculate(inputs, rates)` function applies the TY2026 salaried slabs,
§4AB surcharge, §7B profit tax, credits and §219 rounding, refusing unclear cases. Rates are typed
data per tax year in the guarded `backend/app/tax/rates/` folder, each with its source. A
protected `GET /api/tax/{tax_year}` builds inputs from 003's confirmed certificates and returns
the result with a templated step-by-step breakdown, plus an optional Claude summary that is
dropped unless every number in it appears in the breakdown. Hand-worked, signed-off examples are
written first and drive the tests. Decisions are in [research.md](research.md).

## Technical Context

**Language/Version**: Python 3.13, TypeScript on Node 24 (as in 001)

**Primary Dependencies**: standard-library `decimal`; `anthropic` (summary only, already added in
003); `pyyaml` (dev, worked examples); React

**Storage**: none: results recalculated per request ([data-model.md](data-model.md))

**Testing**: pytest parametrised from signed-off worked examples; band-continuity check;
summary-check tests; Vitest

**Target Platform**: local Docker Compose

**Project Type**: web application

**Performance Goals**: result within 5 seconds of answering ATL (SC-004); the calculation itself
is instant, the summary call is the slow part

**Constraints**: `Decimal` only; `ROUND_HALF_UP` at final amounts; no AI in any figure; rates
only in the guarded folder

**Scale/Scope**: 1 tax year of rates, 1 endpoint, 1 page

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle / rule | Status | How |
|---|---|---|
| I. Deterministic tax math | PASS | Pure `Decimal` function; AI only writes a summary, and code rejects any summary with a figure not in the breakdown (R8) |
| II. Authoritative sources | PASS | Every rate from the Ordinance as amended up to 31.07.2025 with location and Finance Act; one module per year in the guarded folder; FBR circular with wrong amounts rejected |
| III. Human confirmation | PASS | Only confirmed certificates are used (003's `confirmed_documents`) |
| IV. Honest output | PASS | Practitioner label on every result; unclear cases refused; "to be confirmed" instead of "refund" |
| V. Synthetic data only | PASS | No new data collected; ATL answer is not stored |
| VI. Test-first, measured AI | PASS | Hand-worked, signed-off examples become the tests before the code (R9); a test fails while any is unsigned |
| VII. MVP scope | PASS | Salary + bank profit only; out-of-scope items listed in the spec |
| Stack / Secrets | PASS | No new components; API key as in 003 |

**Post-design re-check:** PASS.

## Project Structure

### Documentation (this feature)

```text
specs/004-tax-engine/
├── plan.md
├── research.md        # R1–R10
├── data-model.md      # in-code structures (no tables)
├── quickstart.md
├── contracts/tax-api.md
└── tasks.md           # /speckit-tasks
```

### Source Code (repository root)

```text
backend/
├── app/tax/
│   ├── rates/                 # GUARDED (001 hook)
│   │   ├── __init__.py        # registry: tax year → rates
│   │   ├── model.py           # TaxYearRates, Band, Source dataclasses
│   │   └── ty2026.py          # TY2026 rates with sources
│   ├── engine.py              # calculate(): pure
│   ├── breakdown.py           # step templates
│   ├── summary.py             # Claude summary + number check
│   ├── service.py             # inputs from confirmed_documents
│   └── router.py              # GET /api/tax/{tax_year}
└── tests/tax/
    ├── worked_examples.yaml   # hand-worked, signed off
    ├── test_worked_examples.py
    ├── test_sign_off.py
    ├── test_rates.py          # sources present + band continuity
    ├── test_eligibility.py
    ├── test_summary_check.py
    └── test_tax_api.py

frontend/src/pages/TaxPage.tsx (+ .test.tsx)
```

**Structure Decision**: rates are data inside the guarded folder; everything that turns rates
into numbers lives in `engine.py`, which has no imports from the database, network or AI code.

## Complexity Tracking

No constitution violations; nothing to justify.
