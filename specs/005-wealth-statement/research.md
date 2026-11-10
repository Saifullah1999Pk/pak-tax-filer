# Research: Wealth Statement and Reconciliation (005)

Each decision: what was chosen, why, and what else was considered. FBR sources are in the
[design doc](../../docs/superpowers/specs/2026-11-03-wealth-statement-design.md).

## R1. Pure reconciliation core

- **Decision:** `backend/app/wealth/reconcile.py` exposes `reconcile(inputs: WealthInputs) ->
  ReconciliationResult`: no database, network, clock or AI. Steps run in a fixed order (not-ready
  checks → total assets → total liabilities → net assets → increase → inflows → outflows →
  unreconciled → direction and checklist) and each appends a breakdown step citing its form
  line.
- **Rationale:** same inputs, same output (Principle I); trivially testable; mirrors 004's
  `calculate()`.
- **Alternatives:** computing in the API route or in SQL (harder to test; SQL sums hide the
  steps).

## R2. Formula and sign

- **Decision:** net assets = Σ assets − Σ liabilities (703001); increase = net assets − previous
  net assets (703003); inflows (7049) = Σ inflow lines; outflows (7099) = Σ outflow lines;
  **unreconciled (703000) = inflows − outflows − increase**. Zero → reconciled. Positive →
  "inflows exceed the growth in your assets by Rs X"; negative → "your assets grew Rs X more
  than your inflows explain" (X is the absolute value).
- **Rationale:** FBR's IRIS FAQ: the change in wealth must equal inflows minus outflows; the
  TY2026 screen prints no formula, so the sign is fixed here once and users only see words.
- **Alternatives:** TY2019 form's printed "[23-24-25]" (omits the increase line and counts
  personal expenses separately from outflows; not the TY2026 layout).

## R3. Personal-expense categories

- **Decision:** the TY2026 screen (SRO 1495 PDF p. 41) shows a scrolled list: Asset Insurance /
  Security, Medical, Educational, Club, Functions / Gatherings, Donation, Zakat, Annuity, Profit
  on Debt, Life Insurance Premium etc., Other Personal / Household Expenses, Foreign Travelling,
  Local Travelling. The hidden top of the list is taken from the TY2019 form's Annex-F (SRO 1160
  of 2019): Rent, Rates / Taxes / Charge / Cess, Vehicle Running / Maintenance, Electricity,
  Water, Gas, Telephone. Categories are stored by name as an enum; only the total (7089) is cited
  in the breakdown, since TY2026 sub-codes aren't visible.
- **Rationale:** both lists are FBR's own; the TY2026 tail matches TY2019's order except that
  Travelling is split into Foreign and Local.
- **To confirm:** the hidden items against the live IRIS screen; listed in the PR as a check, not
  a question.
- **Alternatives:** one "personal expenses" total (less guidance; users lose the IRIS structure).

## R4. Asset categories

- **Decision:** enum from the TY2026 screens (PDF pp. 38–39): immovable property; investments
  (stocks, bonds, etc.); advances, prepayments and receivables; cash in hand; bank accounts;
  equipment; animals; motor vehicles; precious possessions; household effects; personal items;
  assets held in others' names (7014); any other asset (7013). Each row's value is at cost (FBR
  instructions).
- **Alternatives:** free text category (can't group like IRIS).

## R5. Inputs from certificates and rounding

- **Decision:** `backend/app/wealth/service.py` builds `WealthInputs` from 003's
  `confirmed_documents(user_id, tax_year)`: sums `taxable_salary`, `gross_salary`,
  `tax_deducted` across salary certificates and `profit_amount`, `tax_withheld` across bank
  certificates, then rounds each sum to whole rupees with `ROUND_HALF_UP` (§219), the rounding
  rule stored in 004's TY2026 rates. Line 7032's salary part = gross − taxable (provisional rule
  4); tax deducted + withheld is one outflow line "tax deducted and withheld at source"
  (provisional rule 1).
- **Rationale:** one source of truth for confirmed figures; whole rupees let a statement reach
  exactly zero.

## R6. Not-ready checks

- **Decision:** checked first; any failure returns `not_ready_reason` and no figures:
  `needs_previous_net_assets`, `no_confirmed_salary_certificate`, `profit_over_limit` (limit read
  from 004's TY2026 rates, `profit_limit`, so the two pages agree), `gross_below_taxable`
  (with the certificate's id and file name).

## R7. Storage and the certificate-change notice

- **Decision:** the user's entries are stored (data model); results never are. On each save the
  statement records `saved_at` and `certificate_ids`, the sorted ids of confirmed certificates
  used. On each view, if the current set differs, the response sets `certificates_changed: true`
  and the page shows the notice. Deletion and re-upload change the set, so corrections are
  detected without changing 003.
- **Alternatives:** comparing `confirmed_at` timestamps (misses deletions).

## R8. API shape

- **Decision:** `GET /api/wealth/{tax_year}` returns the saved statement, the auto-filled lines
  with their source certificates, and the freshly computed result. `PUT /api/wealth/{tax_year}`
  replaces the whole statement (rows included) and returns the same body. Both protected by
  `current_user`; a user only ever sees their own statement.
- **Rationale:** a statement is small (tens of rows); one replace-all save is simpler and safer
  than per-row endpoints; one GET gives the page everything it needs.
- **Alternatives:** per-row CRUD endpoints (more code, partial-save states); a separate
  reconciliation endpoint (two requests for one screen).

## R9. Explanation and the shared number check

- **Decision:** breakdown steps from fixed templates with the actual numbers and form line
  (e.g. "Increase in net assets (703003): Rs 2,450,000 − Rs 2,100,000 = Rs 350,000"). The
  "where to look" lists are two fixed lists in code, chosen by direction. The Claude summary
  follows 004 (official SDK, `SUMMARY_MODEL`, effort `low`, 4-second limit, breakdown as data).
  004's number check is moved from `backend/app/tax/summary.py` to
  `backend/app/explain/number_check.py` and both features import it.
- **Rationale:** one implementation of a safety check (constitution, Principle I); the checklist
  never comes from the model, so it can't suggest amounts.
- **Alternatives:** copying the check (two versions drift); letting Claude write the checklist
  (could suggest amounts, an anti-goal).

## R10. Worked examples and sign-off

- **Decision:** `backend/tests/wealth/worked_examples.yaml`, same format as 004: inputs, hand
  working citing the IRIS FAQ formula and SRO 1495 lines, expected figures, `signed_off_by` /
  `signed_off_date`; a test fails if any is unsigned. Cases: reconciled; each direction of gap;
  a decrease; liabilities larger than assets; negative previous net assets; several certificates
  summed with paisa rounding; no bank certificate; each not-ready reason.

## R11. Naming certificates (added 2026-11-10, during implementation)

- **Decision:** auto-filled lines and the `gross_below_taxable` message name a certificate by
  its type and upload time ("Salary certificate uploaded 2026-11-09 14:05 UTC"). 003's
  `ConfirmedDocument` gains `uploaded_at` (defaulted, so 004 is unaffected).
- **Rationale:** the plan assumed file names, but 003 stores uploads under random names and
  never keeps the original (its research R4); type and upload time are what the Documents page
  shows, so the user can find the certificate.
- **Alternatives:** storing original file names in 003 (a migration and a privacy question for a
  convenience); "Salary certificate 2" (numbers the Documents page doesn't show).
