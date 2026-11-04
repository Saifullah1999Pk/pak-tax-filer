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

- **Decision:** each agent is one `anthropic` Messages call with tool use and a structured final
  answer, through a small client interface with a fake for tests. Tools are read-only functions
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

- **Decision:** document and validation text pass 004's number check (every number equals a
  figure given to the agent); research text passes 006's checks (citations among the passages
  search returned; every number appears in a cited passage). On failure, timeout (10 s) or no API
  key, the step uses its code-written result: the missing-document list, the raw rule issues, or
  the top passages from a fixed query per income type (salary; bank profit).
- **Rationale:** FR-005 to FR-007; reuses existing checks; the run always completes (SC-005).
- **Alternatives:** retrying the call (slower, same failure modes); blocking the run (fails
  SC-005).

## R6. Model setting

- **Decision:** `WORKFLOW_MODEL` setting, default `claude-opus-5-5`, effort `low`, short output,
  same pattern as 003's `EXTRACTION_MODEL` and 004's `SUMMARY_MODEL`.
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
