---

description: "Task list for feature 006: RAG Tax Assistant and MCP Server"
---

# Tasks: RAG Tax Assistant and MCP Server

**Input**: Design documents from `/specs/006-rag-mcp/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md),
[data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md);
features 001–005 implemented; **the lead's approval of the embeddings component** (plan,
Complexity Tracking) recorded in `plan.md` before T001.

**Tests**: written first for every check that enforces a constitution principle (I, III, IV) and
for the eval gate.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an unfinished task)
- **[Story]**: the spec user story it serves (US1–US4)

---

## Phase 1: Setup

- [ ] T001 Add `fastembed`, `pgvector` and `mcp` to `backend/pyproject.toml` with `uv add`; pre-download `BAAI/bge-small-en-v1.5` in `backend/Dockerfile` so containers start offline; add `ANSWER_MODEL` (default `claude-opus-5-5`), `ANSWER_EFFORT` (`low`), `ANSWER_TIMEOUT_SECONDS` (8) and `ASK_LIMIT_PER_HOUR` (30) to `backend/app/settings.py`
- [ ] T002 [P] Add `/data/corpus-cache/` to `.gitignore` and `.dockerignore`; add a note to `backend/CLAUDE.md` that FBR source files are never committed

---

## Phase 2: Foundational (blocking)

- [ ] T003 Create `backend/app/rag/models.py`, `backend/app/tokens/models.py` and Alembic migration `backend/alembic/versions/0006_rag_mcp.py` per [data-model.md](data-model.md): enable `vector`; `corpus_documents` (`kind` "law or guidance"; `sha256` "64 hex characters"); `passages` (`embedding` "vector(384), HNSW index, cosine distance"; deleted with the document); `ask_requests` (indexed on `user_id`, `created_at`; no question text); `personal_access_tokens` (`name` "required, 1–50 characters"; `token_hash` unique; `expires_at` "created_at + 90 days")
- [ ] T004 Write `backend/app/rag/sources.yaml` per research R1 with the two FBR URLs from the [design doc](../../docs/superpowers/specs/2026-11-03-rag-mcp-design.md), their SHA-256 (computed from freshly downloaded files), `kind`, the Ordinance sections (12, 13, 149, 7B, 151) and the manual's page ranges for ch. 4–6 and 14
- [ ] T005 [P] Write `backend/tests/rag/test_split.py` (Ordinance text yields locations like `§149(1)`; manual text yields `ch. 14.3`; every passage has a page; long sections split with the same location; no passage outside the configured sections), then create `backend/app/rag/split.py`
- [ ] T006 [P] Create `backend/app/rag/embed.py`: `fastembed` wrapper plus a deterministic fake embedder for tests
- [ ] T007 Write `backend/tests/rag/test_build.py` (a checksum mismatch stops the build and leaves the existing corpus unchanged; a successful build replaces all passages in one transaction), then create `backend/app/rag/build.py` (`python -m app.rag.build`) per research R1
- [ ] T008 Write `backend/tests/rag/test_search.py` (top 5 by cosine with location, page and kind; below the cut-off returns `not_covered`), then create `backend/app/rag/search.py` and `backend/app/rag/settings.py` per research R4

**Checkpoint**: corpus builds from FBR with checksums; search works.

---

## Phase 3: User Story 1 - Ask a tax question and get a cited answer (Priority: P1) 🎯 MVP

**Goal**: cited answers that can't cite unretrieved passages or add numbers.

**Independent Test**: [quickstart.md](quickstart.md), section 2 steps 1 and 5.

### Tests for User Story 1 (write first, confirm they fail)

- [ ] T009 [P] [US1] Write `backend/tests/rag/test_checks.py` per research R6: an answer citing only retrieved passages with numbers from them passes; a citation outside the retrieved set fails; a number not in a cited passage fails; "§149" passes only if in a cited passage or its location; "5 million" fails (number word)
- [ ] T010 [P] [US1] Write `backend/tests/rag/test_ask_service.py` with a fake Claude client: an answered response has citations with title, kind (`law`/`guidance`), location and page, plus the practitioner label; nothing about the question is stored except an `ask_requests` row

### Implementation for User Story 1

- [ ] T011 [US1] Create `backend/app/rag/answer.py` per research R5: official SDK, `ANSWER_MODEL`, `ANSWER_EFFORT`, timeout, structured output (`answer`, `citations`, `not_covered`, `uncovered_part`, `asks_own_tax_figure`), passages passed as data; fake client for tests
- [ ] T012 [US1] Create `backend/app/rag/checks.py` using `app.explain.number_check` (from 005) with the cited passages' text and locations as the allowed set; T009 passes
- [ ] T013 [US1] Create `backend/app/rag/service.py` (`ask()`: search → answer → checks) and `backend/app/rag/router.py` (`POST /api/ask` per [contracts/ask-and-tokens-api.md](contracts/ask-and-tokens-api.md)); write `backend/tests/rag/test_ask_api.py` (`401` not logged in; `422` empty or over 1,000 characters); include the router in `backend/app/main.py`; T010 passes
- [ ] T014 [P] [US1] Write `frontend/src/pages/AskPage.test.tsx` (question box; answer with citations showing law vs guidance; label always visible; a second question replaces the first), then create `frontend/src/pages/AskPage.tsx` and its route under `RequireAuth`
- [ ] T015 [US1] Run [quickstart.md](quickstart.md) section 2, steps 1 and 5, including the timing check (answer within 10 seconds, SC-004)

**Checkpoint**: User Story 1 works on its own.

---

## Phase 4: User Story 2 - Honest refusal outside the sources (Priority: P2)

**Goal**: explicit refusals, partial answers named, Tax page pointer, question limit.

**Independent Test**: [quickstart.md](quickstart.md), section 2 steps 2–4 and 6.

### Tests for User Story 2 (write first, confirm they fail)

- [ ] T016 [P] [US2] Extend `backend/tests/rag/test_ask_service.py`: below the cut-off → `not_covered` without calling Claude; a question in Urdu → `not_covered`; Claude `not_covered` → refusal; failed checks → refusal; `uncovered_part` returned with a partial answer; `asks_own_tax_figure` → the fixed `tax_page_line` and no number outside cited passages; API error or timeout → `unavailable`; the 31st question within an hour → `limited` with no Claude call; rows older than a day are deleted

### Implementation for User Story 2

- [ ] T017 [US2] Add the refusal paths, the fixed Tax page line and the per-hour limit (research R7) to `backend/app/rag/service.py`; T016 passes
- [ ] T018 [US2] Show each `status` message, the uncovered part and the Tax page line (linking to the Tax page) on `frontend/src/pages/AskPage.tsx`; extend its test
- [ ] T019 [US2] Run [quickstart.md](quickstart.md) section 2, steps 2–4 and 6

**Checkpoint**: User Stories 1 and 2 work.

---

## Phase 5: User Story 3 - Retrieval quality is measured (Priority: P3)

**Goal**: an eval gate in CI with no secrets.

**Independent Test**: [quickstart.md](quickstart.md), section 3.

- [ ] T020 [US3] Write `backend/evals/retrieval/questions.yaml` per research R10: ~30 questions in a salaried user's words (not copying passage wording; some deliberately tricky), each with `expected` stable locations, and ~10 with `expected: out_of_corpus` (e.g. rental income, dividends, sales tax, Urdu); the file is reviewed by the lead in the PR
- [ ] T021 [US3] Write `backend/tests/evals/test_retrieval_gate.py` (a search returning random passages makes the run exit non-zero), then create `backend/evals/retrieval/run.py` (hit@5 and cut-off refusal rate) and `backend/evals/retrieval/thresholds.yaml` (proposed 0.80 / 0.90 until the lead sets them)
- [ ] T022 [US3] Run the eval, choose the relevance cut-off that best separates labelled from out-of-corpus questions, and record the value and the run's scores in `backend/app/rag/settings.py`
- [ ] T023 [US3] Add a `retrieval-eval` job to `.github/workflows/ci.yml`: builds the corpus with FBR files cached by the checksums in `sources.yaml` and the model cached; runs the eval; uses no secrets; fails if FBR is unreachable with no cache
- [ ] T024 [P] [US3] Create `backend/evals/answers/run.py`: a local-only script that asks the eval questions through `ask()` with the real API key and reports refusals and check failures (not run in CI)
- [ ] T025 [US3] Run [quickstart.md](quickstart.md) section 3, including the random-search failure

**Checkpoint**: User Stories 1–3 work.

---

## Phase 6: User Story 4 - Use the tools from an AI assistant (Priority: P4)

**Goal**: exactly three MCP tools acting as the token's owner.

**Independent Test**: [quickstart.md](quickstart.md), section 4.

### Tests for User Story 4 (write first, confirm they fail)

- [ ] T026 [P] [US4] Write `backend/tests/tokens/test_tokens_api.py`: create returns the full `ptx_…` value once and stores only its SHA-256; list never returns values; revoke works immediately; another user's token → `404`; a token past 90 days is invalid; a valid token sent as a bearer token to a cookie-protected endpoint (e.g. `GET /api/tax/2025-26`) → `401` (web login unchanged, FR-015)
- [ ] T027 [P] [US4] Write `backend/tests/mcp/test_mcp_tools.py`: exactly three tools are listed; a missing, wrong, expired or revoked token is refused for every tool (SC-006); `search_tax_documents` returns the same passages as `app.rag.search`; `calculate_income_tax` takes no input and returns the same body as `GET /api/tax/{tax_year}` for a synthetic user (with a profile) built from each of 004's signed-off worked examples (SC-005); a token owner without a profile gets `needs_atl_answer`; a user with only `needs_review` certificates gets 004's not-ready reason and no figures (Principle III guardrail); `validate_salary_information` reports taxable above gross and never returns a tax figure

### Implementation for User Story 4

- [ ] T028 [US4] Create `backend/app/tokens/service.py` and `backend/app/tokens/router.py` (`/api/tokens` per [contracts/ask-and-tokens-api.md](contracts/ask-and-tokens-api.md)) per research R8; include in `backend/app/main.py`; T026 passes
- [ ] T029 [P] [US4] Write `frontend/src/pages/TokensPage.test.tsx` (create shows the value once with a copy button; list shows prefix and expiry; revoke), then create `frontend/src/pages/TokensPage.tsx` and its route under `RequireAuth`
- [ ] T030 [US4] Create `backend/app/mcp_server/__main__.py` per research R9 and [contracts/mcp-tools.md](contracts/mcp-tools.md): stdio, token check on every call (updating `last_used_at`), three tools calling `app.rag.search`, 004's `app.tax.service` and 003's `app/documents/extraction/rules.py`; T027 passes
- [ ] T031 [US4] Add `.mcp.json` at the repo root per [contracts/mcp-tools.md](contracts/mcp-tools.md); the token comes only from the developer's environment
- [ ] T032 [US4] Run [quickstart.md](quickstart.md) section 4 from Claude Code

**Checkpoint**: all four user stories work.

---

## Phase 7: Polish

- [ ] T033 [P] Add "RAG and MCP" sections to `backend/CLAUDE.md`: the corpus is fixed (changes need an approved spec); never commit FBR source files; never let an answer through without the checks; `PAKTAX_TOKEN` only from the environment
- [ ] T034 Run Ruff, mypy, Prettier and `tsc` checks, both test suites and the retrieval eval; list in the PR description the questions for the lead (embeddings approval, the manual as "the guides", the pass mark, adding the First Schedule)

---

## Dependencies & Execution Order

- **Lead approval** of the embeddings component before **T001**. Setup → Foundational (T003 →
  T004 → T007; T005, T006 alongside) → user stories.
- **US1** needs Foundational. **US2** extends US1's `service.py` (T017 after T013). **US3** needs
  search (T008) and the corpus (T007); T022 sets the cut-off used by US2's refusal. **US4** needs
  search (T008), 003, 004 and the token model (T003).
- `service.py` is edited by T013 → T017; `AskPage.tsx` by T014 → T018; `settings.py` by T008 →
  T022. T008 sets a provisional relevance cut-off that US2's refusals use; T022 tunes it from the
  eval.

## Parallel Opportunities

- T005 and T006 together; T009 and T010 together; T026, T027 and T029 together.
- US3 (T020–T025) and US4 (T026–T032) can proceed in parallel once Foundational is done.

## Implementation Strategy

1. **Corpus first:** sources, splitting, build, search (Foundational).
2. **MVP = User Story 1:** cited, checked answers.
3. **US2:** honest refusals and the limit; **US3:** the eval gate; **US4:** MCP tools and tokens.
4. **Polish**, then one implementation PR listing the questions for the lead.

GitHub issues for these tasks are titled `[006] T0NN: <description>`.
