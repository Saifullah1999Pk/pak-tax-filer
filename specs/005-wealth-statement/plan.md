# Implementation Plan: Wealth Statement and Reconciliation

**Branch**: `005-wealth-statement` | **Date**: 2026-11-03 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/005-wealth-statement/spec.md`

## Summary

The user's assets, liabilities, previous net assets and money flows are stored per tax year; a
pure, deterministic `reconcile(inputs)` computes net assets, the increase, inflows, outflows and
the unreconciled amount on every view, with auto-filled lines from 003's confirmed certificates.
A protected `GET`/`PUT /api/wealth/{tax_year}` serves one page. Results come with a templated
breakdown citing SRO 1495(I)/2026 form lines, a fixed "where to look" list by direction, and an
optional Claude summary that passes 004's number check, which moves to a shared module.
Hand-worked, signed-off examples are written first and drive the tests. Decisions are in
[research.md](research.md).

## Technical Context

**Language/Version**: Python 3.13, TypeScript on Node 24 (as in 001)

**Primary Dependencies**: FastAPI, SQLAlchemy 2 async + Alembic (001); standard-library
`decimal`; `anthropic` (summary only, 003); `pyyaml` (dev, 004); React + React Router (002)

**Storage**: PostgreSQL: four tables ([data-model.md](data-model.md)); results never stored

**Testing**: pytest parametrised from signed-off worked examples; API tests; Vitest

**Target Platform**: local Docker Compose

**Project Type**: web application

**Performance Goals**: result within 5 seconds of opening the page (SC-006); the summary call
has 004's 4-second limit

**Constraints**: whole rupees, `Decimal` only; no AI in any figure or in the "where to look"
list; only confirmed certificate data; synthetic data only

**Scale/Scope**: 1 tax year, 2 endpoints, 1 page, tens of rows per statement

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle / rule | Status | How |
|---|---|---|
| I. Deterministic tax math | PASS | Pure `Decimal` function; the checklist is fixed code; AI only writes a summary that the shared number check can reject (R9) |
| II. Authoritative sources | PASS | Form lines from SRO 1495(I)/2026, formula from FBR's IRIS FAQ, duty from §116; the Rs 5m limit and rounding are read from 004's rates module, not duplicated |
| III. Human confirmation | PASS | Auto-filled lines come only from confirmed certificates and are read-only; corrections go through 003 |
| IV. Honest output | PASS | Label on every result; not-ready reasons instead of guesses; four provisional rules asked of the lead |
| V. Synthetic data only | PASS | Demo data only; statements deleted with the user |
| VI. Test-first, measured AI | PASS | Signed-off worked examples before code; a test fails while any is unsigned (R10) |
| VII. MVP scope | PASS | Salary + bank profit filers only; out-of-scope list in the spec |
| Stack / Secrets | PASS | No new components; API key as in 003 |

**Post-design re-check:** PASS.

## Project Structure

### Documentation (this feature)

```text
specs/005-wealth-statement/
├── plan.md
├── research.md        # R1–R10
├── data-model.md      # 4 tables + in-code structures
├── quickstart.md
├── contracts/wealth-api.md
└── tasks.md           # /speckit-tasks
```

### Source Code (repository root)

```text
backend/
├── alembic/versions/0005_wealth.py
├── app/explain/
│   └── number_check.py         # moved from app/tax/summary.py (004), shared
├── app/wealth/
│   ├── models.py               # 4 tables
│   ├── schemas.py              # request/response, validation
│   ├── reconcile.py            # reconcile(): pure
│   ├── breakdown.py            # step templates + where-to-look lists
│   ├── summary.py              # Claude summary using explain.number_check
│   ├── service.py              # inputs from confirmed_documents, save/load
│   └── router.py               # GET/PUT /api/wealth/{tax_year}
└── tests/wealth/
    ├── worked_examples.yaml    # hand-worked, signed off
    ├── test_sign_off.py
    ├── test_worked_examples.py
    ├── test_not_ready.py
    ├── test_reconcile_imports.py
    └── test_wealth_api.py

frontend/src/pages/WealthPage.tsx (+ .test.tsx)
```

**Structure Decision**: `reconcile.py` has no imports from the database, network or AI code;
everything that touches storage or certificates lives in `service.py`.

## Complexity Tracking

No constitution violations. One cross-feature change: 004's number check moves to
`backend/app/explain/` so both features share one implementation (R9).
