# Feature Specification: Full Individual Income Tax Calculation

**Feature Branch**: `010-income-tax-engine`

**Created**: 2026-11-13

**Status**: Draft

**Input**: User description: "Full individual income tax calculation for a resident individual,
salaried or not, for TY2026 and TY2027: eight income sources (salary and bonuses, rental/property,
freelance and consultancy, business, bank profit, dividends, capital gains, other sources) each
under its legal treatment (normal, separate, final, exempt, adjustable withholding); the 75%
salary test and regime; Zakat, charitable donations, pension contributions; tax withheld on
incomes and on bills plus advance tax; one payable or refundable amount; a line-by-line
breakdown. Entry: a 'which incomes do you have?' checklist, then one short section per income,
monthly or yearly amounts; salary typed or from a confirmed certificate; simple inputs. One
engine behind the Tax page, guided filing, PDFs and the MCP tool; the wealth statement uses the
same incomes. Unsupported items shown as such." Source design (approved by the lead, verbally,
2026-11-13): `docs/superpowers/specs/2026-11-13-full-income-tax-engine-design.md`. Constitution
1.3.0 (Principle VII amended for this feature).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Salary plus rent: my actual tax (Priority: P1)

A salaried person who also lets out a property ticks "Salary" and "Rent" on a short checklist,
fills in one section for each (monthly or yearly amounts), and sees their full tax for their
profile's tax year: income per head, the regime that applies and why, tax on each part, tax
already deducted, and one amount payable or refundable.

**Why this priority**: it is the lead's own example (salary Rs 250,000 a month and rent
Rs 140,000 a month) and the most common "salary + other income" case; it proves the entry flow,
the 75% test and the combining step that every later income uses.

**Independent Test**: enter the lead's example (and the other signed worked examples for salary
and rent), open the Tax page and compare every figure with the hand-worked result.

**Acceptance Scenarios**:

1. **Given** a profile for TY2026, **When** the user opens the income entry, **Then** they see a
   checklist of the eight income sources and, for each ticked source, one short section.
2. **Given** salary entered as Rs 250,000 a month and rent as Rs 140,000 a month, **When** the
   user saves, **Then** the amounts are converted to Rs 3,000,000 and Rs 1,680,000 a year and the
   result matches the signed worked example for that case to the rupee.
3. **Given** typed salary (gross pay, exempt allowances the user types, bonuses, tax deducted by
   the employer) and/or confirmed salary certificates, **When** the tax is calculated, **Then**
   every salary source counts and is listed separately.
4. **Given** any combination of incomes, **When** the result is shown, **Then** it states whether
   the salaried or non-salaried table applies, with the salary share used for the 75% test and
   which incomes counted toward it, as the Ordinance sets them.
5. **Given** rent received, **When** the tax is calculated, **Then** property income is taxed
   under the treatment the Ordinance sets for that tax year, shown as its own line.
6. **Given** tax due and tax already deducted, **When** the result is shown, **Then** it shows one
   balance labelled **payable** or **refundable**, with §219 rounding to the rupee.
7. **Given** any result, **When** it is shown, **Then** the "not yet reviewed by a tax
   practitioner; not tax advice" label is visible.

---

### User Story 2 - Business and freelance income, with or without a salary (Priority: P2)

A person with freelance or consultancy work, or a small business, enters receipts and expenses
for each, alongside a salary or with no salary at all, and gets their tax on the right table.

**Why this priority**: the second most common side income, and it exercises the non-salaried
regime the lead's prompt requires.

**Independent Test**: enter the signed worked examples (salary + freelance under and over the
75% line; freelance only; business only) and compare every figure.

**Acceptance Scenarios**:

1. **Given** freelance or business receipts and expenses, **When** the tax is calculated,
   **Then** the taxable amount is receipts minus expenses, under the treatment the Ordinance sets
   for that kind of income.
2. **Given** no salary at all, **When** the tax is calculated, **Then** the non-salaried table is
   used and the result says why.
3. **Given** salary that falls to 75% or less of taxable income because of business income,
   **When** the tax is calculated, **Then** the non-salaried table applies to the whole normal
   income, as the Ordinance requires.
4. **Given** expenses larger than receipts, **When** the user saves, **Then** the result says that
   losses are not supported yet and shows no tax figure for that case.

---

### User Story 3 - Bank profit, dividends, capital gains and other income (Priority: P3)

A person with savings, shares or a property sale enters bank profit, dividends, capital gains
(the gain and the tax already deducted, per kind) and any other income, and sees each taxed
under its own treatment: separately, as a final tax, as normal income or as exempt.

**Why this priority**: completes the eight sources; these are the incomes most often taxed
outside the slabs, which a naive calculator gets wrong.

**Independent Test**: enter the signed worked examples for each source alone and combined with
salary; compare every figure, including which figures are kept outside the slab income.

**Acceptance Scenarios**:

1. **Given** bank profit typed or from confirmed bank profit certificates, **When** the tax is
   calculated, **Then** it is taxed under the treatment the Ordinance sets (TY2026: separately at
   20%, §7B) and the tax withheld by the bank is applied as the law allows.
2. **Given** dividends with the tax deducted, **When** the tax is calculated, **Then** they are
   taxed under the treatment and rate the Ordinance sets for that tax year and the user's ATL
   status.
3. **Given** a capital gain on listed securities or on property, with the tax already deducted,
   **When** the tax is calculated, **Then** each kind is taxed under its own treatment and rate
   as the Ordinance sets them.
4. **Given** other income, **When** the tax is calculated, **Then** it is taxed as income from
   other sources under the Ordinance's treatment.
5. **Given** an income the Ordinance exempts, **When** the result is shown, **Then** it is listed
   as exempt with its source and adds no tax.
6. **Given** a final tax, **When** the result is shown, **Then** the tax deducted on that income
   settles it: it is listed, but neither adds to nor reduces the balance on other income.

---

### User Story 4 - Deductions, credits and tax I have already paid (Priority: P4)

A person enters Zakat paid, charitable donations, pension-fund contributions, tax paid on bills
and other transactions (e.g. electricity, phone, cash withdrawal, vehicle registration) and
advance tax paid, and the balance reflects them.

**Why this priority**: these change most people's final balance, often turning a payable amount
into a refund; without them the balance is wrong.

**Independent Test**: add each item to a signed worked example and compare the changed figures.

**Acceptance Scenarios**:

1. **Given** Zakat paid, **When** the tax is calculated, **Then** it reduces income or tax as the
   Ordinance sets, within its limit, shown as its own line with its source.
2. **Given** charitable donations or pension-fund contributions, **When** the tax is calculated,
   **Then** each gives the reduction or credit the Ordinance sets, within its limit.
3. **Given** tax paid on bills by type, and advance tax paid, **When** the balance is worked out,
   **Then** each type the Ordinance makes adjustable reduces the balance, and each type it makes
   final or not adjustable is listed and explained but does not.
4. **Given** credits larger than the tax due, **When** the balance is shown, **Then** it is
   refundable by the difference, rounded per §219.

---

### User Story 5 - Understand every line, and honest limits (Priority: P5)

The user sees how each figure was reached, line by line, with its rule and source; anything the
app doesn't cover, or a case the law leaves to judgement, is shown as such instead of a number.

**Why this priority**: an unexplained or guessed figure can't be trusted or audited (Principles
II and IV).

**Independent Test**: for each signed worked example, check each breakdown line names its rule
and source; then try each unsupported case and confirm the message and that no figure is
invented.

**Acceptance Scenarios**:

1. **Given** a result, **When** the user views it, **Then** the breakdown shows, in order: gross
   income per source, deductions, taxable income per head, the regime and why, the slab used, tax
   per category, credits, withholding, advance tax, total liability and the balance, each with its
   inputs, rule and source.
2. **Given** a result, **When** it is shown, **Then** a list of items the app doesn't cover yet
   (other deductions and credits, losses, depreciation, perk valuation, minimum and turnover tax,
   per-sale capital gains) is visible.
3. **Given** a case the Ordinance leaves to judgement for the user's situation, **When** the tax
   is requested, **Then** the user is told it needs a tax practitioner and no figure is shown for
   it.
4. **Given** a plain-language summary, **When** it is produced, **Then** it is shown only if every
   number in it appears in the breakdown (as in feature 004).

---

### User Story 6 - TY2027 (Priority: P6)

A user whose profile is set to TY2027 enters that year's incomes and sees a result under the
TY2027 rules, labelled as an estimate while the year is still running.

**Why this priority**: the lead's prompt asks for TY2026 and TY2027; it reuses everything above
with a second set of rates.

**Independent Test**: switch the profile to TY2027, enter the TY2027 signed worked examples and
compare; switch back and confirm TY2026 entries and results are unchanged.

**Acceptance Scenarios**:

1. **Given** a profile set to TY2027, **When** the tax is calculated, **Then** the TY2027 rules
   (the Ordinance as amended by the Finance Act 2026) are used and the result is labelled an
   estimate until 30 June 2027.
2. **Given** entries for both years, **When** the user changes the profile year, **Then** each
   year shows only its own entries and result.
3. **Given** the stored rules, **When** they are inspected, **Then** every one shows its source
   document, section, Finance Act and effective date.

---

### User Story 7 - One result everywhere (Priority: P7)

Guided filing, the PDF export, the MCP tool and the wealth statement use the same incomes and the
same result as the Tax page.

**Why this priority**: two engines that can disagree are an anti-goal; it is mostly rewiring
once the engine exists.

**Independent Test**: for one signed worked example, compare the Tax page, guided filing's
calculate step, the PDF and the MCP tool's answer figure by figure; open the wealth statement and
confirm rent and business income appear as inflows.

**Acceptance Scenarios**:

1. **Given** a set of incomes, **When** guided filing reaches its calculation, **Then** it shows
   the same figures as the Tax page, behind its approval gate.
2. **Given** a result, **When** the user exports the tax PDF, **Then** it shows the same figures
   and breakdown with the practitioner label on every page.
3. **Given** the MCP `calculate_income_tax` tool, **When** called for a user, **Then** it returns
   the same result; the MCP server still has exactly three tools.
4. **Given** typed incomes, **When** the user opens the wealth statement, **Then** each income
   appears as an inflow line, so it never shows as an unexplained gap.

### Edge Cases

- No income ticked, or every amount zero: the page says there is nothing to calculate; no figure.
- No taxpayer profile: refused with `409`, as today.
- A monthly amount with paisa: converted to the year exactly (× 12), rounded only on final
  amounts per §219.
- Salary exactly 75% of the income the test uses: the Ordinance's wording ("exceeds") decides;
  pinned by a worked example.
- Taxable income exactly on every slab limit, and exactly on the surcharge limit: pinned by worked
  examples for both years.
- Two typed salaries with the same employer label: both count; the page warns they may be the
  same job entered twice.
- Typed salaries alongside confirmed salary certificates: all count; the page reminds the user not
  to type a salary a certificate already covers.
- A confirmed certificate is deleted, or an entry changed: the next view recalculates; results
  are never stored.
- Tax deducted exactly equal to tax due: balance zero, labelled neither payable nor refundable.
- Negative amounts, or amounts too large (more than 13 digits before the decimal point): refused
  with the field and reason.
- TY2027 profile with no TY2027 entries: nothing to calculate; TY2026 entries are not carried over.

## Requirements *(mandatory)*

### Functional Requirements

**Entering incomes**

- **FR-001**: Users MUST be able to choose which of the eight sources they have (salary and
  bonuses, rent, freelance and consultancy, business, bank profit, dividends, capital gains,
  other) and fill in one short section per chosen source.
- **FR-002**: Income amounts MUST be enterable per month or per year (per section); one-off
  amounts (bonuses, capital gains, tax deducted, advance tax) are yearly. The calculation works on
  yearly amounts.
- **FR-003**: Inputs MUST be simple: salary as gross pay minus exempt allowances the user types,
  plus bonuses and tax deducted; business and freelance as receipts minus expenses; rent as gross
  rent received; capital gains as the gain and the tax deducted, per kind (listed securities,
  property); other sources and dividends as the amount and tax deducted.
- **FR-004**: Users MUST be able to add several salaries (each with an employer label) and
  several entries for the other sources, and to edit and delete any entry.
- **FR-005**: Salary and bank profit MUST also come from confirmed certificates (feature 003);
  every confirmed certificate and every typed entry counts and is listed separately.
- **FR-006**: Users MUST be able to enter Zakat paid, charitable donations, pension-fund
  contributions, tax paid on bills and transactions by type, and advance tax paid.
- **FR-007**: Entries MUST be stored per user and tax year, visible only to their owner (`404`
  for anyone else's), and MUST NOT include identity fields (name, CNIC, NTN).

**Calculating**

- **FR-008**: The calculation MUST follow this order: gross income per source → allowable
  deductions → taxable income per head → the 75% salary test and the regime → tax on normal
  income → separate and final taxes → credits and rebates → tax deducted and advance tax →
  payable or refundable.
- **FR-009**: Each income MUST be classified by its treatment under the Ordinance for the tax
  year (normal, separately taxed, final, exempt, adjustable withholding); incomes MUST NOT be
  assumed to share one slab.
- **FR-010**: The 75% salary test MUST use the income the Ordinance specifies, and the result MUST
  state the share and which table applies.
- **FR-011**: Tax withheld or paid in advance MUST reduce the balance only where the Ordinance
  makes it adjustable; final taxes settle their own income.
- **FR-012**: The result MUST be one balance, payable or refundable, replacing feature 004's
  separate salary and profit balances; its provisional refusals are replaced by the rules the
  research finds in the law.
- **FR-013**: Calculations MUST use exact decimal arithmetic with §219 rounding on final amounts;
  no figure may be produced, adjusted, rounded or checked by an AI (Principle I).
- **FR-014**: Where the Ordinance leaves a case to judgement, the system MUST refuse that case
  with "needs a tax practitioner" and no figure; items not covered MUST be listed as unsupported.

**Rates and tax years**

- **FR-015**: Every rule MUST be stored as data per tax year (TY2026, TY2027) with its source
  document, section, Finance Act and effective date, from FBR's own documents only (Principle II);
  adding a year MUST NOT change the calculation.
- **FR-016**: Automated checks MUST verify each slab table's internal consistency (each band's
  fixed amount equals the tax at the top of the previous band) for both years.
- **FR-017**: The tax year MUST come from the taxpayer profile, which MUST accept TY2026 and
  TY2027; a TY2027 result MUST be labelled an estimate until 30 June 2027.

**Showing the result**

- **FR-018**: The result MUST show: total gross income, income per category, deductions, taxable
  income per category, the regime and why, the slab used, tax per category, credits, withholding,
  advance tax, total liability and the payable or refundable amount, each as a breakdown line
  with its inputs, rule and source.
- **FR-019**: Every result MUST carry the "not yet practitioner-reviewed; not tax advice" label
  (Principle IV); an AI summary MAY be shown only when every number in it appears in the
  breakdown.
- **FR-020**: The page MUST warn when two salaries share an employer label, and remind the user
  not to type a salary a confirmed certificate already covers.

**One engine**

- **FR-021**: The Tax page, guided filing, the tax PDF and the MCP `calculate_income_tax` tool
  MUST use this one calculation and show the same figures; the MCP server keeps exactly three
  tools.
- **FR-022**: The wealth statement (feature 005) MUST take its income inflows from the same
  entries and certificates.

**Proof**

- **FR-023**: Before each income's code, worked examples covering every slab and boundary, the 75%
  test on both sides, each treatment and each credit MUST be worked out by hand from the
  Ordinance, signed off by the author (marked "author signed") and become the tests (Principle
  VI).

### Key Entities

- **Income entry**: one income a user typed for a tax year: its source, an optional label (e.g.
  employer), whether amounts are monthly or yearly, the amounts the source asks for, and the tax
  deducted.
- **Deduction or credit entry**: Zakat, a donation or a pension contribution, with its amount.
- **Tax paid entry**: tax paid on a bill or transaction (by type) or advance tax, with its amount.
- **Tax-year rules**: for one tax year, each head's treatment, rates, slabs, thresholds, limits,
  which withholdings are adjustable, and the rounding rule, each with source and effective date.
- **Tax result** (never stored): the lines of FR-018, the regime and its reason, the unsupported
  list, any refusal reason, the estimate label, and the optional checked summary.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of the signed worked examples (both years) produce exactly the hand-worked
  figures, to the rupee.
- **SC-002**: 100% of stored rules show their source document, section, Finance Act and effective
  date.
- **SC-003**: A user can enter salary plus one other income and see their result in under 3
  minutes, without help.
- **SC-004**: For the same inputs, the Tax page, guided filing, the PDF and the MCP tool show
  identical figures in 100% of the worked examples.
- **SC-005**: Every unsupported or practitioner case shows a reason and no invented figure.
- **SC-006**: 0 summaries containing a number absent from the breakdown are shown.
- **SC-007**: The result appears within 5 seconds of opening the Tax page.

## Assumptions

- Users are resident individuals; companies, associations of persons, non-residents, agricultural
  income, years before TY2026, filing and tax-planning advice are out of scope (constitution
  1.3.0).
- Sources: TY2026, the Ordinance amended to 31.07.2025 (Finance Act 2025), as feature 004 used;
  TY2027, the Ordinance amended to 30.06.2026 and the Finance Act 2026, both from FBR's site. Each
  head's treatment, the income the 75% test uses, the deductions and limits, and which withholdings
  are adjustable are settled in the plan's research from these documents, never assumed or taken
  from a third-party calculator.
- Salary certificates carry no employer name, so a typed salary can't be matched to a certificate
  automatically. Every source counts and the page warns instead (FR-005, FR-020); this replaces
  the design's earlier line that the certificate is used when both exist. Nothing is dropped
  silently.
- Withholding rates on bills are not modelled: the user types the tax shown on each bill or
  statement.
- ATL status still comes from the profile and is used where a rate depends on it.
- Entries are stored; results never are. Synthetic data only (Principle V).
- Feature 004's spec, contracts and tests change with this feature (one engine); feature 005's
  inflows and feature 007's and 008's callers follow.
