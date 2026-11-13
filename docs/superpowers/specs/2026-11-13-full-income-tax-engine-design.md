# Full individual income tax calculation: design

2026-11-13. From the lead's task prompt ("Implement Pakistan Individual Income Tax Calculation
Engine") and his feedback after trying the app (2026-11-12: "an interface to get info for other
incomes: salary per month, rental, shares or other earnings"; 2026-11-13: "on this combo we need
to find out his actual tax"). His prompt's tool names (OpenSpec, Django) are read as this
project's own (Spec Kit, FastAPI).

## Intent and the why

Today the app calculates tax only for salary and bank profit, from confirmed certificates
(feature 004). A salaried person with rent, freelance work, dividends or capital gains can't get
their actual tax. This feature makes the engine calculate a **full individual's** tax: every
common income source, each under its correct legal treatment, with the salaried test,
deductions, credits and tax already withheld, giving the amount payable or refundable, with a
breakdown a person (or a tax practitioner) can audit line by line, for TY2026 and TY2027.

## Goals

1. Eight income sources: salary and bonuses, rental/property, freelance and consultancy,
   business, bank profit (profit on debt), dividends, capital gains, other sources.
2. Each classified by its treatment as the law sets it: normal (slab) income, separately taxed,
   final tax, exempt, and adjustable withholding. Nothing assumed to share one slab.
3. The calculation in order: gross income per source → allowable deductions → taxable income
   per head → the 75% salary test and the regime (salaried or non-salaried table) → tax on
   normal income → separate and final taxes → credits and rebates → tax already withheld and
   advance tax → payable or refundable.
4. Deductions and credits a salaried person with side income commonly claims: **Zakat,
   charitable donations, pension-fund contributions**. Others listed on the result as "not
   supported yet".
5. TY2026 and TY2027, each rule held as data per tax year with its FBR source (document,
   section, Finance Act) and effective date.
6. Users enter their incomes: a "which incomes do you have?" checklist, then one short section
   per income (monthly or yearly amounts). Salary may be typed or come from a confirmed
   certificate as today.
7. One result: total gross income, income per category, deductions, taxable income per
   category, the regime and why, the slab used, tax per category, credits, withholding, advance
   tax, total liability, payable or refundable, each with how it was worked out.

## Non-goals

Filing or IRIS; companies and associations of persons; non-residents; agricultural income;
every deduction and credit in the Ordinance (only the three above); tax years before TY2026;
advice on tax planning.

## Anti-goals (a failure even if it works)

- Any figure from a third-party calculator (taxcalculator.pk is for flow ideas only;
  Principle II): every rate and rule comes from FBR's Ordinance and Finance Acts.
- A rule guessed when the law is unclear: it is shown as unsupported or "needs a tax
  practitioner", never silently assumed.
- Two engines that can disagree: one engine behind the Tax page, guided filing, PDFs and the
  MCP tool.
- An LLM touching any figure (Principle I).

## Constraints

- **Constitution:** Principle VII lists other income types as out of scope, so the feature
  starts with a scope amendment (lead's approval in the PR). Principles I (deterministic
  `Decimal`), II (FBR sources), IV (the practitioner label), V (synthetic data) and VI (worked
  examples signed off before code; tests for every slab and threshold) apply unchanged.
- **Sources:** TY2026: Income Tax Ordinance 2001 amended to 31.07.2025 (Finance Act 2025), as
  feature 004 used. TY2027: the Ordinance amended to 30.06.2026 and the Finance Act 2026, both on
  FBR's site.
- The rates folder stays guarded (the hook asks before changes); every change cites its source.

## Approaches (the user chose A)

| | Approach | Trade-off |
|---|---|---|
| **A** | **Extend 004's engine**: one plain calculator per income head with its own rates and sources per year; one combining step (75% test, regime, separate and final taxes, credits, withholding); the certificate path becomes one way to fill in salary and bank profit | Reuses what's proven (worked examples, sign-off, breakdown, label, guardrails); one engine everywhere; 004's inputs reshape, so its tests update |
| B | A second engine beside 004's | Less change now, but two engines can disagree; more code |
| C | A generic rule engine (rules as data, interpreted) | Hard to express the law's special cases; hard to check against the Ordinance; too complex for the constitution |

## Decided

- **Engine:** 004's pure, framework-free engine extended (approach A). Each head's calculator
  and the combining step are plain functions; rates per tax year in `app/tax/rates/`
  (`ty2026.py`, new `ty2027.py`) with source and effective date on every rule.
- **Inputs:** typed incomes are stored per user and tax year (like 005's wealth statement
  entries); salary and bank profit can also come from confirmed certificates. If both exist for
  salary, the confirmed certificate is used and the page says so (Claude's proposal: it is the
  stronger evidence).
- **Amounts** entered monthly or yearly (the page converts; the engine works on annual).
- **Unsupported or unclear** rules (a credit not covered, a case the law leaves to judgement)
  appear in the result as such, never as a number.
- **Build order** inside one branch, each step with its worked examples signed off first:
  typed salary and the regime/75% test → property income → business and freelance → bank
  profit (moved onto the new engine) → dividends → capital gains → other sources → the three
  deductions/credits → TY2027. One pull request at the end.
- **Planning:** Spec Kit (`/speckit-specify` … `/speckit-analyze`), with the legal research
  (each head's treatment, rates, thresholds and withholding, with sources) as the plan's
  research step.

## Settled after the builder check (Claude's calls)

- *Salary is optional:* someone with only business or freelance income goes through the same
  engine on the non-salaried table (the lead's prompt covers business income and both regimes).
- *004's provisional rules* (the refusals over Rs 5m profit and an ambiguous salary share, the
  "never add the balances" rule, non-ATL extra withholding) are replaced by what the legal
  research finds in the law; where the law still leaves a case to judgement, it keeps refusing
  ("needs a tax practitioner"). The lead's prompt asks for one payable/refundable figure, which
  answers the question 004 left open about adding the two sides.
- *The wealth statement (005) uses the same incomes:* its inflow lines come from the one engine
  (typed and certificate incomes), so rent or business income never shows as an unexplained gap.
  005's contract and tests change with it.
- *Several salaries:* every salary source counts (each confirmed certificate, each typed salary
  with its employer's name), listed separately on the result; nothing is replaced silently. The
  page warns if the same employer appears twice.
- *TY2027 is still running* (it ends 30 June 2027): its result is labelled an estimate; a user
  moves between TY2026 and TY2027 by their profile year, and entries are kept per tax year.
- *Sign-off:* Saifullah signs off each step's worked examples against the law, marked "author
  signed" (the lead's 009 review asked for this to be explicit); every result keeps the "not yet
  reviewed by a tax practitioner" label (Principle IV).

## Decided with the user after the builder check

- **Simple inputs** (the user's choice): salary as gross pay minus any exempt allowances the
  user types; business and freelance as receipts minus expenses; capital gains as the gain and the
  tax already deducted, per kind (listed securities, property); rent as gross rent received.
  Losses (set-off, carry-forward), depreciation, minimum and turnover tax, perk valuation and
  per-sale capital gains are listed as "not supported yet".
- **Tax paid that isn't on an income** (Claude's recommendation, accepted): typed amounts by
  type, taken from the user's bills and statements (e.g. electricity, phone, cash withdrawal,
  vehicle registration), plus advance tax paid. The research finds which types are adjustable
  against the tax due; their withholding rates are not modelled.

## Legal questions the research must answer from the Ordinance (not assumed here)

- Whether property (rental) income of an individual counts toward "taxable income" for the 75%
  salary test, or is taxed separately outside it. (The lead's example, Rs 3.0m salary and
  Rs 1.68m rent, turns on this: 64% of combined income, or 100% of normal income.)
- The treatment of each head: dividends, profit on debt beyond banks, capital gains on listed
  securities versus property, freelance and consultancy (business income, or a special regime
  for some services), other sources.
- Allowable deductions per head (e.g. repairs allowance on property income, business
  expenses), and how Zakat, donations and pension contributions reduce income or tax.
- Withholding and advance taxes per head and whether each is adjustable or final.
- What changed between TY2026 and TY2027 (the Finance Act 2026).

## Left to the builder (Spec Kit plan)

Data model for entered incomes, endpoint shapes (following `docs/api-conventions.md`), page
layouts, the breakdown's wording, the exact list of unsupported items shown, and how guided
filing, PDFs and the MCP tool use the extended result.
