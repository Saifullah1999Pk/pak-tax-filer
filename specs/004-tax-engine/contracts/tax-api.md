# Contract: Tax API

`GET /api/tax/{tax_year}`. Requires `current_user`. ATL status is read from the user's taxpayer
profile (feature 002's `get_profile`). Follows the
[API conventions](../../001-repo-foundations/contracts/api-conventions.md): money as decimal
strings (plain digits, an optional leading `-`, never an exponent).

Every response has **all** the fields below; a field that doesn't apply is `null` (or `[]` for
`steps`).

| Field | Calculated | Blocked |
|---|---|---|
| `tax_year` | the year | the year |
| `blocked_reason`, `message` | `null` | the reason and what to do |
| `salary_tax`, `surcharge`, `profit_tax` | amounts | `null` |
| `salary_balance` | positive payable, negative over-deducted | `null` |
| `profit_balance` | positive payable, negative over-withheld | `null` |
| `non_atl_extra_withheld` | non-ATL only, else `null` | `null` |
| `steps` | the breakdown, in order | `[]` |
| `summary` | checked AI summary, or `null` | `null` |
| `label` | always | always |

Credits (tax deducted by employers, tax withheld by banks) appear in the salary-side and
profit-side steps of the breakdown (FR-005).

## 200: calculated

```json
{
  "tax_year": "2025-26", "blocked_reason": null, "message": null,
  "salary_tax": "72000", "surcharge": "0", "profit_tax": "10000",
  "salary_balance": "-3000", "profit_balance": "0", "non_atl_extra_withheld": null,
  "steps": [
    { "description": "Salary tax: Rs 1,800,000 falls in the Rs 1,200,001 to Rs 2,200,000 band: Rs 6,000 + 11% of Rs 600,000",
      "rule_location": "Income Tax Ordinance 2001 (amended up to 31.07.2025), First Schedule, Part I, Division I, clause (2), row 3",
      "result": "72000" }
  ],
  "summary": "Your salary tax is Rs 72,000 …",
  "label": "Not yet reviewed by a tax practitioner. Not tax advice."
}
```

## 200: blocked

```json
{
  "tax_year": "2025-26", "blocked_reason": "needs_atl_answer",
  "message": "Set your ATL status in your profile.",
  "salary_tax": null, "surcharge": null, "profit_tax": null,
  "salary_balance": null, "profit_balance": null, "non_atl_extra_withheld": null,
  "steps": [], "summary": null,
  "label": "Not yet reviewed by a tax practitioner. Not tax advice."
}
```

`blocked_reason` values: `needs_atl_answer`, `no_confirmed_salary_certificate`,
`profit_over_limit`, `salary_share_ambiguous`, `surcharge_ambiguous`.

## Errors

`404` unknown tax year; `401` not logged in.
