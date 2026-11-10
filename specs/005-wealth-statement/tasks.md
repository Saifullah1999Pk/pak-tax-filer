---

description: "Task list for feature 005: Wealth Statement and Reconciliation"
---

# Tasks: Wealth Statement and Reconciliation

**Input**: Design documents from `/specs/005-wealth-statement/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md),
[data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md);
features 001–004 implemented. FBR sources: the
[design doc](../../docs/superpowers/specs/2026-11-03-wealth-statement-design.md).

**Tests**: written first, from hand-worked examples signed off by a human (FR-015,
Principle VI). **No reconciliation code (T008 onward) starts until T003 is complete.**

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an unfinished task)
- **[Story]**: the spec user story it serves (US1–US3)

---

## Phase 1: Setup

- [X] T001 Move 004's summary number check from `backend/app/tax/summary.py` to `backend/app/explain/number_check.py` (with `backend/app/explain/__init__.py`), update 004's imports, and confirm `backend/tests/tax/test_summary_check.py` still passes unchanged (research R9)

---

## Phase 2: Foundational (blocking; human sign-off gate)

- [X] T002 Write `backend/tests/wealth/worked_examples.yaml` per research R10: for each case, the inputs, the step-by-step hand-working citing the IRIS FAQ formula and the SRO 1495(I)/2026 form lines, the expected figures (`net_assets`, `increase`, `inflows`, `outflows`, `unreconciled`, `direction`), and empty `signed_off_by` / `signed_off_date`. Cases: reconciled; inflows exceed growth; growth exceeds inflows; a decrease in net assets; liabilities larger than assets; negative previous net assets; two salary and two bank certificates summed with paisa needing §219 rounding (including exactly 50 paisa); no bank certificate; bank profit of exactly Rs 5,000,000 (supported); an asset row with a zero amount; no asset rows at all; gross equal to taxable; one case for each `not_ready_reason` in [contracts/wealth-api.md](contracts/wealth-api.md)
- [X] T003 **Human task (Saifullah):** check every example in `worked_examples.yaml` by hand against the cited sources, correct any error, and fill in `signed_off_by` and `signed_off_date`. Any disagreement with the sources goes to the lead in the PR
- [X] T004 [P] Write `backend/tests/wealth/test_wealth_sign_off.py` (renamed: same-named test files collide in pytest): fails if any example in `worked_examples.yaml` lacks `signed_off_by` or `signed_off_date`
- [X] T005 Create `backend/app/wealth/models.py` and Alembic migration `backend/alembic/versions/0006_wealth.py` per [data-model.md](data-model.md): `wealth_statements` (unique on `user_id`, `tax_year`; money `numeric(14,0)`; `previous_net_assets` "nullable … may be negative"; other amounts "≥ 0, default 0"; `certificate_ids` UUID[]; `saved_at`), `wealth_assets` and `wealth_liabilities` (`description` "required, 1–200 characters"; `creditor` "optional, up to 200 characters"; `amount` "≥ 0"; `position`), `wealth_expenses` (primary key `statement_id`, `category`); all deleted with the statement, statements deleted with the user; asset and expense category enums exactly as listed
- [X] T006 [P] Create `backend/app/wealth/schemas.py`: request and response models for [contracts/wealth-api.md](contracts/wealth-api.md); money as decimal strings, whole rupees only; negative amounts rejected except `previous_net_assets`; unknown categories rejected

**Checkpoint**: examples signed off (T003); tables and validation in place.

---

## Phase 3: User Story 1 - Enter my wealth statement and see whether it reconciles (Priority: P1) 🎯 MVP

**Goal**: correct figures to the rupee for every signed-off example, with entries saved.

**Independent Test**: [quickstart.md](quickstart.md), section 1.

### Tests for User Story 1 (write first, confirm they fail)

- [X] T007 [P] [US1] Write `backend/tests/wealth/test_wealth_worked_examples.py` (renamed: same-named test files collide): one test per ready example in `worked_examples.yaml`, asserting `net_assets`, `increase`, `inflows`, `outflows`, `unreconciled` and `direction` equal the signed-off figures exactly

### Implementation for User Story 1

- [X] T008 [US1] Create `backend/app/wealth/reconcile.py` with `WealthInputs`, `ReconciliationResult` and pure `reconcile(inputs)` per research R1 and R2 (unreconciled = inflows − outflows − increase; zero means `reconciled`); no imports from database, network or AI modules, enforced by `backend/tests/wealth/test_reconcile_imports.py` failing if `reconcile.py` or `breakdown.py` imports `anthropic`, `app.wealth.summary`, `app.explain` or any database module; T007 passes
- [X] T009 [US1] Create `backend/app/wealth/service.py` per research R5 and R7: build `WealthInputs` from `confirmed_documents(user_id, tax_year)` (sum per type, round each sum with `ROUND_HALF_UP`; line 7032 salary part = gross − taxable; tax deducted + withheld as one outflow), each provisional rule (research R5, design rules 1, 2 and 4) as one named constant; keep each auto-filled line's source certificate names; load and replace-all save of the statement, recording `saved_at` and the sorted confirmed certificate ids
- [X] T010 [US1] Write `backend/tests/wealth/test_wealth_api.py` (unauthenticated → `401`; unknown tax year → `404`; `PUT` then `GET` round-trips every field; invalid amounts or categories → `422`; one user can't read or change another's statement (FR-016); auto-filled lines can't be set through `PUT`; a certificate still in `needs_review` never appears in `auto_filled` and never counts toward the reconciliation (Principle III guardrail test)), then create `backend/app/wealth/router.py` with `GET` and `PUT /api/wealth/{tax_year}` and include it in `backend/app/main.py`
- [X] T011 [P] [US1] Write `frontend/src/pages/WealthPage.test.tsx` (three sections: what I own, what I owe, money in and out; add, edit and delete rows; auto-filled lines read-only with certificate names and a "correct the certificate" hint; result shown; practitioner label always visible), then create `frontend/src/pages/WealthPage.tsx` and its route under `RequireAuth` and `RequireProfile` (feature 002), opening on the profile's tax year
- [X] T012 [US1] Run [quickstart.md](quickstart.md) section 1, including the timing check (result within 5 seconds, SC-006) *(2026-11-10, API on the local app: the four certificate lines filled in, naming their certificates; the contract example reconciles (net 2,565,000, increase 465,000, inflows 2,050,000, outflows 1,585,000, unreconciled 0); entries kept; reload 2.9 s with the summary; label present)*

**Checkpoint**: User Story 1 works on its own.

---

## Phase 4: User Story 2 - Understand the result and where to look (Priority: P2)

**Goal**: a step-by-step breakdown, direction in words, a fixed checklist with no amounts, and a
summary that can't introduce figures.

**Independent Test**: [quickstart.md](quickstart.md), section 2.

### Tests for User Story 2 (write first, confirm they fail)

- [X] T013 [P] [US2] Extend `backend/tests/wealth/test_worked_examples.py`: each example's breakdown has the expected steps in order, each with its `form_line`; the message states the absolute amount and direction; `where_to_look` is the fixed list for that direction, empty when reconciled, and contains no digits (SC-003)
- [X] T014 [P] [US2] Write `backend/tests/wealth/test_wealth_summary.py`: a summary using only breakdown numbers is shown; one with a wrong amount is dropped; an API error, refusal or a response slower than 4 seconds returns no summary and the result is still returned

### Implementation for User Story 2

- [X] T015 [US2] Create `backend/app/wealth/breakdown.py`: step templates and the two fixed "where to look" lists per research R2 and R9, used by `reconcile.py`; T013 passes
- [X] T016 [US2] Create `backend/app/wealth/summary.py`: Gemini call (004's summariser with its own instructions, `SUMMARY_MODEL`, `SUMMARY_EFFORT`, 4-second limit, breakdown passed as data, instruction to use only its numbers) checked with `app.explain.number_check`; wire into the router after a ready result; T014 passes using a fake client
- [X] T017 [US2] Show the breakdown (with form lines), the direction message, the checklist and the summary (when present) on `frontend/src/pages/WealthPage.tsx`; extend its test
- [X] T018 [US2] Run [quickstart.md](quickstart.md) section 2 *(2026-11-10: rent 40,000 lower → inflows exceed growth by Rs 40,000 with the missing-asset checklist (no digits); a Rs 40,000 asset added → assets grew Rs 40,000 more with the missing-inflow checklist; every step has its form line; a real Gemini summary appeared and passed the number check)*

**Checkpoint**: User Stories 1 and 2 work.

---

## Phase 5: User Story 3 - Honest limits and staying in sync (Priority: P3)

**Goal**: refuse rather than guess; tell the user when certificates changed.

**Independent Test**: [quickstart.md](quickstart.md), section 3.

### Tests for User Story 3 (write first, confirm they fail)

- [X] T019 [P] [US3] Write `backend/tests/wealth/test_wealth_not_ready.py`: one test per not-ready example in `worked_examples.yaml`, asserting its `not_ready_reason` and that every figure is null; `gross_below_taxable` names the certificate; the Rs 5 million limit is read from 004's TY2026 rates (`profit_limit`), not a copy
- [X] T020 [P] [US3] Extend `backend/tests/wealth/test_wealth_api.py`: `certificates_changed` is false right after a save, true after a certificate is deleted or a new one confirmed, and false again after the next save

### Implementation for User Story 3

- [X] T021 [US3] Add the not-ready checks from research R6 to the start of `reconcile()` in `backend/app/wealth/reconcile.py` (certificate-level checks supplied by `service.py` as inputs); T019 passes
- [X] T022 [US3] Compute `certificates_changed` in `backend/app/wealth/service.py` per research R7; T020 passes
- [X] T023 [US3] Show each not-ready message and the certificate-change notice on `frontend/src/pages/WealthPage.tsx`; extend its test
- [X] T024 [US3] Run [quickstart.md](quickstart.md) section 3 *(2026-11-10: previous net assets cleared → not ready; salary certificate deleted → not ready and the notice; re-uploaded → reconciles, notice cleared by saving; bank profit summing to 5,000,001 → the same message as the tax page; gross below taxable → not ready, naming the certificate)*

**Checkpoint**: all three user stories work.

---

## Phase 6: Polish

- [X] T025 [P] Add a "Wealth statement" section to `backend/CLAUDE.md`: `reconcile.py` stays pure; never compute or check figures, or write the "where to look" list, with an LLM; any change to the formula comes with signed-off worked examples
- [X] T026 Run Ruff, mypy, Prettier and `tsc` checks and both test suites; list in the PR description the four provisional rules, and the hidden expense categories to confirm on the live IRIS screen (research R3)

---

## Dependencies & Execution Order

- **T001** first (004 must already be implemented). **T002 → T003 (human sign-off)**; T004–T006
  can be done alongside T002, but **T008 onward waits for T003**.
- **US1** needs Foundational. **US2** builds on US1's `reconcile.py` (T008). **US3** extends the
  same function and service (T021 after T008, T022 after T009).
- `reconcile.py` is edited by T008 → T015 (uses breakdown) → T021, in that order;
  `WealthPage.tsx` by T011 → T017 → T023; `test_wealth_api.py` by T010 → T020.

## Parallel Opportunities

- T004, T006 alongside T002/T005.
- Test tasks T013, T014, T019 and T020 together once T010 exists.
- Frontend T011 alongside T009/T010.

## Implementation Strategy

1. **Sign-off gate first:** worked examples hand-checked (T003).
2. **MVP = User Story 1:** correct figures, saved entries.
3. **US2:** explanation and where to look; **US3:** honest limits and the change notice.
4. **Polish**, then one implementation PR listing the provisional rules for the lead.

GitHub issues for these tasks are titled `[005] T0NN: <description>`.
