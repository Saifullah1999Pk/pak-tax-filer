---

description: "Task list for feature 009: Policy-Based Bill Approval Agent"
---

# Tasks: Policy-Based Bill Approval Agent

**Input**: Design documents from `/specs/009-bill-approval/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md),
[data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md);
constitution v1.3.0; features 001–008 and PRs #42–#44 (contract check, the busy fix, e2e).

**Tests**: written first for every behaviour (Principle VI): the worked examples are signed off
before the engine; each endpoint's test before its route.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an unfinished task)
- **[Story]**: the spec user story it serves (US1–US3)
- `(manual)`: only a person can do it; the contract check ignores it

---

## Phase 1: Setup

- [ ] T001 Write `backend/tests/claims/test_claims_models.py` (tables and columns per [data-model.md](data-model.md), statuses, cascade on user delete, `users.is_approver` default false, `extraction_attempts.kind` default `document`), then create `backend/app/claims/models.py` and migration `backend/alembic/versions/0009_claims.py` (upgrade and downgrade); the test passes
- [ ] T002 [P] Write `backend/tests/claims/test_policies.py` (every rule has a source naming the synthetic policy; categories and banned categories per research R2; keyed by `2025-26`; an unknown year is `KeyError`), then create `backend/app/claims/policies/__init__.py` and `y2025_26.py`
- [ ] T003 [P] Write `backend/tests/auth/test_cli_approver.py` (`make-approver` / `remove-approver` set and clear the flag; unknown email exits 1 with "No such user."), then add both commands to `backend/app/cli.py`
- [ ] T004 [P] `GET /api/auth/me` returns `is_approver`: test first in `backend/tests/auth/test_login_logout.py`, then the route; update `specs/002-auth-foundation/contracts/auth-api.md` and `api.yaml`

---

## Phase 2: Foundational (blocking)

- [ ] T005 Write `backend/tests/claims/worked_examples.yaml`: hand-worked medical examples (allowed only; a banned line cut; every line banned; the budget edge; budget used up; each flag reason; the `reject_bill` setting; a changed total of exactly 10% and just over) with `signed_off_by` / `signed_off_date` left empty, and `backend/tests/claims/test_claims_sign_off.py` failing while any example is unsigned
- [ ] T006 (manual) Saifullah checks every example against the written provisional policy and signs it off (as for 004 and 005)
- [ ] T007 Write `backend/tests/claims/test_engine.py` parametrised over the signed examples (approved, cut, eligible, each line's result and rule, flag reasons), and running every example under both banned-items settings: only examples with a banned line change outcome (SC-007); confirm it fails for the right reason
- [ ] T008 Create `backend/app/claims/engine.py` (`decide()`, pure: no database, network, clock or AI; research R3); T007 passes
- [ ] T009 [P] Add `app.claims.engine` and `app.claims.policies` as sources in `backend/.importlinter`; `lint-imports` passes and fails with a planted AI import

**Checkpoint**: the policy is proven by examples before any screen exists.

---

## Phase 3: User Story 1 - Get a medical bill decided automatically (Priority: P1) 🎯 MVP

**Goal**: upload, confirm (edit, add, remove lines), decision with partial approval and the
budget cap, explanation (FR-001–FR-011, FR-019–FR-022).

**Independent Test**: [quickstart.md](quickstart.md) scenarios 1–3 and 7.

### Tests for User Story 1 (write first, confirm they fail)

- [ ] T010 [P] [US1] Write `backend/tests/claims/test_reading.py`: `GeminiBillReader` through the SDK with a mock transport (request carries the policy's categories in the schema; reply becomes lines, date or period, total; not a bill; 500/503/504, timeout and no connection marked `service_failed`; retries as 003's) and `FakeBillReader`
- [ ] T011 [P] [US1] Write `backend/tests/claims/test_claims_api.py` per [contracts/claims-api.md](contracts/claims-api.md): upload (file checks, unknown policy, `429` at 10 bills while tax documents are unaffected, the app-wide 100 shared, a Google failure not counted), list, get, file, lines (`409` after confirming; `422` for invalid lines), confirm (decided or flagged; the >10% flag; a line read without an amount must be completed), a failed claim whose lines the employee enters (→ `needs_confirmation`, then flagged `unreadable`), retry, withdraw (`409` once decided), budget, every claim of another user `404`
- [ ] T012 [P] [US1] Write `backend/tests/claims/test_budget_lock.py`: two confirmations at once for the last of a budget never approve more than it (separate sessions, as 007's `test_two_approvals_at_once_record_one`)
- [ ] T013 [P] [US1] Write `backend/tests/claims/test_explanation.py`: shown when every number is the decision's; template (`fallback: true`) for an extra number, a word number, an AI error or timeout; `409` before a decision
- [ ] T014 [P] [US1] Write `frontend/src/pages/ClaimsPage.test.tsx` and `ClaimPage.test.tsx`: choose a policy and upload; the lines table (edit, add, remove); confirm; the decision with each line's result and rule, budget left, the explanation and the provisional label; "Enter the lines yourself" on a claim that couldn't be read; withdraw; amounts shown as the API gives them

### Implementation for User Story 1

- [ ] T015 [US1] Add `claims_reading` and `claims_explanation` to the features in `backend/app/telemetry/ai.py`, then create `backend/app/claims/reading.py` (research R4; `ai_call("claims_reading", …)`, `record_gemini_usage`); T010 passes
- [ ] T016 [US1] Add `kind` to 003's limit (`use_extraction(db, user_id, kind="document")`, per-user by kind, app-wide both) in `backend/app/documents/service.py` with its tests; existing 003 tests still pass
- [ ] T017 [US1] Create `backend/app/claims/service.py` (submit, edit lines, confirm with the lock, retry, withdraw, budget; research R5, R6) and `backend/app/claims/router.py`; include it in `backend/app/main.py`; add `get_bill_reader` to `no_real_ai` in `backend/tests/conftest.py`; T011 and T012 pass
- [ ] T018 [US1] Create `backend/app/claims/explain.py` and `GET /api/claims/{id}/explanation` (research R8; `ai_call("claims_explanation", …)`); T013 passes
- [ ] T019 [US1] Create `frontend/src/api/claims.ts`, `ClaimsPage.tsx`, `ClaimPage.tsx`, routes in `App.tsx`, "Claims" in `navigation.ts`; T014 passes
- [ ] T020 [US1] Run [quickstart.md](quickstart.md) scenarios 1–3 and 7

**Checkpoint**: an employee's medical bill is read, confirmed and decided by the policy.

---

## Phase 4: User Story 2 - An approver decides the unclear claims (Priority: P2)

**Goal**: the approvals queue and decisions, never one's own (FR-012–FR-014).

**Independent Test**: [quickstart.md](quickstart.md) scenarios 4–5.

- [ ] T021 [P] [US2] Write `backend/tests/claims/test_approvals.py`: the access matrix (owner, other employee, approver on others' flagged, own flagged, others' decided: `404` except the allowed cases), the queue (oldest first, never own), approve above the eligible amount `422`, the eligible amount recomputed after another decision, a required note, a withdrawn claim `409`, budget used by the approved amount only
- [ ] T022 [P] [US2] Write `frontend/src/pages/ApprovalsPage.test.tsx`: the queue, opening a claim read-only, approve with amount and note, reject with note, the refusal message shown; "Approvals" in the navigation only for approvers
- [ ] T023 [US2] Add the approvals service functions and `/api/approvals` routes; T021 passes
- [ ] T024 [US2] Create `frontend/src/pages/ApprovalsPage.tsx` and the approver navigation item; T022 passes
- [ ] T025 [US2] Run [quickstart.md](quickstart.md) scenarios 4–5

---

## Phase 5: User Story 3 - Mobile and internet bills under a monthly cap (Priority: P3)

**Goal**: the second policy, with a monthly budget period (FR-017).

**Independent Test**: [quickstart.md](quickstart.md) scenario 6.

- [ ] T026 [US3] Add hand-worked mobile examples to `backend/tests/claims/worked_examples.yaml` (two bills in one month passing the cap; a device line; several months flagged; a new month starts fresh), unsigned
- [ ] T027 (manual) [US3] Saifullah signs off the mobile examples
- [ ] T028 [US3] Extend `engine.py` and the service for the monthly period (`period_key` per month from the billing period); T007 passes for the mobile examples; API tests for a mobile bill in `test_claims_api.py` first
- [ ] T029 [P] [US3] Show the billing period on `ClaimPage.tsx` for mobile bills (test first in `ClaimPage.test.tsx`) and the monthly budget on `ClaimsPage.tsx`
- [ ] T030 [US3] Run [quickstart.md](quickstart.md) scenario 6

---

## Phase 6: Polish

- [ ] T031 [P] Create `backend/evals/claims/` (`generate`: at least 10 synthetic medical and mobile bills with their true lines and categories; `run`: line-amount and category accuracy) and `.github/workflows/claims-eval.yml` (as `extraction-eval.yml`); run it with the key and record the report (SC-006)
- [ ] T032 [P] Add claims to the guardrail suite: `backend/tests/guardrails/test_principle_1.py` (a lying AI never changes a claim amount), `test_principle_3.py` (nothing decided before confirming; flagged only by an approver, never one's own), `test_principle_4.py` (every decision labelled; explanation number-checked); update its README
- [ ] T033 [P] Telemetry: the two new features appear with their outcomes in `backend/tests/telemetry/test_spans.py`; no claim content in spans (`test_no_content.py`)
- [ ] T034 Extend the e2e suite: the fake Gemini answers bills (`e2e/fake_gemini/server.py`, by the schema's `lines` property), a global setup making two approvers with the CLI, and `e2e/tests/claims.spec.ts` (a medical bill decided: Rs 4,200 approved, Rs 800 cut; a flagged claim decided by the other approver; an approver never sees their own); update `e2e/README.md`
- [ ] T035 [P] Add a "Bill approval (feature 009)" section to `backend/CLAUDE.md` (policies only in `app/claims/policies/` with sources and signed examples; the engine pure; the approver access rule; reading through `use_extraction(kind="bill")`), and the feature to `README.md`
- [ ] T036 Run the lint, format and type checks, both test suites, the hook tests, the contract check, the e2e suite and all of [quickstart.md](quickstart.md); record results in the PR description
- [ ] T037 (manual) In the pull request, ask the lead to approve constitution v1.3.0 and a ninth feature

---

## Dependencies & Execution Order

- **Setup (T001–T004)** → **Foundational (T005–T009)**: the engine (T008) waits for the signed
  examples (T006) and their tests (T007).
- **US1** needs the foundation; **US2** needs US1's service (flagged claims exist); **US3** needs
  the engine and US1's pages.
- T016 changes 003's limit function: run 003's tests with it.
- Polish after the stories; T034 (e2e) after US2 (it uses approvers).

## Parallel Opportunities

- T002, T003, T004 together after T001; US1 tests T010–T014 together; US2 tests T021–T022
  together; polish T031, T032, T033, T035 together.

## Implementation Strategy

1. **MVP = User Story 1**: a medical bill decided by the policy for one employee.
2. **Add US2**: the approver, making it the lead's flow.
3. **Add US3**: the second policy, proving the engine is general.
4. **Polish**: eval, guardrails, telemetry, e2e, docs; then one pull request.

GitHub issues for these tasks are titled `[009] T0NN: <description>`.
