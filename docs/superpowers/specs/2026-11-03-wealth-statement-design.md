# 005 Wealth Statement and Reconciliation: Design

**Date:** 2026-11-03 · **Status:** Proposed · **Feature:** 005 (README milestone 5) ·
**Governed by:** [Constitution](../../../.specify/memory/constitution.md)

## Intent

README milestone 5: "Wealth statement + deterministic reconciliation, with LLM explanation of the
result only." The user lists what they own and owe at the end of TY2026; the app computes, in
plain code, whether the growth in their net assets is explained by their income and other inflows
minus their expenses and other outflows. Claude may only explain a result that is already
computed (README non-negotiable, Principle I).

**Who and why:** a salaried TY2026 filer must file a wealth statement with their return
(§116(2)), and IRIS won't accept the return until the reconciliation's unreconciled amount is
exactly zero. The hard part is finding why it isn't.

**Goals:** enter assets, liabilities and money flows in the same structure as the IRIS screens;
see whether it reconciles and, if not, by how much, in which direction and where to look, step by
step with the form lines.

**Non-goals:** filing on IRIS; the guided end-to-end flow (feature 007); everything under Out of
scope.

**Anti-goals** (failure even if the arithmetic is right):
- saying "reconciled" when IRIS wouldn't agree;
- suggesting amounts that would *make* it zero (that helps fudge a legal declaration);
- looking authoritative without the "not yet practitioner-reviewed" label.

## Sources (found 2026-11-03)

| Rule | Location | Content |
|---|---|---|
| Duty to file | Income Tax Ordinance 2001 (amended up to 31.07.2025), §116(2) | every resident individual filing a return furnishes a wealth statement and a wealth reconciliation statement |
| Reconciliation is part of the statement | same, §116(1)(e) | "the reconciliation statement of wealth" |
| TY2026 form | SRO 1495(I)/2026, 2 Sep 2026 (Income Tax Rules 2002, Second Schedule, new Parts II-ZE to II-ZH), PDF p. 38 | personal assets by category, payables, total assets (7019), total liabilities (7029), net assets current year (703001) |
| TY2026 reconciliation | same, PDF p. 40, "Reconciliation of Net Assets" | net assets current year (703001), previous year (703002), increase/decrease (703003); inflows (7049): income subject to normal tax (7031), exempt income (7032), income subject to final/fixed tax (7033), adjustments (7034), foreign remittance (7035), inheritance (7036), gift (7037), contribution in expenses by family members (7088); outflows (7099): personal expenses (7089), adjustments (7098), gift (7091); unreconciled amount (703000) |
| Formula | FBR IRIS FAQ (e.fbr.gov.pk/SOP/IRIS/Iris_FAQ_Urdu.pdf): the difference (703003) between current (703001) and previous year wealth (703002) must equal the difference between inflows and outflows | basis of steps 1–4 below |
| Must be zero | FBR IRIS help (e.fbr.gov.pk/SOP/SideLinks/Iris_help.pdf): "If it is not 0, wealth is not reconciled" | IRIS blocks submission until it is zero |
| Valuation | FBR return instructions (SRO 1160 of 2019, wealth statement notes) | assets declared at cost |

SRO 1495 is scanned IRIS screenshots; the line names and codes above were read from the page
images. The screen prints no formula for the unreconciled amount.

## Scope (approach A, decided by Saifullah)

**The user enters**, for TY2026 (as on 30 June 2026):
- **Assets** as rows: category (from the IRIS list: immovable property; investments; advances
  and receivables; cash in hand; bank accounts; equipment; animals; motor vehicles; precious
  possessions; household effects; personal items; assets in others' names; any other asset),
  description, value at cost.
- **Liabilities** as rows: description, creditor, amount.
- **Net assets as on 30 June 2025**, copied from last year's statement.
- **Other inflows:** other exempt income (beyond the salary part filled in below), foreign
  remittance, inheritance, gifts received, contribution in expenses by family members.
- **Outflows:** personal expenses (one amount per IRIS expense category), gifts given.

**Filled in automatically** from confirmed certificates (feature 003): taxable salary (line 7031),
the exempt part of salary, gross minus taxable (line 7032, provisional rule 4; decided by
Saifullah), bank profit (line 7033, provisional), tax deducted and withheld (provisional rule 1). These are
**read-only** on the wealth page, each showing which certificate it came from; a wrong figure is
corrected on the certificate (decided by Saifullah), so the tax and wealth pages can never
disagree and only human-confirmed data is used (Principle III). In 003 a confirmed certificate
is final, so "correcting" means deleting it and uploading a new one; 003 is not changed.

**Page:** three sections: what I own, what I owe, money in and out. Entries are saved so the
user can return; the reconciliation is **recalculated every time** (never stored). If the set of
confirmed certificates changed (one added or deleted) since the statement was last saved, a
one-line notice says so and asks the user to check the result. *(How the change is detected is
the builder's call.)*

**Calculation (plain code, exact decimals):**
1. Total assets − total liabilities = **net assets current year**.
2. Net assets current year − net assets previous year = **increase or decrease**.
3. Sum of inflows − sum of outflows = **explained change**.
4. Explained change − increase = **unreconciled amount**. Zero means reconciled. A non-zero
   result is described in words, never only as a signed number: "your inflows exceed the growth
   in your assets by Rs X (an expense or asset may be missing)" or "your assets grew Rs X more
   than your inflows explain (an inflow may be missing)".
5. **Where to look:** for a non-zero result, a fixed, code-written checklist chosen by direction
   (assets grew more than explained → check for a missing gift, inheritance, remittance or family
   contribution; inflows exceed growth → check for a missing asset, such as a bank account,
   vehicle or jewellery, or an unfilled expense category). Never amounts, never written by
   Claude.

**Explanation:** the same pattern as 004: a code-generated step-by-step breakdown, always shown,
plus an optional Claude summary shown only if every number in it appears in the breakdown.

## Provisional rules (pending the lead's answers, asked in the PR)

1. **Tax deducted at source:** income goes in at the certificate's gross figure, so the tax
   deducted by the employer and withheld by the bank (money the user never received) is added
   as an outflow. The alternative is entering income net of tax. The TY2026 screen doesn't say
   which.
2. **Bank profit line:** §7B profit goes on line 7033 (income subject to final/fixed tax), not
   7031, because it is taxed separately from salary.
3. **Previous year's net assets:** typed by the user from last year's statement. The app doesn't
   rebuild earlier years; a first-time filer's separate earlier-year reconciliations are out of
   scope.
4. **Exempt part of salary:** gross salary minus taxable salary on the certificate is treated as
   exempt income actually received and filled into line 7032. This is our reading, not FBR text;
   without it, most salaried statements would be short by that amount and fail to reconcile.

## Out of scope

Foreign assets and the §116A statement; business capital and business liabilities; assets
disposed of or transferred during the year (and gains or losses on them); "adjustments" lines
7034/7098; market-value reporting; revised statements; reconciliations for earlier years; PDF
export (008).

## User flow

Same order as the IRIS screens (SRO 1495 PDF pp. 36–40: income, tax computation, then wealth
statement): confirm certificates (003) → see tax (004) → wealth statement (005). Going back to fix
a certificate is the only loop, covered by the notice above. A single guided flow joining the
pages is feature 007, not this one.

## Approaches (level of detail)

| Approach | Trade-off | Outcome |
|---|---|---|
| A. Item list per asset and liability | Mirrors IRIS line by line; one more table on the page | **Chosen** |
| B. One total per category | Less typing; the user still adds up items elsewhere | Rejected |
| C. Net assets only | Simplest; not really a wealth statement | Rejected |

## Decisions

- **Whole rupees:** the user's entries are whole rupees, as in IRIS; certificate figures are
  rounded per §219 before entering the reconciliation, so a reconciled statement is exactly
  zero. *(Builder's call.)*
- **Pure function core:** `reconcile(inputs) -> result`, no database or network, mirroring 004.
  *(Builder's call.)*
- **Test-first with sign-off:** hand-worked examples (reconciled; assets grew more than
  explained; inflows exceed growth; net assets fell; liabilities larger than assets), each citing
  the IRIS FAQ formula and the SRO 1495 lines, are signed off by a human before any
  reconciliation code, as in 004 (Principle VI). *(Builder's call.)*
- **Sign of the raw number:** unreconciled = explained change − increase, fixed so later
  features (e.g. 008's PDF export) print it consistently; users see it in words. *(Builder's
  call.)*
- **Not ready** when previous-year net assets aren't entered, no salary certificate is
  confirmed, or summed bank profit exceeds Rs 5 million (the same block and message as 004, since
  line 7033 assumes §7B applies); the user is told why. *(Builder's call.)* Also when a confirmed
  salary certificate's gross salary is lower than its taxable salary, naming that certificate
  (decided by Saifullah during `/speckit-clarify`).
- **Shared summary check:** 004's number check is reused, not copied. *(Builder's call.)*
- **Synthetic data only**, and the "not yet practitioner-reviewed" label on every result
  (Principles IV, V).

## Done when

- A user with confirmed certificates enters assets, liabilities, last year's net assets and
  expenses, and sees net assets, the increase, inflows, outflows and the unreconciled amount,
  each step with its form line.
- All worked-example tests pass, written before the code.
- The Claude summary never shows a number absent from the breakdown.

## Left to the plan

Tables, API routes, the page layout, how 004's summary check is shared, and the expense
categories' exact list.
