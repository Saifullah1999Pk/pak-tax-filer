# Research: Policy-Based Bill Approval Agent (009)

No open clarifications remained after the spec's session of 2026-11-13; these record the design
choices for the plan.

## R1. One new area, reusing the shared pieces

- **Decision:** `app/claims/` with its own models, service and router (design approach A). It
  reuses 003's `Storage` and `check_file` (PDF, JPEG, PNG; 10 MB; 5 pages), 003's
  `extraction_attempts` for limits (R4), 004's `app.explain.number_check` (R8) and 008's
  `ai_call` (two new features: `claims_reading`, `claims_explanation`).
- **Rationale:** the tax features stay untouched; nothing is copied.
- **Alternatives:** a new document type in 003 (fixed fields per type don't fit any-number lines);
  a fully autonomous agent deciding (breaks Principle I). Both rejected in the design.

## R2. Policies as year-keyed data with sources

- **Decision:** `app/claims/policies/` mirrors `app/tax/rates/`: `POLICIES["2025-26"]` holds
  `MEDICAL` and `MOBILE`, frozen dataclasses: categories, banned categories, budget and its period
  (`policy_year` or `month`), the banned-items setting (`exclude_line` | `reject_bill`), the
  changed-total share (`0.10`), and `source` ("Synthetic demo company medical policy, 2026;
  provisional, pending the accounts department"). Medical: Rs 100,000 a year; banned
  `baby_product`, `energy_drink`, `equipment`. Mobile: Rs 3,000 a month; banned `device`.
- **Rationale:** Principle II for company rules; one place to change a provisional figure.
- **Alternatives:** a policy table edited in the app (out of scope: no in-app editing); YAML
  (the tax rates set the precedent of typed Python data).

## R3. A pure decision engine

- **Decision:** `engine.decide(policy, lines, budget_left, facts) -> Decision`, where `facts`
  holds the confirmed and read totals, the bill date or period and whether reading failed. Per
  line: `approved`, `cut` (with the rule) or `flag` (an "other" line); claim flags for the
  reasons in FR-009; approved = allowed lines' sum, capped at `budget_left`; with
  `reject_bill`, any banned line approves Rs 0. All `Decimal`, two decimal places, no rounding
  beyond the bill's own paisa. `.importlinter` adds `app.claims.engine` and
  `app.claims.policies` as sources that may not import the AI modules. Worked examples
  (`tests/claims/worked_examples.yaml`) are signed off before the engine exists.
- **Rationale:** Principle I and VI exactly as 004 and 005 did.

## R4. Reading a bill

- **Decision:** `GeminiBillReader.read(policy, content, media_type) -> BillReading`: a JSON
  schema with `is_bill`, `bill_date`, `period_start`, `period_end`, `total`, and `lines`
  (`description`, `amount`, `category` from the policy's list), each with a confidence. Same
  client settings as 003 (60-second deadline, 3 attempts on 500/502/503, the 504 and network
  failures marked `service_failed`). Limits: `extraction_attempts.kind` (`document` | `bill`);
  10 bill readings per user per 24 hours, counted with kind `bill`; the app-wide 100 counts both
  kinds; a `service_failed` try deletes its attempt, as #43 does.
- **Rationale:** reuses a proven client and limit; bills never use up tax-document tries.

## R5. Confirming, editing, the changed-total flag

- **Decision:** `PUT /api/claims/{id}/lines` replaces the lines, date or period and total while
  the claim is `needs_confirmation` (adds and removes allowed); `POST …/confirm` then decides.
  Each line keeps what was read (`read_*`) beside what was confirmed. Flag when
  `|confirmed_total − read_total| > 10% of read_total` (policy setting); a bill that couldn't be
  read has no read total and is always flagged.
- **Rationale:** FR-003, the clarifications; server-side, so the screen can't skip it.

## R6. Budget as a ledger, locked at each decision

- **Decision:** budget left = policy budget − the sum of `approved_amount` of the employee's
  decided claims for the same policy and `period_key` (`2025-26` for medical, `2026-03` for a
  March mobile bill). Every decision (automatic or an approver's) takes a transaction-scoped
  advisory lock on (employee, policy, period) before reading the sum, so two decisions at once
  can't both spend the last rupees.
- **Rationale:** FR-007, FR-008, SC-003; the same lock pattern as 003's and 006's limits.

## R7. The approver role and access

- **Decision:** `users.is_approver` (default false), set only by `python -m app.cli
  make-approver --email …` (and `remove-approver`); `/api/auth/me` returns it so the page shows
  Approvals. The queue lists flagged claims whose owner isn't the approver. An approver may read a
  claim (and its file) only if it is flagged and not their own; deciding needs the same, plus the
  amount ≤ the eligible amount recomputed under R6's lock, and a non-empty note. Everything else is
  `404`, as the API conventions say. Tests cover the matrix: owner, other employee, approver
  (others' flagged, own, others' decided).
- **Rationale:** FR-012–FR-014, SC-004; the smallest role model that works.

## R8. The explanation

- **Decision:** `GET /api/claims/{id}/explanation` (like 004's summary: never delays the
  decision): Gemini writes 2–3 sentences from the decision's facts; shown only if
  `uses_only_numbers_from(text, decision_text)` passes, else a template built by code ("Rs 4,200
  approved. Baby products aren't covered: Rs 800 cut. Rs 95,800 of your medical budget left.").
  Response says which (`fallback: true`).
- **Rationale:** FR-011, SC-005; reuses 004's check and 007's fallback idea.

## R9. Measuring the reading

- **Decision:** `evals/claims/`: generate at least 10 synthetic bills (reportlab, as 003's eval),
  each with its true lines and categories; `run` scores line-amount accuracy (target ≥ 90%) and
  category accuracy (≥ 85%) (SC-006). Run with the real key before the PR, report pasted in it,
  as 003's eval is; a CI workflow like `extraction-eval.yml` runs it when the reader changes.
- **Rationale:** Principle VI (measured AI).

## R10. Pages

- **Decision:** `/claims` (choose policy, upload; your claims and budget left per policy),
  `/claims/:id` (lines table with edit, add and remove; date or period; total; Confirm; then the
  decision: each line's result and rule, approved, cut, budget left, the explanation, the
  provisional label; Withdraw while allowed), `/approvals` (approvers only: the queue; opening a
  claim shows it read-only with Approve amount + note or Reject + note).
- **Rationale:** the spec's three stories; the frontend computes nothing (every amount comes
  from the API).

## R11. End-to-end

- **Decision:** the fake Gemini answers a bill schema (recognised by its `lines` property) with a
  synthetic medical bill (medicines Rs 4,200, a baby product Rs 800) or mobile bill (plan Rs
  2,200); explanations get a sentence with no numbers. A Playwright global setup makes two
  approvers with the CLI in the e2e stack. Tests: a medical bill decided automatically (Rs 4,200
  approved, Rs 800 cut); a flagged claim decided by the other approver; the approver never sees
  their own.
- **Rationale:** the same flows as the spec's stories, on the real stack.
