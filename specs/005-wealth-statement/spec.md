# Feature Specification: Wealth Statement and Reconciliation

**Feature Branch**: `005-wealth-statement`

**Created**: 2026-11-03

**Status**: Draft

**Input**: User description: "Wealth statement and reconciliation (README milestone 5). A salaried TY2026 user lists assets and liabilities as rows, last year's net assets, other inflows and outflows; salary, the exempt part of salary, bank profit and tax already taken are filled in read-only from confirmed certificates. Code computes net assets, the increase, inflows minus outflows and the unreconciled amount; zero means reconciled; a non-zero result is described in words with a code-written 'where to look' checklist, never amounts. A step-by-step breakdown citing form lines is always shown; an AI summary only if every number in it appears in the breakdown. Hand-worked examples signed off before the code. Four provisional rules asked of the lead." Source design: `docs/superpowers/specs/2026-11-03-wealth-statement-design.md`, which cites §116 of the Income Tax Ordinance, 2001 and the TY2026 return form (SRO 1495(I)/2026) line by line.

## Clarifications

### Session 2026-11-03

- Q: If a confirmed salary certificate shows gross salary lower than taxable salary, what should the wealth page do? → A: Show "not ready", name the certificate, and ask the user to check it (delete and re-upload if wrong).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Enter my wealth statement and see whether it reconciles (Priority: P1)

A salaried user whose certificates are confirmed opens the wealth statement page, lists what they
own and what they owe as on 30 June 2026, enters last year's net assets and this year's other
money in and out, and sees whether the statement reconciles, in the same structure as the IRIS
screens.

**Why this priority**: every resident individual filing a return must file a wealth statement
and reconciliation (§116(2)), and IRIS won't accept the return until the unreconciled amount is
zero; this is the feature's core promise.

**Independent Test**: with confirmed synthetic certificates and a hand-worked example statement,
enter its rows and amounts, and compare every figure shown with the hand-worked result.

**Acceptance Scenarios**:

1. **Given** asset rows (category, description, value at cost) and liability rows (description,
   creditor, amount), **When** the user views the result, **Then** net assets this year equal
   total assets minus total liabilities.
2. **Given** last year's net assets, **When** the result is shown, **Then** the increase or
   decrease equals this year's net assets minus last year's.
3. **Given** confirmed certificates, **When** the page opens, **Then** taxable salary (line 7031),
   the exempt part of salary (gross minus taxable, line 7032), bank profit (line 7033) and the
   tax deducted and withheld (as an outflow) are filled in, read-only, each showing which
   certificate it came from.
4. **Given** all inflows and outflows, **When** the result is shown, **Then** the unreconciled
   amount equals inflows minus outflows minus the increase, and zero is shown as "reconciled".
5. **Given** the user leaves and returns, **When** they reopen the page, **Then** their rows and
   amounts are still there and the result is recalculated.
6. **Given** any result, **When** it is shown, **Then** a clear "not yet reviewed by a tax
   practitioner; not tax advice" label is visible.

---

### User Story 2 - Understand the result and where to look (Priority: P2)

The user sees how each figure was reached, step by step with the form line for each, and when the
statement doesn't reconcile, by how much, in which direction, and where to look, without being
told what numbers to enter.

**Why this priority**: a bare "unreconciled: Rs 40,000" leaves the user stuck; the README requires
an explanation of the computed result, and the explanation must never suggest amounts that would
force a zero.

**Independent Test**: for hand-worked examples with a gap in each direction, check the wording,
the direction and the checklist; then give the summary check a summary containing a wrong number
and confirm it is not shown.

**Acceptance Scenarios**:

1. **Given** any result, **When** the user views it, **Then** a step-by-step breakdown shows
   each step's inputs, the form line it corresponds to, and its result.
2. **Given** the user's assets grew more than their inflows minus outflows explain, **When** the
   result is shown, **Then** it says so in words with the amount, and lists where to look for a
   missing inflow (gift, inheritance, foreign remittance, family contribution, other exempt
   income).
3. **Given** inflows minus outflows exceed the growth in assets, **When** the result is shown,
   **Then** it says so in words with the amount, and lists where to look for a missing asset
   (e.g. a bank account, vehicle or jewellery) or an unfilled expense category.
4. **Given** any non-zero result, **When** the "where to look" list is shown, **Then** it never
   contains an amount to enter.
5. **Given** a result, **When** a plain-language summary is produced, **Then** it is shown only
   if every number in it appears in the breakdown; otherwise, or if the summary service is
   unavailable, only the breakdown is shown.

---

### User Story 3 - Honest limits and staying in sync (Priority: P3)

When required inputs are missing or the case isn't supported, the app says so instead of
producing a result, and it tells the user when their certificates changed after they last saved
the statement.

**Why this priority**: overstating certainty is the most harmful failure (constitution, Principle
IV); certificates can be corrected (deleted and re-uploaded) after the statement is filled in.

**Independent Test**: try each not-ready case and confirm the message and that no reconciliation
figure is shown; delete and re-confirm a certificate after saving and confirm the notice appears.

**Acceptance Scenarios**:

1. **Given** last year's net assets aren't entered, or no confirmed salary certificate exists,
   **When** the user opens the result, **Then** they are told what is missing and no
   reconciliation figure is shown.
2. **Given** summed bank profit above Rs 5 million, **When** the result is requested, **Then** the
   user is told this case isn't supported yet (the same message as the tax page), and no figure is
   shown.
3. **Given** a confirmed salary certificate whose gross salary is lower than its taxable salary,
   **When** the result is requested, **Then** the user is told which certificate to check (and to
   delete and re-upload it if wrong), and no figure is shown.
4. **Given** a confirmed certificate was added or deleted after the statement was last saved,
   **When** the user opens the page, **Then** a notice says the certificate figures changed and
   asks them to check the result.
5. **Given** an auto-filled figure, **When** the user tries to change it on this page, **Then**
   they can't, and are told to correct the certificate instead.

### Edge Cases

- Unreconciled amount of exactly zero: shown as "reconciled", with no checklist.
- Net assets fell from last year (a decrease): handled the same way; the increase is negative.
- Liabilities larger than assets: net assets are negative and shown as such.
- No bank certificates: lines 7033 and the bank's withheld tax are zero.
- Gross salary equal to taxable salary: line 7032's salary part is zero.
- Gross salary lower than taxable salary on a certificate: not ready; the user is told which
  certificate to check (see User Story 3).
- Certificate figures with paisa: summed per type and rounded to whole rupees per §219 before use,
  so a statement can reconcile to exactly zero.
- An asset or liability row with a zero amount: allowed and counted as zero.
- Bank profit exactly Rs 5,000,000: supported ("exceeds" triggers the limit, as in 004).
- No asset rows at all: allowed; total assets are zero.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Users MUST be able to add, edit and delete asset rows (category from the IRIS list,
  description, value at cost) and liability rows (description, creditor, amount) for TY2026.
- **FR-002**: Users MUST be able to enter net assets as on 30 June 2025, other exempt income,
  foreign remittance, inheritance, gifts received, contribution in expenses by family members,
  personal expenses per IRIS expense category, and gifts given.
- **FR-003**: All user-entered amounts MUST be whole rupees; asset, liability, inflow and outflow
  amounts MUST NOT be negative.
- **FR-004**: The system MUST fill in, read-only, from confirmed certificates only (feature 003),
  summed per type and rounded per §219: taxable salary (line 7031); gross minus taxable salary as
  exempt income (line 7032) *(provisional)*; bank profit (line 7033) *(provisional)*; and tax
  deducted and withheld as an outflow *(provisional)*. Each MUST show its source certificate(s).
- **FR-005**: The system MUST compute net assets (total assets minus total liabilities), the
  increase or decrease from last year, total inflows, total outflows, and the unreconciled amount
  (inflows minus outflows minus the increase), using exact arithmetic.
- **FR-006**: The system MUST show the statement as "reconciled" only when the unreconciled
  amount is exactly zero.
- **FR-007**: For a non-zero result, the system MUST state the amount and direction in words and
  show a fixed list of where to look for that direction; the list MUST NOT contain amounts and
  MUST NOT be written by an AI.
- **FR-008**: No reconciliation figure MUST be produced, adjusted or checked by an AI
  (constitution, Principle I).
- **FR-009**: The system MUST show a step-by-step breakdown for every result, each step naming
  its form line (SRO 1495(I)/2026 code).
- **FR-010**: An AI-written summary MAY be shown only when every number in it appears in the
  breakdown; otherwise it MUST be omitted. The same check as the tax page MUST be used.
- **FR-011**: The system MUST refuse to show a result, with a reason, when last year's net assets
  are missing, no confirmed salary certificate exists, summed bank profit exceeds Rs 5
  million, or any confirmed salary certificate's gross salary is lower than its taxable salary
  (naming that certificate).
- **FR-012**: The user's entries MUST be saved; the result MUST be recalculated each time and
  never stored as final.
- **FR-013**: The system MUST show a notice when the set of confirmed certificates changed since
  the statement was last saved.
- **FR-014**: Every result MUST carry a visible "not yet practitioner-reviewed; not tax advice"
  label.
- **FR-015**: Worked examples (reconciled; each direction of gap; a decrease; liabilities larger
  than assets; several certificates; paisa rounding; each not-ready case) MUST be verified by hand
  against the cited FBR sources and signed off before the reconciliation is built, and MUST
  become its tests.
- **FR-016**: A user MUST only ever see and change their own wealth statement.

### Key Entities

- **Wealth statement**: one per user and tax year: last year's net assets, other inflows,
  outflows, personal expenses per category, when it was last saved, and which confirmed
  certificates were used at that time.
- **Asset row**: category, description, value at cost.
- **Liability row**: description, creditor, amount.
- **Reconciliation result** (never stored): net assets, increase, inflows and outflows by line,
  unreconciled amount, direction, the "where to look" list, the breakdown, any not-ready reason,
  the optional verified summary, and the certificate-change notice.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of the signed-off worked examples produce exactly the hand-worked figures, to
  the rupee.
- **SC-002**: 0 summaries containing a number absent from the breakdown are ever shown (tested
  with deliberately wrong summaries).
- **SC-003**: 0 "where to look" lists contain an amount.
- **SC-004**: A user can enter a statement with 10 assets, 2 liabilities and all expense
  categories, and see the result, in under 10 minutes.
- **SC-005**: Every not-ready case in User Story 3 shows a reason and no reconciliation figure.
- **SC-006**: The result appears within 5 seconds of opening the page.

## Assumptions

- The tax year comes from the user's taxpayer profile (feature 002; today only 2025-26): the
  wealth page opens on it (amended 2026-11-04).

- MVP users are resident salaried individuals whose only income is salary and bank profit;
  synthetic data only.
- The form lines and codes are from the TY2026 return form, SRO 1495(I)/2026, which prints no
  formula; the formula is from FBR's IRIS FAQ.
- Four provisional rules are asked of the lead in the pull request and may change: (1) income is
  entered gross with tax deducted and withheld as an outflow; (2) bank profit goes on line 7033;
  (3) last year's net assets are typed by the user; (4) gross minus taxable salary is exempt
  income received.
- Correcting a confirmed certificate means deleting it and uploading again (feature 003); this
  feature doesn't change that.
- Out of scope: foreign assets and the §116A statement, business capital and liabilities, assets
  disposed of or transferred, the adjustments lines (7034, 7098), market-value reporting, revised
  statements, earlier years' reconciliations, PDF export (feature 008), and the guided flow
  across pages (feature 007).
