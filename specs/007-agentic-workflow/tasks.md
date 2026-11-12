---

description: "Task list for feature 007: Agentic Workflow"
---

# Tasks: Agentic Workflow

**Input**: Design documents from `/specs/007-agentic-workflow/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md),
[data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md);
features 001–006 implemented.

**Tests**: written first for the state machine, the gate (Principle III), the agents' checks
(Principles I and IV) and the API.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an unfinished task)
- **[Story]**: the spec user story it serves (US1–US3)

---

## Phase 1: Setup

- [x] T001 Add `WORKFLOW_MODEL` (default `gemini-3.5-flash-lite`) and `WORKFLOW_EFFORT` (`minimal`) to `backend/app/settings.py` with tests in `backend/tests/test_settings.py` (as 006's `ANSWER_MODEL`), and `STEP_SECONDS = 15` in `backend/app/workflow/settings.py` (research R5, R6; amended 2026-11-12)

---

## Phase 2: Foundational (blocking)

**Purpose**: the run table, fingerprint, transitions and read-only tools every story uses.

- [x] T002 Create `backend/app/workflow/models.py` and `backend/alembic/versions/0008_workflow.py` (down revision `0007_rag_mcp`) per [data-model.md](data-model.md): `workflow_runs` with `user_id` "references users.id, deleted with the user", **unique** on (`user_id`, `tax_year`), `step` enum `document, validate, research, gate, result, done`, `step_outputs` JSONB, `outputs_fingerprint`, `approved_at`, `approved_fingerprint`, `done_at`, timestamps
- [x] T003 [P] Write `backend/tests/workflow/test_fingerprint.py`, then create `backend/app/workflow/fingerprint.py` per research R3: the same inputs give the same hash regardless of order; adding, deleting or re-confirming a certificate, editing a confirmed value, or changing the profile's `tax_year` or `on_atl` changes it; unconfirmed documents don't affect it
- [x] T004 [P] Write `backend/tests/workflow/test_state.py` covering every row of the transitions table in [data-model.md](data-model.md) and that `result`/`done` are unreachable without a matching `approved_fingerprint`, then create `backend/app/workflow/state.py` (pure `next_step`, research R2)
- [x] T005 [P] Create `backend/app/workflow/tools.py` per [contracts/workflow-api.md](contracts/workflow-api.md) (agent tools): `list_confirmed_documents`, `validate_salary_information`, `check_bank_certificate` (003's `rules.py`) and `search_tax_documents` (006's `app.rag.search`), all read-only. The salary check (amount parsing, "Not an amount.", 003's `check_rules` against the profile's year) moves out of `backend/app/mcp_server/server.py` into one shared function that both the MCP tool and this tool call, keeping 006's MCP tests passing; with `backend/tests/workflow/test_tools.py` asserting the tool list has no write, confirm, approve or calculate function
- [x] T006 [P] Create the fake agent client (in `backend/app/workflow/client.py`, beside the real one, so the `no_real_ai` fixture can import it, as 006's `FakeAnswerer`): returning scripted tool calls and final answers, including a timeout, a refusal and a reply with an unchecked number

**Checkpoint**: run rows, fingerprint, transitions and tools exist and are tested without AI.

---

## Phase 3: User Story 1 - Guided run up to the approval gate (Priority: P1) 🎯 MVP

**Goal**: a run goes through document, validation and research to the gate (FR-001 to FR-008).

**Independent Test**: [quickstart.md](quickstart.md) scenarios 1 and 4.

### Tests for User Story 1 (write first, confirm they fail)

- [x] T007 [P] [US1] Write `backend/tests/workflow/test_agents.py` with the fake client: document agent reports a missing salary certificate and calls bank certificates optional; validation agent explains a taxable-above-gross issue naming the certificate and the run still continues; research agent's passages all come from search results with locations; a reply whose number fails 004's check (document/validation) or 006's checks (research) is replaced by the code-written result with `fallback: true`; timeout (15 s, faked) and missing API key also fall back (research R5); research with no passage above the cut-off gives a plain "no passages found" note and the run continues
- [x] T008 [P] [US1] Write `backend/tests/workflow/test_workflow_api.py` (part 1) per [contracts/workflow-api.md](contracts/workflow-api.md): unauthenticated → `401`; no profile → `409` "Set up your profile first."; `GET` before start → `404`; `POST /start` with no confirmed salary certificate → `step: "document"` with `missing: ["salary_certificate"]`; with one → `step: "gate"` showing figures, tax year, `on_atl`, issues and passages; another user's run is never returned; a start counts one `ask_requests` row, and with the user's hourly limit (or the app's daily cap) reached it still reaches the gate with every step `fallback: true` and no agent called (FR-018, research R9)

### Implementation for User Story 1

- [x] T009 [US1] Create `backend/app/workflow/agents.py`: document, validation and research agents (one Gemini call each through `google-genai` with function calling over the T005 tools and a structured final answer; research up to 3 queries; 15 s per step), each with its code-written fallback, using 004's `app.explain.number_check` and 006's `app.rag.checks`; the real Gemini client tested through the SDK with an httpx2 `MockTransport`, as 006's `test_gemini_answerer.py`; T007 passes
- [x] T010 [US1] Create `backend/app/workflow/service.py` (`start`, `get_run` re-running steps 1–3 when the fingerprint differs from `outputs_fingerprint`; each run of steps 1–3 first calls 006's `use_question` and commits, using the fallbacks past a limit); the router gets the agent client through a `get_agent_client` dependency, which the autouse `no_real_ai` fixture in `backend/tests/conftest.py` replaces with the T006 fake, asserted in `backend/tests/test_no_real_ai.py` (as 006 did) and `backend/app/workflow/router.py` (`GET /api/workflow`, `POST /start`, with `current_user` and `require_profile`); include in `backend/app/main.py`; T008 passes
- [x] T011 [P] [US1] Write `frontend/src/pages/WorkflowPage.test.tsx` (step indicator; while steps 1–3 run, "Checking your documents…", "Checking the figures…", "Finding the law that applies…" in turn; missing-document message links to 003's pages; gate shows figures, tax year, ATL status, issues and passages with locations; fallback text is marked), then create `frontend/src/pages/WorkflowPage.tsx` and its route `/workflow` under `RequireAuth` and `RequireProfile`, linked from `frontend/src/pages/HomePage.tsx`; add "Guided filing" to `FILING` in `frontend/src/components/MainNav.tsx` with a test in `AppFrame.test.tsx` (computer top bar and phone Filing sheet; FR-017, research R10)
- [x] T012 [US1] Run [quickstart.md](quickstart.md) scenarios 1 and 4

**Checkpoint**: the run reaches the gate, with and without the AI.

---

## Phase 4: User Story 2 - Approve, calculate, explain and review (Priority: P2)

**Goal**: approval, result and done (FR-009 to FR-012, FR-014).

**Independent Test**: [quickstart.md](quickstart.md) scenario 2.

### Tests for User Story 2 (write first, confirm they fail)

- [ ] T013 [P] [US2] Write `backend/tests/workflow/test_gate.py` (guardrail, Principle III): `GET /result` before approval → `409` "Approval needed."; `POST /approve` away from the gate or with a stale fingerprint → `409`; two approvals at once record one; no agent reply (scripted to "approve", "confirm" or "set figure") changes the run, a document or a figure
- [ ] T014 [P] [US2] Extend `backend/tests/workflow/test_workflow_api.py`: after approval `GET /result` equals `GET /api/tax/{tax_year}` plus `passages` for synthetic users built from each of 004's signed-off worked examples (SC-004), including blocked ones; `POST /done` sets `done_at`; `POST /back` returns to `document`

### Implementation for User Story 2

- [ ] T015 [US2] Add `approve`, `back`, `result` (calls 004's `app.tax.service`, never stored) and `done` to `backend/app/workflow/service.py` and the matching endpoints to `router.py`, using `state.next_step`; T013 and T014 pass
- [ ] T016 [US2] Add the gate's Approve / Go back, the result (004's breakdown display, passages as "Where this comes from", practitioner label) and Mark done to `frontend/src/pages/WorkflowPage.tsx`; extend its test
- [ ] T017 [US2] Run [quickstart.md](quickstart.md) scenario 2

**Checkpoint**: the run works end to end.

---

## Phase 5: User Story 3 - Changes and resuming (Priority: P3)

**Goal**: input changes return the run to the gate; runs resume (FR-002, FR-013).

**Independent Test**: [quickstart.md](quickstart.md) scenario 3.

- [ ] T018 [P] [US3] Extend `backend/tests/workflow/test_workflow_api.py`: a re-run of steps 1–3 after an input change adds one `ask_requests` row (research R9); after approval, confirming a bank certificate, deleting a certificate or changing the profile → next `GET` shows `step: "gate"` (or `document` without a salary certificate), re-run outputs, `approved_at` null, and `GET /result` → `409`; a change before approval also re-runs steps 1–3; `POST /start` on a done run resets it (still one row)
- [ ] T019 [US3] Make `get_run` in `backend/app/workflow/service.py` apply `inputs_changed` (clear approval, re-run, move step) per research R3; T018 passes
- [ ] T020 [US3] Show "Your inputs changed; please review and approve again." on `frontend/src/pages/WorkflowPage.tsx` when the run returns to the gate after an approval; extend its test
- [ ] T021 [US3] Run [quickstart.md](quickstart.md) scenario 3

**Checkpoint**: all three stories work.

---

## Phase 6: Polish

- [ ] T022 [P] Add a "Workflow" section to `backend/CLAUDE.md`: agents get read-only tools only; the gate is checked in `service.py`; never store the tax result; a run of steps 1–3 counts against 006's question limits; tests use the fake agent client (added to the `no_real_ai` fixture)
- [ ] T023 Run the lint, format and type checks (001's CI), both test suites and all of [quickstart.md](quickstart.md); record results in the PR description

---

## Dependencies & Execution Order

- **Setup (T001)** → **Foundational (T002–T006)** → stories.
- **US1** needs Foundational. **US2** needs US1's service and router. **US3** needs US2 (approval
  exists to be cleared).
- Within each story: tests → implementation → quickstart check.
- `service.py` and `router.py` are extended in order T010 → T015 → T019; `WorkflowPage.tsx` T011 →
  T016 → T020; `test_workflow_api.py` T008 → T014 → T018.

## Parallel Opportunities

- Foundational T003, T004, T005, T006 together after T002.
- US1 tests T007, T008 together; T011 alongside T009/T010.
- US2 tests T013, T014 together.

## Implementation Strategy

1. **MVP = User Story 1**: the agentic steps up to the gate.
2. **Add US2**: approval, calculation and review.
3. **Add US3**: changes and resuming.
4. **Polish**, then one implementation PR.

GitHub issues for these tasks are titled `[007] T0NN: <description>`.
