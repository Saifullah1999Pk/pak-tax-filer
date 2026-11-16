# Plain-code Summaries Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Put a short, code-written "Summary" back on the Tax page, the Wealth page, the guided
run's result and both PDFs, where the AI summary used to be.

**Architecture:** Two pure wording functions, one per area, beside the existing breakdown wording
(`app/tax/breakdown.py`, `app/wealth/breakdown.py`), fill fixed sentences with amounts the result
already holds. The API results carry them as `summary: str | None`; the PDFs and React pages only
display them.

**Tech Stack:** FastAPI + Pydantic, Jinja2/WeasyPrint, React + TS (Vitest/RTL), pytest-anyio.

**Spec:** `docs/superpowers/specs/2026-11-16-plain-summary-design.md`

## Global Constraints

- No AI: plain functions only; `.importlinter` and `tests/guardrails` must stay green.
- No new figures: only amounts already on the result; never add salary and bank-profit amounts.
- `summary` is `null` when the tax result is blocked or the wealth result is not ready.
- Amounts via the existing `money()` in `app/tax/breakdown.py` ("Rs 72,000").
- The old `/summary` routes stay 404 (`test_no_ai_rewords_a_computed_result` unchanged).
- Each contract change updates `contracts/*.md`, `api.yaml` and the FR in the same commit.
- Backend tests run in Docker (`docker compose exec -T backend pytest …`); frontend tests in the
  container (`docker compose exec -T frontend npm test -- …`).

## Review Focus

1. Over-deducted salary (negative balance) reads "was deducted too much", never "-Rs 3,000".
2. No bank certificate (profit tax and credit both 0): no bank sentence at all.
3. Non-ATL user: the bank sentence uses the credited amount; the extra withheld stays only in the
   page's existing notice.
4. Wealth increase of 0 or negative reads "the same as" / "less than last year".
5. The guided run's `/result` carries the same summary as `/api/tax/{year}` (it reuses `tax_out`).

---

### Task 1: Tax summary (backend, contracts 004 and 007)

**Files:**
- Modify: `backend/app/tax/breakdown.py` (add `tax_summary`)
- Modify: `backend/app/tax/router.py` (`TaxOut.summary`, set in `tax_out`)
- Test: `backend/tests/tax/test_tax_summary.py` (new), `backend/tests/tax/test_tax_api.py`,
  `backend/tests/workflow/test_workflow_api.py`
- Docs: `specs/004-tax-engine/contracts/tax-api.md`, `specs/004-tax-engine/contracts/api.yaml`,
  `specs/004-tax-engine/spec.md` (FR-011 amendment line), `specs/007-agentic-workflow/contracts/api.yaml`

**Interfaces:**
- Produces: `tax_summary(result: TaxResult) -> str | None`; `TaxOut.summary: str | None`.

The fixed copy (spec decision; `{…}` are `money()` of the field):
- Salary: `"Your salary tax for {tax_year} is {salary_tax}"` + (surcharge > 0:
  `" plus a surcharge of {surcharge}"`) + `". Your employers deducted {salary_credit}, so "` +
  balance > 0 `"{salary_balance} is still payable."` / < 0 `"{-salary_balance} was deducted too
  much."` / 0 `"nothing more is payable."`
- Bank (only if profit_tax or profit_credit ≠ 0): `" Tax on your bank profit is {profit_tax};
  after {profit_credit} withheld by banks, "` + `"{b} is still payable."` / `"{-b} was withheld
  too much."` / `"nothing more is payable."`

- [ ] **Step 1: Failing tests** in `test_tax_summary.py` (build `TaxResult` directly):
  `test_over_deducted_salary` → `"Your salary tax for 2025-26 is Rs 72,000. Your employers deducted
  Rs 75,000, so Rs 3,000 was deducted too much."`; `test_payable_with_surcharge_and_bank_profit`
  (asserts both "plus a surcharge of" and "is still payable." and the bank sentence);
  `test_no_bank_profit_has_no_bank_sentence` (`"bank" not in summary`); `test_blocked_has_none`
  (`tax_summary(TaxResult("2025-26", blocked_reason="needs_atl_answer")) is None`).
  In `test_tax_api.py`: the existing calculated test asserts `body["summary"].startswith("Your
  salary tax for 2025-26 is Rs 72,000.")`; a blocked test asserts `body["summary"] is None`.
  In `test_workflow_api.py::test_after_approval_the_result_is_the_tax_pages`: the result's
  `summary` equals `/api/tax/{PROFILE_YEAR}`'s.
- [ ] **Step 2:** `docker compose exec -T backend pytest tests/tax tests/workflow -q` → FAIL
  (import error / missing key).
- [ ] **Step 3:** Implement `tax_summary`; add `summary` to `TaxOut` and `tax_out`.
- [ ] **Step 4:** Same command → PASS. Update the 004/007 contracts (add `summary` to the field
  table, examples and `api.yaml` required response fields) and the FR-011 dated amendment
  ("summary written by code from the result, 2026-11-16"). Run
  `uv run --project backend python scripts/validate_contracts.py --all` → exit 0.
- [ ] **Step 5: Commit** `feat(004): a plain-code summary on the tax result`.

### Task 2: Wealth summary (backend, contract 005)

**Files:**
- Modify: `backend/app/wealth/breakdown.py` (add `wealth_summary`)
- Modify: `backend/app/wealth/schemas.py` (`ResultOut.summary`), `backend/app/wealth/service.py`
  (`_result_out(result, tax_year)` sets it; `wealth_view` passes `tax_year`)
- Test: `backend/tests/wealth/test_wealth_summary.py` (new), `backend/tests/wealth/test_wealth_api.py`
- Docs: `specs/005-wealth-statement/contracts/wealth-api.md`, `.../api.yaml`, `.../spec.md` (FR-010)

**Interfaces:**
- Consumes: `money()` from `app.tax.breakdown` (already imported there).
- Produces: `wealth_summary(result: ReconciliationResult, tax_year: str) -> str | None`;
  `ResultOut.summary: str | None`.

Copy: `"Your net assets at the end of {tax_year} are {net_assets}, "` + increase > 0
`"{increase} more than last year."` / < 0 `"{-increase} less than last year."` / 0 `"the same as
last year."` + `" Your inflows were {inflows} and your outflows {outflows}."`

- [ ] **Step 1: Failing tests:** `test_growth` with the contract example (net assets 2,565,000,
  increase 465,000) → `"Your net assets at the end of 2025-26 are Rs 2,565,000, Rs 465,000 more
  than last year. Your inflows were Rs 2,050,000 and your outflows Rs 1,585,000."`;
  `test_fall_and_no_change`; `test_not_ready_has_none`. API: saving the contract example
  returns `result.summary` starting `"Your net assets at the end of 2025-26"`; not ready → `None`.
- [ ] **Step 2:** `docker compose exec -T backend pytest tests/wealth -q` → FAIL.
- [ ] **Step 3:** Implement; `breakdown.py` stays free of database/AI imports
  (`test_reconcile_imports.py`).
- [ ] **Step 4:** Same command → PASS; update the 005 contract and FR-010; contract check exit 0.
- [ ] **Step 5: Commit** `feat(005): a plain-code summary on the wealth result`.

### Task 3: PDFs

**Files:** `backend/app/reports/templates/tax.html`, `.../wealth.html`; test `backend/tests/reports/test_pdfs.py`

- [ ] **Step 1: Failing test:** the tax PDF's text contains `"Rs 3,000 was deducted too much"`
  and the wealth PDF's text contains `"Your net assets at the end of 2025-26"` (use the file's
  existing PDF-text helper).
- [ ] **Step 2:** `docker compose exec -T backend pytest tests/reports -q` → FAIL.
- [ ] **Step 3:** `{% if result.summary %}<h2>Summary</h2><p>{{ result.summary }}</p>{% endif %}`
  before "How it was worked out" in `tax.html`; in `wealth.html` the same with
  `wealth.result.summary`, right after `<h2>Result</h2>`.
- [ ] **Step 4:** Same command → PASS.
- [ ] **Step 5: Commit** `feat(008): the PDFs show the plain-code summary`.

### Task 4: Pages

**Files:** `frontend/src/api/tax.ts` (`TaxResult.summary: string | null`),
`frontend/src/api/wealth.ts` (`WealthResult.summary: string | null`),
`frontend/src/components/TaxResultView.tsx`, `frontend/src/pages/WealthPage.tsx`; tests
`TaxPage.test.tsx`, `WealthPage.test.tsx`, `WorkflowPage.test.tsx` (fixtures gain `summary`).

- [ ] **Step 1: Failing tests:** TaxPage: with `summary: "Your salary tax …"` in the mocked
  result, `getByRole("region", { name: "Summary" })` contains it; with `summary: null` no Summary
  region. WealthPage: the same with heading level 3 and its fixture. Keep the "never asks for an
  AI summary" tests.
- [ ] **Step 2:** `docker compose exec -T frontend npm test -- TaxPage WealthPage WorkflowPage` → FAIL.
- [ ] **Step 3:** A `section.panel.summary-panel` (CSS exists in `styles.css`) with heading
  "Summary": in `TaxResultView` after the `headline-pair`, before "How it was worked out" (`h2`);
  in `WealthPage`'s `Result` above `result-message` (`h3`). Render nothing when `summary` is null.
- [ ] **Step 4:** Same command → PASS; then `npx tsc -b`, `npm run lint`, `npx prettier --check src`
  in the container.
- [ ] **Step 5: Commit** `feat(004,005): the pages show the plain-code summary`.

### Finish

Full backend suite, ruff, pylint, mypy, lint-imports, contract check, full frontend suite, e2e
(fake Gemini); then the advisor review; then ask Saifullah before any push.
