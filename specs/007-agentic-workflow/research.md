# Research: Agentic Workflow (007)

Each decision: what was chosen, why, and what else was considered.

## R1. Run storage

- **Decision:** one `workflow_runs` row per user and tax year (unique). Steps 1–3 outputs are
  stored as JSON on the row with the fingerprint they were made for; the tax result is not stored.
- **Rationale:** resuming needs the step and outputs (FR-002); 004 recalculates on every request,
  so storing the result would create a second, possibly stale copy.
- **Alternatives:** a table per step output (more joins, no gain at this size); storing the result
  (stale-copy risk; 008's PDF can recalculate too).

## R2. State machine

- **Decision:** steps `document → validate → research → gate → result → done`. A pure function
  `next_step(run, current_fingerprint, event)` returns the new step; events are `start`, `steps_ok`,
  `missing_salary`, `approve`, `back`, `mark_done`, `inputs_changed`. `back` from the gate returns to
  `document`.
- **Rationale:** the README asks for a state machine; a pure function is unit-tested for every
  step/event pair without a database or AI.
- **Alternatives:** a state-machine library (a dependency for six states); steps as free-form
  flags (illegal combinations possible).

## R3. Fingerprint and the gate

- **Decision:** `fingerprint(user)` = SHA-256 over the user's confirmed documents (id, confirmed
  time, field values, sorted) and the profile's `tax_year` and `on_atl`. On every request the
  service compares it with the fingerprint stored with the step outputs: if different, it re-runs
  steps 1–3 and moves the run to `gate` (or `document` if no salary certificate), clearing the
  approval. The result step requires `approved_fingerprint == current fingerprint`; otherwise `409`.
- **Rationale:** one cheap check covers every kind of input change (FR-013) without hooks into
  003 or 002, and makes the gate a backend rule (FR-009).
- **Alternatives:** events from 003/002 when data changes (couples features, easy to miss one);
  re-running on a timer (stale in between).

## R4. Agents and tools

- **Decision** (amended 2026-11-12): each agent is one Gemini call with function calling and a
  structured final answer (`google-genai`, as 003–006), through a small client interface with a
  fake for tests. Tools are read-only functions
  in `app/workflow/tools.py`, the same functions 006's MCP tools call:
  - document agent: `list_confirmed_documents()` (types, labels, upload pages);
  - validation agent: `validate_salary_information(...)` and `check_bank_certificate(...)`
    (003's rules), called per confirmed certificate;
  - research agent: `search_tax_documents(query)` (006's search), up to 3 queries.
  No tool confirms, edits, approves or calculates.
- **Rationale:** README asks for document, validation and research agents; tool use is the
  agentic part, and read-only tools make FR-010 true by construction. Reusing 006's functions
  keeps one implementation.
- **Alternatives:** agents calling the MCP server as clients (design approach C, rejected); one
  orchestrator agent (approach B, rejected); no tools, just prompts (not agentic, nothing to learn).

## R5. Checks and fallbacks

- **Decision** (amended 2026-11-12): document and validation text pass 004's number check
  (`app.explain.number_check`: every number equals a figure given to the agent; no number words or
  scales); research text passes 006's checks (`app.rag.checks.checked_citations`: citations among
  the passages search returned; every number, with its scale, in a cited passage). On failure,
  timeout (15 s per step, as 006), a reached question limit (R9) or no API key, the step uses its code-written result: the missing-document list, the raw rule issues, or
  the top passages from a fixed query per income type (salary; bank profit).
- **Rationale:** FR-005 to FR-007; reuses existing checks; the run always completes (SC-005).
- **Alternatives:** retrying the call (slower, same failure modes); blocking the run (fails
  SC-005).

## R6. Model setting

- **Decision** (amended 2026-11-12): `WORKFLOW_MODEL` setting, default `gemini-3.5-flash-lite`,
  `WORKFLOW_EFFORT` default `minimal`, short output, in `app/settings.py` like 003's
  `EXTRACTION_MODEL`, 004's `SUMMARY_MODEL` and 006's `ANSWER_MODEL`.
- **Rationale:** one consistent way to choose models across features.

## R7. API

- **Decision:** `/api/workflow` (protected by `current_user` and 002's `require_profile`):
  `GET` current run (advancing steps 1–3 if inputs changed), `POST /start`, `POST /approve`,
  `POST /back`, `POST /done`, and `GET /result` (calls 004's tax service; `409` without a valid
  approval).
- **Rationale:** each user action is one endpoint; the gate check lives in one place.
- **Alternatives:** a single `POST /event` (less clear contract and errors).

## R8. Frontend

- **Decision:** `WorkflowPage` at `/workflow` with a step indicator, each step's message, the gate
  screen (figures, profile, issues, passages, Approve / Go back), and the result (004's breakdown
  component, passages, label, "Mark done"). Linked from the home page.
- **Rationale:** sits alongside the other pages (design decision); reuses 004's breakdown display.

## R9. Shared question limits (added 2026-11-12)

- **Decision:** each time steps 1–3 run (start, restart, or a re-run after an input change), the
  service first calls 006's `app.rag.service.use_question` for the user, so the run counts as
  one question against the same limits as Ask and MCP search (30 an hour per user, the app's 200
  a day; `ASK_DAILY_LIMIT`), under the same lock. Past a limit, no agent is called: each step uses
  its code-written result (R5), marked as such, and the run still reaches the gate (SC-005).
- **Rationale:** the agents and search spend the same free Gemini quota as extraction,
  summaries and Ask; without this, guided runs could exhaust it.
- **Alternatives:** counting each agent call (three per run; would use up a user's hour three
  times as fast for one action); a separate workflow limit (two limits on one quota); blocking
  the run at a limit (fails SC-005).

## R10. Navigation and progress (added 2026-11-12)

- **Decision:** the page's navigation label is "Guided filing" (route `/workflow`), added to
  `FILING` in `frontend/src/components/MainNav.tsx`: a top-bar link on computers and an entry in
  the Filing sheet on phones (006's navigation, design addendum 2026-11-11), and still linked
  from Home (R8). Steps 1–3 run in one request; while it waits, the page shows each step's
  message in turn ("Checking your documents…", "Checking the figures…", "Finding the law that
  applies…"), timed on the page as 006's Ask page times its progress, not reported step by step
  by the backend.
- **Rationale:** the navigation was designed for this entry; one request keeps the backend
  simple, and the messages tell the user why it takes several seconds.
- **Alternatives:** one request per step (three round trips and partial runs to handle);
  streaming step results (shows text before its checks pass).
