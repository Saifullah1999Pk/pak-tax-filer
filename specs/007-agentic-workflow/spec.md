# Feature Specification: Agentic Workflow

**Feature Branch**: `007-agentic-workflow`

**Created**: 2026-11-04

**Status**: Draft

**Input**: README milestone 7: "Agentic workflow wiring (document/validation/research agents,
state machine, human-approval gate before calculation)"; MVP: "document → validate → research →
calculate → explain → review with a mandatory human-approval gate before calculation". Source
design: `docs/superpowers/specs/2026-11-04-agentic-workflow-design.md`.

**Amended 2026-11-12** (design addendum): the stack as built (Gemini; 006's search and limits),
"Guided filing" in the navigation, progress shown while the steps run (FR-017 to FR-019). The
lead's bill-approval agent idea is not part of this feature.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Guided run up to the approval gate (Priority: P1)

A logged-in user with a taxpayer profile starts a guided run. The document step checks their
certificates and says what's missing; the validation step checks each confirmed certificate and
explains any problem; the research step finds the tax-law passages that apply to them, each with
its citation. The run then stops at the approval gate, showing everything the calculation would
use.

**Why this priority**: it is the agentic part of the milestone and leads to the gate, which the
constitution requires before any calculation.

**Independent Test**: with a synthetic user who has one confirmed salary certificate and one
confirmed bank certificate, start a run and check that it reaches the gate showing the confirmed
figures, the profile's tax year and ATL status, any validation issues, and cited passages; with
no confirmed salary certificate, check that it stops at the document step saying what's missing.

**Acceptance Scenarios**:

1. **Given** a user with no confirmed salary certificate, **When** the run starts, **Then** the
   document step says a confirmed salary certificate is needed, links to the upload page, and the
   run does not move on.
2. **Given** a user with a confirmed salary certificate and no bank certificate, **When** the
   document step runs, **Then** it notes the bank certificate is optional and moves on.
3. **Given** a confirmed certificate with a rule issue (e.g. taxable salary above gross), **When**
   the validation step runs, **Then** the issue is explained, naming the certificate, and the run
   still moves on (issues warn, they don't block).
4. **Given** the research step, **When** it finishes, **Then** every passage shown has its source
   and location, and every number in its note appears in a cited passage.
5. **Given** the run reaches the gate, **When** the user looks at it, **Then** it shows the
   confirmed figures, tax year and ATL status from the profile, the validation issues, and the
   passages, with "Approve" and "Go back" choices.
6. **Given** the run at any step, **When** the AI is unavailable or its text fails a check,
   **Then** the step shows a plain, code-written result instead and the run continues.

---

### User Story 2 - Approve, calculate, explain and review (Priority: P2)

At the gate the user approves. The run calculates the tax with the existing tax engine, shows the
step-by-step breakdown with the research passages as "where this comes from", and the user marks
the run done.

**Why this priority**: completes the flow end to end; depends on Story 1 reaching the gate.

**Independent Test**: approve at the gate and check the result equals the Tax page's result for
the same user, the breakdown and passages are shown with the practitioner label, and marking the
run done is recorded; then check that calculation is refused without an approval.

**Acceptance Scenarios**:

1. **Given** the gate, **When** the user approves, **Then** the tax is calculated and the result
   matches the Tax page's figures for the same inputs.
2. **Given** no approval has been recorded, **When** a calculation for the run is requested by
   any route, **Then** it is refused.
3. **Given** a result, **When** it is shown, **Then** the breakdown, the cited passages and the
   "not yet practitioner-reviewed" label are visible.
4. **Given** a result, **When** the user marks the run done, **Then** the run shows as done with
   the date.
5. **Given** any agent step, **When** its output is checked, **Then** it contains no action that
   confirms a certificate, changes a figure or approves the gate.

---

### User Story 3 - Changes and resuming (Priority: P3)

A user who leaves mid-run comes back to the same step. A user who changes their inputs (adds,
deletes or re-confirms a certificate, or changes their profile) has the run re-check them and
return to the gate for a fresh approval.

**Why this priority**: keeps the gate meaningful over time; only matters once a run exists.

**Independent Test**: approve a run, then add a certificate and check the run re-runs the first
three steps and waits at the gate with the old result gone; log out mid-run and check the run
resumes at the same step.

**Acceptance Scenarios**:

1. **Given** a run at any step, **When** the user leaves and returns, **Then** it resumes at the
   same step.
2. **Given** an approved or done run, **When** the user adds, deletes or re-confirms a certificate
   or changes their profile, **Then** the run re-runs the document, validation and research steps
   on the new inputs and waits at the gate; the earlier result is no longer shown.
3. **Given** a change before approval, **When** the user returns to the run, **Then** the first
   three steps have been re-run on the new inputs.
4. **Given** a done run, **When** the user starts a new run, **Then** it replaces the old one;
   there is one active run per user and tax year.

---

### Edge Cases

- The user deletes their only confirmed salary certificate after approval: the run goes back,
  re-runs, and stops at the document step.
- The research step finds no passage above the relevance cut-off: it says so in plain words and
  the run continues; the result still shows the breakdown's own rule locations.
- The tax engine blocks the calculation (e.g. a provisional rule): the result step shows the
  engine's reason, exactly as the Tax page does.
- Two tabs approve at once: one approval is recorded; the result is the same.
- A user without a profile opens the run: sent to set up the profile first (feature 002).
- The user (or the whole app) has reached the tax assistant's question limit: the steps use
  their plain results, marked as such, and the run still reaches the gate (added 2026-11-12).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: A logged-in user with a profile MUST be able to start a guided run with the steps
  document → validate → research → approval gate → calculate → explain → review, alongside the
  existing pages, which keep working on their own.
- **FR-002**: The run MUST record its current step and resume there; there MUST be at most one
  active run per user and tax year.
- **FR-003**: The document step MUST require at least one confirmed salary certificate, treat the
  bank certificate as optional, say in plain words what is missing, and link to the upload pages.
- **FR-004**: The validation step MUST apply feature 003's rule checks to each confirmed
  certificate and explain each issue, naming the certificate; issues MUST NOT block approval and
  MUST be shown again at the gate.
- **FR-005**: The research step MUST search only feature 006's corpus and show each passage with
  its source and location; every number in its note MUST appear in a cited passage.
- **FR-006**: Every number in document and validation step text MUST match a figure the step was
  given (feature 004's number check).
- **FR-007**: Text that fails a check, or a step whose AI is unavailable, MUST be replaced by a
  plain code-written result (missing-document list, rule issues, passages found) and the run MUST
  continue.
- **FR-008**: The gate MUST show the confirmed figures, the profile's tax year and ATL status, the
  validation issues and the passages, and offer approve or go back.
- **FR-009**: No calculation for the run MUST happen unless the user has approved since the last
  change to the inputs. This MUST be enforced by the backend.
- **FR-010**: No agent MUST be able to confirm a certificate, change a figure, or approve the gate
  (Principle III).
- **FR-011**: The calculation MUST use feature 004's engine on confirmed certificates and the
  profile only; no tax figure MUST come from an AI (Principle I).
- **FR-012**: The result MUST show 004's breakdown, the research passages and the "not yet
  practitioner-reviewed" label, and MUST match the Tax page's result for the same inputs.
- **FR-013**: Any change to the inputs after the run starts (certificate added, deleted or
  re-confirmed; profile changed) MUST re-run the document, validation and research steps and
  return the run to the gate, removing any earlier result.
- **FR-014**: The user MUST be able to mark a run done; the date is recorded.
- **FR-015**: The run MUST be visible only to its own user.
- **FR-016**: The feature MUST NOT include the wealth statement, PDF export, telemetry, filing,
  or new tax rules.
- **FR-017** (added 2026-11-12): The run MUST appear in the app's navigation as "Guided filing",
  in the Filing group (feature 006's navigation), and stay linked from the home page.
- **FR-018** (added 2026-11-12): Each run of the document, validation and research steps MUST
  count as one question against the tax assistant's limits (feature 006, FR-009a and FR-009b);
  past a limit, the steps MUST use their plain (code-written) results and the run MUST still
  reach the gate.
- **FR-019** (added 2026-11-12): While the steps run, the page MUST show what each step is doing,
  and each step MUST give its result or its plain result within 15 seconds.

### Key Entities

- **Run**: belongs to one user and tax year; its current step; when it was approved and a
  fingerprint of the inputs approved; whether and when it was marked done. The tax result is
  recalculated from the inputs, not stored (as in feature 004).
- **Step output**: what each of the document, validation and research steps produced for the
  current inputs (message, issues, passages), regenerated when the inputs change.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A synthetic user goes from confirmed certificates to an explained result through
  the run in under 3 minutes, excluding time spent reading.
- **SC-002**: In tests, 100% of calculation attempts without an approval since the last input
  change are refused.
- **SC-003**: In tests, 0 agent outputs confirm, edit or approve anything, and 0 agent texts with
  an unchecked number are shown.
- **SC-004**: The run's result equals the Tax page's result for the same inputs in 100% of 004's
  signed-off worked examples.
- **SC-005**: With the AI unavailable, 100% of runs still reach a result using the plain
  code-written step results.
- **SC-006**: After any input change, 100% of runs are back at the gate with re-run steps and no
  stale result.

## Assumptions

- Builds on feature 002 (login, taxpayer profile), 003 (confirmed certificates and rule checks),
  004 (engine, breakdown, number check, practitioner label) and 006 (corpus search and the
  functions behind its three MCP tools).
- The wealth statement stays its own page (it is not in the README's workflow); PDF export and
  telemetry are feature 008.
- One tax year (2025-26) for now, from the profile.
- Synthetic data only (Principle V); the same AI settings and key handling as 003 and 004.
