---

description: "Task list for feature 004: Deterministic Tax Engine"
---

# Tasks: Deterministic Tax Engine

**Input**: Design documents from `/specs/004-tax-engine/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md),
[data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md);
features 001–003 implemented. Legal sources: the
[design doc](../../docs/superpowers/specs/2026-11-03-tax-engine-design.md).

**Tests**: written first, from hand-worked examples signed off by a human (FR-015,
Principle VI). **No engine code (T009 onward) starts until T003 is complete.**

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an unfinished task)
- **[Story]**: the spec user story it serves (US1–US4)

---

## Phase 1: Setup

- [ ] T001 Add `pyyaml` as a dev dependency in `backend/pyproject.toml` with `uv add --dev`; add `SUMMARY_MODEL` (default `claude-opus-5-5`) and `SUMMARY_EFFORT` (default `low`) to `backend/app/settings.py`

---

## Phase 2: Foundational (blocking; human sign-off gate)

- [ ] T002 Write `backend/tests/tax/worked_examples.yaml` per research R9: for each case, the inputs, the step-by-step hand-working citing the exact Ordinance row used, the expected figures, and empty `signed_off_by` / `signed_off_date`. Cases: every salary band (a value inside, and each band's upper limit exactly); Rs 10,000,000 and Rs 10,000,001 taxable income; Rs 5,000,000 and Rs 5,000,001 bank profit; a case producing exactly 50 paisa before rounding; two salary and two bank certificates summed; zero bank profit; tax deducted equal to tax due; a non-ATL user with 40% withheld; payable salary with over-withheld profit (balances separate); one case for each `blocked_reason` in [contracts/tax-api.md](contracts/tax-api.md)
- [ ] T003 **Human task (Saifullah):** check every example in `worked_examples.yaml` by hand against the Ordinance as amended up to 31.07.2025 (design doc sources table), correct any error, and fill in `signed_off_by` and `signed_off_date`. Any disagreement with the Ordinance's wording goes to the lead in the PR
- [ ] T004 [P] Write `backend/tests/tax/test_sign_off.py`: fails if any example in `worked_examples.yaml` lacks `signed_off_by` or `signed_off_date`
- [ ] T005 Create `backend/app/tax/rates/model.py` with frozen dataclasses `Source(document, location, finance_act)`, `Band(lower, upper | None, fixed, rate, source)` and `TaxYearRates` per [data-model.md](data-model.md); all numbers `Decimal` from strings
- [ ] T006 [P] Write `backend/tests/tax/test_rates.py`: every rule in every registered tax year has a non-empty `Source`; each band's `fixed` equals the previous band's `fixed + rate × (upper − lower)` (research R10); bands are contiguous and the last has no upper limit
- [ ] T007 Create `backend/app/tax/rates/ty2026.py` with the TY2026 values and sources exactly as in the design doc's sources table (slabs: 0 / 1% / 6,000 + 11% / 116,000 + 23% / 346,000 + 30% / 616,000 + 35%; surcharge 9% above 10,000,000; profit 20% up to 5,000,000; §219 rounding); approve the 001 guard-hook prompt for this folder deliberately; T006 passes
- [ ] T008 Create `backend/app/tax/rates/__init__.py` registry mapping `"2025-26"` to the TY2026 rates

**Checkpoint**: examples signed off (T003); rates stored with sources and self-checked.

---

## Phase 3: User Story 1 - See my tax and whether I owe or overpaid (Priority: P1) 🎯 MVP

**Goal**: correct figures to the rupee for every signed-off example.

**Independent Test**: [quickstart.md](quickstart.md), section 1.

### Tests for User Story 1 (write first, confirm they fail)

- [ ] T009 [P] [US1] Write `backend/tests/tax/test_worked_examples.py`: one test per non-blocked example in `worked_examples.yaml`, asserting `salary_tax`, `surcharge`, `profit_tax`, `salary_balance`, `profit_balance` and `non_atl_extra_withheld` equal the signed-off figures exactly

### Implementation for User Story 1

- [ ] T010 [US1] Create `backend/app/tax/engine.py` with `TaxInputs`, `TaxResult` and pure `calculate(inputs, rates)` per research R1 and R3: band selection with "does not exceed" upper limits, surcharge on "exceeds", profit tax, credits, separate balances, `ROUND_HALF_UP` only on final amounts; no imports from database, network or AI modules, enforced by a test in `backend/tests/tax/test_engine_imports.py` that fails if `engine.py` imports `anthropic`, `app.tax.summary` or any database module; T009 passes
- [ ] T011 [US1] Create `backend/app/tax/service.py`: build `TaxInputs` from `confirmed_documents(user_id, tax_year)` (summing per type) and `on_atl` from feature 002's `get_profile` (no profile → `needs_atl_answer`), per research R5
- [ ] T012 [US1] Write `backend/tests/tax/test_tax_api.py` (unauthenticated → `401`; unknown tax year → `404`; an `atl` query parameter has no effect and the profile's ATL status is used; a user's confirmed certificates produce the contract's response shape with money as strings and the label), then create `backend/app/tax/router.py` with `GET /api/tax/{tax_year}` and include it in `backend/app/main.py`
- [ ] T013 [P] [US1] Write `frontend/src/pages/TaxPage.test.tsx` (no ATL question; the `needs_atl_answer` message links to `/profile`; salary and profit results shown separately with no combined total; practitioner label always visible), then create `frontend/src/pages/TaxPage.tsx` and its route under `RequireAuth`
- [ ] T014 [US1] Run [quickstart.md](quickstart.md) section 1

**Checkpoint**: User Story 1 works on its own.

---

## Phase 4: User Story 2 - Understand every step (Priority: P2)

**Goal**: an authoritative breakdown, and a summary that can't introduce figures.

**Independent Test**: [quickstart.md](quickstart.md), section 2.

### Tests for User Story 2 (write first, confirm they fail)

- [ ] T015 [P] [US2] Extend `backend/tests/tax/test_worked_examples.py`: each example's breakdown has the expected steps in order, each with a `rule_location` naming the Ordinance row
- [ ] T016 [P] [US2] Write `backend/tests/tax/test_summary_check.py` per research R8: a summary using only breakdown numbers passes; one with a wrong amount, a wrong percentage, a number with different formatting of a wrong value, or a number word ("1.8 million", "lakh") is rejected; an API error, refusal or a response slower than 4 seconds returns no summary and the breakdown is still returned

### Implementation for User Story 2

- [ ] T017 [US2] Create `backend/app/tax/breakdown.py`: step templates per research R7, used by `engine.py`; T015 passes
- [ ] T018 [US2] Create `backend/app/tax/summary.py`: Claude call (official SDK, `SUMMARY_MODEL`, `SUMMARY_EFFORT`, 4-second limit, breakdown passed as data, instruction to use only its numbers) and the number check; wire into the router after a successful calculation; T016 passes using a fake client
- [ ] T019 [US2] Show the breakdown (with rule locations) and the summary (when present) on `frontend/src/pages/TaxPage.tsx`; extend its test
- [ ] T020 [US2] Run [quickstart.md](quickstart.md) section 2

**Checkpoint**: User Story 2 works on its own.

---

## Phase 5: User Story 3 - Honest limits (Priority: P3)

**Goal**: refuse rather than guess.

**Independent Test**: [quickstart.md](quickstart.md), section 3.

### Tests for User Story 3 (write first, confirm they fail)

- [ ] T021 [P] [US3] Write `backend/tests/tax/test_eligibility.py`: one test per blocked example in `worked_examples.yaml`, asserting its `blocked_reason` and that every figure is null; the non-ATL example's difference is in `non_atl_extra_withheld` and never in a balance labelled refund

### Implementation for User Story 3

- [ ] T022 [US3] Add the eligibility checks from research R4 to the start of `calculate()` in `backend/app/tax/engine.py`, each provisional rule as one named constant; T021 passes
- [ ] T023 [US3] Show each blocked reason's message and the non-ATL "to be confirmed" label on `frontend/src/pages/TaxPage.tsx`; extend its test
- [ ] T024 [US3] Run [quickstart.md](quickstart.md) section 3

**Checkpoint**: User Stories 1–3 work.

---

## Phase 6: User Story 4 - Rates are traceable and correct (Priority: P4)

**Goal**: sources visible and typos caught (mostly delivered by T005–T008).

**Independent Test**: [quickstart.md](quickstart.md), section 4.

- [ ] T025 [US4] Add a test in `backend/tests/tax/test_rates.py` that registering a second, made-up tax year with different bands changes results without any change to `engine.py` (FR-008); use a test-only registry so the real registry is unchanged
- [ ] T026 [US4] Run [quickstart.md](quickstart.md) section 4, including the deliberate 1-rupee change and revert

**Checkpoint**: all four user stories work.

---

## Phase 7: Polish

- [ ] T027 [P] Add a "Tax engine" section to `backend/CLAUDE.md`: rates live only in `backend/app/tax/rates/` with sources; every rate change comes with signed-off worked examples; never compute or check figures with an LLM
- [ ] T028 Run Ruff, mypy, Prettier and `tsc` checks and both test suites; list in the PR description the four provisional rules and the open questions for the lead

---

## Dependencies & Execution Order

- **T001** → **T002 → T003 (human sign-off)**; T004–T008 can be done alongside T002, but **T009
  onward waits for T003**.
- **US1** needs Foundational. **US2** builds on US1's engine (T010). **US3** extends the same
  engine (T022 after T010). **US4** is mostly Foundational; T025 after T010.
- `engine.py` is edited by T010 → T017 (uses breakdown) → T022, in that order; `TaxPage.tsx` by
  T013 → T019 → T023.

## Parallel Opportunities

- T004, T005, T006 alongside T002.
- Test tasks T015, T016 and T021 together once T010 exists.
- Frontend T013 alongside T011/T012.

## Implementation Strategy

1. **Sign-off gate first:** worked examples hand-checked (T003).
2. **MVP = User Story 1:** correct figures.
3. **US2:** explanation; **US3:** honest refusals; **US4:** traceability.
4. **Polish**, then one implementation PR listing the provisional rules for the lead.

GitHub issues for these tasks are titled `[004] T0NN: <description>`.
