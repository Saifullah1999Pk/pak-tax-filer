# Feature Specification: Simple Income Tax Calculator

**Feature Branch**: `010-income-tax-engine`

**Created**: 2026-11-13 (cut down to the simple calculator 2026-11-14)

**Status**: Draft

**Input**: User description: "Basic scenarios on the side: the user can just pass info like
salary, dividend, bonus, rental and you show him tax info; behind the scene some basic formulas"
(the lead, 2026-11-14; asked whether to keep it basic rather than his earlier full-engine prompt,
he answered "Simple"). Source design:
`docs/superpowers/specs/2026-11-13-full-income-tax-engine-design.md`. Constitution 1.3.0.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Type my incomes, see my tax (Priority: P1)

A signed-in user with a taxpayer profile opens the Tax calculator, types their salary per month,
any bonus for the year and any rent per month, and sees the tax on each, the total, which table
applies and why, and how each figure was worked out.

**Why this priority**: it is the lead's own example (salary Rs 250,000 a month and rent
Rs 140,000 a month) and the core of what he asked for.

**Independent Test**: enter the signed worked examples for salary, bonus and rent and compare
every figure with the hand-worked result.

**Acceptance Scenarios**:

1. **Given** a profile for TY2026, **When** the user opens the Tax calculator, **Then** they see
   fields for salary per month, bonus per year, rent per month, dividends per year and bank profit
   per year, each optional.
2. **Given** salary Rs 250,000 a month and rent Rs 140,000 a month, **When** the user calculates,
   **Then** the result shows yearly salary Rs 3,000,000 and rent Rs 1,680,000, and every figure
   matches the signed worked example for that case to the rupee.
3. **Given** a bonus, **When** the user calculates, **Then** it is taxed as salary, with the
   monthly salary × 12, under the salaried or non-salaried table.
4. **Given** rent, **When** the user calculates, **Then** it is taxed under the treatment the
   Ordinance sets for an individual in TY2026, as its own line.
5. **Given** any inputs, **When** the result is shown, **Then** it states which table applies, the
   salary share used for the 75% test and which incomes it counted, as the Ordinance sets them.
6. **Given** any result, **When** it is shown, **Then** the "not yet reviewed by a tax
   practitioner; not tax advice" label is visible.

---

### User Story 2 - Dividends and bank profit (Priority: P2)

The same user adds dividends and bank profit and sees each taxed under its own treatment.

**Why this priority**: dividends are in the lead's list; bank profit is already in the engine
(feature 004) and costs little to include.

**Independent Test**: enter the signed worked examples for dividends and bank profit, alone and
with salary, and compare every figure.

**Acceptance Scenarios**:

1. **Given** dividends, **When** the user calculates, **Then** they are taxed at the rate and under
   the treatment the Ordinance sets for TY2026 and the user's ATL status, as their own line.
2. **Given** bank profit, **When** the user calculates, **Then** it is taxed as feature 004 does
   (separately at 20%, §7B), as its own line.
3. **Given** incomes taxed separately, **When** the result is shown, **Then** they are kept out
   of the slab income and the breakdown says so.

---

### User Story 3 - Every line explained, honest limits (Priority: P3)

The user sees how each figure was reached, with its rule and source; a case the law leaves to
judgement is shown as such, not as a number.

**Why this priority**: an unexplained or guessed figure can't be trusted (Principles II, IV).

**Independent Test**: for each worked example, check each breakdown line names its rule and
source; try each refused case and confirm the message and that no figure is shown.

**Acceptance Scenarios**:

1. **Given** a result, **When** the user views it, **Then** each line shows its inputs, rule,
   source and result, ending with the total tax.
2. **Given** a case the Ordinance leaves to judgement for these inputs, **When** the user
   calculates, **Then** they are told it needs a tax practitioner and no figure is shown.
3. **Given** a result, **When** it is shown, **Then** a short note lists what the calculator does
   not cover (tax deducted, other incomes, deductions and credits).

### Edge Cases

- Every field empty or zero: "enter at least one income"; no figure.
- No taxpayer profile: refused (`409`), as the Tax page does.
- Negative amounts, more than 2 decimal places, or more than 13 digits before the decimal point:
  refused with the field and reason.
- Monthly amounts with paisa: × 12 exactly; only final amounts are rounded (§219).
- Salary exactly 75% of the income the test uses, taxable income exactly on each slab limit,
  exactly on the §4AB Rs 10 million limit, and rent and dividends exactly on any of their limits:
  each pinned by a worked example.
- No salary at all (e.g. rent only): the non-salaried table applies to any slab income, if the law
  puts any there; pinned by a worked example.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST offer a Tax calculator, separate from the Tax page, where a signed-in
  user with a profile types salary per month, bonus per year, rent per month, dividends per year
  and bank profit per year, each optional, at least one above zero.
- **FR-002**: Monthly amounts MUST be converted to yearly (× 12); the calculation works on yearly
  amounts.
- **FR-003**: The inputs MUST NOT be stored, logged or sent to any AI; the result is calculated on
  request and never stored.
- **FR-004**: Each income MUST be taxed under its treatment in the Ordinance for TY2026, with the
  75% salary test and the §4AB surcharge applied to the income the Ordinance specifies.
- **FR-005**: The calculation MUST be feature 004's engine, extended; the Tax page's figures for
  the same salary and bank profit MUST not change.
- **FR-006**: Every new rule (rent, dividends, any other) MUST be stored as TY2026 data with its
  source document, section, Finance Act and effective date, from FBR's own documents only.
- **FR-007**: Calculations MUST use exact decimal arithmetic with §219 rounding on final amounts;
  no figure may be produced, adjusted, rounded or checked by an AI.
- **FR-008**: The result MUST show the yearly amount and tax for each income, the total tax, the
  table used and why (with the salary share), the slab used, and a breakdown line per step with
  its rule and source.
- **FR-009**: Where the Ordinance leaves a case to judgement, the system MUST refuse it with
  "needs a tax practitioner" and no figure.
- **FR-010**: Every result MUST carry the practitioner label and a note of what is not covered.
- **FR-011**: ATL status and the tax year MUST come from the taxpayer profile.
- **FR-012**: Worked examples covering each income, every slab and limit the calculator uses, and
  the 75% test on both sides MUST be worked out by hand from the Ordinance and signed off by the
  author ("author signed") before the code, and become its tests.

### Key Entities

- **Calculator inputs** (never stored): salary per month, bonus, rent per month, dividends, bank
  profit; plus ATL status and tax year from the profile.
- **TY2026 rules**: added to 004's rates: rent and dividend treatment and rates, each with source
  and effective date.
- **Calculator result** (never stored): per-income amounts and tax, total tax, table and reason,
  slab, breakdown lines, any refusal reason, the label and the not-covered note.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of the signed worked examples produce exactly the hand-worked figures, to the
  rupee.
- **SC-002**: 100% of new rules show their source document, section, Finance Act and effective
  date.
- **SC-003**: A user can type their incomes and see the result in under 1 minute.
- **SC-004**: The Tax page's results for all of 004's worked examples are unchanged.
- **SC-005**: Every refused case shows a reason and no figure.

## Assumptions

- Salary means taxable salary per month as on a payslip; exempt allowances aren't analysed.
- TY2026 only, from the Ordinance amended to 31.07.2025 (Finance Act 2025). How rent and dividends
  are taxed, and whether they count toward the 75% test and the surcharge limit, are settled in
  the plan's research from the Ordinance, never from a third-party calculator.
- Out of scope (the lead's "Simple", 2026-11-14): saving inputs; tax deducted and payable or
  refundable; freelance, business, capital gains and other incomes; deductions and credits; tax on
  bills and advance tax; TY2027; guided filing, PDF, MCP and wealth statement links.
- Synthetic data only (Principle V); the calculator needs sign-in like every page.
