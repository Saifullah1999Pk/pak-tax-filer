# Data Model: Deterministic Tax Engine (004)

No database tables: results are recalculated on every request (spec Edge Cases). These are the
in-code structures.

## TaxYearRates (per tax year, in `backend/app/tax/rates/`)

| Field | Content |
|---|---|
| `tax_year` | `"2025-26"` |
| `salary_bands` | ordered list of `(lower, upper or None, fixed, rate)` as `Decimal` |
| `salary_share_threshold` | `0.75` (salaried table applies above this share) |
| `surcharge_rate`, `surcharge_threshold` | `0.09`, `10,000,000` |
| `profit_rate`, `profit_limit` | `0.20`, `5,000,000` |
| `rounding` | "nearest rupee, 50 paisa up" (§219) |
| per rule: `source_document`, `location`, `finance_act` | e.g. "Income Tax Ordinance 2001 as amended up to 31.07.2025", "First Schedule, Part I, Division I, clause (2)", "Finance Act 2025" |

## TaxInputs

`tax_year`, `atl` (true / false / None = unanswered), `taxable_salary`, `tax_deducted`,
`gross_profit`, `tax_withheld`, `has_salary_certificate`. All amounts `Decimal`.

## TaxResult

| Field | Content |
|---|---|
| `blocked_reason` | set when calculation is refused; all figures then null |
| `salary_tax`, `surcharge`, `profit_tax` | rounded per §219 |
| `salary_balance` | positive = payable, negative = over-deducted |
| `profit_balance` | positive = payable, negative = over-withheld |
| `non_atl_extra_withheld` | for non-ATL users: withholding above the profit tax, labelled "to be confirmed" |
| `steps` | ordered list of `{description, inputs, rule_location, result}` |
| `summary` | verified AI summary or null |

Balances are never combined (spec FR-005).
