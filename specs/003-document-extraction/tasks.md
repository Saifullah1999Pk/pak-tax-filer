---

description: "Task list for feature 003: Document Upload + AI Extraction"
---

# Tasks: Document Upload + AI Extraction

**Input**: Design documents from `/specs/003-document-extraction/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md),
[data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md);
features 001 and 002 implemented.

**Tests**: included and written first (constitution, Principle VI). Unit and API tests use the
fake extractor (R8); only the eval (US4) calls the real API. Built first on Claude; switched to
Gemini's free tier on 2026-11-08 (tasks T033-T040).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an unfinished task)
- **[Story]**: the spec user story it serves (US1–US4)

---

## Phase 1: Setup

- [X] T001 Add `anthropic`, `pypdf` and `python-multipart` to `backend/pyproject.toml`, and `reportlab` and `Pillow` as dev dependencies, with `uv add`; update `backend/uv.lock`
- [X] T002 [P] Add settings to `backend/app/settings.py`: `ANTHROPIC_API_KEY` (optional; extraction fails with a clear reason if missing), `EXTRACTION_MODEL` (default `claude-opus-5-5`), `EXTRACTION_EFFORT` (default `low`), `UPLOAD_DIR` (default `/data/uploads`); the tax year comes from the user's profile (feature 002), not a setting
- [X] T003 [P] Add a named volume `uploads` mounted at `/data/uploads` on the `backend` service in `docker-compose.yml`, and pass `ANTHROPIC_API_KEY` to the backend from the uncommitted `.env` (empty if none); add `ANTHROPIC_API_KEY=` to `.env.example`; git-ignore `backend/evals/extraction/cases/` and `report.md`

---

## Phase 2: Foundational

- [X] T004 Create `backend/app/documents/models.py` with `Document` and `ExtractedField` exactly as in [data-model.md](data-model.md): `amount` "numeric(14,2) … never a float"; unique on (`document_id`, `name`); both deleted with their parent
- [X] T005 Create `backend/alembic/versions/0004_documents.py` (revises `0003_taxpayer_profiles`, feature 002) creating both tables and enums
- [X] T006 [P] Write `backend/tests/documents/test_normalise_rules.py`, then create `backend/app/documents/extraction/normalise.py` (amounts with commas, `Rs.`/`PKR`, spaces or brackets → `Decimal`; tax year → `2025-26` form) and `backend/app/documents/extraction/rules.py` (the rules in spec User Story 1 scenario 5; each failure returns the field names and a reason)
- [X] T007 [P] Create `backend/app/documents/extraction/schemas.py`: Pydantic output models per document type per research R2 (`value`, `confidence`, `page`, `label` per field; no identity fields)
- [X] T008 Create `backend/app/documents/extraction/client.py`: an `Extractor` interface; `ClaudeExtractor` per research R1 (official SDK; PDF as `document` block, image as `image` block; structured output from T007; model and effort from settings; server-side refusal fallback; 60 s timeout; typed exception handling most-specific first; returns parsed result or a failure reason); and `FakeExtractor` returning recorded results for tests
- [X] T009 Create `backend/app/documents/extraction/prompt.py` with the extraction instructions (figures only; say "not found" rather than guess; report the printed label and page)

**Checkpoint**: tables exist; normalisation and rules are tested.

---

## Phase 3: User Story 1 - Upload a certificate and get its figures (Priority: P1) 🎯 MVP

**Goal**: upload, validate, store, extract, rule-check.

**Independent Test**: [quickstart.md](quickstart.md), section 1.

### Tests for User Story 1 (write first, confirm they fail)

- [X] T010 [P] [US1] Write `backend/tests/documents/test_uploads.py`: a valid PDF, JPG and PNG are accepted; a `.docx` renamed to `.pdf` (wrong magic bytes) → `415`; 10 MB + 1 byte → `413`; a 6-page PDF, an encrypted PDF and a corrupt (unreadable) PDF → `422`; nothing is sent to the extractor for refused files; stored path is `UPLOAD_DIR/<user_id>/<uuid>.<ext>`, not the uploaded name; a user without a profile → `409` "Set up your profile first."; the document's `tax_year` is the profile's
- [X] T011 [P] [US1] Write `backend/tests/documents/test_extraction.py` with `FakeExtractor`: a salary result produces 4 fields and a bank result 3, with value, confidence, page and label per [contracts/documents-api.md](contracts/documents-api.md); a rule-breaking result lowers the involved fields to `low` with `rule_reason`; an extractor failure or refusal gives status `failed` with a reason and saves no fields; an extractor result containing extra keys (e.g. a name) stores only the listed fields (FR-003)

### Implementation for User Story 1

- [X] T012 [US1] Create `backend/app/documents/uploads.py`: content-type check by magic bytes, size limit, `pypdf` page-count and encryption checks, save to `UPLOAD_DIR` per research R4; T010 passes
- [X] T013 [US1] Create `extract_document()` in `backend/app/documents/service.py`: set `extracting`, call the extractor, normalise, apply rules, save fields, set `needs_review` or `failed`; record `model`; T011 passes
- [X] T014 [US1] Create `backend/app/documents/router.py` with `POST /api/documents` (multipart `file`, `doc_type`), `GET /api/documents/{id}` and `GET /api/documents/{id}/file`, all with `current_user` and `404` for other users' documents, the upload also with feature 002's `require_profile` (its `tax_year` stamps the document and is the year the rule checks compare with); include it in `backend/app/main.py`
- [X] T015 [P] [US1] Write `frontend/src/pages/DocumentsPage.test.tsx` (demo notice shown; type choice required; progress shown while uploading; errors from `413`/`415`/`422` displayed; success navigates to the review page), then create `frontend/src/pages/DocumentsPage.tsx` (upload part) and add its route under `RequireAuth` in `frontend/src/App.tsx`
- [X] T016 [US1] Run [quickstart.md](quickstart.md) section 1 with a real API key *(2026-11-09, Saifullah, with the Gemini key: figures correct)*

**Checkpoint**: User Story 1 works on its own.

---

## Phase 4: User Story 2 - Review, correct and confirm (Priority: P2)

**Goal**: human confirmation before any figure is used (Principle III).

**Independent Test**: [quickstart.md](quickstart.md), section 2.

### Tests for User Story 2 (write first, confirm they fail)

- [X] T017 [P] [US2] Write `backend/tests/documents/test_review_confirm.py`: editing a value re-runs rules and sets `user_edited`; an invalid value → `422`; confirming the document with any unconfirmed or not-found field → `409` listing them; after confirmation edits → `409`; `confirmed_documents(user_id, tax_year)` returns only confirmed documents and returns several confirmed documents of the same type (FR-010a)

### Implementation for User Story 2

- [X] T018 [US2] Add `edit_field()`, `confirm_document()` and `confirmed_documents()` to `backend/app/documents/service.py`, and `PATCH /api/documents/{id}/fields/{name}` and `POST /api/documents/{id}/confirm` to `backend/app/documents/router.py`; T017 passes
- [X] T019 [P] [US2] Write `frontend/src/pages/ReviewPage.test.tsx` (file shown beside fields; low-confidence fields highlighted with reason; editing and confirming a field; document confirm blocked with a list of missing fields; read-only once confirmed), then create `frontend/src/pages/ReviewPage.tsx` and its route
- [ ] T020 [US2] Run [quickstart.md](quickstart.md) section 2

**Checkpoint**: User Story 2 works on its own.

---

## Phase 5: User Story 3 - Manage my documents (Priority: P3)

**Goal**: list, retry, delete; owner-only access.

**Independent Test**: [quickstart.md](quickstart.md), section 3.

### Tests for User Story 3 (write first, confirm they fail)

- [X] T021 [P] [US3] Write `backend/tests/documents/test_access.py`: user B gets `404` for every endpoint on user A's document (read, file, edit, confirm, retry, delete); the list shows only the caller's documents, newest first; retry only works on `failed` (`409` otherwise); delete removes the row, fields and file

### Implementation for User Story 3

- [X] T022 [US3] Add `GET /api/documents`, `POST /api/documents/{id}/retry` and `DELETE /api/documents/{id}` (deleting the stored file) to `backend/app/documents/router.py` and `service.py`; T021 passes
- [X] T023 [US3] Add the document list (type, upload time, status, retry and delete buttons) to `frontend/src/pages/DocumentsPage.tsx` and its test file
- [ ] T024 [US3] Run [quickstart.md](quickstart.md) section 3

**Checkpoint**: User Stories 1–3 work.

---

## Phase 6: User Story 4 - Measure extraction accuracy (Priority: P4)

**Goal**: a labelled synthetic eval and the model choice (Principle VI).

**Independent Test**: [quickstart.md](quickstart.md), section 4.

### Tests for User Story 4 (write first, confirm they fail)

- [X] T025 [P] [US4] Write `backend/tests/documents/test_eval_scoring.py`: scoring treats normalised exact matches as correct, "not found" as correct only when the truth is absent, and computes per-field, per-variant accuracy and the wrong-but-high share; the pass/fail check uses the bars in [contracts/eval.md](contracts/eval.md)

### Implementation for User Story 4

- [X] T026 [US4] Create `backend/evals/extraction/generate.py` per research R6: fixed seed; 20 cases per type; at least 4 layouts per type (varying label wording, table vs free text, amount formats); a clean PDF and a photo-like JPG of each; `ground_truth.json`; include a few rule-breaking and missing-field cases
- [X] T027 [US4] Create `backend/evals/extraction/run.py` per [contracts/eval.md](contracts/eval.md): uses the same prompt, schema, normalisation and rules as the app; Message Batches API matched by `custom_id`; `--model`; writes `report.md` with accuracy, wrong-but-high share and token cost; exit code from the bar; T025 passes
- [X] T028 [US4] Add job `extraction-eval` in its own workflow, `.github/workflows/extraction-eval.yml` (its triggers differ from ci.yml's, which apply to every job), per research R7: runs on push to `main` and `workflow_dispatch` when `backend/app/documents/extraction/**` or `backend/evals/**` change; uses the `ANTHROPIC_API_KEY` secret; never on `pull_request_target`
- [X] T029 [US4] Run the eval for `gemini-3.8-flash` and `gemini-3.5-flash-lite`; set `EXTRACTION_MODEL` to Flash-Lite if it meets the bars (its free limit is higher), otherwise Flash; record both reports in the PR description *(Done 2026-11-09: Flash-Lite passed with 280/280 fields, so it is the default; Flash timed out at Google's 60 s deadline on a PDF (504, twice) and wasn't run in full. See research R1.)*

**Checkpoint**: all four user stories work.

---

## Phase 7: Polish

- [X] T030 [P] Add a "Documents and extraction" section to `backend/CLAUDE.md`: read figures only through `confirmed_documents`; change prompt, schema or rules only together with an eval run
- [X] T031 [P] Create `.github/pull_request_template.md` with a note: PRs touching extraction must paste the local eval report (research R7)
- [X] T032 Run Ruff, mypy, Prettier and `tsc` checks, both test suites, and [quickstart.md](quickstart.md) section 5; confirm no API key or document content appears in logs

---

## Phase 8: Switch to Gemini's free tier (2026-11-08)

**Why**: no Claude key; the lead asked for "anything free" (plan.md "Stack change"; design
[2026-11-08-gemini-provider-design.md](../../docs/superpowers/specs/2026-11-08-gemini-provider-design.md)).
Nothing outside the AI call changes.

- [X] T033 Replace `anthropic` with `google-genai` in `backend/pyproject.toml` (`uv remove`, `uv add`); update `backend/uv.lock`
- [X] T034 Write tests first, then change `backend/app/settings.py`: `GEMINI_API_KEY` replaces `ANTHROPIC_API_KEY` (optional, blank = missing, kept out of repr); `EXTRACTION_MODEL` default `gemini-3.8-flash`; `EXTRACTION_EFFORT` one of `minimal`, `low`, `medium`, `high` (default `low`)
- [X] T035 Pass `GEMINI_API_KEY` instead of `ANTHROPIC_API_KEY` to the backend in `docker-compose.yml`; Saifullah renames the line in `.env.example` by hand (Claude may not read `.env*` files)
- [X] T036 Rewrite `backend/tests/documents/test_claude_extractor.py` as `test_gemini_extractor.py` (the SDK with an injected `httpx2.AsyncClient` on a mock transport: request shape, reply parsing, blocked, cut-off and empty replies, 429, 401/403, 5xx, timeout, connection error, no key), watch it fail, then replace `ClaudeExtractor` with `GeminiExtractor` in `backend/app/documents/extraction/client.py` per research R1
- [X] T037 Update `backend/tests/documents/test_eval_run.py` first, then rewrite `backend/evals/extraction/run.py` per research R6 (one request per case through the app's extractor, paced, stops cleanly at the daily limit)
- [X] T038 `.github/workflows/extraction-eval.yml` uses the `GEMINI_API_KEY` secret; `.github/pull_request_template.md` and `backend/CLAUDE.md` name `GEMINI_API_KEY`
- [X] T039 One line in each of 004-007's `plan.md`: the AI model is Gemini (free tier) per this switch; details settled when each is built
- [X] T040 All checks (both test suites, Ruff, pylint, mypy, Prettier, oxlint, tsc, build); a live upload without a key fails cleanly; no key or document content in logs

---

## Phase 9: Refinements from manual testing (2026-11-09)

- [X] T041 Tests first, then add `document_type` (`salary_certificate`, `bank_profit_certificate` or `other`) to both output schemas in `backend/app/documents/extraction/schemas.py`, ask for it in `prompt.py`, and fail a mismatch in `client.py` with a reason naming what the document looks like (FR-005a)
- [X] T042 Tests first, then teach `parse_tax_year` in `backend/app/documents/extraction/normalise.py` July-to-June periods ("1 July 2025 to 30 June 2026", "July 2025 - June 2026", "01-07-2025 to 30-06-2026")
- [X] T043 Test first, then hide the confidence of "not found" fields on `frontend/src/pages/ReviewPage.tsx`
- [X] T044 Re-run the eval for `gemini-3.5-flash-lite` (the answer's schema changed); all checks pass *(2026-11-09: first re-run 265/280, all four failed certificates were Google 503s, not the type check; with retries for 500/502/503 (c8f0e3a) it passed 280/280 with no failures)*

- [X] T045 Tests first, then refuse a wrong-type upload with `422` and keep nothing (no row, no file); a retry that finds the wrong type marks the document failed with the reason (FR-005a)
- [X] T046 Test first, then on `frontend/src/pages/DocumentsPage.tsx` open the review page only for a document ready to review; otherwise stay with the reason (and the file and type still chosen) and refresh the list

---

## Phase 10: Private bucket storage (2026-11-09, lead's request; FR-018)

- [X] T047 Add `google-cloud-storage` with `uv add`, and `UPLOAD_BUCKET` (optional; empty means the disk) to `backend/app/settings.py`, test first in `backend/tests/test_settings.py`
- [X] T048 Write `backend/tests/documents/test_storage.py` (an in-memory fake of the bucket client; no Google): with a bucket, a save goes only to the bucket as `gs://<bucket>/<user_id>/<uuid>.<ext>` with the file's media type, and is read back and deleted; without one, the disk as before; a `gs://` location from before still reads and deletes, and a disk location still reads and deletes with a bucket configured; a missing file reads as `None` and deletes quietly; then create `backend/app/documents/storage.py` (the client's calls in a worker thread)
- [X] T049 Use the storage from upload, the original-file endpoint, retry and delete in `backend/app/documents/router.py` and `service.py` (the endpoint returns the bytes with the document's media type, still owner-checked); existing tests keep passing on the disk; `conftest.py` overrides the storage instead of the upload folder
- [ ] T050 Add `UPLOAD_BUCKET` to `docker-compose.prod.yml` and the bucket steps to `docs/deployment.md` (us-central1, Standard, public access prevention enforced, uniform access; the VM's identity needs Storage read/write); run all checks

---

## Dependencies & Execution Order

- **Setup (T001–T003)** → **Foundational (T004–T009)** → stories in order.
- **US1** needs Foundational. **US2** needs US1's extraction (T013). **US3** needs US1's router
  (T014). **US4** needs the extraction code (T006–T009) only, so it can run alongside US1–US3.
- `service.py` and `router.py` are extended in order: T013/T014 → T018 → T022.
- Within each story: tests → implementation → quickstart check.

## Parallel Opportunities

- T002 and T003; T006 and T007.
- Test tasks T010, T011, T017, T021 and T025 can be written together once Foundational is done.
- Frontend tasks T015 and T019 alongside backend work.
- The whole of US4 (T025–T029) alongside US2/US3.

## Implementation Strategy

1. **MVP = User Story 1**: upload and see extracted figures.
2. **US2** makes them usable (confirmation).
3. **US3** adds housekeeping and the access tests.
4. **US4** measures accuracy and picks the model; needed before relying on extraction.
5. **Polish**, then one implementation PR with the eval reports.

GitHub issues for these tasks are titled `[003] T0NN: <description>`.
